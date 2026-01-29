import json
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

        return fornecimentos

    def atualizar_inteligencia(self):
        """Treina o classificador de fornecedores e gera a predição para 2025."""
        print("[*] Agente Negociador atualizando inteligência de fornecedores...")
        from iacompras.tools.ml_tools import train_supplier_classifier, classify_suppliers_2025
        
        # 1. Treinar com 2023-2024
        train_result = train_supplier_classifier()
        print(f"[*] Treinamento: {train_result.get('message')}")
        
        # 2. Classificar 2025
        classif_result = classify_suppliers_2025()
        print(f"[*] Classificação 2025: {classif_result.get('message')}")
        
        return self.listar_fornecedores() # Chama a listagem que agora pedirá o filtro

    def filter_suppliers(self, data, filter_query):
        """Aplica o filtro de classificação aos dados com suporte a sinônimos."""
        if not filter_query:
            return data
            
        fq = filter_query.lower()
        if "todos" in fq or "qualquer" in fq:
            return data
            
        # Mapeamento robusto de sinônimos para as categorias do modelo
        mapping = {
            "Ruim / Não recomendado": ["ruim", "ruins", "péssimo", "piores", "não recomendado", "não recomendados", "reprovado"],
            "Médio": ["médio", "regulares", "aceitável"],
            "Bom": ["bom", "bons", "legais", "positivo"],
            "Ótimo / Recomendado": ["ótimo", "ótimos", "excelente", "excelentes", "melhores", "recomendado", "recomendados", "aprovado"]
        }
        
        target = None
        for category, synonyms in mapping.items():
            if any(s in fq for s in synonyms):
                target = category
                break
        
        if not target:
            return data
            
        print(f"[*] Agente Negociador: Filtrando por categoria '{target}'")
        if isinstance(data, list):
            return [s for s in data if s.get('classificacao') == target]
        return data

    def listar_fornecedores(self, query=None):
        """Retorna a lista de fornecedores classificados (com interatividade inteligente)."""
        print("[*] Agente Negociador recuperando lista de fornecedores classificados...")
        from iacompras.tools.ml_tools import get_classified_suppliers
        
        resultado = get_classified_suppliers()
        
        # Se não houver dados, treina automaticamente
        if isinstance(resultado, dict) and "error" in resultado:
            print("[!] Base de inteligência não encontrada. Iniciando treinamento automático...")
            train_supplier_classifier()
            resultado = get_classified_suppliers()

        # Detecção inteligente: verifica se a intenção de filtro já está no prompt
        query_lower = query.lower() if query else ""
        
        # Lista de palavras-chave que indicam interesse em uma categoria específica ou em todos
        keywords = ["todos", "qualquer", "ruim", "péssimo", "piores", "médio", "regular", "bom", "ótimo", "excelente", "melhores", "recomendado"]
        
        # Se o usuário já especificou algo ou pediu "filtrar", processa direto
        if any(k in query_lower for k in keywords) or "filtrar" in query_lower:
            return self.filter_suppliers(resultado, query)

        # Caso contrário, solicita interação
        return {
            "status": "interaction_required",
            "message": "Como deseja visualizar a lista de fornecedores?",
            "options": ["Todos", "Ruim", "Médio", "Bom", "Ótimo"]
        }

    def executar(self, recomendacoes_compras=None, query=None):
        """
        O Agente Negociador atua como especialista em inteligência de fornecedores.
        Suporta fluxo de treinamento -> filtragem ou base atual -> filtragem.
        """
        query_lower = query.lower() if query else ""

        # 1. Se o objetivo for treinar/atualizar o modelo (Zera o fluxo e começa do treino)
        if any(k in query_lower for k in ["treinar", "atualizar", "processar"]):
            return self.atualizar_inteligencia()
        
        # 2. Se o usuário confirmar que quer usar os dados existentes ou já estiver filtrando
        if any(k in query_lower for k in ["usar", "atual", "tabela", "base", "manter", "filtrar", "todos", "ruim", "médio", "bom", "ótimo"]):
            return self.listar_fornecedores(query=query)

        # 3. Verificação de registros existentes no banco para interação inicial (DB vs Retrain)
        from iacompras.tools.db_tools import db_get_latest_classified_suppliers
        existing_data = db_get_latest_classified_suppliers()
        
        if existing_data and not recomendacoes_compras:
            return {
                "status": "interaction_required",
                "message": "Encontrei registros de fornecedores classificados no banco de dados. "
                           "Deseja usar os dados da tabela atual ou treinar novamente os modelos?",
                "options": ["Usar base atual", "Treinar novamente"]
            }

        # 4. Se houver recomendações de compras (Fluxo de Orquestração Completa)
        if recomendacoes_compras and isinstance(recomendacoes_compras, list):
            print("[*] Agente Negociador: Enriquecendo recomendações com dados de fornecedores...")
            return self.negociar_fornecedores(recomendacoes_compras)

        # 5. Padrão: Retorna a lista (que pedirá filtro se necessário)
        return self.listar_fornecedores(query=query_lower)
