import sys
import os
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from iacompras.tools.db_tools import db_get_latest_classified_suppliers
from iacompras.tools.ml_tools import get_classified_suppliers

print("--- Testando db_get_latest_classified_suppliers ---")
try:
    results = db_get_latest_classified_suppliers()
    print(f"Total de registros encontrados: {len(results)}")
    if results:
        print(f"Exemplo de registro: {results[0]}")
except Exception as e:
    print(f"Erro ao ler do banco: {e}")

print("\n--- Testando get_classified_suppliers ---")
try:
    results_tool = get_classified_suppliers()
    if isinstance(results_tool, dict) and "error" in results_tool:
        print(f"Erro retornado pela tool: {results_tool['error']}")
    else:
        print(f"Total de registros via tool: {len(results_tool)}")
except Exception as e:
    print(f"Erro na tool: {e}")
