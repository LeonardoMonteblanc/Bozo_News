"""Rotas de entidades e rede."""
import json
from collections import Counter
from fastapi import APIRouter, Query

from src.api.db import db
from src.api.cache import cache_get, cache_set

router = APIRouter()

FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)"
CACHE_TTL = 300


@router.get("/entidades")
def listar_entidades(limite: int = 40):
    chave = f"entidades|{limite}"
    cached = cache_get(chave)
    if cached:
        return cached

    conn = db()
    rows = conn.execute(f"""
        SELECT entidades_per, entidades_org
        FROM articles
        WHERE {FILTRO_BASE}
          AND entidades_per IS NOT NULL
    """).fetchall()
    conn.close()

    per = Counter()
    org = Counter()
    for r in rows:
        try:
            for p in json.loads(r["entidades_per"] or "[]"):
                per[p] += 1
        except Exception:
            pass
        try:
            for o in json.loads(r["entidades_org"] or "[]"):
                org[o] += 1
        except Exception:
            pass

    res = {
        "per": [{"nome": n, "total": c} for n, c in per.most_common(limite)],
        "org": [{"nome": n, "total": c} for n, c in org.most_common(limite)],
    }
    cache_set(chave, res)
    return res


@router.get("/rede")
def rede(limite: int = 30, min_cooc: int = 3):
    chave = f"rede|{limite}|{min_cooc}"
    cached = cache_get(chave)
    if cached:
        return cached

    conn = db()
    rows = conn.execute(f"""
        SELECT entidades_per FROM articles
        WHERE {FILTRO_BASE} AND entidades_per IS NOT NULL
    """).fetchall()
    conn.close()

    freq = Counter()
    cooc = Counter()
    for r in rows:
        try:
            per = list(set(json.loads(r["entidades_per"] or "[]")))
        except Exception:
            continue
        per = [p for p in per if len(p) >= 4]
        for p in per:
            freq[p] += 1
        for i, a in enumerate(per):
            for b in per[i+1:]:
                par = tuple(sorted([a, b]))
                cooc[par] += 1

    top_nos = [n for n, _ in freq.most_common(limite)]
    top_nos_set = set(top_nos)

    arestas = []
    for (a, b), c in cooc.most_common(limite * 5):
        if a in top_nos_set and b in top_nos_set and c >= min_cooc:
            arestas.append({"source": a, "target": b, "peso": c})

    res = {
        "nos": [{"id": n, "total": c} for n, c in freq.most_common(limite)],
        "arestas": arestas,
    }
    cache_set(chave, res)
    return res
