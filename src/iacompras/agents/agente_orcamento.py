"""
Agente Gerenciador de Orçamento ADK - IACOMPRAS
Responsável por simular cotações e registrar no banco.
"""
import json
import ast
from google.adk.agents import Agent
from iacompras.tools.db_tools import db_insert_orcamento, db_list_orcamentos



def preparar_resumo_orcamentos_tool(selecoes: dict) -> dict:
    """
    Agrupa os produtos por fornecedor e gera um resumo para o usuário.
    
    Args:
        selecoes: Dicionário de seleções {codigo_produto: [{Fornecedor, Preço Médio, CNPJ_FORNECEDOR, ...}, ...]}
    
    Returns:
        dict com resumo de orçamentos agrupados por fornecedor
    """
    import pandas as pd
    if not selecoes:
        return {"type": "budget_summary_view", "orcamentos": []}

    orcamentos_por_fornecedor = {}
    for p_code, list_details in selecoes.items():
        if not isinstance(list_details, list):
            list_details = [list_details]

        for details in list_details:
            forn = details.get('Fornecedor')
            if not forn: 
                continue
            
            if forn not in orcamentos_por_fornecedor:
                orcamentos_por_fornecedor[forn] = {
                    'cnpj': details.get('CNPJ_FORNECEDOR'),
                    'itens': []
                }
            
            orcamentos_por_fornecedor[forn]['itens'].append({
                "codigo_produto": p_code,
                "preco_base": details.get('Preço Médio', 0),
                "recorrencia": details.get('Recorrência', 0)
            })

    resumo_final = []
    for forn, dados in orcamentos_por_fornecedor.items():
        itens = dados['itens']
        valor_total_estimado = sum(i['preco_base'] for i in itens)
        resumo_final.append({
            "fornecedor": forn,
            "cnpj_fornecedor": dados['cnpj'],
            "total_itens": len(itens),
            "valor_total_estimado": valor_total_estimado,
            "itens": itens
        })

    return {
        "type": "budget_summary_view",
        "orcamentos": resumo_final
    }


def confirmar_orcamentos_tool(orcamentos_resumo: list) -> dict:
    """
    Grava os orçamentos finalizados no banco de dados.
    
    Args:
        orcamentos_resumo: Lista de orçamentos para confirmar
    
    Returns:
        dict com status e IDs dos orçamentos gerados
    """
    ids_gerados = []
    for orc in orcamentos_resumo:
        itens_db = [
            {
                "codigo_produto": i['codigo_produto'],
                "preco_unitario": i['preco_base'],
                "recorrencia": i['recorrencia']
            } for i in orc['itens']
        ]
        
        orc_id = db_insert_orcamento(
            razao_fornecedor=orc['fornecedor'],
            valor_total=orc['valor_total_estimado'],
            itens=itens_db,
            cnpj_fornecedor=orc.get('cnpj_fornecedor')
        )
        ids_gerados.append(orc_id)
        
    return {
        "status": "success",
        "type": "budget_confirmation_result",
        "message": f"{len(ids_gerados)} orçamentos gravados com sucesso no banco de dados.",
        "orcamento_ids": ids_gerados,
        "orcamentos_cadastrados": db_list_orcamentos(ids_gerados)
    }


def executar_orcamento_tool(run_id: int = 0, fornecimentos: list = None, query: str = None) -> dict:
    """
    Executa o fluxo principal do Agente de Orçamento.
    
    Args:
        run_id: ID da execução atual
        fornecimentos: Lista de fornecimentos para gerar orçamentos
        query: Consulta do usuário
    
    Returns:
        Resultado da operação
    """
    query_lower = (query or "").lower()
    
    if "gerar_resumo_orcamentos:" in query_lower:
        try:
            parts = query.split("gerar_resumo_orcamentos:")
            selecoes = json.loads(parts[1].strip())
            return preparar_resumo_orcamentos_tool(selecoes)
        except json.JSONDecodeError:
            try:
                selecoes = ast.literal_eval(parts[1].strip())
                return preparar_resumo_orcamentos_tool(selecoes)
            except Exception as e:
                return {"status": "error", "message": f"Erro ao gerar resumo de orçamentos: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"Erro ao gerar resumo de orçamentos: {e}"}

    if "confirmar_orcamentos:" in query_lower:
        try:
            parts = query.split("confirmar_orcamentos:")
            orcamentos_list = ast.literal_eval(parts[1].strip())
            return confirmar_orcamentos_tool(orcamentos_list)
        except Exception as e:
            return {"status": "error", "message": f"Erro ao confirmar orçamentos no BD: {e}"}

    if not fornecimentos:
        return {"status": "error", "message": "Nenhum fornecedor selecionado ou comando de resumo ausente."}
        
    return {"status": "error", "message": "Fluxo não reconhecido. Use 'gerar_resumo_orcamentos:' ou 'confirmar_orcamentos:'."}



class AgenteGerenciadorOrcamento(Agent):
    """
    Agente responsável por simular cotações e registrar no banco.
    """
    name: str = "Agente_Orcamento"
    description: str = "Gere cotações e comunica-se com fornecedores."
    instruction: str = """
    Você é o Agente de Orçamento do sistema IACOMPRAS.
    Responsável por gerar cotações e gravá-las no banco de dados.
    Use as tools disponíveis para:
    - Preparar resumo de orçamentos (preparar_resumo_orcamentos_tool)
    - Confirmar e gravar orçamentos no banco (confirmar_orcamentos_tool)
    """
    tools: list = [
        preparar_resumo_orcamentos_tool,
        confirmar_orcamentos_tool,
        executar_orcamento_tool
    ]
    
    def executar(self, run_id=0, fornecimentos=None, query=None):
        """Método de compatibilidade que invoca a tool principal."""
        return executar_orcamento_tool(run_id, fornecimentos, query)
