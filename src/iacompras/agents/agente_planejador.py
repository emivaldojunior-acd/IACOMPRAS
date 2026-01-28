from google.adk.agents import Agent
from iacompras.tools.ml_tools import predict_demand
from iacompras.tools.data_tools import load_nf_items

class AgentePlanejadorCompras(Agent):
    """
    Agente responsável por prever a demanda e sugerir quantidades de compra.
    """
    name: str = "Agente_Planejador"
    description: str = "Prevê demanda e sugere quantidades de compra."
    instruction: str = "Você deve usar a ferramenta de planejamento de demanda para sugerir as quantidades de compra baseadas no histórico."

    def _get_top_products(self):
        # Para demonstração, pegamos os 20 produtos com mais itens no histórico
        df_items = load_nf_items()
        return df_items['CODIGO_PRODUTO'].value_counts().head(20).index.tolist()

    def planejar_demanda(self) -> list:
        """Sugerir quantidades de compra baseadas na demanda prevista."""
        top_products = self._get_top_products()
        recomendacoes = []
        for cod in top_products:
            previsao = predict_demand(cod)
            if "error" not in previsao:
                quantidade_sugerida = round(previsao['previsao_mensal'], 2)
                recomendacoes.append({
                    "codigo_produto": cod,
                    "quantidade_prevista": previsao['previsao_mensal'],
                    "quantidade_sugerida": quantidade_sugerida,
                    "justificativa": f"Baseado na tendência de demanda prevista para 2026 pelo modelo ML."
                })
        return recomendacoes

    def executar(self, query=None):
        # Wrapper temporário para manter compatibilidade com o orquestrador atual até refatoração completa
        return self.planejar_demanda()
