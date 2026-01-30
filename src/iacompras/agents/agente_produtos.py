import json
import ast
from google.adk.agents import Agent
from iacompras.tools.data_tools import load_nf_items, load_nf_headers
import pandas as pd

class AgenteProdutos(Agent):
    """
    Agente responsável por sugerir produtos com base nos fornecedores selecionados.
    Lógica de inclusão:
    1. Produtos comprados por >= 2 fornecedores selecionados (Auto-inclusão).
    2. Produtos comprados por apenas 1 fornecedor: Top N por recorrência.
    """
    name: str = "Agente_Produtos"
    description: str = "Especialista em catálogo: sugere produtos baseados em histórico e sobreposição de fornecedores."
    instruction: str = "Você deve filtrar e sugerir os melhores produtos para os fornecedores selecionados, priorizando itens comuns e recorrentes."

    def sugerir_produtos_fornecedores(self, fornecedores_selecionados: list) -> dict:
        """
        Gera sugestões de produtos para os fornecedores escolhidos.
        """
        if not fornecedores_selecionados:
            return {"fornecedores_selecionados": [], "produtos_sugeridos": []}

        df_items = load_nf_items()
        df_headers = load_nf_headers()

        df_headers['RAZAO_FORNECEDOR'] = df_headers['RAZAO_FORNECEDOR'].str.strip()
        fornecedores_selecionados = [f.strip() for f in fornecedores_selecionados]

        df = df_items.merge(df_headers[['CODIGO_COMPRA', 'RAZAO_FORNECEDOR']], on='CODIGO_COMPRA', how='left')
        
        df_filtered = df[df['RAZAO_FORNECEDOR'].isin(fornecedores_selecionados)]

        if df_filtered.empty:
            return {
                "type": "dual_grid_selection",
                "fornecedores_selecionados": [{"RAZAO_FORNECEDOR": f} for f in fornecedores_selecionados],
                "produtos_sugeridos": []
            }

        # 1. Identificando produtos por número de fornecedores
        # Pegamos o count de fornecedores DISTINTOS por produto dentro do conjunto selecionado
        prod_forn_count = df_filtered.groupby('CODIGO_PRODUTO')['RAZAO_FORNECEDOR'].nunique()
        auto_include_cods = prod_forn_count[prod_forn_count >= 2].index.tolist()
        single_forn_cods = prod_forn_count[prod_forn_count == 1].index.tolist()

        # 2. Lógica para produtos de apenas 1 fornecedor: Recorrência
        # Conta compras totais por fornecedor e produto
        recurrencia = df_filtered[df_filtered['CODIGO_PRODUTO'].isin(single_forn_cods)].groupby(['RAZAO_FORNECEDOR', 'CODIGO_PRODUTO']).size().reset_index(name='compras')
        
        # Pega Top 10 por fornecedor
        top_n = recurrencia.sort_values(['RAZAO_FORNECEDOR', 'compras'], ascending=[True, False]).groupby('RAZAO_FORNECEDOR').head(10)
        single_include_cods = top_n['CODIGO_PRODUTO'].tolist()

        # Unir todos os códigos selecionados
        selecionados_final_cods = list(set(auto_include_cods + single_include_cods))

        # 3. Montar a lista de retorno consolidada por PRODUTO (Grid Única)
        # Filtramos o DF apenas pelos códigos finais
        df_final = df_filtered[df_filtered['CODIGO_PRODUTO'].isin(selecionados_final_cods)]
        
        # Agrupamos por Produto para consolidar metadados
        # Pegamos a última ocorrência no geral para informações atualizadas
        df_grouped = df_final.groupby('CODIGO_PRODUTO').agg({
            'PRODUTO': 'last',
            'VALOR_UNITARIO': 'last',
            'GRUPO': 'last',
            'MARCA': 'last',
            'RAZAO_FORNECEDOR': lambda x: ", ".join(x.unique()) # Fornecedores que vendem este item
        }).reset_index()

        recomendacoes = []
        for _, row in df_grouped.iterrows():
            cod = row['CODIGO_PRODUTO']
            
            motivo = ""
            if cod in auto_include_cods:
                motivo = f"Disponível em {prod_forn_count[cod]} fornecedores"
            else:
                # Busca recorrência para este único fornecedor
                row_rec = recurrencia[recurrencia['CODIGO_PRODUTO'] == cod].iloc[0]
                motivo = f"Alta recorrência em {row_rec['RAZAO_FORNECEDOR']} ({row_rec['compras']} compras)"

            recomendacoes.append({
                "codigo_produto": cod,
                "descricao": row['PRODUTO'],
                "marca": row['MARCA'] if pd.notna(row['MARCA']) else "N/A",
                "grupo": row['GRUPO'] if pd.notna(row['GRUPO']) else "N/A",
                "ultimo_preco": float(row['VALOR_UNITARIO']),
                "fornecedores": row['RAZAO_FORNECEDOR'],
                "justificativa": motivo
            })
            
        return {
            "type": "product_suggestion_grid",
            "produtos_sugeridos": recomendacoes
        }

    def executar(self, query=None):
        query_lower = (query or "").lower()
        
        if "confirmar_selecao:" in query_lower:
            try:
                parts = query.split("confirmar_selecao:")
                lista_str = parts[1].strip()
                selecionados = ast.literal_eval(lista_str)
                print(f"[*] Agente Produtos: Gerando catálogo para {selecionados}")
                return self.sugerir_produtos_fornecedores(selecionados)
            except Exception as e:
                print(f"[!] Erro no Agente Produtos: {e}")
                return {"status": "error", "message": f"Erro ao processar produtos: {e}"}

        return {"status": "error", "message": "Comando não reconhecido pelo Agente Produtos."}
