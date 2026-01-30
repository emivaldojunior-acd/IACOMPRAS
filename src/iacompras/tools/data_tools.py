import pandas as pd
import os
from pathlib import Path

DATA_PATH = Path("data/samples")

def load_nf_headers():
    path = DATA_PATH / "IACOMPRAS_NOTASFISCAIS_2025.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_excel(path)

def load_nf_items():
    path = DATA_PATH / "IACOMPRAS_NOTAFISCALITENS_2025.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_excel(path)

