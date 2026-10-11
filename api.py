"""
API local — Corpus Bolsonaro 2019-2022.

Roda em http://localhost:8000
Lê corpus.db em modo somente-leitura.
"""
import os
import sqlite3
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from src.api.db import db, row_to_dict
from src.api.cache import cache_get, cache_set
from src.api.routes import noticias, topicos, entidades, agregacoes, sugestoes


# ========================= CONFIG =========================

DB_FILE = "corpus.db"
HOST = "0.0.0.0"
PORT = 8000

FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)"
CACHE_TTL = 300


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
    }


# ========================= ROTAS =========================

# Notícias
app.include_router(noticias, prefix="/api")

# Tópicos
app.include_router(topicos, prefix="/api")

# Entidades e rede
app.include_router(entidades, prefix="/api")

# Agregações (timeline, categorias, dominios, palavras_chave)
app.include_router(agregacoes, prefix="/api")

# Sugestões
app.include_router(sugestoes, prefix="/api")


# ========================= MAIN =========================

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        print(f"[X] {DB_FILE} não encontrado")
        raise SystemExit(1)

    print(f"\n[i] API em http://localhost:{PORT}")
    print(f"[i] Docs: http://localhost:{PORT}/docs")
    print(f"[i] Ctrl+C para parar\n")

    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
