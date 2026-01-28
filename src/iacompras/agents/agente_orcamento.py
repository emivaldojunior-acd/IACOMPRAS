from google.adk.agents import Agent
from iacompras.tools.db_tools import db_insert_cotacao
from iacompras.tools.external_tools import sendgrid_send_email_dry_run

class AgenteGerenciadorOrcamento(Agent):
    """
    Agente responsável por simular cotações e registrar no banco.
    """
    name: str = "Agente_Orcamento"
    description: str = "Gere cotações e comunica-se com fornecedores."
    instruction: str = "Você deve gerar cotações para os produtos selecionados e simular o envio de e-mails para os fornecedores."

    def gerenciar_orcamento(self, run_id: int, fornecimentos: list) -> list:
        """Simular cotações e registrar no banco."""
        status_cotacoes = []
        for item in fornecimentos:
            # Simula um valor unitário
            valor_simulado = 100.0 
            
            # Registra cotação no SQLite
            db_insert_cotacao(
                run_id, 
                item['cnpj'], 
                item['codigo_produto'], 
                valor_simulado, 
                item.get('prazo_estimado', 7),
                "Condição padrão 30 dias"
            )
            
            # Simula envio de e-mail de cotação
            email_log = sendgrid_send_email_dry_run(
                f"vendas@{item['cnpj']}.com.br",
                f"Solicitação de Cotação - Produto {item['codigo_produto']}",
                f"Olá, solicitamos cotação para {item['quantidade_sugerida']} unidades do produto {item['codigo_produto']}.",
                run_id=run_id
            )
            
            status_cotacoes.append({
                **item,
                "valor_unitario": valor_simulado,
                "email_status": email_log['status']
            })
            
        return status_cotacoes

    def executar(self, run_id, fornecimentos):
        # Wrapper temporário
        return self.gerenciar_orcamento(run_id, fornecimentos)
