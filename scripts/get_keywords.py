"""
Preenche o campo `palavras_chave` dos artigos do subset Bolsonaro.

Roda YAKE sobre o texto_limpo de cada artigo, em paralelo.
Atualiza o corpus.db local.
"""

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from src.paths import PROJECT_ROOT, DB_FILE
import os as _os
_os.chdir(PROJECT_ROOT)
import sqlite3
import json
import time
import multiprocessing as mp


DB_FILE = str(DB_FILE)
N_WORKERS = 4
BATCH_DB = 200
TOP_N = 8          # palavras-chave por artigo
NGRAM = 2          # bigramas


# ========================= WORKER =========================

_KW = None

def _init_worker():
    global _KW
    import yake
    _KW = yake.KeywordExtractor(lan="pt", n=NGRAM, top=TOP_N, dedupLim=0.7)


def _processar_lote(lote):
    """lote: lista de (id, texto). Retorna [(id, palavras_json)]."""
    global _KW
    if _KW is None:
        import yake
        _KW = yake.KeywordExtractor(lan="pt", n=NGRAM, top=TOP_N, dedupLim=0.7)

    resultados = []
    for id_, texto in lote:
        if not texto or len(texto) < 100:
            resultados.append((id_, None))
            continue
        try:
            # Limita a 3000 chars para não travar em textos gigantes
            kws = _KW.extract_keywords(texto[:3000])
            # Filtra palavras muito curtas
            palavras = [k[0] for k in kws if len(k[0]) >= 4]
            if palavras:
                resultados.append((id_, json.dumps(palavras, ensure_ascii=False)))
            else:
                resultados.append((id_, None))
        except Exception:
            resultados.append((id_, None))
    return resultados


# ========================= MAIN =========================

def main():
    conn = sqlite3.connect(DB_FILE, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    # Conta pendentes
    n = cur.execute("""
        SELECT COUNT(*) FROM articles
        WHERE (mention_bolsonaro = 1 OR relevance_bolsonaro = 1)
          AND texto_limpo IS NOT NULL
          AND length(texto_limpo) >= 100
    """).fetchone()[0]
    print(f"[i] {n:,} artigos para processar")

    # Carrega todos em memória (só id + texto)
    rows = cur.execute("""
        SELECT id, texto_limpo FROM articles
        WHERE (mention_bolsonaro = 1 OR relevance_bolsonaro = 1)
          AND texto_limpo IS NOT NULL
          AND length(texto_limpo) >= 100
        ORDER BY id
    """).fetchall()
    conn.close()

    print(f"[i] Carregados. Processando com {N_WORKERS} workers...")

    t0 = time.time()
    processados = 0
    lote_size = 100

    # Reconecta para updates
    conn = sqlite3.connect(DB_FILE, timeout=60)
    conn.execute("PRAGMA synchronous=NORMAL")
    cur = conn.cursor()

    with mp.Pool(N_WORKERS, initializer=_init_worker) as pool:
        for i in range(0, len(rows), lote_size * N_WORKERS):
            lote_geral = rows[i:i+lote_size*N_WORKERS]
            # Divide em sub-lotes por worker
            sub_lotes = [
                lote_geral[j:j+lote_size]
                for j in range(0, len(lote_geral), lote_size)
            ]
            resultados = pool.map(_processar_lote, sub_lotes)
            todos = [item for sub in resultados for item in sub]

            cur.executemany(
                "UPDATE articles SET palavras_chave = ? WHERE id = ?",
                [(kw, id_) for id_, kw in todos],
            )
            conn.commit()
            processados += len(todos)

            dt = time.time() - t0
            taxa = processados / dt if dt else 0
            eta = (len(rows) - processados) / taxa if taxa else 0
            print(f"  [{processados:>6,}/{len(rows):,}] "
                  f"{taxa:.0f}/s | ETA {eta/60:.1f}min")

    conn.close()
    dt = time.time() - t0
    print(f"\n[FIM] {processados:,} artigos em {dt/60:.1f} min")


if __name__ == "__main__":
    main()