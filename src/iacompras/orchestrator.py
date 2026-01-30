import sqlite3
import json
from iacompras.tools.db_tools import db_init, db_insert_run, DB_PATH
from iacompras.agents.agente_planejador import AgentePlanejadorCompras
from iacompras.agents.agente_negociador import AgenteNegociadorFornecedores
from iacompras.agents.agente_orcamento import AgenteGerenciadorOrcamento
from iacompras.agents.agente_roteador import AgenteRoteador
from iacompras.agents.agente_produtos import AgenteProdutos
from iacompras.tools.gemini_client import gemini_client

class OrquestradorIACompras:
    """
    Orquestrador ADK que executa o pipeline dos 4 agentes principais.
    Utiliza Gemini 2.5-flash para consolidar a inteligência final.
    """
    def __init__(self, api_key=None):
        db_init() # Garante que o banco existe
        self.planejador = AgentePlanejadorCompras()
        self.negociador = AgenteNegociadorFornecedores()
        self.gerenciador_orcamento = AgenteGerenciadorOrcamento()
        self.roteador = AgenteRoteador()
        self.agente_produtos = AgenteProdutos()

        if api_key:
            gemini_client.configure(api_key)

    def get_agent_descriptions(self):
        """
        Retorna as orientações técnicas de cada agente.
        """
        return {
            "Agente_Negociador": "Especialista em inteligência de fornecedores. Analisa scores de entrega e mantém o ranking de parceiros confiáveis.",
            "Agente_Produtos": "Gestor de catálogo inteligente. Sugere itens de compra com base no histórico de fornecimento e critérios de recorrência por fornecedor.",
            "Agente_Planejamento": "Estrategista de atribuição. Identifica os Top 3 melhores fornecedores para cada produto, cruzando preço médio e rating global.",
            "Agente_Orcamento": "Operacional de compras. Automatiza a geração de orçamentos, simula custos unitários e gerencia a comunicação via e-mail com parceiros."
        }

    def get_agents_info(self):
        """
        Retorna uma lista estruturada de informações sobre os agentes e seus status.
        """
        descriptions = self.get_agent_descriptions()
        return [
            {"name": "Agente_Negociador", "description": descriptions["Agente_Negociador"], "status": "Ativo"},
            {"name": "Agente_Produtos", "description": descriptions["Agente_Produtos"], "status": "Ativo"},
            {"name": "Agente_Planejamento", "description": descriptions["Agente_Planejamento"], "status": "Ativo"},
            {"name": "Agente_Orcamento", "description": descriptions["Agente_Orcamento"], "status": "Ativo"}
        ]

    def get_gemini_agent_options(self):
        """
        Usa o Gemini para gerar uma apresentação amigável das opções de agentes disponíveis.
        """
        descricoes = self.get_agent_descriptions()
        prompt = f"""
        Você é o Orquestrador Sênior do IACOMPRAS (Gemini 2.5-flash). 
        Um usuário perguntou o que você pode fazer ou como você pode ajudá-lo.
        
        Sua missão: Apresentar o sistema de forma amigável, técnica e convidativa.
        Liste as especialidades dos nossos agentes abaixo e explique que você pode orquestrar o workflow completo de compras (do Negociador ao Orçamento).
        
        Agentes:
        {json.dumps(descricoes, indent=2, ensure_ascii=False)}
        
        Finalize encorajando o usuário a iniciar o workflow completo através do botão na barra lateral ou pedindo algo como "Preciso de novos fornecedores".
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
        resultado_final = []

        # Define a cadeia a ser executada
        standard_chain = [
            "Agente_Planejador", "Agente_Negociador", "Agente_Orcamento", "Agente_Produtos"
        ]
        chain_to_run = custom_chain if custom_chain else standard_chain

        # 1. Planejamento (ML)
        if "Agente_Planejador" in chain_to_run:
            print("[1] Executando Agente Planejador...")
            recomendacoes = self.planejador.executar(query=query)
        
        # 1.1 Produtos (Sugestão via Histórico)
        if "Agente_Produtos" in chain_to_run:
            print("[1.1] Executando Agente de Produtos...")
            recomendacoes = self.agente_produtos.executar(query=query)
        
        # 2. Negociação (BrasilAPI)
        if "Agente_Negociador" in chain_to_run:
            print("[2] Executando Agente Negociador...")
            fornecimentos = self.negociador.executar(recomendacoes, query=query)
        
        # 3. Orçamento (Cotações & Email)
        if "Agente_Orcamento" in chain_to_run:
            print("[3] Executando Agente de Orçamento...")
            cotacoes = self.gerenciador_orcamento.executar(run_id, fornecimentos, query=query)
        
        # Determina o resultado final para salvar e consolidar
        if cotacoes:
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
            
            Itens processados: {len(resultado_final) if isinstance(resultado_final, list) else 1}
            
            Dados: {json.dumps(resultado_final[:3] if isinstance(resultado_final, list) else resultado_final, indent=2)}
            
            Gere um sumário executivo curto.
            """
            try:
                insight_gemini = gemini_client.generate_text(resumo_prompt)
                # Se o gemini_client retornar uma string de erro (que agora são amigáveis), o orchestrator apenas aceita.
            except Exception as e:
                print(f"[!] Erro fatal no orquestrador ao chamar Gemini: {e}")
                insight_gemini = "⚠️ Erro inesperado ao gerar insight."
        
        # Finalizar Run
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE runs SET status='completed' WHERE id=?", (run_id,))
        conn.commit()
        conn.close()
        
        return {
            "run_id": run_id,
            "resultado": resultado_final,
            "total_geral": 0.0, # Financeiro removido
            "insight_gemini": insight_gemini
        }

    def rotear_consulta(self, mensagem_usuario, current_stage=None):
        """
        Utiliza o Agente Roteador para identificar o próximo passo.
        """
        return self.roteador.analisar_requisicao(mensagem_usuario, current_stage=current_stage)

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
