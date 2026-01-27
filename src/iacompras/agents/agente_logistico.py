class AgenteLogistico:
    """
    Agente responsável por sugerir janelas de entrega e risco de ruptura.
    """
    def __init__(self):
        self.name = "Logístico"

    def executar(self, auditoria_final):
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
