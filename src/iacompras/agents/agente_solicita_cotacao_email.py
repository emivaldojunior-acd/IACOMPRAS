import configparser
import logging
from datetime import datetime
from pathlib import Path

from iacompras.tools.email_tools import send_email
from iacompras.tools.db_tools import db_list_orcamentos


class AgenteSolicitaCotacao:
    """
    Agente responsável por enviar solicitações de cotação para fornecedores.
    Recebe a lista de orçamentos gerados pelo Agente_Orcamento e envia um email
    para cada fornecedor com os detalhes do orçamento.
    
    Emails são enviados:
    - DE: SMTP_CLIENTE (USER) - remetente/cliente
    - PARA: SMTP_FORNECEDOR (USER) - destinatário/fornecedor
    - USANDO: Credenciais SMTP de SMTP_CLIENTE para autenticação
    """

    def __init__(self, config_path: str = "smtp_config.ini"):
        self.nome = "Agente_Solicita_Cotacao_Email"
        self.config_path = config_path

        self.instructions = """
Você é o Agente de Solicitação de Cotações do sistema IA Compras.

Seu papel é enviar emails formais de solicitação de cotação para os fornecedores
dos orçamentos que foram confirmados pelo usuário.

Você NÃO deve escolher fornecedores nem produtos por conta própria.

O endereço de envio e os parâmetros SMTP são fixos e devem ser carregados
exclusivamente a partir do arquivo de configuração do sistema (smtp_config.ini).

Para cada orçamento recebido, você deve:
- gerar um e-mail corporativo formal com os detalhes do orçamento;
- incluir o nome do fornecedor, CNPJ e lista de itens no corpo da mensagem;
- informar que a cotação foi criada automaticamente pelo sistema IA Compras;
- registrar a tentativa de envio no log do sistema;
- sinalizar falhas de comunicação para o orquestrador.

Você não deve modificar credenciais nem destinatários.

O conteúdo da mensagem deve ser claro, objetivo e padronizado.

Caso o envio falhe, retorne erro estruturado contendo motivo técnico e timestamp.

Sua saída deve ser uma confirmação de envio ou erro controlado.
"""

        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        if "SMTP_CLIENTE" not in self.config:
            raise RuntimeError("Seção SMTP_CLIENTE não encontrada no smtp_config.ini")
        
        if "SMTP_FORNECEDOR" not in self.config:
            raise RuntimeError("Seção SMTP_FORNECEDOR não encontrada no smtp_config.ini")

        self.email_cliente = self.config["SMTP_CLIENTE"]["USER"]
        self.email_fornecedor = self.config["SMTP_FORNECEDOR"]["USER"]

        self.logger = logging.getLogger(self.nome)
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

        self.template_path = (
            Path(__file__).resolve()
            .parent.parent
            / "templates"
            / "email_envia_cotacao_fornecedor.txt"
        )

    # ------------------------------------------------------------------

    def _carregar_template(self) -> str:
        """Carrega o template de email do arquivo."""
        if not self.template_path.exists():
            raise FileNotFoundError(
                f"Template de email não encontrado: {self.template_path}"
            )
        return self.template_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------

    def _formatar_lista_itens(self, itens: list) -> str:
        """Formata a lista de itens para o corpo do email."""
        if not itens:
            return "  (Nenhum item especificado)"
        
        linhas = []
        for i, item in enumerate(itens, 1):
            codigo = item.get('codigo_produto', 'N/A')
            preco = item.get('preco_unitario', item.get('preco_base', 0))
            recorrencia = item.get('recorrencia', 0)
            linhas.append(f"  {i}. Código: {codigo} | Preço Base: R$ {preco:.2f} | Recorrência: {recorrencia}")
        
        return "\n".join(linhas)

    # ------------------------------------------------------------------

    def enviar_cotacao_fornecedor(self, orcamento: dict) -> dict:
        """
        Envia email de solicitação de cotação para um fornecedor específico.
        
        Args:
            orcamento: Dicionário com dados do orçamento (fornecedor, cnpj, valor_total, itens)
        
        Returns:
            dict com status do envio
        """
        nome_fornecedor = orcamento.get('fornecedor') or orcamento.get('razao_fornecedor', 'N/A')
        cnpj = orcamento.get('cnpj_fornecedor', 'N/A')
        valor_total = orcamento.get('valor_total') or orcamento.get('valor_total_estimado', 0)
        itens = orcamento.get('itens', [])

        subject = f"Solicitação de Cotação - {nome_fornecedor}"

        self.logger.info(
            f"Preparando envio de cotação para fornecedor: {nome_fornecedor}"
        )

        try:
            template = self._carregar_template()

            body = template.format(
                nome_fornecedor=nome_fornecedor,
                cnpj_fornecedor=cnpj,
                data_solicitacao=datetime.now().strftime("%d/%m/%Y %H:%M"),
                lista_itens=self._formatar_lista_itens(itens),
                valor_total=f"{valor_total:.2f}"
            )

            # Enviando email
            send_email(
                to_email=self.email_fornecedor,
                subject=subject,
                body=body,
                smtp_section="SMTP_CLIENTE",
                config_path=self.config_path
            )

            self.logger.info(f"Email de cotação enviado com sucesso para: {nome_fornecedor}")

            return {
                "success": True,
                "fornecedor": nome_fornecedor,
                "cnpj": cnpj,
                "email_destino": self.email_fornecedor,
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Cotação enviada com sucesso para {nome_fornecedor}",
                "error": None,
            }

        except Exception as e:
            self.logger.error(
                f"Falha ao enviar cotação para {nome_fornecedor}: {str(e)}"
            )

            return {
                "success": False,
                "fornecedor": nome_fornecedor,
                "cnpj": cnpj,
                "email_destino": self.email_fornecedor,
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Erro ao enviar cotação: {str(e)}",
                "error": str(e),
            }


    def enviar_cotacoes_em_lote(self, orcamentos: list) -> dict:
        """
        Envia cotações para todos os fornecedores da lista de orçamentos.
        Após envio bem-sucedido, aciona automaticamente o AgenteFornecedorEmail
        para enviar confirmações de recebimento.
        
        Args:
            orcamentos: Lista de orçamentos confirmados
        
        Returns:
            dict com resumo dos envios
        """
        if not orcamentos:
            return {
                "status": "error",
                "type": "quotation_send_result",
                "message": "Nenhum orçamento fornecido para envio de cotações.",
                "enviados": 0,
                "falhas": 0,
                "detalhes": []
            }

        resultados = []
        enviados = 0
        falhas = 0
        orcamentos_enviados = []  

        for orc in orcamentos:
            resultado = self.enviar_cotacao_fornecedor(orc)
            resultados.append(resultado)
            if resultado.get('success'):
                enviados += 1
                orcamentos_enviados.append(orc)
            else:
                falhas += 1

        status = "success" if falhas == 0 else ("partial" if enviados > 0 else "error")

        # Se houve envios bem-sucedidos, aciona o AgenteFornecedorEmail para responder
        confirmacoes_fornecedor = None
        if orcamentos_enviados:
            self.logger.info(f"Acionando AgenteFornecedorEmail para {len(orcamentos_enviados)} orçamentos...")
            try:
                from iacompras.agents.agente_fornecedor_email import AgenteFornecedorEmail
                agente_fornecedor = AgenteFornecedorEmail(config_path=self.config_path)
                confirmacoes_fornecedor = agente_fornecedor.enviar_confirmacoes_em_lote(orcamentos_enviados)
                self.logger.info(f"Confirmações do fornecedor: {confirmacoes_fornecedor.get('message')}")
            except Exception as e:
                self.logger.error(f"Erro ao acionar AgenteFornecedorEmail: {e}")
                confirmacoes_fornecedor = {
                    "status": "error",
                    "message": f"Erro ao enviar confirmações do fornecedor: {e}"
                }

        return {
            "status": status,
            "type": "quotation_send_result",
            "message": f"Cotações enviadas: {enviados} | Falhas: {falhas}",
            "enviados": enviados,
            "falhas": falhas,
            "detalhes": resultados,
            "confirmacoes_fornecedor": confirmacoes_fornecedor
        }


    def executar(self, query=None, orcamentos=None, orcamento_ids=None):
        """
        Executa o agente para enviar cotações.
        
        Args:
            query: String de comando (opcional)
            orcamentos: Lista de orçamentos para enviar cotações
            orcamento_ids: Lista de IDs de orçamentos para buscar no banco
        
        Returns:
            dict com resultado da operação
        """
        query_lower = (query or "").lower()

        # Se recebeu IDs, busca os orçamentos do banco
        if orcamento_ids:
            orcamentos_db = db_list_orcamentos(orcamento_ids)
            if not orcamentos_db:
                return {
                    "status": "error",
                    "type": "quotation_send_result",
                    "message": "Nenhum orçamento encontrado com os IDs fornecidos."
                }
            return self.enviar_cotacoes_em_lote(orcamentos_db)

        # Se recebeu lista de orçamentos diretamente
        if orcamentos and isinstance(orcamentos, list):
            return self.enviar_cotacoes_em_lote(orcamentos)

        # Comando via query string
        if "enviar_cotacoes:" in query_lower:
            import ast
            try:
                parts = query.split("enviar_cotacoes:")
                orc_data = ast.literal_eval(parts[1].strip())

                if isinstance(orc_data, list) and all(isinstance(x, int) for x in orc_data):
                    # Lista de IDs
                    orcamentos_db = db_list_orcamentos(orc_data)
                    return self.enviar_cotacoes_em_lote(orcamentos_db)
                else:
                    # Lista de dicts de orçamentos
                    return self.enviar_cotacoes_em_lote(orc_data)
            except Exception as e:
                return {
                    "status": "error",
                    "type": "quotation_send_result",
                    "message": f"Erro ao processar comando de envio de cotações: {e}"
                }

        return {
            "status": "error",
            "type": "quotation_send_result",
            "message": "Comando não reconhecido pelo Agente Solicita Cotação. Use 'enviar_cotacoes: [lista_orcamentos]'."
        }
