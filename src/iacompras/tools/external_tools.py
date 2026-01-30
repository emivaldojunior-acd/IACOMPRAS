import requests
import sqlite3
from iacompras.tools.db_tools import db_upsert_supplier, DB_PATH

def brasilapi_cnpj_lookup(cnpj):
    """
    Consulta BrasilAPI para obter dados do fornecedor via CNPJ.
    Cacheia o resultado no SQLite.
    """
    print(f"Consultando BrasilAPI para CNPJ: {cnpj}")

    # Limpa o CNPJ (deixa apenas números) e garante 14 dígitos com zeros à esquerda
    cnpj_clean = "".join(filter(str.isdigit, str(cnpj)))
    cnpj_clean = cnpj_clean.zfill(14)  # Padding para 14 dígitos
    
    # 1. Tentar buscar no Cache (SQLite)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers WHERE cnpj = ?", (cnpj_clean,))
    cached = cursor.fetchone()
    conn.close()
    
    if cached:
        import json
        return json.loads(cached[4]) # brasilapi_json
    
    # 2. Consultar API Externa
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_clean}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Cachear
            import json
            db_upsert_supplier(
                cnpj_clean, 
                data.get("razao_social"), 
                data.get("municipio"), 
                data.get("uf"), 
                json.dumps(data)
            )
            return data
        else:
            return {"error": f"BrasilAPI retornou status {response.status_code}", "status": response.status_code}
    except Exception as e:
        return {"error": f"Falha na consulta BrasilAPI: {str(e)}"}

