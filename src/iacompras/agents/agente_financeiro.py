from google.adk.agents import Agent

class AgenteFinanceiro(Agent):
    """
    Agente responsável por estimar o impacto financeiro.
    """
    name: str = "Agente_Financeiro"
    description: str = "Analisa impacto financeiro e fluxo de caixa."
    instruction: str = "Você deve calcular o custo total estimado e sugerir projeções de fluxo de caixa."

    def analisar_financeiro(self, cotacoes: list) -> dict:
        """Estimar o impacto financeiro."""
        analise_financeira = []
        total_geral = 0
        
        for item in cotacoes:
            custo_total = item['quantidade_sugerida'] * item['valor_unitario']
            total_geral += custo_total
            
            analise_financeira.append({
                **item,
                "custo_estimado": custo_total,
                "projecao_fluxo": f"Parcelamento sugerido: 3x de {custo_total/3:.2f}"
            })
            
        return {
            "itens": analise_financeira,
            "total_geral": total_geral,
            "resumo_caixa": f"Impacto total de R$ {total_geral:.2f} no próximo mês."
        }

    def executar(self, cotacoes=None, query=None):
        # Se não houver cotações, o financeiro não deve rodar
        if not cotacoes:
            print("[!] Agente Financeiro: Nenhuma cotação recebida para análise.")
            return {"status": "error", "message": "Nenhuma cotação disponível. Execute o Agente de Orçamento primeiro."}
            
        return self.analisar_financeiro(cotacoes)
