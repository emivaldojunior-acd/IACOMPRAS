import streamlit as st
import pandas as pd
import os
import sys
import json
from pathlib import Path

current_dir = Path(__file__).resolve().parent 
src_dir = current_dir.parent 
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from iacompras.orchestrator import OrquestradorIACompras
from iacompras.tools.db_tools import db_init

db_init()

st.set_page_config(page_title="IACOMPRAS - Camada Agêntica ADK", layout="wide")

st.title("🛒 IACOMPRAS: Gestão Agêntica de Compras")
st.markdown("Automação de planejamento, negociação e auditoria via Google ADK & Gemini.")


def render_workflow_progress():
    """Renderiza o indicador de progresso do workflow com ícones de status."""
    
    workflow_stages = [
        {"id": "negociador", "label": "Fornecedores"},
        {"id": "produtos", "label": "Produtos"},
        {"id": "planejamento", "label": "Planejamento"},
        {"id": "orcamento", "label": "Orçamento"},
        {"id": "emails", "label": "Emails"},
    ]
    
    stage_order = {s["id"]: i for i, s in enumerate(workflow_stages)}
    current_stage = st.session_state.get("current_stage", None) 
    current_idx = stage_order.get(current_stage, -1) 
    workflow_completed = st.session_state.get("workflow_completed", False)
    stage_errors = st.session_state.get("stage_errors", {}) 
    
    st.markdown("""
    <style>
    @keyframes pulse-dot {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.3); }
    }
    .dot-active {
        animation: pulse-dot 1.5s ease-in-out infinite;
    }
    .workflow-dot {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-right: 6px;
        font-size: 11px;
        font-weight: bold;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
    
    stages_html = []
    for i, stage in enumerate(workflow_stages):
        stage_id = stage["id"]
        has_error = stage_errors.get(stage_id, False)
        
        if has_error:
            color = "#ef4444"
            icon = "✗"
            animation_class = ""
        elif workflow_completed or i < current_idx:
            color = "#22c55e"
            icon = "✓"
            animation_class = ""
        elif i == current_idx and current_idx >= 0:
            color = "#f59e0b"
            icon = ""
            animation_class = "dot-active"
        else:
            color = "#6b7280"
            icon = ""
            animation_class = ""
        
        stages_html.append(
            f'<span style="display: inline-flex; align-items: center; margin-right: 16px;">'
            f'<span class="workflow-dot {animation_class}" style="background: {color};">{icon}</span>'
            f'<span style="color: {color}; font-size: 13px;">{stage["label"]}</span>'
            f'</span>'
        )
    
    st.markdown(
        f'<div style="padding: 10px 0; margin-bottom: 10px;">{"".join(stages_html)}</div>',
        unsafe_allow_html=True
    )


render_workflow_progress()


with st.sidebar:
    st.header("⚙️ Configurações")
    gemini_api_key = st.text_input("Gemini API Key", type="password", help="Insira sua chave do Google Gemini")
    
    orc_side = OrquestradorIACompras(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY"))

    st.divider()
    if st.button("🚀 Iniciar Workflow de Compras", use_container_width=True):
        for key in ['last_run', 'active_supplier', 'budget_selections', 'item_selections_map', 'selected_products_final', 'active_product', 'final_decisions', 'messages', 'workflow_completed', 'df_produtos_sugeridos', '_produtos_source', 'stage_errors']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.session_state.current_stage = "negociador" 
        st.session_state.workflow_completed = False
        st.session_state.stage_errors = {}
        st.session_state.messages = []
        
        with st.spinner("Iniciando fluxo de compras..."):
            agent_tech_name = "Agente_Negociador"
            st.session_state['last_agent'] = agent_tech_name
            resultado = orc_side.planejar_compras("Iniciar classificação de fornecedores", custom_chain=[agent_tech_name])
            st.session_state['last_run'] = resultado
            st.rerun()

    st.divider()
    st.info("Utilize o chat ao lado para solicitar ações aos agentes especializados.")


st.divider()
st.subheader("💬 Chatbot Assistente")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_stage" not in st.session_state:
    st.session_state.current_stage = None  

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("suggestion"):
            suggested = message['suggestion']['agente_sugerido']
            if st.button(f"🚀 Iniciar Processo do Agente: {suggested.capitalize()}", key=f"btn_{i}_{suggested}"):
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

if prompt := st.chat_input("Ex: 'Preciso planejar as compras' ou 'Verifique os prazos de entrega'"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analisando sua solicitação..."):
            analise = orc_side.rotear_consulta(prompt, current_stage=st.session_state.current_stage)
            
            resposta = analise["explicacao"]
            if analise.get("pergunta_confirmacao"):
                resposta += f"\n\n**{analise['pergunta_confirmacao']}**"
            
            st.markdown(resposta)
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": resposta,
                "suggestion": analise if analise.get("agente_sugerido") else None
            })
            
            if analise.get("agente_sugerido"):
                st.rerun()

if st.session_state.get('last_run'):
    st.divider()
    res = st.session_state['last_run']
    
    if res and res.get('insight_gemini'):
        with st.expander("🤖 Insight do Gemini", expanded=True):
            st.info(res['insight_gemini'])

    resultado = res.get('resultado')

    if isinstance(resultado, dict):
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
            # grid de Produtos Sugeridos
            if 'selected_products_final' not in st.session_state:
                st.session_state.selected_products_final = {}

            st.write("### 💡 Catálogo de Produtos Sugeridos")
            st.info("Selecione os produtos que deseja incluir no planejamento de orçamento.")
            
            if 'df_produtos_sugeridos' not in st.session_state or st.session_state.get('_produtos_source') != id(resultado['produtos_sugeridos']):
                df_prod = pd.DataFrame(resultado['produtos_sugeridos'])
                if not df_prod.empty and 'Confirmar' not in df_prod.columns:
                    df_prod.insert(0, 'Confirmar', False)
                st.session_state.df_produtos_sugeridos = df_prod
                st.session_state._produtos_source = id(resultado['produtos_sugeridos'])
            
            df_prod = st.session_state.df_produtos_sugeridos
            
            if df_prod.empty:
                st.warning("Nenhum produto sugerido encontrado para os fornecedores selecionados.")
            else:
                edited_df = st.data_editor(
                    df_prod,
                    hide_index=True,
                    use_container_width=True,
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

                st.session_state.df_produtos_sugeridos = edited_df
                
                st.session_state.selected_products_final = dict(zip(edited_df['codigo_produto'], edited_df['Confirmar']))

                # botão de ação
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
            if 'active_product' not in st.session_state:
                st.session_state.active_product = None
            if 'final_decisions' not in st.session_state:
                st.session_state.final_decisions = {}

            st.write("### 🎯 Seleção Final: Fornecedor por Produto")
            st.info("💡 Clique em um produto para ver os 3 fornecedores mais recomendados.")
            
            data_final = resultado['selecao_final']
            df_master = pd.DataFrame([{"Código": p['codigo_produto'], "Descrição": p['descricao']} for p in data_final])
            
            effective_decisions = {k: v for k, v in st.session_state.final_decisions.items() if v}
            df_master['Status'] = df_master['Código'].apply(lambda x: "✅ Selecionado" if x in effective_decisions else "⏳ Pendente")

            # grid para filtrar produtos
            st.write("#### 1. Filtrar Produto")
            opcoes_produtos = {p['codigo_produto']: f"{p['codigo_produto']} - {p['descricao']}" for p in data_final}
            
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

            # grid com os 3 fornecedores mais recomendados para o produto
            active_p = st.session_state.active_product
            if active_p:
                st.divider()
                st.write(f"#### 2. Melhores Fornecedores para: **{active_p}**")
                
                # busca dados do produto ativo
                prod_data = next(p for p in data_final if p['codigo_produto'] == active_p)
                df_detail = pd.DataFrame(prod_data['fornecedores_recomendados'])
                
                # formata para exibição
                df_detail = df_detail.rename(columns={
                    'RAZAO_FORNECEDOR': 'Fornecedor',
                    'preco_medio': 'Preço Médio',
                    'rating': 'Score',
                    'classificacao': 'Classificação',
                    'recurrencia_local': 'Recorrência'
                })

                if 'Escolher' not in df_detail.columns:
                    df_detail.insert(0, 'Escolher', False)
                
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

                # salva escolhas (permite múltiplas conforme solicitado)
                new_sel_list = edited_detail[edited_detail['Escolher'] == True].to_dict('records')
                # remove a coluna 'Escolher' interna dos dicts para limpar o dado enviado ao agente
                for d in new_sel_list: d.pop('Escolher', None)
                
                if new_sel_list != current_choices:
                    st.session_state.final_decisions[active_p] = new_sel_list
                    st.rerun()
            
            total_prods = len(df_master)
            total_done = len(effective_decisions)
            
            st.divider()
            if total_done == total_prods:
                st.success("✅ Todos os produtos possuem um fornecedor definido!")
                if st.button("🏁 Gerar Resumo de Orçamentos"):
                    import json
                    query_orc = f"gerar_resumo_orcamentos: {json.dumps(effective_decisions, default=str)}"
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
            st.balloons()
            st.success(f"🎊 {resultado.get('message')}")
            
            if resultado.get('orcamentos_cadastrados'):
                st.write("### 📋 Orçamentos Cadastrados")
                df_orcamentos = pd.DataFrame(resultado['orcamentos_cadastrados'])
                
                if 'email_fornecedor' in df_orcamentos.columns:
                    df_orcamentos = df_orcamentos.drop(columns=['email_fornecedor'])
                
                column_names = {
                    'id': 'ID',
                    'razao_fornecedor': 'Fornecedor',
                    'cnpj_fornecedor': 'CNPJ',
                    'telefone_fornecedor': 'Telefone',
                    'valor_total': 'Valor Total',
                    'created_at': 'Data Cadastro'
                }
                df_orcamentos = df_orcamentos.rename(columns=column_names)
                
                st.dataframe(
                    df_orcamentos,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Valor Total": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Data Cadastro": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")
                    }
                )
            elif 'orcamento_ids' in resultado:
                st.write(f"Os seguintes IDs de orçamento foram gerados: `{resultado['orcamento_ids']}`")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📧 Enviar Cotações por Email"):
                    orcamentos_para_envio = resultado.get('orcamentos_cadastrados', [])
                    if not orcamentos_para_envio and 'orcamento_ids' in resultado:
                        from iacompras.tools.db_tools import db_list_orcamentos
                        orcamentos_para_envio = db_list_orcamentos(resultado['orcamento_ids'])
                    
                    if orcamentos_para_envio:
                        with st.spinner("Enviando cotações para fornecedores..."):
                            st.session_state.current_stage = "emails"  
                            from iacompras.agents.agente_solicita_cotacao_email import AgenteSolicitaCotacao
                            agente_cotacao = AgenteSolicitaCotacao()
                            resultado_envio = agente_cotacao.executar(orcamentos=orcamentos_para_envio)
                            
                            if resultado_envio.get('status') in ['success', 'partial']:
                                st.session_state.workflow_completed = True
                            
                            st.session_state['last_run'] = {"resultado": resultado_envio}
                            st.rerun()
                    else:
                        st.error("Nenhum orçamento encontrado para enviar cotações.")
            
            with col2:
                if st.button("🔄 Iniciar Novo Planejamento"):                    
                    for key in ['last_run', 'active_supplier', 'budget_selections', 'item_selections_map', 'selected_products_final', 'active_product', 'final_decisions', 'current_stage', 'workflow_completed', 'df_produtos_sugeridos', '_produtos_source', 'stage_errors']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
        elif resultado.get('type') == 'quotation_send_result':
            status = resultado.get('status', 'error')
            
            if status == 'success':
                st.balloons()
                st.success(f"🎉 {resultado.get('message')}")
            elif status == 'partial':
                st.warning(f"⚠️ {resultado.get('message')}")
            else:
                st.error(f"❌ {resultado.get('message')}")
            
            detalhes = resultado.get('detalhes', [])
            if detalhes:
                st.write("### 📤 Cotações Enviadas (Cliente → Fornecedor)")
                for det in detalhes:
                    icon = "✅" if det.get('success') else "❌"
                    st.write(f"{icon} **{det.get('fornecedor')}** - {det.get('message')}")
            
            confirmacoes = resultado.get('confirmacoes_fornecedor')
            if confirmacoes:
                st.divider()
                st.write("### 📥 Confirmações do Fornecedor (Fornecedor → Cliente)")
                
                conf_status = confirmacoes.get('status', 'error')
                if conf_status == 'success':
                    st.success(f"🎉 {confirmacoes.get('message')}")
                elif conf_status == 'partial':
                    st.warning(f"⚠️ {confirmacoes.get('message')}")
                else:
                    st.error(f"❌ {confirmacoes.get('message')}")
                
                conf_detalhes = confirmacoes.get('detalhes', [])
                for det in conf_detalhes:
                    icon = "✅" if det.get('success') else "❌"
                    st.write(f"{icon} **{det.get('fornecedor')}** - {det.get('message')}")
            
            if st.button("🔄 Iniciar Novo Planejamento"):
                for key in ['last_run', 'active_supplier', 'budget_selections', 'item_selections_map', 'selected_products_final', 'active_product', 'final_decisions', 'current_stage', 'workflow_completed', 'df_produtos_sugeridos', '_produtos_source', 'stage_errors']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    elif isinstance(resultado, list) and resultado:
        try:
            df = pd.DataFrame(resultado)
            # tenta selecionar colunas se existirem
            existing_cols = df.columns.tolist()
            base_cols = [c for c in ['RAZAO_FORNECEDOR', 'CNPJ_FORNECEDOR', 'telefone', 'classificacao', 'score', 'codigo_produto', 'descricao', 'ultimo_preco', 'justificativa', 'quantidade_sugerida', 'custo_estimado', 'risco_ruptura', 'flags_auditoria'] if c in existing_cols]
            
            if not base_cols:
                base_cols = existing_cols 

            # se for uma listagem de fornecedores, adiciona checkbox para seleção
            if 'RAZAO_FORNECEDOR' in existing_cols or 'classificacao' in existing_cols:
                st.write("💡 Selecione os fornecedores desejados na tabela abaixo:")
                
                selection_df = df[base_cols].copy()
                if 'Selecionar' not in selection_df.columns:
                    selection_df.insert(0, 'Selecionar', False)
                
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
                    disabled=[c for c in base_cols] 
                )
                
                # se houver seleções, mostra botão de ação
                selected_suppliers = edited_df[edited_df['Selecionar'] == True]
                if not selected_suppliers.empty:
                    st.success(f"✅ {len(selected_suppliers)} fornecedor(es) selecionado(s).")
                    if st.button("🚀 Confirmar Seleção e Prosseguir"):
                        selected_names = selected_suppliers['RAZAO_FORNECEDOR'].tolist()
                        query_confirmacao = f"confirmar_selecao: {selected_names}"
                        
                        with st.spinner(f"Sugerindo produtos para os fornecedores selecionados..."):
                            agent_tech_name = "Agente_Produtos"
                            st.session_state['last_agent'] = agent_tech_name
                            st.session_state.current_stage = "produtos"
                            
                            novo_resultado = orc_side.planejar_compras(query_confirmacao, custom_chain=[agent_tech_name])
                            st.session_state['last_run'] = novo_resultado
                            st.rerun()
            
            elif 'codigo_produto' in existing_cols and 'justificativa' in existing_cols:
                st.write("💡 Produtos sugeridos para os fornecedores selecionados:")
                            
                selection_df = df[base_cols].copy()
                if 'Confirmar' not in selection_df.columns:
                    selection_df.insert(0, 'Confirmar', False)
                
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
                st.dataframe(df[base_cols], width="stretch")
                
        except Exception as e:
            st.warning(f"Não foi possível exibir os dados em formato de tabela. Exibindo formato bruto.")
            st.write(resultado)
    else:
        st.warning("Nenhum dado detalhado retornado pelo agente.")

else:
    st.info("Aguardando interação via chat para iniciar processos.")
