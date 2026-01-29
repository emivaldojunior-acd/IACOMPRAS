from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import os

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "samples"
MODEL_DIR = BASE_DIR / "models"

def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-6)


def score_to_rating(score_series):
    return pd.qcut(score_series, q=5, labels=[1, 2, 3, 4, 5]).astype(int)


def rating_to_label(rating: int) -> str:
    if rating <= 2:
        return "Ruim / Não recomendado"
    elif rating == 3:
        return "Médio"
    elif rating == 4:
        return "Bom"
    else:
        return "Ótimo / Recomendado"


def engenharia_features_fornecedores(df_nf, df_items):
    """
    Realiza a engenharia de features para os fornecedores com base nas notas fiscais e itens.
    """
    supplier_features = df_nf.groupby('RAZAO_FORNECEDOR').agg({
        'PRAZO_ENTREGA_DIAS': ['mean', 'std'],
        'CODIGO_COMPRA': 'count',
        'TOTAL_NOTAFISCAL': 'sum',
        'TOTAL_PRODUTOS': 'sum',
        'TOTAL_DESCONTO': 'sum'
    })

    supplier_features.columns = [
        'avg_lead_time', 'std_lead_time', 'recurrence',
        'total_spent', 'total_products_value', 'total_discount'
    ]

    supplier_features = supplier_features.fillna(0)

    supplier_features['discount_rate'] = (
        supplier_features['total_discount'] /
        (supplier_features['total_products_value'] + 1e-6)
    )

    avg_price = (
        df_items
        .merge(df_nf[['CODIGO_COMPRA', 'RAZAO_FORNECEDOR']], on='CODIGO_COMPRA')
        .groupby('RAZAO_FORNECEDOR')['VALOR_UNITARIO']
        .mean()
        .rename('avg_item_price')
    )

    supplier_features = supplier_features.join(avg_price).fillna(0)
    return supplier_features


def treinar_modelo_avaliacao_fornecedores():
    base_path = DATA_DIR
    nf_path = base_path / "IACOMPRAS_NOTASFISCAIS_2023_2024.xlsx"
    items_path = base_path / "IACOMPRAS_NOTAFISCALITENS_2023_2024.xlsx"

    print(f"Carregando dados de treino de: {base_path}")
    if not nf_path.exists() or not items_path.exists():
        print("Erro: Arquivos de dados de treino não encontrados em data/samples/")
        return

    df_nf = pd.read_excel(nf_path)
    df_items = pd.read_excel(items_path)

    print("Criando features por fornecedor...")
    supplier_features = engenharia_features_fornecedores(df_nf, df_items)


    print("Calculando score contínuo...")

    score = (
        0.4 * (1 - normalize(supplier_features['avg_lead_time'])) +
        0.3 * normalize(supplier_features['recurrence']) +
        0.3 * normalize(supplier_features['discount_rate'])
    )

    supplier_features['score'] = score
    supplier_features['rating'] = score_to_rating(score)
    supplier_features['classificacao'] = supplier_features['rating'].apply(rating_to_label)

    print("Distribuição das classificações:\n")
    print(supplier_features['classificacao'].value_counts())


    X = supplier_features[[
        'avg_lead_time', 'std_lead_time', 'recurrence',
        'total_spent', 'discount_rate', 'avg_item_price'
    ]]

    y = supplier_features['rating']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)


    print("Treinando modelo...")

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=5,
        random_state=42
    )

    model.fit(X_train_scaled, y_train)

    preds = model.predict(X_test_scaled)
    preds_rounded = np.clip(np.round(preds), 1, 5)

    mae = mean_absolute_error(y_test, preds_rounded)
    print(f"MAE (escala 1–5): {mae:.3f}")

    cv_scores = cross_val_score(
        model,
        scaler.fit_transform(X),
        y,
        cv=5,
        scoring='neg_mean_absolute_error'
    )

    print("MAE médio CV:", -cv_scores.mean())

    os.makedirs(MODEL_DIR, exist_ok=True)

    joblib.dump(model, MODEL_DIR / "modelo_classificacao_fornecedores.pkl")
    joblib.dump(scaler, MODEL_DIR / "escalonador_fornecedores.pkl")
    
    # Adicionando timestamp de execução
    current_time = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    supplier_features['dt_execucao'] = current_time
    
    # Salvando CSV para compatibilidade foi removido conforme solicitado.
    # supplier_features.to_csv(MODEL_DIR / "fornecedores_classificados.csv")
    
    # Persistindo no Banco de Dados SQLite
    import sqlite3
    db_path = BASE_DIR / "data" / "iacompras.db"
    os.makedirs(db_path.parent, exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        # Salvando o DataFrame na tabela 'fornecedores_classificados'
        # Usamos 'append' para manter histórico de todas as execuções
        # index=True garante que RAZAO_FORNECEDOR (índice do DF) seja salvo como uma coluna
        supplier_features.to_sql('fornecedores_classificados', conn, if_exists='append', index=True)
        print(f"Dados salvos com sucesso no banco de dados: {db_path}")
    except Exception as e:
        print(f"Erro ao salvar no banco de dados: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

    print(f"Modelo salvo em: {MODEL_DIR}")


if __name__ == "__main__":
    treinar_modelo_avaliacao_fornecedores()
