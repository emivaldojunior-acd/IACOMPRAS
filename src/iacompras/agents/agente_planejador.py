from iacompras.tools.ml_tools import predict_demand
from iacompras.tools.data_tools import load_nf_items

class AgentePlanejadorCompras:
    """
    Agente responsável por prever a demanda e sugerir quantidades de compra.
    """
    def __init__(self):
        self.name = "Planejador de Compras"

    def executar(self, query=None):
        # Para demonstração, pegamos os 20 produtos com mais itens no histórico
        df_items = load_nf_items()
        top_products = df_items['CODIGO_PRODUTO'].value_counts().head(20).index.tolist()
        
        recomendacoes = []
        for cod in top_products:
            previsao = predict_demand(cod)
            if "error" not in previsao:
                # Sugestão simples: comprar a demanda mensal prevista para 2026
                quantidade_sugerida = round(previsao['previsao_mensal'], 2)
                recomendacoes.append({
                    "codigo_produto": cod,
                    "quantidade_prevista": previsao['previsao_mensal'],
                    "quantidade_sugerida": quantidade_sugerida,
                    "justificativa": f"Baseado na tendência de demanda prevista para 2026 pelo modelo ML."
                })
        
        return recomendacoes
