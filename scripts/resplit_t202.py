"""
Segunda passada: desmembra T202 (4.136 artigos) em subtópicos menores.

Após esta rodada, esperamos 3-4 subtemas dentro de T202:
- Restrições e lockdown
- Mortes e estatísticas
- Política da pandemia
- Impactos econômicos
"""
import json
import time
import sqlite3
from datetime import datetime

DB_FILE = "corpus.db"
OUT_DIR = "cc_news_pt"
MODEL_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

MIN_TOPIC_SIZE = 200
NR_TOPICS = 5
MIN_GRAM = (1, 2)
MIN_DIST = 0.0
MIN_DF = 2

# Stopwords MAIS AGRESSIVAS (remove "os", "as", "anos", "casos")
STOPWORDS = [
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "um", "uma", "para", "por", "com", "sem",
    "que", "qual", "quais", "quando", "onde", "como", "porque",
    "se", "ao", "aos", "à", "às", "é", "são", "foi", "foram",
    "ser", "está", "estão", "ter", "tem", "tinha", "os", "as",
    "mais", "menos", "muito", "pouco", "já", "ainda", "anos", "ano",
    "também", "só", "após", "antes", "durante", "contra", "desde",
    "até", "esse", "essa", "isso", "este", "esta", "isto",
    "presidente", "governo", "brasil", "federal", "nacional",
    "paulo", "brasília", "folhapress", "agência brasil",
    "estadão conteúdo", "reuters", "jair bolsonaro", "bolsonaro",
    "casos", "caso", "dia", "dias", "nesta", "sobre",
]


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1] Carregando artigos do T202...")
    conn = sqlite3.connect(DB_FILE, timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT id, titulo, resumo
        FROM articles
        WHERE topico_id_v4 = 202
    """).fetchall()
    print(f"    {len(rows):,} artigos")

    ids = [r["id"] for r in rows]
    docs = [
        ((r["titulo"] or "") + ". " + (r["resumo"] or ""))[:1000]
        for r in rows
    ]
    conn.close()

    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    embedding_model = SentenceTransformer(MODEL_EMBEDDINGS)
    umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=MIN_DIST,
                      metric="cosine", random_state=42)
    vectorizer = CountVectorizer(stop_words=STOPWORDS, ngram_range=MIN_GRAM, min_df=MIN_DF)

    print(f"[2] Treinando BERTopic ({MIN_TOPIC_SIZE}/{NR_TOPICS})...")
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

    # Novos IDs: 300+ (para não colidir com 200-203)
    print("\n[3] Atualizando corpus.db...")
    conn = sqlite3.connect(DB_FILE, timeout=60)
    cur = conn.cursor()

    buffer = []
    for id_, tid_bt in zip(ids, topicos_bt):
        tid_novo = 300 + int(tid_bt) if tid_bt >= 0 else None
        palavras = topicos_meta.get(int(tid_bt), {}).get("palavras_bertopic", [])
        # Nome provisório baseado nas 2 primeiras palavras do BERTopic
        nome = " ".join(palavras[:2]).title() if palavras else "Não classificado"
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

    resultado = {
        "versao": "t202-resplit",
        "subtopicos": {
            str(300 + tid): {
                "nome_provisorio": " ".join(topicos_meta[tid]["palavras_bertopic"][:2]).title(),
                "total": topicos_meta[tid]["total"],
                "palavras": topicos_meta[tid]["palavras_bertopic"],
            }
            for tid in topicos_meta.keys()
        },
        "gerado_em": datetime.utcnow().isoformat(),
    }

    with open(f"{OUT_DIR}/_t202_split.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("[FIM] Subtópicos de T202:")
    print("=" * 70)
    for k, v in sorted(resultado["subtopicos"].items(), key=lambda x: -x[1]["total"]):
        print(f"  T{k} ({v['total']:>5}) — {v['nome_provisorio']}")
        print(f"          {', '.join(v['palavras'][:8])}")


if __name__ == "__main__":
    main()