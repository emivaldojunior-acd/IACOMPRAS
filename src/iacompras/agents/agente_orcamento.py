from google.adk.agents import Agent
from iacompras.tools.db_tools import db_insert_cotacao, db_insert_orcamento
from iacompras.tools.external_tools import sendgrid_send_email_dry_run

class AgenteGerenciadorOrcamento(Agent):
    """
    Agente responsável por simular cotações e registrar no banco.
    """
    name: str = "Agente_Orcamento"
    description: str = "Gere cotações e comunica-se com fornecedores."
    instruction: str = "Você deve gerar cotações para os produtos selecionados e simular o envio de e-mails para os fornecedores."

    def preparar_resumo(self, selecoes: dict) -> dict:
        """
        Agrupa os produtos por fornecedor e gera um resumo para o usuário.
        selecoes: {codigo_produto: [{Fornecedor: str, Preço Médio: float, ...}, ...]}
        """
        import pandas as pd
        if not selecoes:
            return {"type": "budget_summary_view", "orcamentos": []}

        # Agrupar itens por Fornecedor (Suporta múltiplos fornecedores por produto)
        orcamentos_por_fornecedor = {}
        for p_code, list_details in selecoes.items():
            # Garante que seja lista para iterar
            if not isinstance(list_details, list):
                list_details = [list_details]

            for details in list_details:
                forn = details.get('Fornecedor')
                if not forn: continue
                
                if forn not in orcamentos_por_fornecedor:
                    orcamentos_por_fornecedor[forn] = []
                
                orcamentos_por_fornecedor[forn].append({
                    "codigo_produto": p_code,
                    "preco_base": details.get('Preço Médio', 0),
                    "recorrencia": details.get('Recorrência', 0)
                })

        resumo_final = []
        for forn, itens in orcamentos_por_fornecedor.items():
            valor_total_estimado = sum(i['preco_base'] for i in itens)
            resumo_final.append({
                "fornecedor": forn,
                "total_itens": len(itens),
                "valor_total_estimado": valor_total_estimado,
                "itens": itens
            })

        return {
            "type": "budget_summary_view",
            "orcamentos": resumo_final
        }

    def confirmar_orcamentos(self, orcamentos_resumo: list) -> dict:
        """
        Grava os orçamentos finalizados no banco de dados.
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
                itens=itens_db
            )
            ids_gerados.append(orc_id)
            
        return {
            "status": "success",
            "message": f"{len(ids_gerados)} orçamentos gravados com sucesso no banco de dados.",
            "orcamento_ids": ids_gerados
        }

    def executar(self, run_id=0, fornecimentos=None, query=None):
        query_lower = (query or "").lower()
        
        # 1. Fluxo de Resumo (Novo)
        if "gerar_resumo_orcamentos:" in query_lower:
            import ast
            try:
                parts = query.split("gerar_resumo_orcamentos:")
                selecoes = ast.literal_eval(parts[1].strip())
                return self.preparar_resumo(selecoes)
            except Exception as e:
                return {"status": "error", "message": f"Erro ao gerar resumo de orçamentos: {e}"}

        # 2. Fluxo de Confirmação Final (Gravação no BD)
        if "confirmar_orcamentos:" in query_lower:
            import ast
            try:
                parts = query.split("confirmar_orcamentos:")
                orcamentos_list = ast.literal_eval(parts[1].strip())
                return self.confirmar_orcamentos(orcamentos_list)
            except Exception as e:
                return {"status": "error", "message": f"Erro ao confirmar orçamentos no BD: {e}"}

        # 3. Fluxo Legado/Direto (antigo)
        if not fornecimentos:
            return {"status": "error", "message": "Nenhum fornecedor selecionado ou comando de resumo ausente."}
            
        return self.gerenciar_orcamento(run_id, fornecimentos)
