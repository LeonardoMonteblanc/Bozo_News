"""Rotas de sugestões (autocomplete)."""
import json
from collections import Counter
from fastapi import APIRouter, Query

from src.api.db import db

router = APIRouter()

FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)"


@router.get("/sugestoes")
def sugestoes(q: str = ""):
    q = (q or "").strip().lower()
    if len(q) < 2:
        return {"entidades": [], "topicos": [], "categorias": [], "total_noticias": 0}

    conn = db()
    like = f"%{q}%"

    # Total de notícias que combinam
    total = conn.execute(f"""
        SELECT COUNT(*) AS n FROM articles
        WHERE {FILTRO_BASE}
          AND (LOWER(titulo) LIKE ? OR LOWER(resumo) LIKE ?)
    """, (like, like)).fetchone()["n"]

    # Entidades — busca otimizada sem LIMIT 300 desnecessário
    ent_rows = conn.execute(f"""
        SELECT entidades_per, entidades_org FROM articles
        WHERE {FILTRO_BASE}
          AND (LOWER(entidades_per) LIKE ? OR LOWER(entidades_org) LIKE ?)
        LIMIT 500
    """, (like, like)).fetchall()

    ent_map = Counter()
    for r in ent_rows:
        for campo in ("entidades_per", "entidades_org"):
            try:
                for e in json.loads(r[campo] or "[]"):
                    if q in str(e).lower():
                        ent_map[str(e)] += 1
            except Exception:
                pass

    entidades = [{"nome": n, "total": c} for n, c in ent_map.most_common(5)]

    # Tópicos — usa colunas v5
    top_rows = conn.execute(f"""
        SELECT topico_id_v5 AS topico_id,
               topico_nome_v5 AS nome,
               COUNT(*) AS total
        FROM articles
        WHERE {FILTRO_BASE} AND topico_id_v5 IS NOT NULL
        GROUP BY topico_id_v5
    """).fetchall()

    topicos = []
    for r in top_rows:
        nome = r["nome"] or ""
        if q in nome.lower():
            topicos.append({
                "id": r["topico_id"],
                "nome": nome,
                "total": r["total"],
            })

    # Categorias
    cat_rows = conn.execute(f"""
        SELECT categoria, COUNT(*) AS total FROM articles
        WHERE {FILTRO_BASE} AND LOWER(categoria) LIKE ?
        GROUP BY categoria ORDER BY total DESC LIMIT 3
    """, (like,)).fetchall()

    conn.close()
    return {
        "entidades": entidades,
        "topicos": topicos[:5],
        "categorias": [{"nome": r["categoria"], "total": r["total"]} for r in cat_rows],
        "total_noticias": total,
    }
