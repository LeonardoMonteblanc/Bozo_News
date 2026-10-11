"""Rotas de agregações (timeline, categorias, dominios, palavras_chave)."""
import json
from collections import Counter
from fastapi import APIRouter, Query

from src.api.db import db
from src.api.cache import cache_get, cache_set

router = APIRouter()

FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)"
CACHE_TTL = 300


@router.get("/timeline")
def timeline(
    de: str = Query("2019-01-01"),
    ate: str = Query("2022-12-31"),
    so_relevantes: bool = Query(False),
):
    chave = f"timeline|{de}|{ate}|{so_relevantes}"
    cached = cache_get(chave)
    if cached:
        return cached

    filtro = " AND relevance_bolsonaro = 1" if so_relevantes else ""
    conn = db()
    rows = conn.execute(f"""
        SELECT substr(data,1,7) AS mes, COUNT(*) AS total
        FROM articles
        WHERE data BETWEEN ? AND ? {filtro}
        GROUP BY mes ORDER BY mes
    """, (de, ate)).fetchall()
    conn.close()

    res = [dict(r) for r in rows]
    cache_set(chave, res)
    return res


@router.get("/categorias")
def categorias():
    chave = "categorias"
    cached = cache_get(chave)
    if cached:
        return cached

    conn = db()
    rows = conn.execute(f"""
        SELECT COALESCE(categoria,'?') AS categoria, COUNT(*) AS total
        FROM articles
        WHERE {FILTRO_BASE}
        GROUP BY categoria ORDER BY total DESC
    """).fetchall()
    conn.close()

    res = [dict(r) for r in rows]
    cache_set(chave, res)
    return res


@router.get("/dominios")
def dominios(limite: int = 30):
    chave = f"dominios|{limite}"
    cached = cache_get(chave)
    if cached:
        return cached

    conn = db()
    rows = conn.execute(f"""
        SELECT domain, COUNT(*) AS total
        FROM articles
        WHERE {FILTRO_BASE} AND domain IS NOT NULL
        GROUP BY domain ORDER BY total DESC LIMIT ?
    """, (limite,)).fetchall()
    conn.close()

    res = [dict(r) for r in rows]
    cache_set(chave, res)
    return res


@router.get("/palavras_chave")
def palavras_chave(limite: int = 100, min_freq: int = 3):
    chave = f"kw|{limite}|{min_freq}"
    cached = cache_get(chave)
    if cached:
        return cached

    conn = db()
    rows = conn.execute(f"""
        SELECT palavras_chave FROM articles
        WHERE {FILTRO_BASE}
          AND palavras_chave IS NOT NULL AND palavras_chave != '[]'
    """).fetchall()
    conn.close()

    freq = Counter()
    for r in rows:
        try:
            kws = json.loads(r["palavras_chave"])
        except Exception:
            continue
        for kw in kws:
            k = str(kw).strip().lower()
            if len(k) < 4 or len(k) > 40:
                continue
            freq[k] += 1

    resultado = [
        {"palavra": p, "total": n}
        for p, n in freq.most_common(limite) if n >= min_freq
    ]
    cache_set(chave, resultado)
    return resultado
