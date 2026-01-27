import pandas as pd
import os
from pathlib import Path

DATA_PATH = Path("data/samples")

def load_nf_headers():
    """Lê IACOMPRAS_NOTASFISCAL_2023_24_25.xlsx"""
    path = DATA_PATH / "IACOMPRAS_NOTASFISCAL_2023_24_25.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_excel(path)

def load_nf_items():
    """Lê IACOMPRAS_NOTASFSICALSITENS_2023_24_25.xlsx"""
    path = DATA_PATH / "IACOMPRAS_NOTASFSICALSITENS_2023_24_25.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_excel(path)

def get_purchase_history(codigo_produto, start_date=None, end_date=None):
    """Retorna o histórico de compras de um produto específico."""
    df_items = load_nf_items()
    df_headers = load_nf_headers()
    
    # Merge usando CODIGO_COMPRA para pegar a data da compra
    df = df_items.merge(df_headers[['CODIGO_COMPRA', 'DATA_COMPRA']], on='CODIGO_COMPRA', how='left')
    df['DATA_COMPRA'] = pd.to_datetime(df['DATA_COMPRA'])
    
    product_data = df[df['CODIGO_PRODUTO'] == codigo_produto]
    
    if start_date:
        product_data = product_data[product_data['DATA_COMPRA'] >= pd.to_datetime(start_date)]
    if end_date:
        product_data = product_data[product_data['DATA_COMPRA'] <= pd.to_datetime(end_date)]
        
    return product_data.to_dict('records')

def get_supplier_history(cnpj_or_razao):
    """Retorna o histórico de compras por fornecedor."""
    df_headers = load_nf_headers()
    # Como não temos CNPJ no Excel de cabeçalho, usamos apenas RAZAO_FORNECEDOR
    # ou tentamos encontrar por string
    supplier_data = df_headers[df_headers['RAZAO_FORNECEDOR'].str.contains(cnpj_or_razao, case=False, na=False)]
        
    return supplier_data.to_dict('records')
