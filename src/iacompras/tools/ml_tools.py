import pandas as pd
import sys
import os
from pathlib import Path

# Adiciona o diretório src ao path para importar o modelo
sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from iacompras.ml.IACOMPRAS_GradientBoostingRegressor import load_dataset, train_and_evaluate
    from iacompras.ml.treinar_classificador_fornecedor import treinar_modelo_avaliacao_fornecedores
except ImportError:
    # Caso o import direto falhe por causa do nome do arquivo com pontos
    import importlib.util
    ml_dir = Path(__file__).resolve().parents[1] / "ml"
    
    # Load GradientBoostingRegressor
    spec = importlib.util.spec_from_file_location(
        "model_ml", 
        str(ml_dir / "IACOMPRAS.GradientBoostingRegressor.py")
    )
    model_ml = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model_ml)
    load_dataset = model_ml.load_dataset
    train_and_evaluate = model_ml.train_and_evaluate

    # Load treinar_classificador_fornecedor
    spec_supp = importlib.util.spec_from_file_location(
        "supp_ml",
        str(ml_dir / "treinar_classificador_fornecedor.py")
    )
    supp_ml = importlib.util.module_from_spec(spec_supp)
    spec_supp.loader.exec_module(supp_ml)
    treinar_modelo_avaliacao_fornecedores = supp_ml.treinar_modelo_avaliacao_fornecedores

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

def train_supplier_classifier():
    """
    Executa o script de treinamento do classificador de fornecedores.
    """
    treinar_modelo_avaliacao_fornecedores()
    return {"status": "success", "message": "Modelo de classificação de fornecedores treinado com sucesso."}

def get_classified_suppliers():
    """
    Lê o arquivo de fornecedores classificados e retorna como lista de dicionários.
    """
    # parents[2] points to src/iacompras/tools -> src/iacompras -> src
    # parents[3] points to d:/IACOMPRAS
    BASE_DIR = Path(__file__).resolve().parents[3]
    CSV_PATH = BASE_DIR / "models" / "fornecedores_classificados.csv"
    
    if not CSV_PATH.exists():
        return {"error": "Arquivo de fornecedores classificados não encontrado. É necessário treinar o modelo primeiro."}
    
    df = pd.read_csv(CSV_PATH)
    # Converte o DataFrame para uma lista de dicionários para ser consumida pelo agente/UI
    return df.to_dict(orient='records')
