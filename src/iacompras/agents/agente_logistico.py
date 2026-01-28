from google.adk.agents import Agent

class AgenteLogistico(Agent):
    """
    Agente responsável por sugerir janelas de entrega e risco de ruptura.
    """
    name: str = "Agente_Logistico"
    description: str = "Planeja logística de entrega e avalia riscos."
    instruction: str = "Você deve sugerir janelas de entrega e avaliar o risco de ruptura baseado nos prazos."

    def planejar_logistica(self, auditoria_final: list) -> list:
        """Sugerir janelas de entrega e risco de ruptura."""
        plano_logistico = []
        for item in auditoria_final:
            prazo = item.get('prazo_dias', 7)
            risco = "BAIXO" if prazo < 5 else "MEDIO"
            
            plano_logistico.append({
                **item,
                "janela_entrega_sugerida": f"Entrega em {prazo} dias úteis.",
                "risco_ruptura": risco
            })
            
        return plano_logistico

    def executar(self, auditoria_final):
        # Wrapper temporário
        return self.planejar_logistica(auditoria_final)
