import pandas as pd
import os
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

def load_dataset():
    """
    Carrega o dataset_modelo.csv do diretório data/samples/.
    """
    path = Path("data/samples/dataset_modelo.csv")
    
    # Se não encontrar no CWD (provavelmente a raiz), tenta relativo ao arquivo
    if not path.exists():
        # d:/IACOMPRAS/src/iacompras/ml/IACOMPRAS.GradientBoostingRegressor.py -> 3 níveis acima é src, 4 níveis é a raiz
        path = Path(__file__).resolve().parents[3] / "data" / "samples" / "dataset_modelo.csv"
        
    if path.exists():
        return pd.read_csv(path)
    
    raise FileNotFoundError(f"Arquivo não encontrado: {path}")

def train_and_evaluate(df):
    """
    Treina o modelo GradientBoostingRegressor e gera as previsões para 2026 de forma correta.
    """
    # 1. Definição de Features para Treino (Prever 2025 usando 2023 e 2024)
    features_base = ['GIRO_MEDIO_DIAS', 'GIRO_MEDIO_MESES', 'TENDENCIA_PERC']
    features_train = features_base + ['2023', '2024']
    target = '2025'
    
    X = df[features_train]
    y = df[target]
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Modelo GradientBoostingRegressor
    modelo = GradientBoostingRegressor(random_state=42)
    
    modelo.fit(X_train, y_train)
    
    # Avaliação (no conjunto de teste de 2025)
    y_pred = modelo.predict(X_test)
    erro = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print(f'Erro médio absoluto (MAE) no Teste: {erro:.2f}')
    print(f'Percentual de Variância Explicada (R²): {r2:.2%}')
    
    # 2. Previsões para 2026 (Usando 2024 e 2025 como entrada)
    # Criamos um conjunto de dados "deslocado" para que o modelo projete o futuro
    X_2026 = df[features_base].copy()
    X_2026['2023'] = df['2024'] 
    X_2026['2024'] = df['2025'] 
    
    # Garantir a ordem das colunas igual ao treino
    X_2026 = X_2026[features_train]
    
    df['PREVISAO_2026_MENSAL'] = modelo.predict(X_2026)
    df['PREVISAO_2026_ANUAL'] = (df['PREVISAO_2026_MENSAL'] * 12).round(0)
    
    print("\nPrevisões REAIS para 2026 (Sem Data Leakage):")
    print(df[
        [
            'CODIGO_PRODUTO',
            'CLASSIFICACAO_GIRO',
            'PREVISAO_2026_MENSAL',
            'PREVISAO_2026_ANUAL'
        ]
    ].head())
    
    return modelo

if __name__ == "__main__":
    try:
        dataset = load_dataset()
        train_and_evaluate(dataset)
    except Exception as e:
        print(f"Erro na execução: {e}")
