class AgenteFinanceiro:
    """
    Agente responsável por estimar o impacto financeiro.
    """
    def __init__(self):
        self.name = "Financeiro"

    def executar(self, cotacoes):
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
