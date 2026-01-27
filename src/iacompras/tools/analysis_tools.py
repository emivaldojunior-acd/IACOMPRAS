import numpy as np

def score_supplier(prazo_medio, historico_volume, uf_fixa="GO"):
    """
    Calcula um score para o fornecedor (0 a 100).
    """
    score = 50 # Base
    
    # Prazo (quanto menor, melhor)
    if prazo_medio <= 7: score += 20
    elif prazo_medio <= 15: score += 10
    
    # UF do projeto (Logística facilitada em GO)
    if uf_fixa == "GO": score += 10
    
    # Histórico de volume (confiança)
    if historico_volume > 1000: score += 20
    
    return min(100, score)

def detect_anomalies(valores):
    """
    Detecta anomalias em uma lista de valores usando IQR.
    """
    if not valores or len(valores) < 4:
        return []
    
    q1 = np.percentile(valores, 25)
    q3 = np.percentile(valores, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    anomalies = [v for v in valores if v < lower_bound or v > upper_bound]
    return anomalies
