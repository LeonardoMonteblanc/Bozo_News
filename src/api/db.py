"""Conexão com SQLite em modo read-only."""
import json
import sqlite3
from pathlib import Path

# Database file is at project root (same level as api.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = _PROJECT_ROOT / "corpus.db"


def db():
    conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row):
    """Converte sqlite3.Row para dict, parseando campos JSON."""
    d = dict(row)
    for campo in ("palavras_chave", "entidades_per", "entidades_org",
                  "entidades_loc", "entidades_misc",
                  "topico_palavras", "topico_palavras_v2"):
        v = d.get(campo)
        if v:
            try:
                d[campo] = json.loads(v)
            except Exception:
                d[campo] = []
        else:
            d[campo] = []
    return d
