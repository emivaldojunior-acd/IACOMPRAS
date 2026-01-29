import streamlit as st
import pandas as pd
import os
import sys
import json
from pathlib import Path

# Adiciona o diretório 'src' ao sys.path para que o pacote 'iacompras' seja encontrado
current_dir = Path(__file__).resolve().parent # iacompras
src_dir = current_dir.parent # src
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from iacompras.orchestrator import OrquestradorIACompras

st.set_page_config(page_title="IACOMPRAS - Camada Agêntica", layout="wide")

st.title("🛒 IACOMPRAS: Gestão Agêntica de Compras")
st.markdown("Automação de planejamento, negociação e auditoria via Google ADK & Gemini.")

# --- Barra Lateral: Configurações Apenas ---
with st.sidebar:
    st.header("⚙️ Configurações")
    gemini_api_key = st.text_input("Gemini API Key", type="password", help="Insira sua chave do Google Gemini")
    orcamento_max = st.number_input("Orçamento Máximo (R$)", value=50000.0, step=1000.0)
    mes_referencia = st.selectbox("Mês de Referência", ["Próximo Mês", "Março 2026", "Abril 2026"])
    
    st.divider()
    st.info("Utilize o chat ao lado para solicitar ações aos agentes especializados.")

# Inicializa Orquestrador via Sidebar para uso no chat
orc_side = OrquestradorIACompras(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY"))

# --- Seção do Chatbot ---
st.divider()
st.subheader("💬 Chatbot Assistente")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe mensagens do histórico
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("suggestion"):
            suggested = message['suggestion']['agente_sugerido']
            if st.button(f"🚀 Iniciar Processo do Agente: {suggested.capitalize()}", key=f"btn_{i}_{suggested}"):
                # Mapeia agente do roteador para o nome técnico usado no orchestrator
                mapping = {
                    "auditor": "Agente_Auditor",
                    "financeiro": "Agente_Financeiro",
                    "logístico": "Agente_Logistico",
                    "negociador": "Agente_Negociador",
                    "orçamento": "Agente_Orcamento",
                    "planejador": "Agente_Planejador"
                }
                agent_tech_name = mapping.get(suggested)
                if agent_tech_name:
                    with st.spinner(f"Executando {agent_tech_name}..."):
                        resultado = orc_side.planejar_compras(f"Chat: {agent_tech_name}", custom_chain=[agent_tech_name])
                        st.session_state['last_run'] = resultado
                        st.session_state['last_agent'] = agent_tech_name
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"✅ O `{agent_tech_name}` concluiu o processamento. Você pode ver os resultados abaixo."
                        })
                        st.rerun()

# Input do usuário
if prompt := st.chat_input("Ex: 'Preciso planejar as compras' ou 'Verifique os prazos de entrega'"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analisando sua solicitação..."):
            # Usa o orc_side já configurado
            analise = orc_side.rotear_consulta(prompt)
            
            resposta = analise["explicacao"]
            if analise.get("pergunta_confirmacao"):
                resposta += f"\n\n**{analise['pergunta_confirmacao']}**"
            
            st.markdown(resposta)
            
            # Adiciona à sessão
            st.session_state.messages.append({
                "role": "assistant", 
                "content": resposta,
                "suggestion": analise if analise.get("agente_sugerido") else None
            })
            
            if analise.get("agente_sugerido"):
                st.rerun()

# --- Resultados da Última Execução ---
if 'last_run' in st.session_state:
    st.divider()
    res = st.session_state['last_run']
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Run ID", res['run_id'])
    col2.metric("Total Estimado", f"R$ {res['total_geral']:,.2f}")
    col3.metric("Status", "Finalizado")

    if res.get('insight_gemini'):
        with st.expander("🤖 Insight do Gemini", expanded=True):
            st.info(res['insight_gemini'])

    st.subheader("📋 Resultados do Processamento")
    resultado = res.get('resultado')

    if isinstance(resultado, dict):
        # Caso o agente tenha retornado um dicionário de status/erro
        if resultado.get('status') == 'error':
            st.error(resultado.get('message', 'Erro desconhecido no agente.'))
        elif resultado.get('status') == 'interaction_required':
            st.warning(f"⚠️ {resultado.get('message', 'Interação necessária.')}")
            options = resultado.get('options', [])
            cols = st.columns(len(options))
            for idx, opt in enumerate(options):
                if cols[idx].button(opt, key=f"opt_{idx}"):
                    last_agent = st.session_state.get('last_agent')
                    with st.spinner(f"Processando sua escolha: {opt}..."):
                        chain = [last_agent] if last_agent else None
                        novo_resultado = orc_side.planejar_compras(opt, custom_chain=chain)
                        st.session_state['last_run'] = novo_resultado
                        st.rerun()
        elif resultado.get('type') == 'dual_grid_selection':
            # NOVO: Renderiza duas grids para sugestão de produtos
            st.write("### 🏢 Fornecedores Selecionados")
            df_forn = pd.DataFrame(resultado['fornecedores_selecionados'])
            st.dataframe(df_forn, use_container_width=True, hide_index=True)
            
            st.divider()
            
            st.write("### 💡 Produtos Sugeridos")
            df_prod = pd.DataFrame(resultado['produtos_sugeridos'])
            
            # Adiciona checkbox para seleção de produtos
            if 'Confirmar' not in df_prod.columns:
                df_prod.insert(0, 'Confirmar', False)
            
            edited_prod_df = st.data_editor(
                df_prod,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Confirmar": st.column_config.CheckboxColumn(
                        "Confirmar",
                        help="Marque para planejar o orçamento deste produto",
                        default=False,
                    )
                },
                disabled=[c for c in df_prod.columns if c != "Confirmar"]
            )
            
            selected_products = edited_prod_df[edited_prod_df['Confirmar'] == True]
            if not selected_products.empty:
                st.success(f"✅ {len(selected_products)} produto(s) selecionado(s).")
                if st.button("💰 Planejar Orçamento"):
                    st.info("Iniciando planejamento de orçamento... (Fluxo seguinte em desenvolvimento)")
        else:
            st.json(resultado)
    elif isinstance(resultado, list) and resultado:
        try:
            df = pd.DataFrame(resultado)
            # Tenta selecionar colunas se existirem
            existing_cols = df.columns.tolist()
            base_cols = [c for c in ['RAZAO_FORNECEDOR', 'classificacao', 'score', 'codigo_produto', 'descricao', 'ultimo_preco', 'justificativa', 'quantidade_sugerida', 'custo_estimado', 'risco_ruptura', 'flags_auditoria'] if c in existing_cols]
            
            if not base_cols:
                base_cols = existing_cols 

            # Se for uma listagem de fornecedores, adiciona checkbox para seleção
            if 'RAZAO_FORNECEDOR' in existing_cols or 'classificacao' in existing_cols:
                st.write("💡 Selecione os fornecedores desejados na tabela abaixo:")
                
                # Prepara o DF com coluna de seleção
                selection_df = df[base_cols].copy()
                if 'Selecionar' not in selection_df.columns:
                    selection_df.insert(0, 'Selecionar', False)
                
                # Usa data_editor para permitir edição do checkbox
                edited_df = st.data_editor(
                    selection_df, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "Selecionar",
                            help="Marque para escolher este fornecedor",
                            default=False,
                        )
                    },
                    disabled=[c for c in base_cols] # Apenas o checkbox é editável
                )
                
                # Se houver seleções, mostra botão de ação
                selected_suppliers = edited_df[edited_df['Selecionar'] == True]
                if not selected_suppliers.empty:
                    st.success(f"✅ {len(selected_suppliers)} fornecedor(es) selecionado(s).")
                    if st.button("🚀 Confirmar Seleção e Prosseguir"):
                        selected_names = selected_suppliers['RAZAO_FORNECEDOR'].tolist()
                        query_confirmacao = f"confirmar_selecao: {selected_names}"
                        
                        with st.spinner(f"Sugerindo produtos para os fornecedores selecionados..."):
                            # SEMPRE usa o Agente Planejador para esta transição, como solicitado
                            agent_tech_name = "Agente_Planejador"
                            st.session_state['last_agent'] = agent_tech_name
                            
                            novo_resultado = orc_side.planejar_compras(query_confirmacao, custom_chain=[agent_tech_name])
                            st.session_state['last_run'] = novo_resultado
                            st.rerun()
            
            # Caso o resultado seja sugestão de produtos
            elif 'codigo_produto' in existing_cols and 'justificativa' in existing_cols:
                st.write("💡 Produtos sugeridos para os fornecedores selecionados:")
                
                # Prepara o DF com coluna de seleção
                selection_df = df[base_cols].copy()
                if 'Confirmar' not in selection_df.columns:
                    selection_df.insert(0, 'Confirmar', False)
                
                # Usa data_editor para seleção de produtos
                edited_prod_df = st.data_editor(
                    selection_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Confirmar": st.column_config.CheckboxColumn(
                            "Confirmar",
                            help="Marque para planejar o orçamento deste produto",
                            default=False,
                        )
                    },
                    disabled=[c for c in base_cols]
                )
                
                selected_products = edited_prod_df[edited_prod_df['Confirmar'] == True]
                if not selected_products.empty:
                    st.success(f"✅ {len(selected_products)} produto(s) selecionado(s).")
                    if st.button("💰 Planejar Orçamento"):
                        st.info("Iniciando planejamento de orçamento... (Fluxo seguinte em desenvolvimento)")
            else:
                # Caso comum de outros agentes
                st.dataframe(df[base_cols], use_container_width=True)
                
        except Exception as e:
            st.warning(f"Não foi possível exibir os dados em formato de tabela. Exibindo formato bruto.")
            st.write(resultado)
    else:
        st.warning("Nenhum dado detalhado retornado pelo agente.")

else:
    st.info("Aguardando interação via chat para iniciar processos.")
