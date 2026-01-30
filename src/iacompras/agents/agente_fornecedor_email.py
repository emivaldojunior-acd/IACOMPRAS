import configparser
import logging
from datetime import datetime
from pathlib import Path

from iacompras.tools.email_tools import send_email


class AgenteFornecedorEmail:
    """
    Agente responsável por enviar confirmações de recebimento de pedidos para clientes.
    
    Simula a resposta do fornecedor ao cliente após receber uma solicitação de cotação.
    
    Emails são enviados:
    - DE: SMTP_FORNECEDOR (USER) - fornecedor/remetente
    - PARA: SMTP_CLIENTE (USER) - cliente/destinatário
    - USANDO: Credenciais SMTP de SMTP_FORNECEDOR para autenticação
    """

    def __init__(self, config_path: str = "smtp_config.ini"):
        self.nome = "Agente_Fornecedor_Email"
        self.config_path = config_path

        self.instructions = """
Você é o Agente de Resposta do Fornecedor do sistema IA Compras.

Seu papel é simular a resposta automática do fornecedor ao cliente, confirmando
o recebimento da solicitação de cotação.

Você NÃO deve escolher fornecedores nem produtos por conta própria.

O endereço de envio e os parâmetros SMTP são fixos e devem ser carregados
exclusivamente a partir do arquivo de configuração do sistema.

Para cada orçamento recebido, você deve:
- gerar um e-mail de confirmação formal;
- incluir o nome do fornecedor, CNPJ e lista de itens no corpo da mensagem;
- informar que o pedido foi recebido e está sendo processado;
- registrar a tentativa de envio no log do sistema;
- sinalizar falhas de comunicação para o orquestrador.

Você não deve modificar credenciais nem destinatários.

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
            / "email_envia_pedido_iacompras.txt"
        )


    def _carregar_template(self) -> str:
        if not self.template_path.exists():
            raise FileNotFoundError(
                f"Template de email não encontrado: {self.template_path}"
            )
        return self.template_path.read_text(encoding="utf-8")


    def _formatar_lista_itens(self, itens: list) -> str:
        if not itens:
            return "  (Nenhum item especificado)"
        
        linhas = []
        for i, item in enumerate(itens, 1):
            codigo = item.get('codigo_produto', 'N/A')
            preco = item.get('preco_unitario', item.get('preco_base', 0))
            recorrencia = item.get('recorrencia', 0)
            linhas.append(f"  {i}. Código: {codigo} | Preço Base: R$ {preco:.2f} | Recorrência: {recorrencia}")
        
        return "\n".join(linhas)


    def enviar_confirmacao_pedido(self, orcamento: dict) -> dict:
        """
        Envia email de confirmação de recebimento do pedido para o cliente.
        
        Args:
            orcamento: Dicionário com dados do orçamento (fornecedor, cnpj, valor_total, itens)
        
        Returns:
            dict com status do envio
        """
        nome_fornecedor = orcamento.get('fornecedor') or orcamento.get('razao_fornecedor', 'N/A')
        cnpj = orcamento.get('cnpj_fornecedor', 'N/A')
        valor_total = orcamento.get('valor_total') or orcamento.get('valor_total_estimado', 0)
        itens = orcamento.get('itens', [])

        subject = f"Confirmação de Recebimento - Pedido {nome_fornecedor}"

        self.logger.info(
            f"Preparando envio de confirmação de pedido do fornecedor: {nome_fornecedor}"
        )

        try:
            template = self._carregar_template()

            body = template.format(
                nome_fornecedor=nome_fornecedor,
                cnpj_fornecedor=cnpj,
                data_recebimento=datetime.now().strftime("%d/%m/%Y %H:%M"),
                lista_itens=self._formatar_lista_itens(itens),
                valor_total=f"{valor_total:.2f}"
            )

            # Envia email:
            # - Para: email do cliente (SMTP_CLIENTE USER)
            # - Usando credenciais de: SMTP_FORNECEDOR
            send_email(
                to_email=self.email_cliente,
                subject=subject,
                body=body,
                smtp_section="SMTP_FORNECEDOR",
                config_path=self.config_path
            )

            self.logger.info(f"Confirmação de pedido enviada com sucesso para cliente: {self.email_cliente}")

            return {
                "success": True,
                "fornecedor": nome_fornecedor,
                "cnpj": cnpj,
                "email_destino": self.email_cliente,
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Confirmação enviada por {nome_fornecedor} para o cliente",
                "error": None,
            }

        except Exception as e:
            self.logger.error(
                f"Falha ao enviar confirmação do fornecedor {nome_fornecedor}: {str(e)}"
            )

            return {
                "success": False,
                "fornecedor": nome_fornecedor,
                "cnpj": cnpj,
                "email_destino": self.email_cliente,
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Erro ao enviar confirmação: {str(e)}",
                "error": str(e),
            }

    # ------------------------------------------------------------------

    def enviar_confirmacoes_em_lote(self, orcamentos: list) -> dict:
        """
        Envia confirmações para todos os orçamentos da lista.
        
        Args:
            orcamentos: Lista de orçamentos confirmados
        
        Returns:
            dict com resumo dos envios
        """
        if not orcamentos:
            return {
                "status": "error",
                "type": "supplier_confirmation_result",
                "message": "Nenhum orçamento fornecido para envio de confirmações.",
                "enviados": 0,
                "falhas": 0,
                "detalhes": []
            }

        resultados = []
        enviados = 0
        falhas = 0

        for orc in orcamentos:
            resultado = self.enviar_confirmacao_pedido(orc)
            resultados.append(resultado)
            if resultado.get('success'):
                enviados += 1
            else:
                falhas += 1

        status = "success" if falhas == 0 else ("partial" if enviados > 0 else "error")

        return {
            "status": status,
            "type": "supplier_confirmation_result",
            "message": f"Confirmações de fornecedores enviadas: {enviados} | Falhas: {falhas}",
            "enviados": enviados,
            "falhas": falhas,
            "detalhes": resultados
        }

    # ------------------------------------------------------------------

    def executar(self, query=None, orcamentos=None):
        """
        Executa o agente para enviar confirmações de pedido.
        
        Args:
            query: String de comando (opcional)
            orcamentos: Lista de orçamentos para enviar confirmações
        
        Returns:
            dict com resultado da operação
        """
        # Se recebeu lista de orçamentos diretamente
        if orcamentos and isinstance(orcamentos, list):
            return self.enviar_confirmacoes_em_lote(orcamentos)

        return {
            "status": "error",
            "type": "supplier_confirmation_result",
            "message": "Nenhum orçamento fornecido para o Agente Fornecedor Email."
        }
