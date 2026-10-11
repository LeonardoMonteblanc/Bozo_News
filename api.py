"""
API local — Corpus Bolsonaro 2019-2022.

Roda em http://localhost:8000
Lê corpus.db em modo somente-leitura.
"""
import os
import json
import time
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


# ========================= CONFIG =========================

DB_FILE = "corpus.db"
HOST = "0.0.0.0"
PORT = 8000

FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)"
CACHE_TTL = 300


# ========================= CONEXÃO =========================

def db():
    conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row):
    d = dict(row)
    for campo in ("palavras_chave", "entidades_per", "entidades_org",
                  "entidades_loc", "entidades_misc",
                  "topico_palavras", "topico_palavras_v2"):
        v = d.get(campo)
        if v:
            try:
                d[campo] = json.loads(v)
            except Exception:
                d[campo] = []
        else:
            d[campo] = []
    return d


# ========================= CACHE =========================

_cache = {}

def cache_get(chave):
    item = _cache.get(chave)
    if item and (time.time() - item["t"]) < CACHE_TTL:
        return item["v"]
    return None

def cache_set(chave, valor):
    _cache[chave] = {"v": valor, "t": time.time()}


# ========================= APP =========================

app = FastAPI(title="Corpus Bolsonaro API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ========================= RAIZ =========================

@app.get("/", response_class=HTMLResponse)
def raiz():
    if os.path.exists("index.html"):
        with open("index.html", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html não encontrado</h1>"


@app.get("/health")
def health():
    conn = db()
    n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return {
        "status": "ok",
        "artigos_no_banco": n,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ========================= NOTÍCIAS =========================

@app.get("/api/noticias")
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
    where = [FILTRO_BASE]
    params = []

    if so_relevantes:
        where.append("relevance_bolsonaro = 1")
    if de:
        where.append("data >= ?"); params.append(de)
    if ate:
        where.append("data <= ?"); params.append(ate)
    if categoria:
        where.append("categoria = ?"); params.append(categoria)
    if dominio:
        where.append("domain = ?"); params.append(dominio)
    if topico is not None:
        where.append("topico_id_v3 = ?"); params.append(topico)
    if sentimento:
        where.append("sentimento_label = ?"); params.append(sentimento)
    if entidade:
        where.append("(entidades_per LIKE ? OR entidades_org LIKE ?)")
        params += [f"%{entidade}%", f"%{entidade}%"]

    where_sql = " AND ".join(where)

    if q:
        sql_count = f"""
            SELECT COUNT(*) FROM articles a
            JOIN articles_fts f ON f.rowid = a.id
            WHERE articles_fts MATCH ? AND {where_sql}
        """
        sql_data = f"""
            SELECT a.id, a.data, a.titulo, a.resumo, a.url, a.sitename,
                   a.categoria, a.sentimento_label,
                   a.topico_id, a.topico_id_v3, a.topico_nome_v3,
                   a.entidades_per, a.entidades_org, a.bolsonaro_score
            FROM articles a
            JOIN articles_fts f ON f.rowid = a.id
            WHERE articles_fts MATCH ? AND {where_sql}
            ORDER BY a.data DESC
            LIMIT ? OFFSET ?
        """
        params_count = [q] + params
        params_data  = [q] + params + [limit, offset]
    else:
        order_map = {
            "data_desc": "data DESC",
            "data_asc":  "data ASC",
            "relevancia": "bolsonaro_score DESC, data DESC",
        }
        order = order_map.get(ordenar, "data DESC")
        sql_count = f"SELECT COUNT(*) FROM articles WHERE {where_sql}"
        sql_data = f"""
            SELECT id, data, titulo, resumo, url, sitename,
                   categoria, sentimento_label,
                   topico_id, topico_id_v3, topico_nome_v3,
                   entidades_per, entidades_org, bolsonaro_score
            FROM articles
            WHERE {where_sql}
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """
        params_count = params[:]
        params_data  = params + [limit, offset]

    conn = db()
    total = conn.execute(sql_count, params_count).fetchone()[0]
    rows = conn.execute(sql_data, params_data).fetchall()
    conn.close()

    itens = []
    for r in rows:
        d = dict(r)
        for campo in ("entidades_per", "entidades_org"):
            try:
                d[campo] = json.loads(d[campo]) if d[campo] else []
            except Exception:
                d[campo] = []
        itens.append(d)

    return {"total": total, "limit": limit, "offset": offset, "itens": itens}


@app.get("/api/noticia/{id_}")
def obter_noticia(id_: int):
    conn = db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (id_,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Notícia não encontrada")

    d = row_to_dict(row)
    if d.get("texto_limpo"):
        d["texto_limpo"] = d["texto_limpo"][:8000]
    return d


# ========================= AGREGAÇÕES =========================

@app.get("/api/timeline")
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


@app.get("/api/categorias")
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


@app.get("/api/dominios")
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


@app.get("/api/topicos")
def topicos():
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


@app.get("/api/entidades")
def entidades(limite: int = 40):
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


@app.get("/api/rede")
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


# ========================= PALAVRAS-CHAVE =========================

@app.get("/api/palavras_chave")
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


# ========================= SUGESTÕES =========================

@app.get("/api/sugestoes")
def sugestoes(q: str = ""):
    q = (q or "").strip().lower()
    if len(q) < 2:
        return {"entidades": [], "topicos": [], "categorias": [], "total_noticias": 0}

    conn = db()
    like = f"%{q}%"

    total = conn.execute(f"""
        SELECT COUNT(*) AS n FROM articles
        WHERE {FILTRO_BASE}
          AND (LOWER(titulo) LIKE ? OR LOWER(resumo) LIKE ?)
    """, (like, like)).fetchone()["n"]

    ent_rows = conn.execute(f"""
        SELECT entidades_per, entidades_org FROM articles
        WHERE {FILTRO_BASE}
          AND (LOWER(entidades_per) LIKE ? OR LOWER(entidades_org) LIKE ?)
        LIMIT 300
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


# ========================= TÓPICOS COM PALAVRAS =========================
@app.get("/api/topicos_com_palavras")
@app.get("/api/topicos_com_palavras")
def topicos_com_palavras(limite: int = 20, palavras_por_topico: int = 15):
    """
    Retorna cada tópico final (v5) com as palavras mais frequentes.
    Filtra ruído: nomes de veículos, Bolsonaro, termos genéricos.
    """
    chave = f"tcp5|{limite}|{palavras_por_topico}"
    cached = cache_get(chave)
    if cached:
        return cached

    BLACKLIST = {
        "jair bolsonaro", "bolsonaro", "jair", "presidente jair",
        "presidente", "folhapress", "agência brasil", "agencia brasil",
        "estadão conteúdo", "estadao conteudo", "reuters", "brasil",
        "paulo", "são paulo", "sao paulo", "reprodução", "reproducao",
        "foto", "imagem", "g1", "globo", "uol", "folha",
        "ministério", "ministerio", "governo", "federal", "nacional",
    }

    conn = db()
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

    por_topico = {}
    for r in rows:
        tid = r["topico_id"]
        pal = r["palavra"].lower().strip()
        if pal in BLACKLIST:
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




# ========================= MAIN =========================

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        print(f"[X] {DB_FILE} não encontrado")
        raise SystemExit(1)

    print(f"\n[i] API em http://localhost:{PORT}")
    print(f"[i] Docs: http://localhost:{PORT}/docs")
    print(f"[i] Ctrl+C para parar\n")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")