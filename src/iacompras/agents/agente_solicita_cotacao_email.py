"""
Agente Solicita Cotação ADK - IACOMPRAS
Responsável por enviar solicitações de cotação para fornecedores.
"""
import configparser
import logging
import ast
from datetime import datetime
from pathlib import Path

from google.adk.agents import Agent
from iacompras.tools.email_tools import send_email
from iacompras.tools.db_tools import db_list_orcamentos


DEFAULT_CONFIG_PATH = "smtp_config.ini"

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "email_envia_cotacao_fornecedor.txt"

logger = logging.getLogger("Agente_Solicita_Cotacao_Email")
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



def enviar_cotacao_fornecedor_tool(orcamento: dict, config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Envia email de solicitação de cotação para um fornecedor específico.
    
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

    subject = f"Solicitação de Cotação - {nome_fornecedor}"

    logger.info(f"Preparando envio de cotação para fornecedor: {nome_fornecedor}")

    try:
        template = _carregar_template()

        body = template.format(
            nome_fornecedor=nome_fornecedor,
            cnpj_fornecedor=cnpj,
            data_solicitacao=datetime.now().strftime("%d/%m/%Y %H:%M"),
            lista_itens=_formatar_lista_itens(itens),
            valor_total=f"{valor_total:.2f}"
        )

        # enviando email
        send_email(
            to_email=email_fornecedor,
            subject=subject,
            body=body,
            smtp_section="SMTP_CLIENTE",
            config_path=config_path
        )

        logger.info(f"Email de cotação enviado com sucesso para: {nome_fornecedor}")

        return {
            "success": True,
            "fornecedor": nome_fornecedor,
            "cnpj": cnpj,
            "email_destino": email_fornecedor,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Cotação enviada com sucesso para {nome_fornecedor}",
            "error": None,
        }

    except Exception as e:
        logger.error(f"Falha ao enviar cotação para {nome_fornecedor}: {str(e)}")

        return {
            "success": False,
            "fornecedor": nome_fornecedor,
            "cnpj": cnpj,
            "email_destino": email_fornecedor,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Erro ao enviar cotação: {str(e)}",
            "error": str(e),
        }


def enviar_cotacoes_em_lote_tool(orcamentos: list, config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Envia cotações para todos os fornecedores da lista de orçamentos.
    Após envio bem-sucedido, aciona automaticamente o AgenteFornecedorEmail
    para enviar confirmações de recebimento.
    
    Args:
        orcamentos: Lista de orçamentos confirmados
        config_path: Caminho para o arquivo de configuração SMTP
    
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
        resultado = enviar_cotacao_fornecedor_tool(orc, config_path)
        resultados.append(resultado)
        if resultado.get('success'):
            enviados += 1
            orcamentos_enviados.append(orc)
        else:
            falhas += 1

    status = "success" if falhas == 0 else ("partial" if enviados > 0 else "error")

    #se houve envios bem-sucedidos, aciona o AgenteFornecedorEmail para responder
    confirmacoes_fornecedor = None
    if orcamentos_enviados:
        logger.info(f"Acionando AgenteFornecedorEmail para {len(orcamentos_enviados)} orçamentos...")
        try:
            from iacompras.agents.agente_fornecedor_email import enviar_confirmacoes_em_lote_tool as enviar_confirmacoes
            confirmacoes_fornecedor = enviar_confirmacoes(orcamentos_enviados, config_path)
            logger.info(f"Confirmações do fornecedor: {confirmacoes_fornecedor.get('message')}")
        except Exception as e:
            logger.error(f"Erro ao acionar AgenteFornecedorEmail: {e}")
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


def executar_solicita_cotacao_tool(query: str = None, orcamentos: list = None, orcamento_ids: list = None, config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Executa o agente para enviar cotações.
    
    Args:
        query: String de comando (opcional)
        orcamentos: Lista de orçamentos para enviar cotações
        orcamento_ids: Lista de IDs de orçamentos para buscar no banco
        config_path: Caminho para o arquivo de configuração SMTP
    
    Returns:
        dict com resultado da operação
    """
    query_lower = (query or "").lower()

    #se recebeu IDs, busca os orçamentos do banco
    if orcamento_ids:
        orcamentos_db = db_list_orcamentos(orcamento_ids)
        if not orcamentos_db:
            return {
                "status": "error",
                "type": "quotation_send_result",
                "message": "Nenhum orçamento encontrado com os IDs fornecidos."
            }
        return enviar_cotacoes_em_lote_tool(orcamentos_db, config_path)

    #se recebeu lista de orçamentos diretamente
    if orcamentos and isinstance(orcamentos, list):
        return enviar_cotacoes_em_lote_tool(orcamentos, config_path)

    #comando via query string
    if "enviar_cotacoes:" in query_lower:
        try:
            parts = query.split("enviar_cotacoes:")
            orc_data = ast.literal_eval(parts[1].strip())

            if isinstance(orc_data, list) and all(isinstance(x, int) for x in orc_data):
                orcamentos_db = db_list_orcamentos(orc_data)
                return enviar_cotacoes_em_lote_tool(orcamentos_db, config_path)
            else:
                return enviar_cotacoes_em_lote_tool(orc_data, config_path)
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


class AgenteSolicitaCotacao(Agent):
    """
    Agente responsável por enviar solicitações de cotação para fornecedores.
    Recebe a lista de orçamentos gerados pelo Agente_Orcamento e envia um email
    para cada fornecedor com os detalhes do orçamento.
    """
    name: str = "Agente_Solicita_Cotacao_Email"
    description: str = "Envia solicitações de cotação para fornecedores via email."
    instruction: str = """
    Você é o Agente de Solicitação de Cotações do sistema IA Compras.
    
    Seu papel é enviar emails formais de solicitação de cotação para os fornecedores
    dos orçamentos que foram confirmados pelo usuário.
    
    Você NÃO deve escolher fornecedores nem produtos por conta própria.
    
    Use as tools disponíveis para:
    - Enviar cotação individual (enviar_cotacao_fornecedor_tool)
    - Enviar cotações em lote (enviar_cotacoes_em_lote_tool)
    """
    tools: list = [
        enviar_cotacao_fornecedor_tool,
        enviar_cotacoes_em_lote_tool,
        executar_solicita_cotacao_tool
    ]
    
    def executar(self, query=None, orcamentos=None, orcamento_ids=None, config_path: str = DEFAULT_CONFIG_PATH):
        """Método de compatibilidade que invoca a tool principal."""
        return executar_solicita_cotacao_tool(query, orcamentos, orcamento_ids, config_path)
