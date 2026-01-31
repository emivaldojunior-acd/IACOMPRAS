"""
Agente Fornecedor Email ADK - IACOMPRAS
Responsável por enviar confirmações de recebimento de pedidos para clientes.
Simula a resposta do fornecedor ao cliente após receber uma solicitação de cotação.
"""
import configparser
import logging
from datetime import datetime
from pathlib import Path

from google.adk.agents import Agent
from iacompras.tools.email_tools import send_email



DEFAULT_CONFIG_PATH = "smtp_config.ini"

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "email_envia_pedido_iacompras.txt"

logger = logging.getLogger("Agente_Fornecedor_Email")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _carregar_config(config_path: str = DEFAULT_CONFIG_PATH) -> tuple:
    """Carrega configurações SMTP do arquivo."""
    config = configparser.ConfigParser()
    config.read(config_path)

    if "SMTP_CLIENTE" not in config:
        raise RuntimeError("Seção SMTP_CLIENTE não encontrada no smtp_config.ini")
    
    if "SMTP_FORNECEDOR" not in config:
        raise RuntimeError("Seção SMTP_FORNECEDOR não encontrada no smtp_config.ini")

    email_cliente = config["SMTP_CLIENTE"]["USER"]
    email_fornecedor = config["SMTP_FORNECEDOR"]["USER"]
    
    return email_cliente, email_fornecedor, config_path


def _carregar_template() -> str:
    """Carrega o template de email do arquivo."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template de email não encontrado: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _formatar_lista_itens(itens: list) -> str:
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



def enviar_confirmacao_pedido_tool(orcamento: dict, config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Envia email de confirmação de recebimento do pedido para o cliente.
    
    Args:
        orcamento: Dicionário com dados do orçamento (fornecedor, cnpj, valor_total, itens)
        config_path: Caminho para o arquivo de configuração SMTP
    
    Returns:
        dict com status do envio
    """
    email_cliente, email_fornecedor, config_path = _carregar_config(config_path)
    
    nome_fornecedor = orcamento.get('fornecedor') or orcamento.get('razao_fornecedor', 'N/A')
    cnpj = orcamento.get('cnpj_fornecedor', 'N/A')
    valor_total = orcamento.get('valor_total') or orcamento.get('valor_total_estimado', 0)
    itens = orcamento.get('itens', [])

    subject = f"Confirmação de Recebimento - Pedido {nome_fornecedor}"

    logger.info(f"Preparando envio de confirmação de pedido do fornecedor: {nome_fornecedor}")

    try:
        template = _carregar_template()

        body = template.format(
            nome_fornecedor=nome_fornecedor,
            cnpj_fornecedor=cnpj,
            data_recebimento=datetime.now().strftime("%d/%m/%Y %H:%M"),
            lista_itens=_formatar_lista_itens(itens),
            valor_total=f"{valor_total:.2f}"
        )

        send_email(
            to_email=email_cliente,
            subject=subject,
            body=body,
            smtp_section="SMTP_FORNECEDOR",
            config_path=config_path
        )

        logger.info(f"Confirmação de pedido enviada com sucesso para cliente: {email_cliente}")

        return {
            "success": True,
            "fornecedor": nome_fornecedor,
            "cnpj": cnpj,
            "email_destino": email_cliente,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Confirmação enviada por {nome_fornecedor} para o cliente",
            "error": None,
        }

    except Exception as e:
        logger.error(f"Falha ao enviar confirmação do fornecedor {nome_fornecedor}: {str(e)}")

        return {
            "success": False,
            "fornecedor": nome_fornecedor,
            "cnpj": cnpj,
            "email_destino": email_cliente,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Erro ao enviar confirmação: {str(e)}",
            "error": str(e),
        }


def enviar_confirmacoes_em_lote_tool(orcamentos: list, config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Envia confirmações para todos os orçamentos da lista.
    
    Args:
        orcamentos: Lista de orçamentos confirmados
        config_path: Caminho para o arquivo de configuração SMTP
    
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
        resultado = enviar_confirmacao_pedido_tool(orc, config_path)
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


def executar_fornecedor_email_tool(query: str = None, orcamentos: list = None, config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Executa o agente para enviar confirmações de pedido.
    
    Args:
        query: String de comando (opcional)
        orcamentos: Lista de orçamentos para enviar confirmações
        config_path: Caminho para o arquivo de configuração SMTP
    
    Returns:
        dict com resultado da operação
    """

    if orcamentos and isinstance(orcamentos, list):
        return enviar_confirmacoes_em_lote_tool(orcamentos, config_path)

    return {
        "status": "error",
        "type": "supplier_confirmation_result",
        "message": "Nenhum orçamento fornecido para o Agente Fornecedor Email."
    }


class AgenteFornecedorEmail(Agent):
    """
    Agente responsável por enviar confirmações de recebimento de pedidos para clientes.
    Simula a resposta do fornecedor ao cliente após receber uma solicitação de cotação.
    """
    name: str = "Agente_Fornecedor_Email"
    description: str = "Envia confirmações de recebimento de pedidos do fornecedor para o cliente."
    instruction: str = """
    Você é o Agente de Resposta do Fornecedor do sistema IA Compras.
    
    Seu papel é simular a resposta automática do fornecedor ao cliente, confirmando
    o recebimento da solicitação de cotação.
    
    Você NÃO deve escolher fornecedores nem produtos por conta própria.
    
    Use as tools disponíveis para:
    - Enviar confirmação de pedido individual (enviar_confirmacao_pedido_tool)
    - Enviar confirmações em lote (enviar_confirmacoes_em_lote_tool)
    """
    tools: list = [
        enviar_confirmacao_pedido_tool,
        enviar_confirmacoes_em_lote_tool,
        executar_fornecedor_email_tool
    ]
    
    def executar(self, query=None, orcamentos=None, config_path: str = DEFAULT_CONFIG_PATH):
        """Método de compatibilidade que invoca a tool principal."""
        return executar_fornecedor_email_tool(query, orcamentos, config_path)
