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

    # Tabela de orçamentos (headers)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orcamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        razao_fornecedor TEXT,
        cnpj_fornecedor TEXT,
        telefone_fornecedor TEXT,
        valor_total REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Migração: Adiciona colunas novas se não existirem na tabela já criada
    cursor.execute("PRAGMA table_info(orcamento)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    if 'cnpj_fornecedor' not in existing_columns:
        cursor.execute("ALTER TABLE orcamento ADD COLUMN cnpj_fornecedor TEXT")
    if 'telefone_fornecedor' not in existing_columns:
        cursor.execute("ALTER TABLE orcamento ADD COLUMN telefone_fornecedor TEXT")

    # Tabela de itens do orçamento
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orcamento_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orcamento_id INTEGER,
        codigo_produto TEXT,
        preco_unitario REAL,
        recorrencia INTEGER,
        FOREIGN KEY (orcamento_id) REFERENCES orcamento (id)
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

def db_insert_orcamento(razao_fornecedor, valor_total, itens, cnpj_fornecedor=None):
    """
    Insere um orçamento e seus itens no banco.
    itens: lista de dicts [{'codigo_produto', 'preco_unitario', 'recorrencia'}, ...]
    cnpj_fornecedor: CNPJ do fornecedor para consultar telefone via BrasilAPI
    """
    from iacompras.tools.external_tools import brasilapi_cnpj_lookup
    
    # Consulta BrasilAPI para obter telefone (prioridade: ddd_telefone_1 -> ddd_telefone_2 -> ddd_fax)
    telefone_fornecedor = None
    if cnpj_fornecedor:
        dados_api = brasilapi_cnpj_lookup(cnpj_fornecedor)
        if not dados_api.get('error'):
            # Tenta obter telefone na ordem de prioridade
            telefone_fornecedor = dados_api.get('ddd_telefone_1') or ""
            if not telefone_fornecedor.strip():
                telefone_fornecedor = dados_api.get('ddd_telefone_2') or ""
            if not telefone_fornecedor.strip():
                telefone_fornecedor = dados_api.get('ddd_fax') or ""
            telefone_fornecedor = telefone_fornecedor.strip() if telefone_fornecedor else None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO orcamento (razao_fornecedor, cnpj_fornecedor, telefone_fornecedor, valor_total) VALUES (?, ?, ?, ?)",
            (razao_fornecedor, cnpj_fornecedor, telefone_fornecedor, valor_total)
        )
        orc_id = cursor.lastrowid
        
        for item in itens:
            cursor.execute('''
                INSERT INTO orcamento_itens (orcamento_id, codigo_produto, preco_unitario, recorrencia)
                VALUES (?, ?, ?, ?)
            ''', (orc_id, item['codigo_produto'], item['preco_unitario'], item['recorrencia']))
        
        conn.commit()
        return orc_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def db_list_orcamentos(orcamento_ids=None):
    """
    Lista os orçamentos cadastrados no banco de dados.
    Se orcamento_ids for fornecido, filtra apenas esses IDs.
    Retorna lista de dicionários com todos os campos da tabela, incluindo 'itens'.
    """
    if not os.path.exists(DB_PATH):
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if orcamento_ids:
        placeholders = ','.join('?' * len(orcamento_ids))
        cursor.execute(f"SELECT * FROM orcamento WHERE id IN ({placeholders})", orcamento_ids)
    else:
        cursor.execute("SELECT * FROM orcamento ORDER BY created_at DESC")
    
    columns = [column[0] for column in cursor.description]
    orcamentos = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # Buscar itens de cada orçamento
    for orc in orcamentos:
        cursor.execute(
            "SELECT codigo_produto, preco_unitario, recorrencia FROM orcamento_itens WHERE orcamento_id = ?",
            (orc['id'],)
        )
        itens = [
            {'codigo_produto': row[0], 'preco_unitario': row[1], 'recorrencia': row[2]}
            for row in cursor.fetchall()
        ]
        orc['itens'] = itens
    
    conn.close()
    return orcamentos

