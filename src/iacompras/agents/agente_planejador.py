"""
Agente Planejador ADK - IACOMPRAS
Responsável por prever demanda e facilitar seleção de fornecedores.
"""
import json
import ast
import pandas as pd
from google.adk.agents import Agent
from iacompras.tools.ml_tools import get_classified_suppliers, train_supplier_classifier
from iacompras.tools.data_tools import load_nf_items, load_nf_headers
from iacompras.tools.gemini_client import gemini_client



def interpretar_intencao_tool(query: str) -> str:
    """
    Usa Gemini para identificar se o usuário quer SELECIONAR fornecedores.
    
    Args:
        query: Consulta do usuário para análise de intenção
    
    Returns:
        String indicando a intenção detectada ('SELECAO')
    """
    prompt = f"""
    Analise a solicitação do usuário e identifique se a intenção principal é selecionar fornecedores:
    - 'SELECAO': Se o usuário quer selecionar, buscar, listar ou filtrar fornecedores ou produtos para compra.
    
    Solicitação: "{query}"
    
    Responda APENAS com a palavra 'SELECAO'.
    """
    try:
        resposta = gemini_client.generate_text(prompt).strip().upper()
        if "SELECAO" in resposta: 
            return "SELECAO"
    except:
        pass
        
    return "SELECAO"


def get_top_products_tool() -> list:
    """
    Retorna os 20 produtos mais comprados do histórico.
    
    Returns:
        Lista de códigos dos 20 produtos mais frequentes
    """
    df_items = load_nf_items()
    return df_items['CODIGO_PRODUTO'].value_counts().head(20).index.tolist()


def sugerir_produtos_tool(fornecedores_selecionados: list) -> dict:
    """
    Sugere produtos baseados nos fornecedores selecionados.
    
    Processo:
    1. Sanitiza nomes dos fornecedores.
    2. Busca histórico de itens.
    3. Identifica produtos comprados em todos os fornecedores ou recorrentemente.
    4. Retorna sugestões com descrição real e justificativa detalhada.
    
    Args:
        fornecedores_selecionados: Lista de razões sociais dos fornecedores
    
    Returns:
        dict com fornecedores selecionados e produtos sugeridos
    """
    if not fornecedores_selecionados:
        return {"fornecedores_selecionados": [], "produtos_sugeridos": []}

    df_items = load_nf_items()
    df_headers = load_nf_headers()

    df_headers['RAZAO_FORNECEDOR'] = df_headers['RAZAO_FORNECEDOR'].str.strip()
    fornecedores_selecionados = [f.strip() for f in fornecedores_selecionados]

    df = df_items.merge(df_headers[['CODIGO_COMPRA', 'RAZAO_FORNECEDOR']], on='CODIGO_COMPRA', how='left')
    
    df_filtered = df[df['RAZAO_FORNECEDOR'].isin(fornecedores_selecionados)]

    prod_forn_count = df_filtered.groupby('CODIGO_PRODUTO')['RAZAO_FORNECEDOR'].nunique()
    total_forn_selecionados = len(fornecedores_selecionados)
    produtos_em_todos = prod_forn_count[prod_forn_count == total_forn_selecionados].index.tolist()


    prod_frequencia = df_filtered.groupby(['RAZAO_FORNECEDOR', 'CODIGO_PRODUTO']).size().reset_index(name='count')
    produtos_frequentes = prod_frequencia[prod_frequencia['count'] > 1]['CODIGO_PRODUTO'].unique().tolist()

    sugestoes_codigos = list(set(produtos_em_todos + produtos_frequentes))
    
    if not sugestoes_codigos:
        print("[*] Planejador: Nenhuma sugestão estrita encontrada. Usando fallback por volume.")
        sugestoes_codigos = df_filtered['CODIGO_PRODUTO'].value_counts().head(20).index.tolist()

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
        
    return {
        "type": "dual_grid_selection",
        "fornecedores_selecionados": [{"RAZAO_FORNECEDOR": f} for f in fornecedores_selecionados],
        "produtos_sugeridos": recomendacoes
    }


def filter_suppliers_planejador_tool(data: list, filter_query: str) -> list:
    """
    Aplica filtros de classificação ou detecta 'Selecionar Desejados'.
    
    Args:
        data: Lista de fornecedores para filtrar
        filter_query: Critério de filtro
    
    Returns:
        Lista de fornecedores filtrados
    """
    fq = (filter_query or "").lower()
    
    if "desejados" in fq or "selecionar" in fq:
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


def recomendar_fornecedores_por_produto_tool(produtos_selecionados: list) -> dict:
    """
    Para cada produto selecionado, encontra os 3 fornecedores mais recomendados.
    Critérios: Rating do classificador, Menor Preço, Maior Recorrência local.
    
    Args:
        produtos_selecionados: Lista de códigos de produtos
    
    Returns:
        dict com seleção final de produtos e fornecedores recomendados
    """
    if not produtos_selecionados:
        return {"produtos": []}

    df_items = load_nf_items()
    df_headers = load_nf_headers()
    suppliers_classified = get_classified_suppliers()
    
    if isinstance(suppliers_classified, dict) and "error" in suppliers_classified:
        df_class = pd.DataFrame(columns=['RAZAO_FORNECEDOR', 'rating', 'classificacao'])
    else:
        df_class = pd.DataFrame(suppliers_classified)

    df_full = df_items.merge(df_headers[['CODIGO_COMPRA', 'RAZAO_FORNECEDOR']], on='CODIGO_COMPRA', how='left')
    
    resultados = []
    for prod_cod in produtos_selecionados:
        df_prod = df_full[df_full['CODIGO_PRODUTO'] == prod_cod].copy()
        if df_prod.empty:
            continue

        local_metrics = df_prod.groupby('RAZAO_FORNECEDOR').agg({
            'VALOR_UNITARIO': 'mean',
            'CODIGO_PRODUTO': 'count' 
        }).rename(columns={'VALOR_UNITARIO': 'preco_medio', 'CODIGO_PRODUTO': 'recurrencia_local'}).reset_index()

        recommendations = local_metrics.merge(df_class[['RAZAO_FORNECEDOR', 'CNPJ_FORNECEDOR', 'rating', 'classificacao']], on='RAZAO_FORNECEDOR', how='left')
        recommendations['rating'] = recommendations['rating'].fillna(1)  # Neutro se não classificado
        recommendations['classificacao'] = recommendations['classificacao'].fillna('N/A')

        top_3 = recommendations.sort_values(
            by=['rating', 'preco_medio', 'recurrencia_local'], 
            ascending=[False, True, False]
        ).head(3)

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


def executar_planejador_tool(query: str = None) -> dict:
    """
    Executa o fluxo principal do Agente Planejador de Compras.
    Processa seleção de produtos e recomendação de fornecedores.
    
    Args:
        query: Consulta do usuário
    
    Returns:
        Resultado da operação
    """
    query_lower = (query or "").lower()
    
    if "recomendar_fornecedores:" in query_lower:
        try:
            parts = query.split("recomendar_fornecedores:")
            lista_str = parts[1].strip()
            produtos_selecionados = ast.literal_eval(lista_str)
            print(f"[*] Planejador: Recomendando fornecedores para {len(produtos_selecionados)} produtos")
            return recomendar_fornecedores_por_produto_tool(produtos_selecionados)
        except Exception as e:
            print(f"[!] Erro ao recomendar fornecedores: {e}")
            return {"status": "error", "message": f"Erro na recomendação final: {e}"}

    if "confirmar_selecao:" in query_lower:
        try:
            parts = query.split("confirmar_selecao:")
            lista_str = parts[1].strip()
            selecionados = ast.literal_eval(lista_str)
            
            print(f"[*] Planejador: Sugerindo produtos para {selecionados}")
            selecionados_limpos = [s.strip() for s in selecionados]
            return sugerir_produtos_tool(selecionados_limpos)
        except Exception as e:
            print(f"[!] Erro ao processar seleção de fornecedores: {e}")
            return {"status": "error", "message": f"Falha ao processar os fornecedores selecionados: {e}"}

    fluxo_botoes = ["usar base", "treinar novamente", "filtrar", "ver todos", "desejados"]
    if any(k in query_lower for k in fluxo_botoes):
        intencao = "SELECAO"
    else:
        intencao = interpretar_intencao_tool(query_lower)
    
    print(f"[*] Agente Planejador: Intenção detectada -> {intencao}")

 
    fontes = ["usar base", "treinar novamente"]
    filtros_labels = ["todos", "ruim", "médio", "bom", "ótimo"]
    
    if not any(k in query_lower for k in fontes + filtros_labels + ["filtrar", "ver todos", "desejados"]):
        return {
            "status": "interaction_required",
            "message": "Agente Planejador: Encontrei registros no banco. Deseja usar a base atual ou treinar novamente?",
            "options": ["Usar base atual", "Treinar novamente"]
        }

    if "treinar novamente" in query_lower:
        print("[*] Planejador: Iniciando treinamento...")
        train_supplier_classifier()
        query_lower = "usar base" 

    if not any(k in query_lower for k in filtros_labels + ["filtrar", "desejados"]):
        return {
            "status": "interaction_required",
            "message": "Como deseja filtrar os fornecedores para seleção?",
            "options": ["Todos", "Ruim", "Médio", "Bom", "Ótimo"]
        }

    fornecedores = get_classified_suppliers()
    if isinstance(fornecedores, dict) and "error" in fornecedores:
        print("[!] Planejador: Base não encontrada após etapa de fonte. Treinando...")
        train_supplier_classifier()
        fornecedores = get_classified_suppliers()

    return filter_suppliers_planejador_tool(fornecedores, query_lower)


class AgentePlanejadorCompras(Agent):
    """
    Agente responsável por prever a demanda e facilitar a seleção de fornecedores.
    Interpreta se o usuário deseja planejar compras ou selecionar fornecedores.
    """
    name: str = "Agente_Planejador"
    description: str = "Estrategista de compras: planejamento de demanda e seleção de fornecedores."
    instruction: str = """
    Você é o Agente Planejador do sistema IACOMPRAS.
    Responsável por auxiliar no planejamento de volumes de compra e seleção estratégica.
    Use as tools disponíveis para:
    - Interpretar intenção do usuário (interpretar_intencao_tool)
    - Sugerir produtos para fornecedores selecionados (sugerir_produtos_tool)
    - Recomendar fornecedores para produtos (recomendar_fornecedores_por_produto_tool)
    - Filtrar fornecedores por classificação (filter_suppliers_planejador_tool)
    """
    tools: list = [
        interpretar_intencao_tool,
        get_top_products_tool,
        sugerir_produtos_tool,
        filter_suppliers_planejador_tool,
        recomendar_fornecedores_por_produto_tool,
        executar_planejador_tool
    ]
    
    def executar(self, query=None):
        """Método de compatibilidade que invoca a tool principal."""
        return executar_planejador_tool(query)
