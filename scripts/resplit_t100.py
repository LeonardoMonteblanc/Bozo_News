"""
Re-clusteriza apenas os 7.435 artigos do T100 em 4-6 subtópicos.

Combina:
- BERTopic refinado (min_topic_size=150, nr_topics=6)
- Validação cruzada por keywords (vacinação, auxílio, cloroquina...)

Saída:
- cc_news_pt/_t100_split.json
- corpus.db atualizado com topico_id_v4 + topico_nome_v4
"""

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from src.paths import PROJECT_ROOT, DB_FILE
import os as _os
_os.chdir(PROJECT_ROOT)
import json
import time
import sqlite3
from datetime import datetime

DB_FILE = str(DB_FILE)
OUT_DIR = "cc_news_pt"
MODEL_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

# Parâmetros finos (só para T100)
MIN_TOPIC_SIZE = 100
NR_TOPICS = 6
MIN_GRAM = (1, 2)
MIN_DIST = 0.0
MIN_DF = 2

STOPWORDS = [
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "um", "uma", "para", "por", "com", "sem",
    "que", "qual", "quais", "quando", "onde", "como", "porque",
    "se", "ao", "aos", "à", "às", "é", "são", "foi", "foram",
    "ser", "está", "estão", "ter", "tem", "tinha",
    "mais", "menos", "muito", "pouco", "já", "ainda",
    "também", "só", "após", "antes", "durante", "contra", "desde",
    "até", "esse", "essa", "isso", "este", "esta", "isto",
    "presidente", "governo", "brasil", "federal", "nacional",
    "paulo", "brasília", "folhapress", "agência brasil",
    "estadão conteúdo", "reuters", "jair bolsonaro", "bolsonaro",
]


# ================== REGRAS DE KEYWORD (validação cruzada) ==================

REGRAS_KEYWORD = {
    "Vacinação e doses": ["vacinação", "vacina", "dose", "imunização", "butantan", "pfizer", "coronavac"],
    "Auxílio emergencial": ["auxílio emergencial", "auxilio emergencial", "auxílio brasil", "bolsa família", "benefício"],
    "Cloroquina e tratamento precoce": ["cloroquina", "hidroxicloroquina", "tratamento precoce", "ivermectina", "kit covid"],
    "Restrições e lockdown": ["lockdown", "isolamento", "restrição", "quarentena", "toque de recolher", "máscara"],
    "Mortes e casos": ["mortes", "óbitos", "casos confirmados", "taxa de ocupação", "leitos", "uti"],
    "Lockdown e economia": ["economia", "pib", "desemprego", "inflação", "auxílio", "empresas"],
}


def classificar_por_keyword(palavras):
    """Classifica artigo por regras de keyword. Retorna nome do subtópico ou None."""
    texto = " ".join(str(p).lower() for p in palavras)
    for nome, kws in REGRAS_KEYWORD.items():
        if any(kw in texto for kw in kws):
            return nome
    return None


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1] Carregando artigos do T100...")
    conn = sqlite3.connect(DB_FILE, timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT id, titulo, resumo, palavras_chave
        FROM articles
        WHERE topico_id_v3 = 100
    """).fetchall()

    print(f"    {len(rows):,} artigos")

    ids = [r["id"] for r in rows]
    docs = [
        ((r["titulo"] or "") + ". " + (r["resumo"] or ""))[:1000]
        for r in rows
    ]

    # Guarda palavras-chave originais para validação cruzada
    palavras_por_id = {}
    for r in rows:
        try:
            palavras_por_id[r["id"]] = json.loads(r["palavras_chave"] or "[]")
        except Exception:
            palavras_por_id[r["id"]] = []

    conn.close()

    # ==================== BERTopic refinado ====================

    print("\n[2] Importando BERTopic...")
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    embedding_model = SentenceTransformer(MODEL_EMBEDDINGS)

    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=MIN_DIST,
        metric="cosine",
        random_state=42,
    )

    vectorizer = CountVectorizer(
        stop_words=STOPWORDS,
        ngram_range=MIN_GRAM,
        min_df=MIN_DF,
    )

    print(f"[3] Treinando BERTopic ({MIN_TOPIC_SIZE}/{NR_TOPICS})...")
    t0 = time.time()

    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        vectorizer_model=vectorizer,
        language="portuguese",
        min_topic_size=MIN_TOPIC_SIZE,
        nr_topics=NR_TOPICS,
        calculate_probabilities=False,
        verbose=False,
    )

    topicos_bt, _ = topic_model.fit_transform(docs)
    print(f"    Treinado em {(time.time()-t0)/60:.1f} min")

    # ==================== Metadados BERTopic ====================

    info = topic_model.get_topic_info()
    topicos_meta = {}
    for _, row in info.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            continue
        words = topic_model.get_topic(tid) or []
        topicos_meta[tid] = {
            "palavras_bertopic": [w[0] for w in words[:10]],
            "total": int(row["Count"]),
        }

    # ==================== Validação cruzada por keyword ====================

    print("\n[4] Aplicando validação cruzada por keyword...")
    # Para cada artigo, verifica qual subtópico o keyword sugere
    contagem = {}  # {(topico_bt, keyword_nome): n}
    for id_, tid_bt in zip(ids, topicos_bt):
        if tid_bt == -1:
            continue
        kw_class = classificar_por_keyword(palavras_por_id.get(id_, []))
        if kw_class:
            chave = (int(tid_bt), kw_class)
            contagem[chave] = contagem.get(chave, 0) + 1

    # Para cada tópico BERTopic, qual keyword domina
    nome_por_topico = {}
    for tid in topicos_meta.keys():
        cands = [(k[1], v) for k, v in contagem.items() if k[0] == tid]
        if cands:
            cands.sort(key=lambda x: -x[1])
            nome_por_topico[tid] = cands[0][0]
        else:
            # Fallback: usa as 3 palavras mais representativas
            palavras = topicos_meta[tid]["palavras_bertopic"][:3]
            nome_por_topico[tid] = " ".join(palavras).title()

    # ==================== Aplica na base ====================

    print("\n[5] Atualizando corpus.db...")
    conn = sqlite3.connect(DB_FILE, timeout=60)
    cur = conn.cursor()

    for col, tipo in [
        ("topico_id_v4", "INTEGER"),
        ("topico_nome_v4", "TEXT"),
    ]:
        try:
            cur.execute(f"ALTER TABLE articles ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError:
            pass

    # Copia v3 → v4 para artigos fora do T100
    cur.execute("""
        UPDATE articles
        SET topico_id_v4 = topico_id_v3,
            topico_nome_v4 = topico_nome_v3
        WHERE topico_id_v3 IS NOT NULL AND topico_id_v3 != 100
    """)

    # Substitui T100 pelos subtópicos (prefixados com 200)
    buffer = []
    for id_, tid_bt in zip(ids, topicos_bt):
        if tid_bt == -1:
            tid_novo = None
            nome = "Não classificado (pandemia)"
        else:
            tid_novo = 200 + int(tid_bt)
            nome = nome_por_topico.get(int(tid_bt), "Pandemia (geral)")

        buffer.append((tid_novo, nome, id_))

        if len(buffer) >= 5000:
            cur.executemany("""
                UPDATE articles SET topico_id_v4 = ?, topico_nome_v4 = ?
                WHERE id = ?
            """, buffer)
            conn.commit()
            buffer.clear()

    if buffer:
        cur.executemany("""
            UPDATE articles SET topico_id_v4 = ?, topico_nome_v4 = ?
            WHERE id = ?
        """, buffer)
        conn.commit()

    conn.close()

    # ==================== Salva JSON ====================

    resultado = {
        "versao": "t100-resplit-v4",
        "config": {
            "min_topic_size": MIN_TOPIC_SIZE,
            "nr_topics": NR_TOPICS,
        },
        "subtopicos": {
            str(200 + tid): {
                "nome": nome_por_topico[tid],
                "total": topicos_meta[tid]["total"],
                "palavras_bertopic": topicos_meta[tid]["palavras_bertopic"],
            }
            for tid in topicos_meta.keys()
        },
        "gerado_em": datetime.utcnow().isoformat(),
    }

    with open(f"{OUT_DIR}/_t100_split.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    # ==================== Resumo ====================

    print("\n" + "=" * 70)
    print("[FIM] Subtópicos de T100:")
    print("=" * 70)
    for k, v in sorted(resultado["subtopicos"].items(), key=lambda x: -x[1]["total"]):
        print(f"  T{k} ({v['total']:>5}) — {v['nome']}")
        print(f"          palavras: {', '.join(v['palavras_bertopic'][:5])}")


if __name__ == "__main__":
    main()