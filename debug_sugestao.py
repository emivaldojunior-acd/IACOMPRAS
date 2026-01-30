
import pandas as pd
from pathlib import Path
import ast

DATA_PATH = Path("data/samples")

def load_nf_headers():
    path = DATA_PATH / "IACOMPRAS_NOTASFISCAL_2023_24_25.xlsx"
    return pd.read_excel(path)

def load_nf_items():
    path = DATA_PATH / "IACOMPRAS_NOTASFSICALSITENS_2023_24_25.xlsx"
    return pd.read_excel(path)

def test_sugestao_robusta():
    df_items = load_nf_items()
    df_headers = load_nf_headers()

    # Simula sanitização
    df_headers['RAZAO_FORNECEDOR'] = df_headers['RAZAO_FORNECEDOR'].str.strip()
    
    # Seleciona dois fornecedores que sabemos que existem
    sample_suppliers = df_headers['RAZAO_FORNECEDOR'].unique()[:2].tolist()
    # Adiciona um com espaços extras para testar sanitização
    sample_suppliers_with_spaces = [sample_suppliers[0] + " ", "  " + sample_suppliers[1]]
    
    print("\nTesting with suppliers (with spaces):", sample_suppliers_with_spaces)

    # Limpa os inputs como o agente faz
    selecionados_limpos = [s.strip() for s in sample_suppliers_with_spaces]
    
    # Merge logic
    df = df_items.merge(df_headers[['CODIGO_COMPRA', 'RAZAO_FORNECEDOR']], on='CODIGO_COMPRA', how='left')
    df_filtered = df[df['RAZAO_FORNECEDOR'].isin(selecionados_limpos)]
    
    print("\nFiltered size:", len(df_filtered))

    if len(df_filtered) == 0:
        print("!!! Filtered dataframe is empty!")
        return

    # Lógica de sugestão
    prod_forn_count = df_filtered.groupby('CODIGO_PRODUTO')['RAZAO_FORNECEDOR'].nunique()
    total_forn_selecionados = len(selecionados_limpos)
    produtos_em_todos = prod_forn_count[prod_forn_count == total_forn_selecionados].index.tolist()

    prod_frequencia = df_filtered.groupby(['RAZAO_FORNECEDOR', 'CODIGO_PRODUTO']).size().reset_index(name='count')
    produtos_frequentes = prod_frequencia[prod_frequencia['count'] > 1]['CODIGO_PRODUTO'].unique().tolist()

    sugestoes_codigos = list(set(produtos_em_todos + produtos_frequentes))
    
    print(f"Produtos em todos: {len(produtos_em_todos)}")
    print(f"Produtos frequentes: {len(produtos_frequentes)}")

    if not sugestoes_codigos:
        print("[*] Fallback acionado...")
        sugestoes_codigos = df_filtered['CODIGO_PRODUTO'].value_counts().head(20).index.tolist()
    
    print(f"Total de sugestões finais: {len(sugestoes_codigos)}")
    
    if len(sugestoes_codigos) > 0:
        # Testa se a descrição real está vindo
        cod = sugestoes_codigos[0]
        prod_info = df_filtered[df_filtered['CODIGO_PRODUTO'] == cod].iloc[-1]
        print(f"Exemplo de sugestão: {cod} - {prod_info.get('PRODUTO')}")
        print("SUCCESS")
    else:
        print("FAILED: No products suggested even with fallback")

if __name__ == "__main__":
    test_sugestao_robusta()
