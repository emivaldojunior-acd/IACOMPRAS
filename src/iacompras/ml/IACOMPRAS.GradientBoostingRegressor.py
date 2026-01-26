import pandas as pd
import os
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

def load_dataset():
    """
    Carrega o dataset_modelo.csv de forma robusta procurando no workspace.
    """
    filename = "dataset_modelo.csv"
    
    # 1. Tentar variáveis de ambiente
    for env_var in ["WORKSPACE_MODELO", "ANTIGRAVITY_WORKSPACE", "GOOGLE_WORKSPACE"]:
        env_path = os.getenv(env_var)
        if env_path:
            path = Path(env_path) / filename
            if path.exists():
                return pd.read_csv(path)

    # 2. Procurar em subpastas conhecidas a partir do CWD
    cwd = Path.cwd()
    possible_paths = [
        cwd / "WORKSPACE_MODELO" / filename,
        cwd / "workspace_modelo" / filename,
        cwd / filename
    ]
    for path in possible_paths:
        if path.exists():
            return pd.read_csv(path)

    # 3. Busca recursiva limitada (profundidade 3)
    for path in cwd.rglob(filename):
        if len(path.relative_to(cwd).parts) <= 3:
            return pd.read_csv(path)

    error_msg = f"Erro: Arquivo {filename} não encontrado. Procurado em: {cwd} e variáveis de ambiente."
    raise FileNotFoundError(error_msg)

def train_and_evaluate(df):
    """
    Treina o modelo GradientBoostingRegressor e gera as previsões.
    """
    features = [
        'GIRO_MEDIO_DIAS',
        'GIRO_MEDIO_MESES',
        'TENDENCIA_PERC',
        '2023',
        '2024',
        '2025'
    ]
    
    X = df[features]
    y = df['2025']
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Modelo GradientBoostingRegressor
    modelo = GradientBoostingRegressor(random_state=42)
    
    modelo.fit(X_train, y_train)
    
    # Avaliação
    y_pred = modelo.predict(X_test)
    erro = mean_absolute_error(y_test, y_pred)
    print(f'Erro médio absoluto (MAE): {erro:.2f}')
    
    # Previsões para 2026
    df['PREVISAO_2026_MENSAL'] = modelo.predict(X)
    df['PREVISAO_2026_ANUAL'] = (df['PREVISAO_2026_MENSAL'] * 12).round(0)
    
    print("\nPrevisões para 2026 (Primeiras linhas):")
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
