from iacompras.tools.analysis_tools import detect_anomalies

class AgenteAuditor:
    """
    Agente responsável por detectar anomalias e inconsistências.
    """
    def __init__(self):
        self.name = "Auditor"

    def executar(self, analise_financeira):
        itens = analise_financeira['itens']
        valores_unitarios = [item['valor_unitario'] for item in itens]
        
        # Detecta anomalias nos preços unitários
        anomalias_preco = detect_anomalies(valores_unitarios)
        
        auditoria_final = []
        for item in itens:
            flags = []
            if item['valor_unitario'] in anomalias_preco:
                flags.append("PRECO_FORA_PADRAO")
            
            if item['quantidade_sugerida'] > 1000: # Exemplo de threshold
                flags.append("GRANDE_QUANTIDADE")
                
            auditoria_final.append({
                **item,
                "flags_auditoria": ", ".join(flags) if flags else "OK",
                "aprovacao_automatica": len(flags) == 0
            })
            
        return auditoria_final
