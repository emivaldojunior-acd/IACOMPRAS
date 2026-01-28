from google.adk.agents import Agent
from iacompras.tools.external_tools import brasilapi_cnpj_lookup
from iacompras.tools.data_tools import get_supplier_history
from iacompras.tools.analysis_tools import score_supplier
from iacompras.tools.ml_tools import train_supplier_classifier

class AgenteNegociadorFornecedores(Agent):
    """
    Agente responsável por selecionar fornecedores e validar dados via BrasilAPI.
    """
    name: str = "Agente_Negociador"
    description: str = "Seleciona fornecedores e valida dados cadastrais."
    instruction: str = "Você deve selecionar os melhores fornecedores para cada produto e validar seus dados via BrasilAPI."

    def negociar_fornecedores(self, recomendacoes_compras: list) -> list:
        """Selecionar fornecedores e validar dados cadastrais."""
        fornecimentos = []
        for item in recomendacoes_compras:
            # Simulando seleção de fornecedor do dataset
            exemplo_fornecedor = {
                "nome": "FORNECEDOR EXEMPLO LTDA",
                "cnpj": "00000000000191", 
                "prazo_medio": 10,
                "volume_historico": 5000,
                "uf": "GO"
            }
            
            # Enriquecimento via BrasilAPI
            info_cadastral = brasilapi_cnpj_lookup(exemplo_fornecedor['cnpj'])
            
            # Scoring
            score = score_supplier(exemplo_fornecedor['prazo_medio'], exemplo_fornecedor['volume_historico'])
            
            fornecimentos.append({
                **item,
                "fornecedor_sugerido": info_cadastral.get("razao_social", exemplo_fornecedor['nome']),
                "cnpj": exemplo_fornecedor['cnpj'],
                "cidade": info_cadastral.get("municipio"),
                "uf": info_cadastral.get("uf"),
                "score": score,
                "justificativa_fornecedor": f"Fornecedor com score {score}. Localizado em {info_cadastral.get('uf')}."
            })
            
        return fornecimentos

    def executar(self, recomendacoes_compras):
        # Wrapper temporário para compatibilidade
        return self.negociar_fornecedores(recomendacoes_compras)
