import sqlite3
conn = sqlite3.connect("corpus.db")
cur = conn.cursor()

print("=== Colunas adicionadas ===")
cols = [r[1] for r in cur.execute("PRAGMA table_info(articles)").fetchall()]
for c in ("topico_id_v2", "topico_id_v3", "topico_palavras_v2", "topico_nome_v3"):
    print(f"  {c}: {'OK' if c in cols else 'FALTA'}")

print("\n=== Contagem por nome ===")
rows = cur.execute("""
    SELECT topico_id_v3, topico_nome_v3, COUNT(*) AS n
    FROM articles
    WHERE topico_id_v3 IS NOT NULL
    GROUP BY topico_id_v3
    ORDER BY n DESC
""").fetchall()
for tid, nome, n in rows:
    print(f"  T{tid:>3} {nome or '(sem nome)':<40} {n:>5}")

print(f"\nTotal com v3: {sum(r[2] for r in rows):,}")
print(f"Sem v3:       {cur.execute('SELECT COUNT(*) FROM articles WHERE topico_id_v3 IS NULL').fetchone()[0]:,}")
conn.close()