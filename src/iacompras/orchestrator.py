import sqlite3
import json
from iacompras.tools.db_tools import db_init, db_insert_run, DB_PATH
from iacompras.agents.agente_01 import AgentePlanejadorCompras
from iacompras.agents.agente_02 import AgenteNegociadorFornecedores
from iacompras.agents.agente_03 import AgenteGerenciadorOrcamento
from iacompras.agents.agente_04 import AgenteFinanceiro
from iacompras.agents.agente_05 import AgenteAuditor
from iacompras.agents.agente_06 import AgenteLogistico
from iacompras.tools.gemini_client import gemini_client

class OrquestradorIACompras:
    """
    Orquestrador ADK (Simulado) que executa o pipeline dos 6 agentes.
    Utiliza Gemini 2.5-flash para consolidar a inteligência final.
    """
    def __init__(self, api_key=None):
        db_init() # Garante que o banco existe
        self.agente_01 = AgentePlanejadorCompras()
        self.agente_02 = AgenteNegociadorFornecedores()
        self.agente_03 = AgenteGerenciadorOrcamento()
        self.agente_04 = AgenteFinanceiro()
        self.agente_05 = AgenteAuditor()
        self.agente_06 = AgenteLogistico()

        if api_key:
            gemini_client.configure(api_key)

    def planejar_compras(self, query):
        print(f"[*] Iniciando orquestração para: {query}")
        
        # 0. Registrar Run no SQLite
        run_id = db_insert_run(query, status="processing")
        
        # 1. Planejamento (ML)
        print("[1] Executando Agente Planejador...")
        recomendacoes = self.agente_01.executar()
        
        # 2. Negociação (BrasilAPI)
        print("[2] Executando Agente Negociador...")
        fornecimentos = self.agente_02.executar(recomendacoes)
        
        # 3. Orçamento (Cotações & Email)
        print("[3] Executando Agente de Orçamento...")
        cotacoes = self.agente_03.executar(run_id, fornecimentos)
        
        # 4. Financeiro
        print("[4] Executando Agente Financeiro...")
        analise_financeira = self.agente_04.executar(cotacoes)
        
        # 5. Auditoria
        print("[5] Executando Agente Auditor...")
        auditoria = self.agente_05.executar(analise_financeira)
        
        # 6. Logística
        print("[6] Executando Agente Logístico...")
        resultado_final = self.agente_06.executar(auditoria)
        
        # Salvar run_items no banco
        self._save_run_items(run_id, resultado_final)
        
        # 7. Consolidação com Gemini 2.5-flash
        print("[7] Gemini 2.5-flash consolidando resposta final...")
        resumo_prompt = f"""
        Você é o orquestrador sênior do sistema IACOMPRAS. 
        O planejamento de compras para a seguinte solicitação foi concluído: '{query}'
        
        Total estimado das compras: R$ {analise_financeira['total_geral']:.2f}
        Número de produtos analisados: {len(resultado_final)}
        
        Dados de amostra dos agentes:
        {json.dumps(resultado_final[:3], indent=2)}
        
        Com base nestes dados, gere um sumário executivo profissional destacando:
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
