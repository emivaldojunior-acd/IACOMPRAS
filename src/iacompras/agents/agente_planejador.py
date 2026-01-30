import json
import ast
import pandas as pd
from google.adk.agents import Agent
from iacompras.tools.ml_tools import get_classified_suppliers, train_supplier_classifier
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
        """Usa Gemini para identificar se o usuário quer SELECIONAR fornecedores."""
        prompt = f"""
        Analise a solicitação do usuário e identifique se a intenção principal é selecionar fornecedores:
        - 'SELECAO': Se o usuário quer selecionar, buscar, listar ou filtrar fornecedores ou produtos para compra.
        
        Solicitação: "{query}"
        
        Responda APENAS com a palavra 'SELECAO'.
        """
        try:
            resposta = gemini_client.generate_text(prompt).strip().upper()
            if "SELECAO" in resposta: return "SELECAO"
        except:
            pass
            
        return "SELECAO"

    def _get_top_products(self):
        df_items = load_nf_items()
        return df_items['CODIGO_PRODUTO'].value_counts().head(20).index.tolist()


    def sugerir_produtos(self, fornecedores_selecionados: list) -> dict:
        """
        Sugere produtos baseados nos fornecedores selecionados.
        1. Sanitiza nomes dos fornecedores.
        2. Busca histórico de itens.
        3. Identifica produtos comprados em todos os fornecedores ou recorrentemente.
        4. Retorna sugestões com descrição real e justificativa detalhada.
        """
        if not fornecedores_selecionados:
            return {"fornecedores_selecionados": [], "produtos_sugeridos": []}

        df_items = load_nf_items()
        df_headers = load_nf_headers()

        # Sanitização: Remove espaços extras nos nomes dos fornecedores
        df_headers['RAZAO_FORNECEDOR'] = df_headers['RAZAO_FORNECEDOR'].str.strip()
        fornecedores_selecionados = [f.strip() for f in fornecedores_selecionados]

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

        # Unir as listas de sugestões (estritas)
        sugestoes_codigos = list(set(produtos_em_todos + produtos_frequentes))
        
        # Fallback: Se não encontrou produtos nas regras estritas, pega os mais comprados no geral desses fornecedores
        if not sugestoes_codigos:
            print("[*] Planejador: Nenhuma sugestão estrita encontrada. Usando fallback por volume.")
            sugestoes_codigos = df_filtered['CODIGO_PRODUTO'].value_counts().head(20).index.tolist()

        # Montar a resposta detalhada de produtos - Agora retornando TODOS os itens para suportar master-detail na UI
        # Vamos usar o df_filtered que já tem o merge com RAZAO_FORNECEDOR
        # Agrupamos por Fornecedor e Produto para evitar duplicidade de itens iguais no mesmo fornecedor
        df_grouped = df_filtered.groupby(['RAZAO_FORNECEDOR', 'CODIGO_PRODUTO']).agg({
            'PRODUTO': 'last',
            'VALOR_UNITARIO': 'last'
        }).reset_index()

        recomendacoes = []
        for _, row in df_grouped.iterrows():
            cod = row['CODIGO_PRODUTO']
            forn = row['RAZAO_FORNECEDOR']
            
            motivos = []
            if cod in produtos_em_todos:
                motivos.append("Presente em todos os fornecedores")
            if cod in produtos_frequentes:
                motivos.append("Histórico recorrente")
            
            if not motivos:
                motivos.append("Disponível neste fornecedor")

            recomendacoes.append({
                "RAZAO_FORNECEDOR": forn,
                "codigo_produto": cod,
                "descricao": row['PRODUTO'],
                "ultimo_preco": float(row['VALOR_UNITARIO']),
                "justificativa": " | ".join(motivos)
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

    def recomendar_fornecedores_por_produto(self, produtos_selecionados: list) -> dict:
        """
        Para cada produto selecionado, encontra os 3 fornecedores mais recomendados.
        Critérios: Rating do classificador, Menor Preço, Maior Recorrência local.
        """
        if not produtos_selecionados:
            return {"produtos": []}

        df_items = load_nf_items()
        df_headers = load_nf_headers()
        suppliers_classified = get_classified_suppliers()
        
        # Converte lista de classified para DF para merge fácil
        if isinstance(suppliers_classified, dict) and "error" in suppliers_classified:
            # Fallback se não houver classificados
            df_class = pd.DataFrame(columns=['RAZAO_FORNECEDOR', 'rating', 'classificacao'])
        else:
            df_class = pd.DataFrame(suppliers_classified)

        # Merge headers e items para ter fornecedor e preço/produto
        df_full = df_items.merge(df_headers[['CODIGO_COMPRA', 'RAZAO_FORNECEDOR']], on='CODIGO_COMPRA', how='left')
        
        resultados = []
        for prod_cod in produtos_selecionados:
            # Filtra histórico deste produto
            df_prod = df_full[df_full['CODIGO_PRODUTO'] == prod_cod].copy()
            if df_prod.empty:
                continue

            # Agrupa por fornecedor para pegar métricas locais
            local_metrics = df_prod.groupby('RAZAO_FORNECEDOR').agg({
                'VALOR_UNITARIO': 'mean',
                'CODIGO_PRODUTO': 'count' # Recorrência local
            }).rename(columns={'VALOR_UNITARIO': 'preco_medio', 'CODIGO_PRODUTO': 'recurrencia_local'}).reset_index()

            # Merge com classificações globais
            recommendations = local_metrics.merge(df_class[['RAZAO_FORNECEDOR', 'rating', 'classificacao']], on='RAZAO_FORNECEDOR', how='left')
            recommendations['rating'] = recommendations['rating'].fillna(1) # Neutro se não classificado
            recommendations['classificacao'] = recommendations['classificacao'].fillna('N/A')

            # Ranking: Rating desc, Preço asc, Recorrência desc
            top_3 = recommendations.sort_values(
                by=['rating', 'preco_medio', 'recurrencia_local'], 
                ascending=[False, True, False]
            ).head(3)

            # Pega descrição do produto
            desc = df_prod['PRODUTO'].iloc[-1]

            resultados.append({
                "codigo_produto": prod_cod,
                "descricao": desc,
                "fornecedores_recomendados": top_3.to_dict('records')
            })

        return {
            "type": "final_product_supplier_selection",
            "selecao_final": resultados
        }

    def executar(self, query=None):
        query_lower = (query or "").lower()
        
        # 1. PRIORIDADE: Recomendar Fornecedores para Produtos Selecionados
        if "recomendar_fornecedores:" in query_lower:
            try:
                parts = query.split("recomendar_fornecedores:")
                lista_str = parts[1].strip()
                produtos_selecionados = ast.literal_eval(lista_str)
                print(f"[*] Planejador: Recomendando fornecedores para {len(produtos_selecionados)} produtos")
                return self.recomendar_fornecedores_por_produto(produtos_selecionados)
            except Exception as e:
                print(f"[!] Erro ao recomendar fornecedores: {e}")
                return {"status": "error", "message": f"Erro na recomendação final: {e}"}

        # 2. PRIORIDADE: Seleção de Produtos (Antigo Fluxo, mantido para compatibilidade se necessário)
            try:
                # Extrai a lista de fornecedores da query (ex: "confirmar_selecao: ['FORN A', 'FORN B']")
                # Usamos split e depois tratamos a string para ser mais robusto que json.loads direto se houver aspas mistas
                parts = query.split("confirmar_selecao:")
                lista_str = parts[1].strip()
                # Remove colchetes e aspas das pontas, depois quebra por ", " ou ','
                # Uma forma simples e segura para listas de strings simples:
                selecionados = ast.literal_eval(lista_str)
                
                print(f"[*] Planejador: Sugerindo produtos para {selecionados}")
                # Remove espaços extras de cada fornecedor selecionado vindo da UI
                selecionados_limpos = [s.strip() for s in selecionados]
                return self.sugerir_produtos(selecionados_limpos)
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
