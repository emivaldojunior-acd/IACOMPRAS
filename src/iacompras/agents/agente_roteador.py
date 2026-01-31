"""
Agente Roteador ADK - IACOMPRAS
Utiliza Gemini 2.5-flash para entender a necessidade do usuário
e indicar o agente especializado mais adequado.
"""
import json
from google.adk.agents import Agent
from iacompras.tools.gemini_client import gemini_client


AGENTES_DISPONIVEIS = {
    "negociador": "Especialista em fornecedores. Seleciona parceiros, lista fornecedores recomendados e atualiza a inteligência/score de fornecedores.",
    "produtos": "Gestor de catálogo. Sugere produtos com base no histórico de compras e critérios de recorrência por fornecedor.",
    "planejador": "Estrategista de atribuição. Identifica os Top 3 melhores fornecedores para cada produto selecionado.",
    "orçamento": "Operacional de compras. Gerencia cotações, simula custos unitários e automatiza a comunicação por e-mail com fornecedores.",
    "planejamento": "Estrategista de demanda (Legado). Utilizado anteriormente para previsões via ML, agora integrado aos fluxos de planejamento."
}


def roteamento_local_tool(mensagem: str, current_stage: str = None) -> dict:
    """
    Realiza roteamento baseado em palavras-chave quando a API Gemini falha ou excede cota.
    
    Args:
        mensagem: Mensagem do usuário para análise
        current_stage: Estágio atual do fluxo (negociador, produtos, planejador, orçamento)
    
    Returns:
        dict com agente_sugerido, explicacao e pergunta_confirmacao
    """
    m = mensagem.lower()
    
    regras = {
        "negociador": ["fornecedor", "lista", "ranking", "melhor", "classificado", "quem vende", "cnpj", "inteligência", "score", "processo", "compras", "iniciar", "sim", "quero", "ok", "vamos"],
        "planejador": ["atribuição", "top 3", "escolher fornecedor", "definir", "vincular"],
        "orçamento": ["cotação", "e-mail", "proposta", "falar com", "preço unitário", "orcamento"],
        "ajuda": ["ajuda", "socorro", "o que você faz", "como funciona", "quem é você", "capacidade", "funcionalidade", "ajudar", "instrução", "fazer", "posso", "pode"]
    }
    
    # caso específico para ajuda/informação geral (Offline)
    if any(k in m for k in regras["ajuda"]):
        txt_ajuda = "Olá! Eu sou o assistente do sistema IACOMPRAS. Atualmente posso te ajudar com:\n\n"
        for ag, desc in AGENTES_DISPONIVEIS.items():
            if ag != "planejador":  
                txt_ajuda += f"- **{ag.capitalize()}**: {desc}\n"
        txt_ajuda += "\nVocê pode digitar algo como 'Preciso de fornecedores' ou 'Gerar orçamentos' para começar."
        return {
            "agente_sugerido": None,
            "explicacao": f"Identifiquei que você busca informações sobre o sistema. {txt_ajuda}",
            "pergunta_confirmacao": "Deseja iniciar o workflow completo de compras agora?"
        }

    agente_identificado = None
    for agente, keywords in regras.items():
        if any(k in m for k in keywords):
            agente_identificado = agente
            break
    
    if agente_identificado == "orçamento" and current_stage not in ["planejador", "orçamento"]:
        return {
            "agente_sugerido": "negociador",
            "explicacao": "Notei que você quer gerar um orçamento, mas para isso precisamos primeiro definir os fornecedores e os produtos. Vou te direcionar ao **Agente Negociador** para começarmos do passo 1.",
            "pergunta_confirmacao": "Deseja iniciar a classificação de fornecedores (Passo 1)?"
        }

    if agente_identificado:
        desc = AGENTES_DISPONIVEIS.get(agente_identificado, "")
        return {
            "agente_sugerido": agente_identificado,
            "explicacao": f"Identifiquei sua necessidade através do meu motor de busca local (API Offline). Com base nas palavras-chave, o **Agente {agente_identificado.capitalize()}** é o mais qualificado: {desc}",
            "pergunta_confirmacao": f"Deseja iniciar o processo do Agente {agente_identificado.capitalize()} agora?"
        }
    
    txt_resumo = "Não identifiquei uma instrução específica (como 'fornecedor' ou 'orçamento'), mas aqui está como posso te ajudar:\n\n"
    for ag, desc in AGENTES_DISPONIVEIS.items():
        if ag != "planejador":
            txt_resumo += f"- **{ag.capitalize()}**: {desc}\n"
    
    txt_resumo += "\n💡 **Dica**: Você pode iniciar o workflow completo clicando no botão 🚀 na barra lateral ou simplesmente descrevendo o que precisa."

    return {
        "agente_sugerido": None,
        "explicacao": txt_resumo,
        "pergunta_confirmacao": "Deseja que eu te ajude a iniciar o processo de compras?"
    }


def analisar_requisicao_tool(mensagem_usuario: str, current_stage: str = None) -> dict:
    """
    Analisa a requisição do usuário usando Gemini para identificar o agente especializado mais adequado.
    
    Args:
        mensagem_usuario: Mensagem do usuário para análise
        current_stage: Estágio atual do fluxo (negociador, produtos, planejador, orçamento)
    
    Returns:
        dict com agente_sugerido, explicacao e pergunta_confirmacao
    """
    prompt = f"""
    Você é o Roteador Inteligente de Elite do sistema IACOMPRAS.
    Sua missão é atuar como o cérebro central, analisando profundamente a intenção do usuário para direcioná-lo ao especialista correto, respeitando estritamente o fluxo de planejamento.

    ### Estágio Atual do Usuário:
    O usuário está no estágio: **{current_stage if current_stage else 'Início (Nenhum)'}**

    ### Ordem Obrigatória dos Agentes de Planejamento:
    1. **negociador**: Classificação e escolha de fornecedores.
    2. **produtos**: Sugestão e escolha de catálogo de itens.
    3. **planejador**: Atribuição final de Fornecedor x Produto (Top 3).
    4. **orçamento**: Agrupamento final e gravação dos orçamentos no banco.

    ### Regras Críticas de Fluxo:
    - Se o usuário fizer uma pergunta genérica como "O que você pode fazer?" ou "Como você pode me ajudar?", explique as capacidades do sistema de forma amigável e técnica, listando os agentes disponíveis.
    - Se o usuário confirmar o interesse em iniciar o processo ou disser algo como "Preciso de um processo de compras" após uma instrução sua, direcione-o imediatamente para o **negociador** (Step 1).
    - SE o usuário pedir algo relacionado a "orçamento" (Step 4) mas ainda não tiver concluído os passos anteriores (especialmente o 1), você DEVE redirecioná-lo para o **negociador** (Step 1).
    - Justifique o redirecionamento explicando que é necessário seguir a ordem lógica para garantir dados precisos.
    - Mantenha a interpretação de contexto: se o usuário mandar um novo texto, identifique em qual estágio ele está baseado nas informações acima.

    ### Agentes e Especialidades:
    {json.dumps(AGENTES_DISPONIVEIS, indent=2, ensure_ascii=False)}

    ### Formato de Resposta Obrigatório (JSON):
    Você DEVE responder APENAS com um objeto JSON puro, sem markdown, seguindo esta estrutura:
    {{
        "agente_sugerido": "nome_do_agente_em_minusculo",
        "explicacao": "Uma justificativa técnica, amigável e contextualmente ciente do estágio atual.",
        "pergunta_confirmacao": "Uma pergunta direta para iniciar o processo correto."
    }}

    Mensagem do Usuário: "{mensagem_usuario}"
    """
    
    resposta_texto = gemini_client.generate_text(prompt)
    
    if resposta_texto.startswith("Erro") or "⚠️" in resposta_texto:
        print(f"[!] Problema no Gemini detectado: {resposta_texto}. Ativando roteamento local...")
        return roteamento_local_tool(mensagem_usuario, current_stage)

    try:
        json_str = resposta_texto.strip()
        
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = json_str[start_idx:end_idx+1]

        return json.loads(json_str)
    except Exception as e:
        print(f"[!] Erro ao parsear resposta do Gemini: {e}")
        print(f"[!] Resposta Bruta: {resposta_texto}")
        return {
            "agente_sugerido": None,
            "explicacao": "Tive um problema ao processar meu pensamento interno. Pode tentar reformular sua solicitação?",
            "pergunta_confirmacao": None
        }


class AgenteRoteador(Agent):
    """
    Agente que utiliza Gemini 2.5-flash para entender a necessidade do usuário
    e indicar o agente especializado mais adequado.
    """
    name: str = "Agente_Roteador"
    description: str = "Roteador inteligente que direciona o usuário ao agente especializado correto."
    instruction: str = """
    Você é o Roteador Inteligente do sistema IACOMPRAS.
    Sua missão é analisar a intenção do usuário e direcioná-lo ao agente especializado correto.
    Use a tool analisar_requisicao_tool para processar mensagens do usuário.
    Se a API Gemini falhar, use roteamento_local_tool como fallback.
    """
    tools: list = [analisar_requisicao_tool, roteamento_local_tool]
    
    @property
    def agentes(self):
        """Retorna dicionário de agentes disponíveis para compatibilidade."""
        return AGENTES_DISPONIVEIS
    
    def analisar_requisicao(self, mensagem_usuario: str, current_stage: str = None) -> dict:
        """Método de compatibilidade que invoca a tool de análise."""
        return analisar_requisicao_tool(mensagem_usuario, current_stage)
