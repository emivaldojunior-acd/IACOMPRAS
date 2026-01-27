from iacompras.tools.external_tools import brasilapi_cnpj_lookup
from iacompras.tools.data_tools import get_supplier_history
from iacompras.tools.analysis_tools import score_supplier

class AgenteNegociadorFornecedores:
    """
    Agente responsável por selecionar fornecedores e validar dados via BrasilAPI.
    """
    def __init__(self):
        self.name = "Negociador de Fornecedores"

    def executar(self, recomendacoes_compras):
        fornecimentos = []
        for item in recomendacoes_compras:
            cod_produto = item['codigo_produto']
            
            # Busca fornecedores que já venderam este produto
            # (Simplificado: pegamos do histórico geral de notas que contenham o produto)
            # Para este MVP, vamos pegar um fornecedor exemplo baseado no histórico
            history = get_supplier_history("") # Pega tudo
            # Filtro simulado para encontrar quem vende o produto X
            # (Na vida real, faria merge com NF_ITEMS)
            
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
