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
from iacompras.tools.db_tools import db_init

# Inicializa o banco de dados na primeira carga
db_init()

st.set_page_config(page_title="IACOMPRAS - Camada Agêntica", layout="wide")

st.title("🛒 IACOMPRAS: Gestão Agêntica de Compras")
st.markdown("Automação de planejamento, negociação e auditoria via Google ADK & Gemini.")

# --- Barra Lateral: Configurações Apenas ---
with st.sidebar:
    st.header("⚙️ Configurações")
    gemini_api_key = st.text_input("Gemini API Key", type="password", help="Insira sua chave do Google Gemini")
    
    # Inicializa Orquestrador aqui para que esteja disponível para o botão abaixo
    orc_side = OrquestradorIACompras(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY"))

    st.divider()
    if st.button("🚀 Iniciar Workflow de Compras", use_container_width=True):
        # Limpa estados para recomeçar do zero
        for key in ['last_run', 'active_supplier', 'budget_selections', 'item_selections_map', 'selected_products_final', 'active_product', 'final_decisions', 'messages']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.session_state.current_stage = "negociador"
        st.session_state.messages = [] # Reinicia chat também se desejar, ou apenas o fluxo
        
        # Dispara o primeiro agente (Negociador) automaticamente
        with st.spinner("Iniciando fluxo de compras..."):
            agent_tech_name = "Agente_Negociador"
            st.session_state['last_agent'] = agent_tech_name
            resultado = orc_side.planejar_compras("Iniciar classificação de fornecedores", custom_chain=[agent_tech_name])
            st.session_state['last_run'] = resultado
            st.rerun()

    st.divider()
    st.info("Utilize o chat ao lado para solicitar ações aos agentes especializados.")

# --- Seção do Chatbot ---
st.divider()
st.subheader("💬 Chatbot Assistente")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_stage" not in st.session_state:
    st.session_state.current_stage = "negociador" # Estágio inicial padrão

# Exibe mensagens do histórico
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("suggestion"):
            suggested = message['suggestion']['agente_sugerido']
            if st.button(f"🚀 Iniciar Processo do Agente: {suggested.capitalize()}", key=f"btn_{i}_{suggested}"):
                # Mapeia agente do roteador para o nome técnico usado no orchestrator
                mapping = {
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
                        
                        # Atualiza o estágio sugerido
                        mapping_stage = {
                            "Agente_Negociador": "negociador",
                            "Agente_Produtos": "produtos",
                            "Agente_Planejador": "planejamento",
                            "Agente_Orcamento": "orcamento"
                        }
                        if agent_tech_name in mapping_stage:
                            st.session_state.current_stage = mapping_stage[agent_tech_name]

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
            # Usa o orc_side já configurado e passa o estágio atual para contexto
            analise = orc_side.rotear_consulta(prompt, current_stage=st.session_state.current_stage)
            
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
if st.session_state.get('last_run'):
    st.divider()
    res = st.session_state['last_run']
    
    if res and res.get('insight_gemini'):
        with st.expander("🤖 Insight do Gemini", expanded=True):
            st.info(res['insight_gemini'])

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
        elif resultado.get('type') == 'product_suggestion_grid':
            # --- Grid Única de Produtos Sugeridos ---
            if 'selected_products_final' not in st.session_state:
                st.session_state.selected_products_final = {}

            st.write("### 💡 Catálogo de Produtos Sugeridos")
            st.info("Selecione os produtos que deseja incluir no planejamento de orçamento.")
            
            df_prod = pd.DataFrame(resultado['produtos_sugeridos'])
            
            if df_prod.empty:
                st.warning("Nenhum produto sugerido encontrado para os fornecedores selecionados.")
            else:
                # Adiciona coluna 'Confirmar' baseada no estado salvo
                if 'Confirmar' not in df_prod.columns:
                    df_prod.insert(0, 'Confirmar', False)
                
                # Sincroniza com session_state
                df_prod['Confirmar'] = df_prod['codigo_produto'].apply(lambda x: st.session_state.selected_products_final.get(x, False))

                # Renderiza a Grid Única
                edited_df = st.data_editor(
                    df_prod,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Confirmar": st.column_config.CheckboxColumn(
                            "Confirmar",
                            help="Marque para incluir este item no orçamento",
                            default=False,
                        ),
                        "codigo_produto": st.column_config.TextColumn("Código"),
                        "descricao": st.column_config.TextColumn("Descrição", width="large"),
                        "marca": st.column_config.TextColumn("Marca"),
                        "grupo": st.column_config.TextColumn("Grupo"),
                        "ultimo_preco": st.column_config.NumberColumn("Último Preço", format="R$ %.2f"),
                        "fornecedores": st.column_config.TextColumn("Fornecedores Disponíveis"),
                        "justificativa": st.column_config.TextColumn("Justificativa", width="medium")
                    },
                    disabled=[c for c in df_prod.columns if c != "Confirmar"],
                    key="product_final_grid"
                )

                # Salva alterações
                new_selections = dict(zip(edited_df['codigo_produto'], edited_df['Confirmar']))
                if new_selections != st.session_state.selected_products_final:
                    st.session_state.selected_products_final = new_selections

                # Botão de ação
                total_sel = sum(1 for v in st.session_state.selected_products_final.values() if v)
                if total_sel > 0:
                    st.success(f"✅ {total_sel} produto(s) selecionado(s).")
                    if st.button("💰 Prosseguir para Seleção de Fornecedores"):
                        selected_codes = [k for k, v in st.session_state.selected_products_final.items() if v]
                        query_recomendacao = f"recomendar_fornecedores: {selected_codes}"
                        
                        with st.spinner(f"Identificando melhores fornecedores para {len(selected_codes)} produtos..."):
                            agent_tech_name = "Agente_Planejador"
                            st.session_state['last_agent'] = agent_tech_name
                            st.session_state.current_stage = "planejamento"
                            
                            novo_resultado = orc_side.planejar_compras(query_recomendacao, custom_chain=[agent_tech_name])
                            st.session_state['last_run'] = novo_resultado
                            st.rerun()
        elif resultado.get('type') == 'final_product_supplier_selection':
            # --- Estado da Seleção Final ---
            if 'active_product' not in st.session_state:
                st.session_state.active_product = None
            if 'final_decisions' not in st.session_state:
                # {codigo_produto: {fornecedor_selecionado_dict}}
                st.session_state.final_decisions = {}

            st.write("### 🎯 Seleção Final: Fornecedor por Produto")
            st.info("💡 Clique em um produto para ver os 3 fornecedores mais recomendados.")
            
            data_final = resultado['selecao_final']
            df_master = pd.DataFrame([{"Código": p['codigo_produto'], "Descrição": p['descricao']} for p in data_final])
            
            # Adiciona indicador de conclusão na grid mestre
            # Consideramos 'Selecionado' apenas se houver pelo menos 1 fornecedor na lista
            effective_decisions = {k: v for k, v in st.session_state.final_decisions.items() if v}
            df_master['Status'] = df_master['Código'].apply(lambda x: "✅ Selecionado" if x in effective_decisions else "⏳ Pendente")

            # --- Grid Mestre (Produtos - Filtro) ---
            st.write("#### 1. Filtrar Produto")
            opcoes_produtos = {p['codigo_produto']: f"{p['codigo_produto']} - {p['descricao']}" for p in data_final}
            
            # Encontra o índice inicial baseado no session_state
            default_index = 0
            if st.session_state.active_product in opcoes_produtos:
                default_index = list(opcoes_produtos.keys()).index(st.session_state.active_product)

            selected_p_code = st.selectbox(
                "Selecione um produto para visualizar sugestões:",
                options=list(opcoes_produtos.keys()),
                format_func=lambda x: opcoes_produtos[x],
                index=default_index,
                key="product_selector"
            )

            if selected_p_code != st.session_state.active_product:
                st.session_state.active_product = selected_p_code
                st.rerun()

            # --- Grid Detalhe (Top 3 Fornecedores) ---
            active_p = st.session_state.active_product
            if active_p:
                st.divider()
                st.write(f"#### 2. Melhores Fornecedores para: **{active_p}**")
                
                # Busca dados do produto ativo
                prod_data = next(p for p in data_final if p['codigo_produto'] == active_p)
                df_detail = pd.DataFrame(prod_data['fornecedores_recomendados'])
                
                # Formata para exibição
                df_detail = df_detail.rename(columns={
                    'RAZAO_FORNECEDOR': 'Fornecedor',
                    'preco_medio': 'Preço Médio',
                    'rating': 'Score',
                    'classificacao': 'Classificação',
                    'recurrencia_local': 'Recorrência'
                })

                # Coluna de rádio/seleção simulada no data_editor
                if 'Escolher' not in df_detail.columns:
                    df_detail.insert(0, 'Escolher', False)
                
                # Sincroniza escolha anterior (Suporta múltiplas)
                current_choices = st.session_state.final_decisions.get(active_p, [])
                chosen_names = [c.get('Fornecedor') for c in current_choices]
                df_detail['Escolher'] = df_detail['Fornecedor'].isin(chosen_names)

                edited_detail = st.data_editor(
                    df_detail,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Escolher": st.column_config.CheckboxColumn("Selecionar", default=False),
                        "Preço Médio": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Score": st.column_config.ProgressColumn(min_value=1, max_value=5)
                    },
                    disabled=[c for c in df_detail.columns if c != "Escolher"],
                    key=f"final_detail_{active_p}"
                )

                # Salva escolhas (Permite múltiplas conforme solicitado)
                new_sel_list = edited_detail[edited_detail['Escolher'] == True].to_dict('records')
                # Remove a coluna 'Escolher' interna dos dicts para limpar o dado enviado ao agente
                for d in new_sel_list: d.pop('Escolher', None)
                
                # Compara para evitar reruns infinitos se nada mudou
                if new_sel_list != current_choices:
                    st.session_state.final_decisions[active_p] = new_sel_list
                    st.rerun()
            
            # --- Finalização ---
            total_prods = len(df_master)
            total_done = len(effective_decisions)
            
            st.divider()
            if total_done == total_prods:
                st.success("✅ Todos os produtos possuem um fornecedor definido!")
                if st.button("🏁 Gerar Resumo de Orçamentos"):
                    query_orc = f"gerar_resumo_orcamentos: {effective_decisions}"
                    with st.spinner("Agrupando produtos e gerando orçamentos por fornecedor..."):
                        agent_tech_name = "Agente_Orcamento"
                        st.session_state['last_agent'] = agent_tech_name
                        st.session_state.current_stage = "orcamento"
                        
                        novo_resultado = orc_side.planejar_compras(query_orc, custom_chain=[agent_tech_name])
                        st.session_state['last_run'] = novo_resultado
                        st.rerun()
            else:
                st.warning(f"Faltam {total_prods - total_done} produtos para selecionar o fornecedor.")
        elif resultado.get('type') == 'budget_summary_view':
            # --- Visualização de Resumo de Orçamentos ---
            st.write("### 📝 Resumo dos Orçamentos Gerados")
            st.info("Confira os itens agrupados por fornecedor antes de confirmar o envio.")
            
            for orc in resultado['orcamentos']:
                with st.expander(f"🏢 Fornecedor: {orc['fornecedor']} - Total: R$ {orc['valor_total_estimado']:.2f}"):
                    st.write(f"**Total de Itens:** {orc['total_itens']}")
                    df_itens = pd.DataFrame(orc['itens'])
                    st.table(df_itens.rename(columns={
                        'codigo_produto': 'Código',
                        'preco_base': 'Preço Base',
                        'recorrencia': 'Recorrência'
                    }))
            
            st.divider()
            col1, col2 = st.columns([1, 4])
            if col1.button("✅ Confirmar Budgets"):
                query_confirm = f"confirmar_orcamentos: {resultado['orcamentos']}"
                with st.spinner("Gravando orçamentos no banco de dados..."):
                    agent_tech_name = "Agente_Orcamento"
                    st.session_state['last_agent'] = agent_tech_name
                    
                    final_res = orc_side.planejar_compras(query_confirm, custom_chain=[agent_tech_name])
                    st.session_state['last_run'] = final_res
                    st.rerun()
            if col2.button("↩️ Voltar para Edição"):
                selected_codes = [k for k, v in st.session_state.get('selected_products_final', {}).items() if v]
                if selected_codes:
                    with st.spinner("Retornando para seleção de fornecedores..."):
                        agent_tech_name = "Agente_Planejador"
                        query_reco = f"recomendar_fornecedores: {selected_codes}"
                        st.session_state.current_stage = "planejamento"
                        res_reco = orc_side.planejar_compras(query_reco, custom_chain=[agent_tech_name])
                        st.session_state['last_run'] = res_reco
                        st.rerun()
                else:
                    st.session_state['last_run'] = None
                    st.rerun()
        elif isinstance(resultado, dict) and resultado.get('status') == 'success':
            # --- Tela Final de Sucesso ---
            st.balloons()
            st.success(f"🎊 {resultado.get('message')}")
            if 'orcamento_ids' in resultado:
                st.write(f"Os seguintes IDs de orçamento foram gerados: `{resultado['orcamento_ids']}`")
            
            if st.button("🔄 Iniciar Novo Planejamento"):
                # Limpa estados para recomeçar
                for key in ['last_run', 'active_supplier', 'budget_selections', 'item_selections_map', 'selected_products_final', 'active_product', 'final_decisions', 'current_stage']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
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
                    width="stretch",
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
                            # NOVO: Agora chama o Agente_Produtos para gerar o catálogo
                            agent_tech_name = "Agente_Produtos"
                            st.session_state['last_agent'] = agent_tech_name
                            st.session_state.current_stage = "produtos"
                            
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
                    width="stretch",
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
                st.dataframe(df[base_cols], width="stretch")
                
        except Exception as e:
            st.warning(f"Não foi possível exibir os dados em formato de tabela. Exibindo formato bruto.")
            st.write(resultado)
    else:
        st.warning("Nenhum dado detalhado retornado pelo agente.")

else:
    st.info("Aguardando interação via chat para iniciar processos.")
