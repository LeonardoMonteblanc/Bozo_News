"""Aplica nomes curados finais aos subtópicos e renumera."""
import sqlite3

# Mapa final v4 → nome curado
NOMES_FINAIS = {
    100: "Pandemia e saúde",
    101: "Reformas e Congresso",       # T300 renomeado
    102: "Pandemia de COVID-19",        # T301 renomeado
    # Subtópicos do T100 (mantidos)
    200: "Vacinação e doses",
    201: "Auxílio emergencial",
    202: "Reformas e Congresso",        # ← excluído (virou 101)
    203: "Cloroquina e tratamento precoce",
    # Tópicos não-T100 (mantidos)
    1:   "Combustíveis e Petrobras",
    3:   "Saúde de Bolsonaro",
    4:   "Fake news e redes sociais",
    5:   "Manifestações políticas",
    7:   "Sergio Moro e Justiça",
    8:   "América Latina e Venezuela",
    9:   "Bolsonaro e Palácio do Alvorada",
    10:  "Polícia Federal e operações",
    11:  "STF e Flávio Bolsonaro",
    12:  "Eleições 2022 em SP",
    13:  "Lula e o PT",
}

# Remapeamento: topico_id_v4 original → topico_id_v5 final
REMAP = {
    300: 101,   # Reforma Câmara → Reformas e Congresso
    301: 102,   # Pandemia Coronavírus → Pandemia de COVID-19
}

DB = "corpus.db"

conn = sqlite3.connect(DB, timeout=60)
cur = conn.cursor()

# Adiciona colunas v5
for col, tipo in [("topico_id_v5", "INTEGER"), ("topico_nome_v5", "TEXT")]:
    try:
        cur.execute(f"ALTER TABLE articles ADD COLUMN {col} {tipo}")
    except sqlite3.OperationalError:
        pass

# Copia v4 → v5
cur.execute("""
    UPDATE articles
    SET topico_id_v5 = topico_id_v4,
        topico_nome_v5 = topico_nome_v4
    WHERE topico_id_v4 IS NOT NULL
""")
conn.commit()

# Aplica remapeamento (300→101, 301→102)
for antigo, novo in REMAP.items():
    cur.execute("""
        UPDATE articles SET topico_id_v5 = ? WHERE topico_id_v5 = ?
    """, (novo, antigo))
    print(f"  T{antigo} → T{novo} ({cur.rowcount} artigos)")

# Aplica nomes curados
print("\nAplicando nomes:")
for tid, nome in NOMES_FINAIS.items():
    cur.execute("""
        UPDATE articles SET topico_nome_v5 = ? WHERE topico_id_v5 = ?
    """, (nome, tid))
    if cur.rowcount > 0:
        print(f"  T{tid:>3} → {nome:<40} ({cur.rowcount} artigos)")

conn.commit()

# Resumo final
print("\n" + "=" * 70)
print("TÓPICOS FINAIS (v5):")
print("=" * 70)
rows = cur.execute("""
    SELECT topico_id_v5, topico_nome_v5, COUNT(*) AS n
    FROM articles
    WHERE topico_id_v5 IS NOT NULL
    GROUP BY topico_id_v5
    ORDER BY n DESC
""").fetchall()

total = sum(r[2] for r in rows)
for tid, nome, n in rows:
    pct = 100 * n / total
    print(f"  T{tid:>3} {nome:<40} {n:>6} ({pct:>4.1f}%)")

conn.close()
print(f"\n[FIM] {len(rows)} tópicos finais · {total:,} artigos")