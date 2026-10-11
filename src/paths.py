"""Caminhos absolutos do projeto, derivados da raiz do repositório.

Todos os scripts/pipeline devem importar daqui para funcionar
independentemente do diretório de trabalho atual (CWD).
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "corpus.db"
WORK_DATA = PROJECT_ROOT / "work_data"
EXPORT_R2 = PROJECT_ROOT / "export_r2"
CC_NEWS = PROJECT_ROOT / "cc_news_pt"
