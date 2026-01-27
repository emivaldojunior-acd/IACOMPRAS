import pandas as pd
import sys
import os
from pathlib import Path

# Adiciona o diretório src ao path para importar o modelo
sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from iacompras.ml.IACOMPRAS_GradientBoostingRegressor import load_dataset, train_and_evaluate
except ImportError:
    # Caso o import direto falhe por causa do nome do arquivo com pontos
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "model_ml", 
        str(Path(__file__).resolve().parents[1] / "ml" / "IACOMPRAS.GradientBoostingRegressor.py")
    )
    model_ml = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model_ml)
    load_dataset = model_ml.load_dataset
    train_and_evaluate = model_ml.train_and_evaluate

def predict_demand(codigo_produto, reference_month=None):
    """
    Chama o modelo já treinado para prever a demanda.
    Retorna a previsão mensal para 2026.
    """
    df = load_dataset()
    # No projeto atual, o script train_and_evaluate já calcula para todo o DF
    modelo = train_and_evaluate(df)
    
    # Filtra o produto solicitado
    product_row = df[df['CODIGO_PRODUTO'] == codigo_produto]
    
    if product_row.empty:
        return {"error": f"Produto {codigo_produto} não encontrado no dataset de treino."}
    
    return {
        "codigo_produto": codigo_produto,
        "previsao_mensal": float(product_row['PREVISAO_2026_MENSAL'].values[0]),
        "previsao_anual": float(product_row['PREVISAO_2026_ANUAL'].values[0])
    }
