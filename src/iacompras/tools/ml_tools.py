import pandas as pd
import sys
import os
from pathlib import Path

# Adiciona o diretório src ao path para importar o modelo
sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from iacompras.ml.treinar_classificador_fornecedor import (
        treinar_modelo_avaliacao_fornecedores, 
        engenharia_features_fornecedores,
        rating_to_label,
        MODEL_DIR,
        DATA_DIR
    )
except ImportError:
    # Caso o import direto falhe por causa do nome do arquivo com pontos
    import importlib.util
    ml_dir = Path(__file__).resolve().parents[1] / "ml"
    
    # Load treinar_classificador_fornecedor
    spec_supp = importlib.util.spec_from_file_location(
        "supp_ml",
        str(ml_dir / "treinar_classificador_fornecedor.py")
    )
    supp_ml = importlib.util.module_from_spec(spec_supp)
    spec_supp.loader.exec_module(supp_ml)
    treinar_modelo_avaliacao_fornecedores = supp_ml.treinar_modelo_avaliacao_fornecedores
    engenharia_features_fornecedores = supp_ml.engenharia_features_fornecedores
    rating_to_label = supp_ml.rating_to_label
    MODEL_DIR = supp_ml.MODEL_DIR
    DATA_DIR = supp_ml.DATA_DIR

from iacompras.tools.db_tools import db_get_latest_classified_suppliers

def train_supplier_classifier():
    """
    Executa o script de treinamento do classificador de fornecedores.
    """
    treinar_modelo_avaliacao_fornecedores()
    return {"status": "success", "message": "Modelo de classificação de fornecedores treinado com sucesso."}

def get_classified_suppliers():
    """
    Lê os fornecedores classificados do banco de dados SQLite e retorna como lista de dicionários.
    """
    suppliers = db_get_latest_classified_suppliers()
    
    if not suppliers:
        return {"error": "Nenhum fornecedor classificado encontrado no banco de dados. É necessário treinar o modelo primeiro."}
    
    return suppliers

def classify_suppliers_2025():
    """
    Usa o modelo treinado para classificar os fornecedores com base nos dados de 2025.
    Salva o resultado em fornecedores_classificados_2025.csv.
    """
    import joblib
    import numpy as np

    nf_path = DATA_DIR / "IACOMPRAS_NOTASFISCAIS_2025.xlsx"
    items_path = DATA_DIR / "IACOMPRAS_NOTAFISCALITENS_2025.xlsx"

    if not nf_path.exists() or not items_path.exists():
        return {"error": "Arquivos de dados de 2025 não encontrados em data/samples/"}

    df_nf = pd.read_excel(nf_path)
    df_items = pd.read_excel(items_path)

    print("[*] Gerando features para dados de 2025...")
    supplier_features = engenharia_features_fornecedores(df_nf, df_items)

    model_path = MODEL_DIR / "modelo_classificacao_fornecedores.pkl"
    scaler_path = MODEL_DIR / "escalonador_fornecedores.pkl"

    if not model_path.exists() or not scaler_path.exists():
        return {"error": "Modelo ou escalonador não encontrados. Treine o classificador primeiro."}

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    X = supplier_features[[
        'avg_lead_time', 'std_lead_time', 'recurrence',
        'total_spent', 'discount_rate', 'avg_item_price'
    ]]

    X_scaled = scaler.transform(X)
    preds = model.predict(X_scaled)
    preds_rounded = np.clip(np.round(preds), 1, 5).astype(int)

    supplier_features['rating'] = preds_rounded
    supplier_features['classificacao'] = supplier_features['rating'].apply(rating_to_label)

    output_path = MODEL_DIR / "fornecedores_classificados_2025.csv"
    supplier_features.to_csv(output_path)
    
    print(f"[*] Classificação 2025 salva em: {output_path}")
    return {"status": "success", "message": f"Classificação 2025 gerada em {output_path}"}
