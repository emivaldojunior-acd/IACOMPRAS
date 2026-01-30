from google.adk.agents import Agent
from iacompras.tools.db_tools import db_insert_orcamento, db_list_orcamentos

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
        selecoes: {codigo_produto: [{Fornecedor: str, Preço Médio: float, CNPJ_FORNECEDOR: str, ...}, ...]}
        """
        import pandas as pd
        if not selecoes:
            return {"type": "budget_summary_view", "orcamentos": []}

        # Agrupar itens por Fornecedor (Suporta múltiplos fornecedores por produto)
        orcamentos_por_fornecedor = {}
        for p_code, list_details in selecoes.items():
            if not isinstance(list_details, list):
                list_details = [list_details]

            for details in list_details:
                forn = details.get('Fornecedor')
                if not forn: continue
                
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

    def executar(self, run_id=0, fornecimentos=None, query=None):
        query_lower = (query or "").lower()
        
        if "gerar_resumo_orcamentos:" in query_lower:
            import json
            try:
                parts = query.split("gerar_resumo_orcamentos:")
                selecoes = json.loads(parts[1].strip())
                return self.preparar_resumo(selecoes)
            except json.JSONDecodeError:
                import ast
                try:
                    selecoes = ast.literal_eval(parts[1].strip())
                    return self.preparar_resumo(selecoes)
                except Exception as e:
                    return {"status": "error", "message": f"Erro ao gerar resumo de orçamentos: {e}"}
            except Exception as e:
                return {"status": "error", "message": f"Erro ao gerar resumo de orçamentos: {e}"}

        if "confirmar_orcamentos:" in query_lower:
            import ast
            try:
                parts = query.split("confirmar_orcamentos:")
                orcamentos_list = ast.literal_eval(parts[1].strip())
                return self.confirmar_orcamentos(orcamentos_list)
            except Exception as e:
                return {"status": "error", "message": f"Erro ao confirmar orçamentos no BD: {e}"}

        if not fornecimentos:
            return {"status": "error", "message": "Nenhum fornecedor selecionado ou comando de resumo ausente."}
            
        return {"status": "error", "message": "Fluxo não reconhecido. Use 'gerar_resumo_orcamentos:' ou 'confirmar_orcamentos:'."}

