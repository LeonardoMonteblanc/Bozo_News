"""
Retreina BERTopic com configuração melhorada + hierarquia.

Saída:
  - cc_news_pt/_topicos_v2.json         (metadados: macro + micro)
  - cc_news_pt/_topicos_hierarquia.json (árvore de hierarquia)
  - corpus.db atualizado com novo topico_id
"""

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from src.paths import PROJECT_ROOT, DB_FILE
import os as _os
_os.chdir(PROJECT_ROOT)
import os
import json
import time
import sqlite3
import numpy as np
from datetime import datetime

# ========================= CONFIG =========================

DB_FILE = str(DB_FILE)
OUT_DIR = "cc_news_pt"
MODEL_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

# Configuração agressiva
MIN_TOPIC_SIZE = 100        # 0,48% dos 20k — pouca fragmentação
NR_TOPICS = 25              # forçado
N_GRAM = (1, 2)
MIN_DIST = 0.0              # UMAP
MIN_DF = 5                  # vectorizer

# Stopwords políticas
STOPWORDS = [
    "presidente", "presidenta", "governo", "brasil", "brasileiro", "brasileira",
    "federal", "nacional", "ministro", "ministra", "ministério",
    "deputado", "deputada", "senador", "senadora",
    "país", "estado", "política", "político",
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "um", "uma", "para", "por", "com", "sem",
    "que", "qual", "quais", "quando", "onde", "como", "porque",
    "se", "ao", "aos", "à", "às", "é", "são", "foi", "foram",
    "ser", "está", "estão", "ter", "tem", "tinha",
    "mais", "menos", "muito", "pouco", "já", "ainda",
    "também", "só", "após", "antes", "durante", "contra", "desde",
    "até", "esse", "essa", "isso", "este", "esta", "isto",
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1] Carregando artigos do corpus.db...")
    conn = sqlite3.connect(DB_FILE, timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT id, titulo, resumo
        FROM articles
        WHERE (mention_bolsonaro = 1 OR relevance_bolsonaro = 1)
          AND titulo IS NOT NULL
          AND length(titulo) >= 10
    """).fetchall()

    print(f"    {len(rows):,} artigos")

    ids = [r["id"] for r in rows]
    docs = [
        ((r["titulo"] or "") + ". " + (r["resumo"] or ""))[:1000]
        for r in rows
    ]

    conn.close()

    # ========================= BERTopic =========================

    print("\n[2] Importando BERTopic...")
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    print("[3] Carregando embeddings...")
    embedding_model = SentenceTransformer(MODEL_EMBEDDINGS)

    print("[4] Configurando UMAP (min_dist=0.0)...")
    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=MIN_DIST,
        metric="cosine",
        random_state=42,
    )

    print("[5] Configurando vectorizer (stopwords + n-gramas)...")
    vectorizer = CountVectorizer(
        stop_words=STOPWORDS,
        ngram_range=N_GRAM,
        min_df=MIN_DF,
    )

    print(f"[6] Treinando BERTopic (min_topic_size={MIN_TOPIC_SIZE}, nr_topics={NR_TOPICS})...")
    t0 = time.time()

    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        vectorizer_model=vectorizer,
        language="portuguese",
        min_topic_size=MIN_TOPIC_SIZE,
        nr_topics=NR_TOPICS,
        calculate_probabilities=False,
        verbose=True,
    )

    topicos, _ = topic_model.fit_transform(docs)
    print(f"    Treinado em {(time.time()-t0)/60:.1f} min")

    # ========================= Hierarquia =========================

    print("\n[7] Construindo hierarquia de tópicos...")
    try:
        hierarchical_topics = topic_model.hierarchical_topics(docs)

        # Salva a árvore em JSON
        ht_records = hierarchical_topics.to_dict(orient="records")
        with open(f"{OUT_DIR}/_topicos_hierarquia.json", "w", encoding="utf-8") as f:
            json.dump(ht_records, f, ensure_ascii=False, indent=2, default=str)
        print(f"    {len(ht_records)} nós na hierarquia salvos")

        # Sugere merge automático para reduzir a ~8-10 macro-temas
        # Usa o próprio link tree para agrupar
        new_topics = topic_model.reduce_hierarchy(
            docs=docs,
            topics=topicos,
            hierarchical_topics=hierarchical_topics,
            nr_topics=8,  # 8 macro-temas
        )
        print(f"    Hierarquia reduzida para 8 macro-temas")
    except Exception as e:
        print(f"    [aviso] Hierarquia falhou: {e}")
        new_topics = topicos

    # ========================= Metadados =========================

    print("\n[8] Extraindo metadados dos tópicos...")
    info = topic_model.get_topic_info()

    topicos_meta = {}
    for _, row in info.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            continue
        words = topic_model.get_topic(tid) or []
        topicos_meta[str(tid)] = {
            "palavras_bertopic": [w[0] for w in words[:12]],
            "total": int(row["Count"]),
        }

    # Macro-temas (rótulo)
    macro = {}
    try:
        # Cada topico tem um pai na hierarquia
        for _, row in hierarchical_topics.iterrows():
            if row["Parent_ID"] != -1:
                macro.setdefault(int(row["Child_Left_ID"]), []).append(int(row["Parent_ID"]))
                macro.setdefault(int(row["Child_Right_ID"]), []).append(int(row["Parent_ID"]))
    except Exception:
        pass

    # ========================= Salva JSON =========================

    print("\n[9] Salvando metadados...")
    with open(f"{OUT_DIR}/_topicos_v2.json", "w", encoding="utf-8") as f:
        json.dump({
            "versao": "bertopic-v2-hierarquico",
            "config": {
                "min_topic_size": MIN_TOPIC_SIZE,
                "nr_topics": NR_TOPICS,
                "n_gram": list(N_GRAM),
                "min_dist": MIN_DIST,
                "min_df": MIN_DF,
                "stopwords_count": len(STOPWORDS),
            },
            "topicos": topicos_meta,
            "gerado_em": datetime.utcnow().isoformat(),
        }, f, ensure_ascii=False, indent=2)

    # ========================= Atualiza DB =========================

    print("\n[10] Atualizando corpus.db com novos topico_id...")
    conn = sqlite3.connect(DB_FILE, timeout=60)
    cur = conn.cursor()

    # Adiciona coluna se não existir
    try:
        cur.execute("ALTER TABLE articles ADD COLUMN topico_id_v2 INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE articles ADD COLUMN topico_palavras_v2 TEXT")
    except sqlite3.OperationalError:
        pass

    buffer = []
    for id_, tid in zip(ids, new_topics):
        tid_int = int(tid)
        tid_db = tid_int if tid_int >= 0 else None
        palavras = topicos_meta.get(str(tid_int), {}).get("palavras_bertopic", [])
        buffer.append((
            tid_db,
            json.dumps(palavras, ensure_ascii=False) if palavras else None,
            id_,
        ))

        if len(buffer) >= 5000:
            cur.executemany("""
                UPDATE articles SET topico_id_v2 = ?, topico_palavras_v2 = ?
                WHERE id = ?
            """, buffer)
            conn.commit()
            buffer.clear()

    if buffer:
        cur.executemany("""
            UPDATE articles SET topico_id_v2 = ?, topico_palavras_v2 = ?
            WHERE id = ?
        """, buffer)
        conn.commit()

    conn.close()

    print("\n" + "=" * 60)
    print(f"[FIM] {len(topicos_meta)} tópicos gerados")
    print(f"      TOP 10 tópicos:")
    for tid, meta in sorted(topicos_meta.items(), key=lambda x: -x[1]["total"])[:10]:
        pals = ", ".join(meta["palavras_bertopic"][:6])
        print(f"      T{tid:>3} ({meta['total']:>5}): {pals}")
    print("=" * 60)


if __name__ == "__main__":
    main()