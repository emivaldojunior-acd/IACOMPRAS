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

    def atualizar_inteligencia(self):
        """Treina o classificador de fornecedores para atualizar scores e ratings."""
        print("[*] Agente Negociador atualizando inteligência de fornecedores...")
        return train_supplier_classifier()

    def listar_fornecedores(self):
        """Retorna a lista de fornecedores classificados (com auto-treino se necessário)."""
        print("[*] Agente Negociador recuperando lista de fornecedores classificados...")
        from iacompras.tools.ml_tools import get_classified_suppliers
        
        resultado = get_classified_suppliers()
        
        # Se o arquivo não existir, treina automaticamente e tenta novamente
        if isinstance(resultado, dict) and "error" in resultado:
            print("[!] Arquivo de inteligência não encontrado. Iniciando treinamento automático...")
            self.atualizar_inteligencia()
            resultado = get_classified_suppliers()
            
        return resultado

    def executar(self, recomendacoes_compras=None, query=None):
        """
        O Agente Negociador agora atua como especialista em inteligência de fornecedores.
        Ele pode atualizar a base de conhecimento (treinar) ou listar o ranking atual.
        """
        # 1. Se o objetivo for treinar/atualizar o modelo
        if query and any(k in query.lower() for k in ["treinar", "atualizar", "processar"]):
            return self.atualizar_inteligencia()
        
        # 2. Se houver recomendações de compras (vindo do Planejador ou Orquestrador), realiza o enriquecimento
        if recomendacoes_compras and isinstance(recomendacoes_compras, list):
            print("[*] Agente Negociador: Enriquecendo recomendações com dados de fornecedores...")
            return self.negociar_fornecedores(recomendacoes_compras)

        # 3. Padrão: Fornecer o resultado de todos os fornecedores classificados (Standalone)
        # Este é o comportamento solicitado: gerar a lista com todos classificados.
        print("[*] Agente Negociador: Gerando lista de todos os fornecedores classificados.")
        return self.listar_fornecedores()
