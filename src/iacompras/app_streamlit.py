import streamlit as st
import pandas as pd
import os
import sys
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

with st.sidebar:
    st.header("Configurações")
    gemini_api_key = st.text_input("Gemini API Key", type="password", help="Insira sua chave do Google Gemini (necessária para os sumários)")
    orcamento_max = st.number_input("Orçamento Máximo (R$)", value=50000.0, step=1000.0)
    mes_referencia = st.selectbox("Mês de Referência", ["Próximo Mês", "Março 2026", "Abril 2026"])
    
    if st.button("🚀 Executar Orquestração", type="primary"):
        if not gemini_api_key and not os.getenv("GEMINI_API_KEY"):
            st.warning("⚠️ Por favor, informe a Gemini API Key na barra lateral para obter o sumário inteligente.")
        
        with st.spinner("Agentes trabalhando..."):
            orc = OrquestradorIACompras(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY"))
            resultado = orc.planejar_compras(f"Planejar compras para {mes_referencia} com orçamento de {orcamento_max}")
            st.session_state['last_run'] = resultado
            st.success("Orquestração concluída!")

# Instanciação inicial e exibição de opções de agentes
if 'agent_options' not in st.session_state:
    st.session_state['agent_options'] = None

if gemini_api_key or os.getenv("GEMINI_API_KEY"):
    if not st.session_state['agent_options']:
        with st.spinner("Gemini descrevendo agentes disponíveis..."):
            orc_init = OrquestradorIACompras(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY"))
            st.session_state['agent_options'] = orc_init.get_gemini_agent_options()

if st.session_state['agent_options']:
    with st.expander("🤖 Conheça seus Agentes Especialistas", expanded=True):
        st.markdown(st.session_state['agent_options'])

if 'last_run' in st.session_state:
    res = st.session_state['last_run']
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Run ID", res['run_id'])
    col2.metric("Total Estimado", f"R$ {res['total_geral']:,.2f}")
    col3.metric("Status", "Finalizado")

    if res.get('insight_gemini'):
        st.subheader("🤖 Sumário Inteligente (Gemini 2.5-flash)")
        st.info(res['insight_gemini'])

    st.subheader("📋 Recomendações dos Agentes")
    df = pd.DataFrame(res['resultado'])
    
    # Formatação para exibição
    display_df = df[[
        'codigo_produto', 'quantidade_sugerida', 'fornecedor_sugerido', 
        'custo_estimado', 'risco_ruptura', 'flags_auditoria'
    ]]
    
    st.dataframe(display_df, use_container_width=True)

    with st.expander("🔍 Detalhes de Auditoria e Logística"):
        for item in res['resultado']:
            st.write(f"**Produto: {item['codigo_produto']}**")
            st.write(f"- Justificativa: {item['justificativa']}")
            st.write(f"- Auditoria: {item['flags_auditoria']}")
            st.write(f"- Logística: {item['janela_entrega_sugerida']}")
            st.divider()

else:
    st.info("Aguardando execução. Configure os parâmetros na lateral e clique em 'Executar Orquestração'.")

# --- Nova Seção: Classificação de Fornecedores ---
st.divider()
st.subheader("📊 Classificação de Fornecedores")

col_train, col_view = st.columns([1, 3])

with col_train:
    st.markdown("### Treinamento")
    if st.button("🔄 Atualizar Classificador", help="Executa o modelo de ML para classificar fornecedores"):
        with st.spinner("Treinando modelo..."):
            try:
                from iacompras.tools.ml_tools import train_supplier_classifier
                resultado = train_supplier_classifier()
                st.success(resultado['message'])
                st.rerun() # Atualiza a tela para carregar o novo CSV
            except Exception as e:
                st.error(f"Erro ao treinar modelo: {e}")

with col_view:
    st.markdown("### Base de Fornecedores Classificados")
    # Tenta carregar o CSV gerado pelo modelo - BASE_DIR deve ser a raiz do projeto (IACOMPRAS)
    # iacompras/app_streamlit.py -> iacompras/ -> src/ -> IACOMPRAS/ (3 níveis para cima)
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    MODEL_DIR = BASE_DIR / "models"
    CSV_PATH = MODEL_DIR / "fornecedores_classificados.csv"

    if CSV_PATH.exists():
        df_fornecedores = pd.read_csv(CSV_PATH)
        
        # Filtra colunas relevantes para exibição
        cols_display = [
            'RAZAO_FORNECEDOR', 'avg_lead_time', 'recurrence', 
            'discount_rate', 'score', 'classificacao'
        ]
        
        # Garante que as colunas existem antes de filtrar
        available_cols = [c for c in cols_display if c in df_fornecedores.columns]
        
        st.dataframe(
            df_fornecedores[available_cols].sort_values(by='score', ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("Nenhum dado de classificação encontrado. Clique em 'Atualizar Classificador' para gerar.")
