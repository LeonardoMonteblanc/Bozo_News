"""
Aplica nomes curados manualmente aos tópicos consolidados.
Substitui os nomes gerados pelo LLM.
"""
import json
import sqlite3


NOMES_CURADOS = {
    100: "Pandemia e vacinação",
    11:  "STF e Flávio Bolsonaro",
    13:  "Lula e o PT",
    9:   "Bolsonaro e Palácio do Alvorada",
    1:   "Combustíveis e Petrobras",
    5:   "Manifestações políticas",
    4:   "Fake news e redes sociais",
    7:   "Sergio Moro e Justiça",
    3:   "Saúde e hospitais",
    12:  "Eleições estaduais SP",
    10:  "Polícia Federal e operações",
    8:   "América Latina e Venezuela",
}

DB = "corpus.db"

conn = sqlite3.connect(DB, timeout=60)
cur = conn.cursor()

for tid, nome in NOMES_CURADOS.items():
    cur.execute(
        "UPDATE articles SET topico_nome_v3 = ? WHERE topico_id_v3 = ?",
        (nome, tid),
    )
    print(f"  T{tid:>3} → {nome} ({cur.rowcount} artigos)")

conn.commit()

# Atualiza o JSON também
with open("cc_news_pt/_topicos_v3.json", encoding="utf-8") as f:
    dados = json.load(f)

for tid_str, meta in dados["topicos"].items():
    tid = int(tid_str)
    if tid in NOMES_CURADOS:
        meta["nome"] = NOMES_CURADOS[tid]

with open("cc_news_pt/_topicos_v3.json", "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=2)

conn.close()
print("\n[FIM] Nomes curados aplicados.")