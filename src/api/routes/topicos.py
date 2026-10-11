"""Rotas de tópicos."""
import json
from fastapi import APIRouter, Query

from src.api.db import db
from src.api.cache import cache_get, cache_set

router = APIRouter()

FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)"
CACHE_TTL = 300

BLACKLIST_KEYWORDS = {
    "jair bolsonaro", "bolsonaro", "jair", "presidente jair",
    "presidente", "folhapress", "agência brasil", "agencia brasil",
    "estadão conteúdo", "estadao conteudo", "reuters", "brasil",
    "paulo", "são paulo", "sao paulo", "reprodução", "reproducao",
    "foto", "imagem", "g1", "globo", "uol", "folha",
    "ministério", "ministerio", "governo", "federal", "nacional",
}


@router.get("/topicos")
def listar_topicos():
    chave = "topicos_v5"
    cached = cache_get(chave)
    if cached:
        return cached

    conn = db()
    rows = conn.execute(f"""
        SELECT topico_id_v5 AS topico_id,
               topico_nome_v5 AS nome,
               COUNT(*) AS total
        FROM articles
        WHERE {FILTRO_BASE} AND topico_id_v5 IS NOT NULL
        GROUP BY topico_id_v5
        ORDER BY total DESC
    """).fetchall()
    conn.close()

    res = [dict(r) for r in rows]
    cache_set(chave, res)
    return res


@router.get("/topicos_com_palavras")
def topicos_com_palavras(limite: int = 20, palavras_por_topico: int = 15):
    """Retorna cada tópico final (v5) com as palavras mais frequentes."""
    chave = f"tcp5|{limite}|{palavras_por_topico}"
    cached = cache_get(chave)
    if cached:
        return cached

    conn = db()

    # Palavras por tópico (do campo palavras_chave)
    rows = conn.execute(f"""
        SELECT
            a.topico_id_v5 AS topico_id,
            j.value AS palavra,
            COUNT(*) AS total
        FROM articles a, json_each(a.palavras_chave) j
        WHERE {FILTRO_BASE}
          AND a.topico_id_v5 IS NOT NULL
          AND a.palavras_chave IS NOT NULL
          AND length(j.value) >= 5
        GROUP BY a.topico_id_v5, j.value
        ORDER BY a.topico_id_v5, total DESC
    """).fetchall()

    # Metadados dos tópicos
    meta_rows = conn.execute(f"""
        SELECT topico_id_v5 AS topico_id,
               topico_nome_v5 AS nome,
               COUNT(*) AS total,
               MAX(topico_palavras_v2) AS palavras
        FROM articles
        WHERE {FILTRO_BASE} AND topico_id_v5 IS NOT NULL
        GROUP BY topico_id_v5
        ORDER BY total DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()

    # Agrupa palavras por tópico, filtrando ruído
    por_topico = {}
    for r in rows:
        tid = r["topico_id"]
        pal = r["palavra"].lower().strip()
        if pal in BLACKLIST_KEYWORDS:
            continue
        if pal.startswith("bolsonaro ") or pal.endswith(" bolsonaro"):
            continue
        if pal.startswith("presidente "):
            continue
        if tid not in por_topico:
            por_topico[tid] = []
        if len(por_topico[tid]) < palavras_por_topico:
            por_topico[tid].append({
                "palavra": r["palavra"],
                "total": r["total"],
            })

    resultado = []
    for m in meta_rows:
        tid = m["topico_id"]
        try:
            keywords_bertopic = json.loads(m["palavras"] or "[]")
        except Exception:
            keywords_bertopic = []
        resultado.append({
            "id": tid,
            "nome": m["nome"] or f"Tópico {tid}",
            "total": m["total"],
            "keywords_bertopic": keywords_bertopic[:8],
            "palavras_top": por_topico.get(tid, []),
        })

    cache_set(chave, resultado)
    return resultado
