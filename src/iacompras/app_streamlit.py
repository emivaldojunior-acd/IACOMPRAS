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
            orc = OrquestradorIACompras(api_key=gemini_api_key)
            resultado = orc.planejar_compras(f"Planejar compras para {mes_referencia} com orçamento de {orcamento_max}")
            st.session_state['last_run'] = resultado
            st.success("Orquestração concluída!")

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
