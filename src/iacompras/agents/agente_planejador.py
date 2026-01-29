import json
from google.adk.agents import Agent
from iacompras.tools.ml_tools import predict_demand, get_classified_suppliers, train_supplier_classifier
from iacompras.tools.data_tools import load_nf_items
from iacompras.tools.gemini_client import gemini_client

class AgentePlanejadorCompras(Agent):
    """
    Agente responsável por prever a demanda e facilitar a seleção de fornecedores.
    Interpreta se o usuário deseja planejar compras ou selecionar fornecedores.
    """
    name: str = "Agente_Planejador"
    description: str = "Estrategista de compras: planejamento de demanda e seleção de fornecedores."
    instruction: str = "Você deve auxiliar no planejamento de volumes de compra e na seleção estratégica de fornecedores."

    def interpretar_intencao(self, query: str) -> str:
        """Usa Gemini para identificar se o usuário quer PLANEJAR ou SELECIONAR."""
        prompt = f"""
        Analise a solicitação do usuário e identifique a intenção principal:
        - 'PLANEJAMENTO': Se o usuário quer planejar compras, orçamentos, prever demanda ou volumes.
        - 'SELECAO': Se o usuário quer selecionar, buscar, listar ou filtrar fornecedores.
        
        Solicitação: "{query}"
        
        Responda APENAS com a palavra 'PLANEJAMENTO' ou 'SELECAO'.
        """
        try:
            resposta = gemini_client.generate_text(prompt).strip().upper()
            if "PLANEJAMENTO" in resposta: return "PLANEJAMENTO"
            if "SELECAO" in resposta: return "SELECAO"
        except:
            pass
            
        # Fallback offline
        q = query.lower()
        if any(k in q for k in ["planejar", "previsão", "quanto", "orçamento", "demanda", "volume"]):
            return "PLANEJAMENTO"
        return "SELECAO"

    def _get_top_products(self):
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

    def filter_suppliers(self, data, filter_query):
        """Aplica filtros de classificação ou detecta 'Selecionar Desejados'."""
        fq = (filter_query or "").lower()
        
        if "desejados" in fq or "selecionar" in fq:
            # Opção para seleção manual (Simulado por um filtro de score alto por enquanto)
            print("[*] Agente Planejador: Modo de seleção de fornecedores desejados.")
            return [s for s in data if s.get('rating', 0) >= 4]

        if "todos" in fq or not fq:
            return data
            
        mapping = {
            "Ruim / Não recomendado": ["ruim", "péssimo"],
            "Médio": ["médio", "regular"],
            "Bom": ["bom"],
            "Ótimo / Recomendado": ["ótimo", "excelente", "recomendado"]
        }
        
        for cat, synonyms in mapping.items():
            if any(s in fq for s in synonyms):
                return [s for s in data if s.get('classificacao') == cat]
        
        return data

    def executar(self, query=None):
        query_lower = (query or "").lower()
        
        # 1. Interpretação da Intenção (apenas se não estiver no meio de um fluxo de botões)
        # Se contiver 'usar base', 'treinar novamente' ou 'filtrar', pulamos a interpretação automática
        fluxo_botoes = ["usar base", "treinar novamente", "filtrar", "ver todos", "desejados"]
        if any(k in query_lower for k in fluxo_botoes):
            intencao = "SELECAO"
        else:
            intencao = self.interpretar_intencao(query_lower)
        
        print(f"[*] Agente Planejador: Intenção detectada -> {intencao}")

        # 2. Se for Planejamento de Demanda
        if intencao == "PLANEJAMENTO":
            return self.planejar_demanda()

        # 3. Se for Seleção de Fornecedores (com filtros)
        
        # Etapa 3.1: Escolha da Fonte (Base vs Treino)
        fontes = ["usar base", "treinar novamente"]
        # Importante: incluímos os novos labels de filtros para que ao clicar neles o fluxo não volte para o início
        filtros_labels = ["todos", "ruim", "médio", "bom", "ótimo"]
        
        if not any(k in query_lower for k in fontes + filtros_labels + ["filtrar", "ver todos", "desejados"]):
            return {
                "status": "interaction_required",
                "message": "Agente Planejador: Encontrei registros no banco. Deseja usar a base atual ou treinar novamente?",
                "options": ["Usar base atual", "Treinar novamente"]
            }

        # Se escolheu treinar, executa e continua o fluxo
        if "treinar novamente" in query_lower:
            print("[*] Planejador: Iniciando treinamento...")
            train_supplier_classifier()
            # Reiniciamos a query para cair na próxima etapa (Filtros)
            query_lower = "usar base" 

        # Etapa 3.2: Escolha do Filtro
        if not any(k in query_lower for k in filtros_labels + ["filtrar", "desejados"]):
            return {
                "status": "interaction_required",
                "message": "Como deseja filtrar os fornecedores para seleção?",
                "options": ["Todos", "Ruim", "Médio", "Bom", "Ótimo"]
            }

        # Etapa 3.3: Listagem Final
        fornecedores = get_classified_suppliers()
        if isinstance(fornecedores, dict) and "error" in fornecedores:
            print("[!] Planejador: Base não encontrada após etapa de fonte. Treinando...")
            train_supplier_classifier()
            fornecedores = get_classified_suppliers()

        return self.filter_suppliers(fornecedores, query_lower)
