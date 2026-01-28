import sqlite3
import json
from iacompras.tools.db_tools import db_init, db_insert_run, DB_PATH
from iacompras.agents.agente_planejador import AgentePlanejadorCompras
from iacompras.agents.agente_negociador import AgenteNegociadorFornecedores
from iacompras.agents.agente_orcamento import AgenteGerenciadorOrcamento
from iacompras.agents.agente_financeiro import AgenteFinanceiro
from iacompras.agents.agente_auditor import AgenteAuditor
from iacompras.agents.agente_logistico import AgenteLogistico
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

    def planejar_compras(self, query):
        print(f"[*] Iniciando orquestração para: {query}")
        
        # 0. Registrar Run no SQLite
        run_id = db_insert_run(query, status="processing")
        
        # 1. Planejamento (ML)
        print("[1] Executando Agente Planejador...")
        recomendacoes = self.planejador.executar()
        
        # 2. Negociação (BrasilAPI)
        print("[2] Executando Agente Negociador...")
        fornecimentos = self.negociador.executar(recomendacoes)
        
        # 3. Orçamento (Cotações & Email)
        print("[3] Executando Agente de Orçamento...")
        cotacoes = self.gerenciador_orcamento.executar(run_id, fornecimentos)
        
        # 4. Financeiro
        print("[4] Executando Agente Financeiro...")
        analise_financeira = self.financeiro.executar(cotacoes)
        
        # 5. Auditoria
        print("[5] Executando Agente Auditor...")
        auditoria = self.auditor.executar(analise_financeira)
        
        # 6. Logística
        print("[6] Executando Agente Logístico...")
        resultado_final = self.logistico.executar(auditoria)
        
        # Salvar run_items no banco
        self._save_run_items(run_id, resultado_final)
        
        # 7. Consolidação com Gemini 2.5-flash
        print("[7] Gemini 2.5-flash consolidando resposta final...")
        agent_info = self.get_agent_descriptions()
        resumo_prompt = f"""
        Você é o orquestrador sênior do sistema IACOMPRAS (Gemini 2.5-flash). 
        O planejamento de compras para a seguinte solicitação foi concluído: '{query}'
        
        Contexto dos Agentes que participaram:
        {json.dumps(agent_info, indent=2, ensure_ascii=False)}

        Total estimado das compras: R$ {analise_financeira['total_geral']:.2f}
        Número de produtos analisados: {len(resultado_final)}
        
        Dados de amostra dos agentes:
        {json.dumps(resultado_final[:3], indent=2)}
        
        Com base nestes dados e no papel de cada agente, gere um sumário executivo profissional destacando:
        1. Resumo financeiro.
        2. Principais fornecedores envolvidos.
        3. Alertas de auditoria ou riscos logísticos relevantes.
        Use um tom técnico e direto.
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
            "total_geral": analise_financeira['total_geral'],
            "insight_gemini": insight_gemini
        }

    def _save_run_items(self, run_id, items):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for item in items:
            cursor.execute('''
            INSERT INTO run_items (run_id, codigo_produto, quantidade_prevista, quantidade_sugerida, 
                                 fornecedor_sugerido, custo_estimado, prazo_estimado, flags_auditoria)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run_id, 
                item['codigo_produto'], 
                item['quantidade_prevista'], 
                item['quantidade_sugerida'],
                item['fornecedor_sugerido'],
                item['custo_estimado'],
                item.get('prazo_dias', 0),
                item['flags_auditoria']
            ))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    orc = OrquestradorIACompras()
    res = orc.planejar_compras("Planejar compras para o próximo mês")
    print("\n[V] Orquestração concluída com Gemini 2.5-flash!")
    print(f"Run ID: {res['run_id']}")
    print(f"Insight: {res['insight_gemini']}")
