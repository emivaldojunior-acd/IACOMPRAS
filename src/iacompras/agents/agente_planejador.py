import json
import ast
from google.adk.agents import Agent
from iacompras.tools.ml_tools import predict_demand, get_classified_suppliers, train_supplier_classifier
from iacompras.tools.data_tools import load_nf_items, load_nf_headers
from iacompras.tools.gemini_client import gemini_client

class AgentePlanejadorCompras(Agent):
    """
    Agente responsável por prever a demanda e facilitar a seleção de fornecedores.
    Interpreta se o usuário deseja planejar compras ou selecionar fornecedores.
    """
    name: str = "Agente_Planejador"
    description: str = "Estrategista de compras: planejamento de demanda e seleção de fornecedores."
    instruction: str = "Você deve auxiliar no planejamento de volumes de compra e na seleção estratégica de fornecedores e produtos."

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
                # Arredonda para 2 casas decimais e garante que não seja negativo
                quantidade_sugerida = max(0.0, round(previsao['previsao_mensal'], 2))
                recomendacoes.append({
                    "codigo_produto": cod,
                    "quantidade_prevista": previsao['previsao_mensal'],
                    "quantidade_sugerida": quantidade_sugerida,
                    "justificativa": f"Baseado na tendência de demanda prevista para 2026 pelo modelo ML."
                })
        return recomendacoes

    def sugerir_produtos(self, fornecedores_selecionados: list) -> dict:
        """
        Sugere produtos baseados nos fornecedores selecionados.
        1. Produtos comprados em TODOS os fornecedores selecionados.
        2. Produtos comprados mais de uma vez em cada fornecedor selecionado.
        """
        if not fornecedores_selecionados:
            return {"fornecedores": [], "produtos": []}

        df_items = load_nf_items()
        df_headers = load_nf_headers()

        # Merge para ter RAZAO_FORNECEDOR nos itens
        df = df_items.merge(df_headers[['CODIGO_COMPRA', 'RAZAO_FORNECEDOR']], on='CODIGO_COMPRA', how='left')
        
        # Filtra apenas pelos fornecedores selecionados
        df_filtered = df[df['RAZAO_FORNECEDOR'].isin(fornecedores_selecionados)]

        # 1. Encontrar produtos comprados em TODOS os fornecedores selecionados
        prod_forn_count = df_filtered.groupby('CODIGO_PRODUTO')['RAZAO_FORNECEDOR'].nunique()
        total_forn_selecionados = len(fornecedores_selecionados)
        produtos_em_todos = prod_forn_count[prod_forn_count == total_forn_selecionados].index.tolist()

        # 2. Encontrar produtos comprados mais de uma vez por fornecedor
        prod_frequencia = df_filtered.groupby(['RAZAO_FORNECEDOR', 'CODIGO_PRODUTO']).size().reset_index(name='count')
        produtos_frequentes = prod_frequencia[prod_frequencia['count'] > 1]['CODIGO_PRODUTO'].unique().tolist()

        # Unir as listas de sugestões
        sugestoes_codigos = list(set(produtos_em_todos + produtos_frequentes))
        
        # Montar a resposta detalhada de produtos
        recomendacoes = []
        for cod in sugestoes_codigos:
            prod_info = df_filtered[df_filtered['CODIGO_PRODUTO'] == cod].iloc[-1]
            motivos = []
            if cod in produtos_em_todos:
                motivos.append("Comprado em todos os fornecedores")
            if cod in produtos_frequentes:
                motivos.append("Comprado recorrentemente")
            
            recomendacoes.append({
                "codigo_produto": cod,
                "descricao": f"Produto {cod}",
                "ultimo_preco": float(prod_info['PRECO_UNITARIO']),
                "justificativa": " & ".join(motivos)
            })
            
        # Retorna o dicionário estruturado para as duas grids
        return {
            "type": "dual_grid_selection",
            "fornecedores_selecionados": [{"RAZAO_FORNECEDOR": f} for f in fornecedores_selecionados],
            "produtos_sugeridos": recomendacoes
        }

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
        
        # 1. PRIORIDADE: Seleção de Produtos (Novo Fluxo de Confirmação)
        if "confirmar_selecao:" in query_lower:
            try:
                # Extrai a lista de fornecedores da query (ex: "confirmar_selecao: ['FORN A', 'FORN B']")
                # Usamos split e depois tratamos a string para ser mais robusto que json.loads direto se houver aspas mistas
                parts = query.split("confirmar_selecao:")
                lista_str = parts[1].strip()
                # Remove colchetes e aspas das pontas, depois quebra por ", " ou ','
                # Uma forma simples e segura para listas de strings simples:
                selecionados = ast.literal_eval(lista_str)
                
                print(f"[*] Planejador: Sugerindo produtos para {selecionados}")
                return self.sugerir_produtos(selecionados)
            except Exception as e:
                print(f"[!] Erro ao processar seleção de fornecedores: {e}")
                return {"status": "error", "message": f"Falha ao processar os fornecedores selecionados: {e}"}

        # 2. Interpretação da Intenção (apenas se não estiver no meio de um fluxo de botões)
        # Se contiver 'usar base', 'treinar novamente' ou 'filtrar', pulamos a interpretação automática
        fluxo_botoes = ["usar base", "treinar novamente", "filtrar", "ver todos", "desejados"]
        if any(k in query_lower for k in fluxo_botoes):
            intencao = "SELECAO"
        else:
            intencao = self.interpretar_intencao(query_lower)
        
        print(f"[*] Agente Planejador: Intenção detectada -> {intencao}")

        # 3. Se for Planejamento de Demanda
        if intencao == "PLANEJAMENTO":
            return self.planejar_demanda()

        # 4. Se for Seleção de Fornecedores (com filtros interativos)
        
        # Etapa 4.1: Escolha da Fonte (Base vs Treino)
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

        # Etapa 4.2: Escolha do Filtro
        if not any(k in query_lower for k in filtros_labels + ["filtrar", "desejados"]):
            return {
                "status": "interaction_required",
                "message": "Como deseja filtrar os fornecedores para seleção?",
                "options": ["Todos", "Ruim", "Médio", "Bom", "Ótimo"]
            }

        # Etapa 4.3: Listagem Final de Fornecedores
        fornecedores = get_classified_suppliers()
        if isinstance(fornecedores, dict) and "error" in fornecedores:
            print("[!] Planejador: Base não encontrada após etapa de fonte. Treinando...")
            train_supplier_classifier()
            fornecedores = get_classified_suppliers()

        return self.filter_suppliers(fornecedores, query_lower)
