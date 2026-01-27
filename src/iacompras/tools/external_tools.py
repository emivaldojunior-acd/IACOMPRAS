import requests
import sqlite3
import os
from iacompras.tools.db_tools import db_upsert_supplier, DB_PATH

def brasilapi_cnpj_lookup(cnpj):
    """
    Consulta BrasilAPI para obter dados do fornecedor via CNPJ.
    Cacheia o resultado no SQLite.
    """
    # Limpa o CNPJ (deixa apenas números)
    cnpj_clean = "".join(filter(str.isdigit, str(cnpj)))
    
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

def sendgrid_send_email_dry_run(to_email, subject, body, run_id=None):
    """
    Simula envio de e-mail via SendGrid. 
    Grava no banco SQLite com dry_run=1.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO emails_outbox (run_id, to_email, subject, body, provider, status, dry_run)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, to_email, subject, body, "SendGrid", "queued", 1))
    
    conn.commit()
    conn.close()
    
    return {
        "status": "simulated",
        "message": f"E-mail para {to_email} enfileirado no modo Dry-Run.",
        "instructions": "Para envio real, mude DRY_RUN_SENDGRID=false e configure SENDGRID_API_KEY."
    }
