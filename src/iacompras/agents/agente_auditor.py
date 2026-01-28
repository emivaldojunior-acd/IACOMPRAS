from google.adk.agents import Agent
from iacompras.tools.analysis_tools import detect_anomalies

class AgenteAuditor(Agent):
    """
    Agente responsável por detectar anomalias e inconsistências.
    """
    name: str = "Agente_Auditor"
    description: str = "Audita transações e detecta anomalias."
    instruction: str = "Você deve analisar os preços e quantidades para detectar anomalias ou falhas de conformidade."

    def auditar_compras(self, analise_financeira: dict) -> list:
        """Detectar anomalias e inconsistências."""
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

    def executar(self, analise_financeira):
        # Wrapper temporário
        return self.auditar_compras(analise_financeira)
