import sqlite3
import json
from iacompras.tools.db_tools import db_init, db_insert_run, DB_PATH
from iacompras.agents.agente_planejador import AgentePlanejadorCompras
from iacompras.agents.agente_negociador import AgenteNegociadorFornecedores
from iacompras.agents.agente_orcamento import AgenteGerenciadorOrcamento
from iacompras.agents.agente_financeiro import AgenteFinanceiro
from iacompras.agents.agente_auditor import AgenteAuditor
from iacompras.agents.agente_logistico import AgenteLogistico
from iacompras.agents.agente_roteador import AgenteRoteador
from iacompras.tools.gemini_client import gemini_client

class OrquestradorIACompras:
    """
    Orquestrador ADK (Simulado) que executa o pipeline dos 6 agentes.
    Utiliza Gemini 2.5-flash para consolidar a inteligência final.
    """
    def __init__(self, api_key=None):
        db_init() # Garante que o banco existe
        self.planejador = AgentePlanejadorCompras()
        self.negociador = AgenteNegociadorFornecedores()
        self.gerenciador_orcamento = AgenteGerenciadorOrcamento()
        self.financeiro = AgenteFinanceiro()
        self.auditor = AgenteAuditor()
        self.logistico = AgenteLogistico()
        self.roteador = AgenteRoteador()

        if api_key:
            gemini_client.configure(api_key)

    def get_agent_descriptions(self):
        """
        Retorna as orientações técnicas de cada agente.
        """
        return {
            "Agente_Planejador": "Previsão de demanda via Machine Learning e sugestão de volumes de compra baseada em tendências históricas.",
            "Agente_Negociador": "Busca e validação de fornecedores (BrasilAPI), análise de score e histórico de fornecimento.",
            "Agente_Orcamento": "Gestão de cotações, simulação de custos unitários e comunicação via e-mail com fornecedores.",
            "Agente_Financeiro": "Cálculo de impacto financeiro total, projeção de fluxo de caixa e viabilidade orçamentária.",
            "Agente_Auditor": "Detecção de anomalias em preços e quantidades, garantindo conformidade e segurança nas compras.",
            "Agente_Logistico": "Análise de prazos de entrega, janelas de recebimento e avaliação de risco de ruptura de estoque."
        }

    def get_agents_info(self):
        """
        Retorna uma lista estruturada de informações sobre os agentes e seus status.
        """
        descriptions = self.get_agent_descriptions()
        # Status simulado: 'Ativo' para todos no momento
        return [
            {"name": "Agente_Planejador", "description": descriptions["Agente_Planejador"], "status": "Ativo"},
            {"name": "Agente_Negociador", "description": descriptions["Agente_Negociador"], "status": "Ativo"},
            {"name": "Agente_Orcamento", "description": descriptions["Agente_Orcamento"], "status": "Ativo"},
            {"name": "Agente_Financeiro", "description": descriptions["Agente_Financeiro"], "status": "Ativo"},
            {"name": "Agente_Auditor", "description": descriptions["Agente_Auditor"], "status": "Ativo"},
            {"name": "Agente_Logistico", "description": descriptions["Agente_Logistico"], "status": "Ativo"}
        ]

    def get_gemini_agent_options(self):
        """
        Usa o Gemini para gerar uma apresentação amigável das opções de agentes disponíveis.
        """
        descricoes = self.get_agent_descriptions()
        prompt = f"""
        Você é o Orquestrador IACOMPRAS (Gemini 2.5-flash). 
        Apresente ao usuário os agentes disponíveis no sistema e o que cada um faz, de forma profissional e convidativa.
        
        Agentes:
        {json.dumps(descricoes, indent=2, ensure_ascii=False)}
        
        Formate como uma lista clara e técnica. Diga que estou pronto para orquestrar qualquer uma dessas especialidades.
        """
        return gemini_client.generate_text(prompt)

    def planejar_compras(self, query, custom_chain=None):
        """
        Executa o pipeline de compras. 
        Se custom_chain for fornecido (lista de nomes de agentes), executa apenas esses agentes.
        Caso contrário, executa o fluxo padrão completo.
        """
        print(f"[*] Iniciando orquestração para: {query}")
        
        # 0. Registrar Run no SQLite
        run_id = db_insert_run(query, status="processing")
        
        # Estado inicial (vazio ou carregado de dados prévios se necessário)
        recomendacoes = []
        fornecimentos = []
        cotacoes = []
        analise_financeira = {"total_geral": 0.0}
        auditoria = []
        resultado_final = []

        # Define a cadeia a ser executada
        standard_chain = [
            "Agente_Planejador", "Agente_Negociador", "Agente_Orcamento", 
            "Agente_Financeiro", "Agente_Auditor", "Agente_Logistico"
        ]
        chain_to_run = custom_chain if custom_chain else standard_chain

        # 1. Planejamento (ML)
        if "Agente_Planejador" in chain_to_run:
            print("[1] Executando Agente Planejador...")
            recomendacoes = self.planejador.executar(query=query)
        
        # 2. Negociação (BrasilAPI)
        if "Agente_Negociador" in chain_to_run:
            print("[2] Executando Agente Negociador...")
            fornecimentos = self.negociador.executar(recomendacoes, query=query)
        
        # 3. Orçamento (Cotações & Email)
        if "Agente_Orcamento" in chain_to_run:
            print("[3] Executando Agente de Orçamento...")
            cotacoes = self.gerenciador_orcamento.executar(run_id, fornecimentos, query=query)
        
        # 4. Financeiro
        if "Agente_Financeiro" in chain_to_run:
            print("[4] Executando Agente Financeiro...")
            analise_financeira = self.financeiro.executar(cotacoes, query=query)
        
        # 5. Auditoria
        if "Agente_Auditor" in chain_to_run:
            print("[5] Executando Agente Auditor...")
            auditoria = self.auditor.executar(analise_financeira if analise_financeira['total_geral'] > 0 else cotacoes, query=query)
        
        # 6. Logística
        if "Agente_Logistico" in chain_to_run:
            print("[6] Executando Agente Logístico...")
            resultado_final = self.logistico.executar(auditoria if auditoria else analise_financeira, query=query)

        # Se nenhum agente de saída (Audit/Log) rodou, tenta usar o que tivermos disponível na ordem reversa da cadeia
        if not resultado_final:
            if auditoria:
                resultado_final = auditoria
            elif isinstance(analise_financeira, dict) and analise_financeira.get('itens'):
                resultado_final = analise_financeira['itens']
            elif cotacoes:
                resultado_final = cotacoes
            elif fornecimentos:
                resultado_final = fornecimentos
            elif recomendacoes:
                resultado_final = recomendacoes

        # Salvar run_items no banco se houver resultados
        if resultado_final:
            self._save_run_items(run_id, resultado_final)
        
        # 7. Consolidação com Gemini 2.5-flash
        insight_gemini = "Sem insumos suficientes para sumário inteligente."
        if api_key := gemini_client.api_key:
            print("[7] Gemini 2.5-flash consolidando resposta final...")
            agent_info = self.get_agent_descriptions()
            resumo_prompt = f"""
            Você é o orquestrador sênior do sistema IACOMPRAS (Gemini 2.5-flash). 
            O processamento para a seguinte solicitação foi concluído: '{query}'
            Cadeia executada: {', '.join(chain_to_run)}
            
            Total estimado: R$ {analise_financeira.get('total_geral', 0):.2f}
            Itens processados: {len(resultado_final)}
            
            Dados: {json.dumps(resultado_final[:3], indent=2)}
            
            Gere um sumário executivo curto.
            """
            insight_gemini = gemini_client.generate_text(resumo_prompt)
        
        # Finalizar Run
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE runs SET status='completed' WHERE id=?", (run_id,))
        conn.commit()
        conn.close()
        
        return {
            "run_id": run_id,
            "resultado": resultado_final,
            "total_geral": analise_financeira.get('total_geral', 0),
            "insight_gemini": insight_gemini
        }

    def rotear_consulta(self, mensagem_usuario):
        """
        Utiliza o Agente Roteador para identificar o próximo passo.
        """
        return self.roteador.analisar_requisicao(mensagem_usuario)

    def _save_run_items(self, run_id, items):
        if not isinstance(items, list):
            print(f"[*] Orquestrador: Resultado não é uma lista, ignorando salvamento de itens individuais. Tipo: {type(items)}")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for item in items:
            # Verifica se o item é um dicionário e se contém chaves de produto
            # Isso evita erros quando o resultado é uma lista de strings ou lista de fornecedores sem dados de produto
            if not isinstance(item, dict) or 'codigo_produto' not in item:
                continue

            cursor.execute('''
            INSERT INTO run_items (run_id, codigo_produto, quantidade_prevista, quantidade_sugerida, 
                                 fornecedor_sugerido, custo_estimado, prazo_estimado, flags_auditoria)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run_id, 
                item.get('codigo_produto', 'N/A'), 
                item.get('quantidade_prevista', 0.0), 
                item.get('quantidade_sugerida', 0.0),
                item.get('fornecedor_sugerido', 'N/A'),
                item.get('custo_estimado', 0.0),
                item.get('prazo_dias', 0),
                item.get('flags_auditoria', 'N/A')
            ))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    orc = OrquestradorIACompras()
    res = orc.planejar_compras("Planejar compras para o próximo mês")
    print("\n[V] Orquestração concluída com Gemini 2.5-flash!")
    print(f"Run ID: {res['run_id']}")
    print(f"Insight: {res['insight_gemini']}")
