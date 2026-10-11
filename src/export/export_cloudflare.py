"""
Export corpus.db → D1 (SQL) + R2 (JSON por artigo).

Estrutura esperada:
  corpus.db                    (entrada)
  work_data/export_d1/         (saída SQL para D1)
  export_r2/arts/              (saída JSON para R2)

Usa colunas topico_id_v5 e topico_nome_v5 (tópicos finais).
"""
import json
import os
import sqlite3
from pathlib import Path

DB_FILE  = "corpus.db"
OUT_D1   = "work_data/export_d1"
OUT_R2   = "export_r2"

FILTRO    = "mention_bolsonaro = 1"
BATCH_SQL = 500


def sql_escape(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def main():
    Path(OUT_D1).mkdir(parents=True, exist_ok=True)
    Path(f"{OUT_R2}/arts").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("[1] Selecionando subset Bolsonaro...")
    rows = cur.execute(f"""
        SELECT id, hash, data, titulo, resumo, url, domain, sitename, autor,
               categoria, sentimento_label, sentimento_compound,
               topico_id, topico_palavras,
               entidades_per, entidades_org, entidades_loc, entidades_misc,
               palavras_chave, n_palavras, n_chars,
               mention_bolsonaro, relevance_bolsonaro,
               bolsonaro_score, quality_score, texto_limpo,
               topico_id_v5, topico_nome_v5
        FROM articles
        WHERE {FILTRO}
        ORDER BY id
    """).fetchall()
    print(f"    {len(rows):,} artigos")

    # ==================== Schema ====================
    schema = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    hash TEXT, data TEXT, titulo TEXT, resumo TEXT, url TEXT,
    domain TEXT, sitename TEXT, autor TEXT, categoria TEXT,
    sentimento_label TEXT, sentimento_compound REAL,
    topico_id INTEGER, topico_palavras TEXT,
    entidades_per TEXT, entidades_org TEXT,
    entidades_loc TEXT, entidades_misc TEXT,
    palavras_chave TEXT,
    n_palavras INTEGER, n_chars INTEGER,
    mention_bolsonaro INTEGER, relevance_bolsonaro INTEGER,
    bolsonaro_score REAL, quality_score REAL, r2_key TEXT,
    topico_id_v5 INTEGER, topico_nome_v5 TEXT
);
CREATE INDEX IF NOT EXISTS idx_data      ON articles(data);
CREATE INDEX IF NOT EXISTS idx_categoria ON articles(categoria);
CREATE INDEX IF NOT EXISTS idx_domain    ON articles(domain);
CREATE INDEX IF NOT EXISTS idx_topico_v5 ON articles(topico_id_v5);
CREATE INDEX IF NOT EXISTS idx_bolso     ON articles(relevance_bolsonaro);
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    titulo, resumo,
    content='articles', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, titulo, resumo)
    VALUES (new.id, new.titulo, new.resumo);
END;
"""
    with open(f"{OUT_D1}/schema.sql", "w", encoding="utf-8") as f:
        f.write(schema)
    print(f"[2] schema.sql escrito")

    # ==================== INSERTs ====================
    cols = ["id", "hash", "data", "titulo", "resumo", "url", "domain", "sitename",
            "autor", "categoria", "sentimento_label", "sentimento_compound",
            "topico_id", "topico_palavras",
            "entidades_per", "entidades_org", "entidades_loc", "entidades_misc",
            "palavras_chave", "n_palavras", "n_chars",
            "mention_bolsonaro", "relevance_bolsonaro",
            "bolsonaro_score", "quality_score", "r2_key",
            "topico_id_v5", "topico_nome_v5"]
    col_list = ",".join(cols)

    print(f"[3] Gerando INSERTs em lotes de {BATCH_SQL}...")
    n_sql = 0
    for inicio in range(0, len(rows), BATCH_SQL):
        lote = rows[inicio:inicio + BATCH_SQL]
        idx = inicio // BATCH_SQL
        path = f"{OUT_D1}/data_{idx:04d}.sql"
        with open(path, "w", encoding="utf-8") as f:
            for r in lote:
                r2_key = f"arts/{r['id']}.json"
                vals = [
                    r["id"], r["hash"], r["data"], r["titulo"], r["resumo"],
                    r["url"], r["domain"], r["sitename"], r["autor"],
                    r["categoria"], r["sentimento_label"],
                    r["sentimento_compound"], r["topico_id"],
                    r["topico_palavras"],
                    r["entidades_per"], r["entidades_org"],
                    r["entidades_loc"], r["entidades_misc"],
                    r["palavras_chave"],
                    r["n_palavras"], r["n_chars"],
                    r["mention_bolsonaro"], r["relevance_bolsonaro"],
                    r["bolsonaro_score"], r["quality_score"], r2_key,
                    r["topico_id_v5"], r["topico_nome_v5"],
                ]
                f.write(
                    f"INSERT OR REPLACE INTO articles ({col_list}) "
                    f"VALUES ({','.join(sql_escape(v) for v in vals)});\n"
                )
        n_sql += 1
    print(f"    {n_sql} arquivos SQL")

    # ==================== R2 ====================
    print("[4] Gerando JSONs R2...")
    for r in rows:
        payload = {
            "id": r["id"],
            "titulo": r["titulo"],
            "url": r["url"],
            "texto_limpo": r["texto_limpo"] or "",
        }
        with open(f"{OUT_R2}/arts/{r['id']}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    total_r2 = sum(1 for _ in Path(f"{OUT_R2}/arts").glob("*.json"))
    print(f"    {total_r2} arquivos R2")

    conn.close()
    print("\n[FIM] Pronto.")


if __name__ == "__main__":
    main()