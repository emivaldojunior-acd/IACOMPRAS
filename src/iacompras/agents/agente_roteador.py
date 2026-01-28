import json
from iacompras.tools.gemini_client import gemini_client

class AgenteRoteador:
    """
    Agente que utiliza Gemini 2.5-flash para entender a necessidade do usuário
    e indicar o agente especializado mais adequado.
    """
    def __init__(self):
        self.agentes = {
            "auditor": "Especialista em conformidade e segurança. Detecta anomalias em preços, quantidades e irregularidades nas transações de compra.",
            "financeiro": "Analista de impacto orçamentário. Calcula o custo total, projeções de fluxo de caixa e viabilidade financeira da operação.",
            "logístico": "Gestor de suprimentos e prazos. Avalia janelas de recebimento, prazos de entrega e riscos de ruptura de estoque.",
            "negociador": "Especialista em fornecedores. Valida dados cadastrais (BrasilAPI), seleciona parceiros, lista fornecedores recomendados e atualiza a inteligência/score de fornecedores.",
            "orçamento": "Operacional de compras. Gerencia cotações, simula custos unitários e automatiza a comunicação por e-mail com fornecedores.",
            "planejador": "Estrategista de demanda. Utiliza Machine Learning para prever necessidades futuras e sugerir volumes ideais de compra baseados no histórico."
        }

    def _roteamento_local(self, mensagem):
        """Implementação baseada em palavras-chave para quando a API falhar ou exceder cota."""
        m = mensagem.lower()
        
        regras = {
            "negociador": ["fornecedor", "lista", "ranking", "melhor", "classificado", "quem vende", "cnpj", "inteligência", "score"],
            "planejador": ["previsão", "futuro", "demanda", "ml", "quanto comprar", "histórico", "planeja"],
            "auditor": ["preço justo", "anomalia", "irregular", "suspeito", "auditoria", "fraude", "verificação", "audita"],
            "orçamento": ["cotação", "e-mail", "proposta", "falar com", "preço unitário", "orcamento"],
            "financeiro": ["caixa", "gasto", "total", "viabilidade", "pagamento", "custo", "financeiro"],
            "logístico": ["frete", "atraso", "entrega", "prazo", "ruptura", "estoque", "logística"]
        }
        
        for agente, keywords in regras.items():
            if any(k in m for k in keywords):
                desc = self.agentes[agente]
                return {
                    "agente_sugerido": agente,
                    "explicacao": f"Identifiquei sua necessidade através do meu motor de busca local (API Offline). Com base nas palavras-chave, o **Agente {agente.capitalize()}** é o mais qualificado: {desc}",
                    "pergunta_confirmacao": f"Deseja iniciar o processo do Agente {agente.capitalize()} agora?"
                }
        
        return {
            "agente_sugerido": None,
            "explicacao": "Minha inteligência principal (Gemini) está offline e não consegui identificar palavras-chave claras na sua mensagem para um direcionamento manual. Pode ser mais específico?",
            "pergunta_confirmacao": None
        }

    def analisar_requisicao(self, mensagem_usuario):
        prompt = f"""
        Você é o Roteador Inteligente de Elite do sistema IACOMPRAS.
        Sua missão é atuar como o cérebro central, analisando profundamente a intenção do usuário para direcioná-lo ao especialista correto.

        ### Agentes e Especialidades:
        {json.dumps(self.agentes, indent=2, ensure_ascii=False)}

        ### Regras de Ouro para Roteamento:
        1. **Agente Negociador**: Deve ser escolhido SEMPRE que o usuário mencionar "fornecedores", "lista", "ranking", "melhores", "classificados", "quem vende", "CNPJ", "BrasilAPI" ou "treinar modelo".
        2. **Agente Planejador**: Escolhido para "previsão", "futuro", "quanto comprar", "demandas", "histórico de vendas" ou "ML".
        3. **Agente Auditor**: Escolhido para "preço justo", "conforme", "irregular", "anomalia", "suspeito", "fraude" ou "verificação".
        4. **Agente Orçamento**: Escolhido para "cotação", "e-mail", "preço unitário", "falar com fornecedor" ou "gerar proposta".
        5. **Agente Financeiro**: Escolhido para "caixa", "gastos", "total", "viabilidade", "pagamento" ou "quanto vamos gastar".
        6. **Agente Logístico**: Escolhido para "atraso", "frete", "entrega", "quando chega", "estoque" ou "ruptura".

        ### Formato de Resposta Obrigatório (JSON):
        Você DEVE responder APENAS com um objeto JSON puro, sem markdown, seguindo esta estrutura:
        {{
            "agente_sugerido": "nome_do_agente_em_minusculo",
            "explicacao": "Uma justificativa técnica e amigável.",
            "pergunta_confirmacao": "Uma pergunta direta para iniciar o processo."
        }}

        ### Exemplo de Sucesso:
        Usuário: "Quero ver a lista de quem entrega mais rápido."
        Resposta: {{
            "agente_sugerido": "negociador",
            "explicacao": "Identifiquei que você deseja analisar o ranking de fornecedores. O Agente Negociador possui a base de inteligência com os prazos de entrega e scores de cada parceiro.",
            "pergunta_confirmacao": "Deseja que eu apresente a lista dos fornecedores classificados agora?"
        }}

        Mensagem do Usuário: "{mensagem_usuario}"
        """
        
        resposta_texto = gemini_client.generate_text(prompt)
        
        # Se a resposta for uma mensagem de erro vinda do cliente (Ex: Quota Excedida)
        if resposta_texto.startswith("Erro"):
            print(f"[!] Erro Gemini detectado: {resposta_texto}. Ativando roteamento local...")
            return self._roteamento_local(mensagem_usuario)

        try:
            # Limpeza ultra-robusta de JSON
            json_str = resposta_texto.strip()
            
            # Se a resposta vier com markdown ```json ... ```
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            # Busca o primeiro '{' e o último '}' para isolar o objeto JSON
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
