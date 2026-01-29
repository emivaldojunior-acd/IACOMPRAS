import sqlite3
import os
from datetime import datetime

DB_PATH = "data/iacompras.db"

def db_init():
    """
    Inicializa o banco de dados SQLite com as tabelas necessárias.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabela de execuções (runs)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        user_query TEXT,
        status TEXT
    )
    ''')

    # Tabela de itens da execução
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS run_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        codigo_produto TEXT,
        quantidade_prevista REAL,
        quantidade_sugerida REAL,
        fornecedor_sugerido TEXT,
        custo_estimado REAL,
        prazo_estimado INTEGER,
        flags_auditoria TEXT,
        FOREIGN KEY (run_id) REFERENCES runs (id)
    )
    ''')

    # Tabela de fornecedores
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS suppliers (
        cnpj TEXT PRIMARY KEY,
        razao TEXT,
        cidade TEXT,
        uf TEXT,
        brasilapi_json TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Tabela de cotações
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cotacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        cnpj TEXT,
        codigo_produto TEXT,
        valor_unitario REAL,
        prazo_dias INTEGER,
        condicoes TEXT,
        status TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (run_id) REFERENCES runs (id)
    )
    ''')

    # Tabela de e-mails (outbox)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emails_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        to_email TEXT,
        subject TEXT,
        body TEXT,
        provider TEXT,
        status TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        dry_run INTEGER DEFAULT 1,
        FOREIGN KEY (run_id) REFERENCES runs (id)
    )
    ''')

    conn.commit()
    conn.close()
    return f"Banco de dados inicializado em {DB_PATH}"

def db_insert_run(user_query, status="started"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO runs (user_query, status) VALUES (?, ?)", (user_query, status))
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id

def db_upsert_supplier(cnpj, razao, cidade, uf, brasilapi_json):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO suppliers (cnpj, razao, cidade, uf, brasilapi_json, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(cnpj) DO UPDATE SET
        razao=excluded.razao,
        cidade=excluded.cidade,
        uf=excluded.uf,
        brasilapi_json=excluded.brasilapi_json,
        updated_at=excluded.updated_at
    ''', (cnpj, razao, cidade, uf, brasilapi_json, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def db_insert_cotacao(run_id, cnpj, codigo_produto, valor_unitario, prazo_dias, condicoes, status="pendente"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO cotacoes (run_id, cnpj, codigo_produto, valor_unitario, prazo_dias, condicoes, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, cnpj, codigo_produto, valor_unitario, prazo_dias, condicoes, status))
    conn.commit()
    conn.close()

def db_list_cotacoes(run_id, codigo_produto=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if codigo_produto:
        cursor.execute("SELECT * FROM cotacoes WHERE run_id = ? AND codigo_produto = ?", (run_id, codigo_produto))
    else:
        cursor.execute("SELECT * FROM cotacoes WHERE run_id = ?", (run_id,))
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return results

def db_get_latest_classified_suppliers():
    """
    Recupera a última execução do classificador de fornecedores do banco de dados.
    """
    if not os.path.exists(DB_PATH):
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verifica se a tabela existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fornecedores_classificados'")
    if not cursor.fetchone():
        conn.close()
        return []

    # Busca a data da última execução
    cursor.execute("SELECT MAX(dt_execucao) FROM fornecedores_classificados")
    last_exec = cursor.fetchone()[0]
    
    if not last_exec:
        conn.close()
        return []
        
    # Busca todos os registros dessa última execução
    cursor.execute("SELECT * FROM fornecedores_classificados WHERE dt_execucao = ?", (last_exec,))
    
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return results
