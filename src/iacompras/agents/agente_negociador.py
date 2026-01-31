"""
Agente Negociador ADK - IACOMPRAS
Responsável por selecionar fornecedores e validar dados via BrasilAPI.
"""
import json
from google.adk.agents import Agent
from iacompras.tools.external_tools import brasilapi_cnpj_lookup
from iacompras.tools.analysis_tools import score_supplier
from iacompras.tools.ml_tools import train_supplier_classifier, get_classified_suppliers
from iacompras.tools.db_tools import db_get_latest_classified_suppliers


def negociar_fornecedores_tool(recomendacoes_compras: list) -> list:
    """
    Valida e enriquece dados de fornecedores via BrasilAPI.
    
    Args:
        recomendacoes_compras: Lista de itens de compra com fornecedores para validação
    
    Returns:
        Lista de fornecimentos com dados validados e score calculado
    """
    fornecimentos = []
    for item in recomendacoes_compras:
        
        nome_fornecedor = item.get('RAZAO_FORNECEDOR') or item.get('fornecedor') or item.get('nome', 'N/A')
        cnpj_fornecedor = item.get('CNPJ_FORNECEDOR') or item.get('cnpj', '')
        prazo_medio = item.get('prazo_medio', 10)
        volume_historico = item.get('volume_historico', 0)
        
        print(f"[*] Negociador: validando fornecedor {nome_fornecedor}")
                
        info_cadastral = {}
        if cnpj_fornecedor:
            info_cadastral = brasilapi_cnpj_lookup(cnpj_fornecedor)
        
        
        score = score_supplier(prazo_medio, volume_historico)
        
        fornecimentos.append({
            **item,
            "fornecedor_sugerido": info_cadastral.get("razao_social", nome_fornecedor),
            "cnpj": cnpj_fornecedor,
            "cidade": info_cadastral.get("municipio"),
            "uf": info_cadastral.get("uf", item.get('uf')),
            "score": score,
            "justificativa_fornecedor": f"Fornecedor com score {score}. Localizado em {info_cadastral.get('uf', 'N/A')}."
        })
    return fornecimentos


def atualizar_inteligencia_tool() -> list:
    """
    Treina o classificador de fornecedores e gera a predição para 2025.
    
    Returns:
        Lista de fornecedores classificados atualizada
    """
    print("[*] Agente Negociador atualizando inteligência de fornecedores...")
    from iacompras.tools.ml_tools import classify_suppliers_2025
    
    train_result = train_supplier_classifier()
    print(f"[*] Treinamento: {train_result.get('message')}")
    
    classif_result = classify_suppliers_2025()
    print(f"[*] Classificação 2025: {classif_result.get('message')}")
    
    return listar_fornecedores_tool()


def filter_suppliers_tool(data: list, filter_query: str) -> list:
    """
    Aplica filtro de classificação aos dados com suporte a sinônimos.
    
    Args:
        data: Lista de fornecedores para filtrar
        filter_query: Critério de filtro (todos, ruim, médio, bom, ótimo)
    
    Returns:
        Lista de fornecedores filtrados
    """
    if not filter_query:
        return data
        
    fq = filter_query.lower()
    if "todos" in fq or "qualquer" in fq:
        return data
        
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


def listar_fornecedores_tool(query: str = None) -> dict:
    """
    Retorna a lista de fornecedores classificados com interatividade inteligente.
    
    Args:
        query: Consulta opcional para filtrar resultados
    
    Returns:
        Lista de fornecedores ou dict com opções de interação
    """
    print("[*] Agente Negociador recuperando lista de fornecedores classificados...")
    
    resultado = get_classified_suppliers()
    
    if isinstance(resultado, dict) and "error" in resultado:
        print("[!] Base de inteligência não encontrada. Iniciando treinamento automático...")
        train_supplier_classifier()
        resultado = get_classified_suppliers()
    

    query_lower = query.lower() if query else ""
    
    keywords = ["todos", "qualquer", "ruim", "péssimo", "piores", "médio", "regular", "bom", "ótimo", "excelente", "melhores", "recomendado"]
    
    if any(k in query_lower for k in keywords) or "filtrar" in query_lower:
        return filter_suppliers_tool(resultado, query)

    return {
        "status": "interaction_required",
        "message": "Como deseja visualizar a lista de fornecedores?",
        "options": ["Todos", "Ruim", "Médio", "Bom", "Ótimo"]
    }


def executar_negociador_tool(recomendacoes_compras: list = None, query: str = None) -> dict:
    """
    Executa o fluxo principal do Agente Negociador de fornecedores.
    Suporta treinamento, filtragem ou uso da base atual.
    
    Args:
        recomendacoes_compras: Lista opcional de recomendações para negociação
        query: Consulta do usuário para determinar o fluxo
    
    Returns:
        Resultado da operação (lista de fornecedores ou dados de interação)
    """
    query_lower = query.lower() if query else ""

    if any(k in query_lower for k in ["treinar", "atualizar", "processar"]):
        return atualizar_inteligencia_tool()
    
    if any(k in query_lower for k in ["usar", "atual", "tabela", "base", "manter", "filtrar", "todos", "ruim", "médio", "bom", "ótimo"]):
        return listar_fornecedores_tool(query=query)

    existing_data = db_get_latest_classified_suppliers()
    
    if existing_data and not recomendacoes_compras:
        return {
            "status": "interaction_required",
            "message": "Encontrei registros de fornecedores classificados no banco de dados. "
                       "Deseja usar os dados da tabela atual ou treinar novamente os modelos?",
            "options": ["Usar base atual", "Treinar novamente"]
        }

    if recomendacoes_compras and isinstance(recomendacoes_compras, list):
        print("[*] Agente Negociador: Enriquecendo recomendações com dados de fornecedores...")
        return negociar_fornecedores_tool(recomendacoes_compras)

    return listar_fornecedores_tool(query=query_lower)


class AgenteNegociadorFornecedores(Agent):
    """
    Agente responsável por selecionar fornecedores e validar dados via BrasilAPI.
    """
    name: str = "Agente_Negociador"
    description: str = "Seleciona fornecedores e valida dados cadastrais."
    instruction: str = """
    Você é o Agente Negociador do sistema IACOMPRAS.
    Responsável por classificar, filtrar e selecionar os melhores fornecedores.
    Use as tools disponíveis para:
    - Treinar/atualizar o modelo de classificação (atualizar_inteligencia_tool)
    - Listar fornecedores classificados (listar_fornecedores_tool)
    - Filtrar fornecedores por categoria (filter_suppliers_tool)
    - Negociar fornecedores para recomendações (negociar_fornecedores_tool)
    """
    tools: list = [
        negociar_fornecedores_tool,
        atualizar_inteligencia_tool,
        filter_suppliers_tool,
        listar_fornecedores_tool,
        executar_negociador_tool
    ]
    
    def executar(self, recomendacoes_compras=None, query=None):
        """Método de compatibilidade que invoca a tool principal."""
        return executar_negociador_tool(recomendacoes_compras, query)
