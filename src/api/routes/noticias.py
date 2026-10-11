"""Rotas de notícias."""
from fastapi import APIRouter, Query

from src.api.db import db, row_to_dict
from src.api.cache import cache_get, cache_set

router = APIRouter()

FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)"
CACHE_TTL = 300


def _build_where(params: dict):
    """Constrói WHERE SQL e lista de binds a partir dos parâmetros."""
    where = [FILTRO_BASE]
    binds = []

    if params.get("so_relevantes"):
        where.append("relevance_bolsonaro = 1")
    if params.get("de"):
        where.append("data >= ?"); binds.append(params["de"])
    if params.get("ate"):
        where.append("data <= ?"); binds.append(params["ate"])
    if params.get("categoria"):
        where.append("categoria = ?"); binds.append(params["categoria"])
    if params.get("dominio"):
        where.append("domain = ?"); binds.append(params["dominio"])
    if params.get("topico") is not None:
        where.append("topico_id_v5 = ?"); binds.append(params["topico"])
    if params.get("sentimento"):
        where.append("sentimento_label = ?"); binds.append(params["sentimento"])
    if params.get("entidade"):
        # Escapa caracteres especiais do LIKE para evitar match indevido
        entidade_escaped = params["entidade"].replace("%", "\\%").replace("_", "\\_")
        where.append("(entidades_per LIKE ? ESCAPE '\\\\' OR entidades_org LIKE ? ESCAPE '\\\\')")
        binds += [f"%{entidade_escaped}%", f"%{entidade_escaped}%"]

    return " AND ".join(where), binds


def _parse_noticia(row):
    """Retorna dict com campos básicos para a lista de notícias."""
    d = dict(row)
    for campo in ("entidades_per", "entidades_org"):
        try:
            d[campo] = json.loads(d[campo]) if d[campo] else []
        except Exception:
            d[campo] = []
    return d


@router.get("/noticias")
def listar_noticias(
    q: str = Query(None),
    categoria: str = Query(None),
    dominio: str = Query(None),
    topico: int = Query(None),
    entidade: str = Query(None),
    sentimento: str = Query(None),
    de: str = Query(None),
    ate: str = Query(None),
    so_relevantes: bool = Query(False),
    ordenar: str = Query("data_desc"),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    params = {
        "q": q, "categoria": categoria, "dominio": dominio,
        "topico": topico, "entidade": entidade, "sentimento": sentimento,
        "de": de, "ate": ate, "so_relevantes": so_relevantes,
    }
    where_sql, binds = _build_where(params)

    order_map = {
        "data_desc": "data DESC",
        "data_asc": "data ASC",
        "relevancia": "bolsonaro_score DESC, data DESC",
    }
    order = order_map.get(ordenar, "data DESC")

    if q:
        sql_count = f"""
            SELECT COUNT(*) FROM articles a
            JOIN articles_fts f ON f.rowid = a.id
            WHERE articles_fts MATCH ? AND {where_sql}
        """
        sql_data = f"""
            SELECT a.id, a.data, a.titulo, a.resumo, a.url, a.sitename,
                   a.categoria, a.sentimento_label,
                   a.topico_id, a.topico_id_v5, a.topico_nome_v5,
                   a.entidades_per, a.entidades_org, a.bolsonaro_score
            FROM articles a
            JOIN articles_fts f ON f.rowid = a.id
            WHERE articles_fts MATCH ? AND {where_sql}
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """
        params_count = [q] + binds
        params_data = [q] + binds + [limit, offset]
    else:
        sql_count = f"SELECT COUNT(*) FROM articles WHERE {where_sql}"
        sql_data = f"""
            SELECT id, data, titulo, resumo, url, sitename,
                   categoria, sentimento_label,
                   topico_id, topico_id_v5, topico_nome_v5,
                   entidades_per, entidades_org, bolsonaro_score
            FROM articles
            WHERE {where_sql}
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """
        params_count = binds[:]
        params_data = binds + [limit, offset]

    conn = db()
    total = conn.execute(sql_count, params_count).fetchone()[0]
    rows = conn.execute(sql_data, params_data).fetchall()
    conn.close()

    itens = [_parse_noticia(r) for r in rows]
    return {"total": total, "limit": limit, "offset": offset, "itens": itens}


@router.get("/noticia/{id_}")
def obter_noticia(id_: int):
    conn = db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (id_,)).fetchone()
    conn.close()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "Notícia não encontrada")

    d = row_to_dict(row)
    if d.get("texto_limpo"):
        d["texto_limpo"] = d["texto_limpo"][:8000]
    return d
