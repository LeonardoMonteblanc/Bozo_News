"""
Pipeline completo — 2019-2022 corpus sobre Bolsonaro.

Fases:
  0. Pré-checagem (parquets, banco, libs, modelos)
  1. Recuperar texto_bruto dos parquets
  2. Limpeza com Trafilatura
  3. Sentimento com BERTimbau (BERTweet-PT)
  4. NER com BERTimbau HAREM
  5. Tópicos com BERTopic
  6. Rebuild FTS5 + estatísticas finais

Estado e checkpoints ficam na tabela _pipeline_state do corpus.db.
Cada fase é executada apenas uma vez. Retomada automática.

Uso:
    python run_all.py                  # tudo
    python run_all.py --apenas-fase 3  # só a fase 3
    python run_all.py --reset-fase 3   # refaz a fase 3
    python run_all.py --reset-tudo     # apaga estado e refaz
"""

import os

# Limita threads ANTES de importar numpy/torch
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import re
import sys
import glob
import json
import time
import signal
import sqlite3
import hashlib
import argparse
import logging
import warnings
import traceback
import multiprocessing as mp
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", category=Warning)
warnings.filterwarnings("ignore", category=UserWarning)


# ========================= CONFIG =========================
from src.pipeline.config import (
    DB_FILE, DADOS_DIR, SHARDS_DIR, LOG_FILE, CKPT_DIR,
    N_WORKERS_TEXTO, N_WORKERS_BERT, TORCH_THREADS_PER_WORKER,
    BATCH_TEXTO, BATCH_BERT, BATCH_DB,
    MODEL_SENTIMENTO, MODEL_NER, MODEL_EMBEDDINGS,
    N_TOPICOS_MIN, N_TOPICOS_MAX,
)

# Bolsonaro
PER_BOLSONARO = {
    "bolsonaro", "jair bolsonaro", "jair messias bolsonaro",
    "carlos bolsonaro", "flávio bolsonaro", "flavio bolsonaro",
    "eduardo bolsonaro", "michelle bolsonaro",
    "sérgio moro", "sergio moro", "paulo guedes",
    "hamilton mourão", "hamilton mourao",
    "onyx lorenzoni", "damares alves",
    "ernesto araújo", "ernesto araujo", "abraham weintraub",
    "marcelo queiroga", "eduardo pazuello", "nelson teich",
    "tarcísio de freitas", "tarcisio de freitas",
    "braga netto", "anderson torres", "augusto heleno",
    "augusto aras", "andre mendonça", "kassio nunes",
    "alexandre de moraes", "gilmar mendes",
    "luís roberto barroso", "luis roberto barroso",
    "dias toffoli", "edson fachin", "carmen lúcia", "carmen lucia",
    "rosa weber", "ricardo lewandowski",
}
ORG_GOVERNO = {
    "planalto", "congresso", "senado", "câmara", "camara",
    "stf", "supremo", "tse", "pgr", "mpf", "pf",
    "polícia federal", "policia federal", "governo federal",
    "presidência da república", "tcu", "banco central",
    "bacen", "receita federal", "agu",
}
TERMOS_CONTEXTO = {
    "bolsonaro", "bolsonarista", "bolsonarismo",
    "jair bolsonaro", "governo bolsonaro", "ex-presidente",
    "impeachment", "cloroquina", "tratamento precoce",
    "auxílio emergencial", "auxilio emergencial",
    "orçamento secreto", "orcamento secreto",
    "rachadinha", "queiroz", "milícia", "milicia",
    "fake news", "desinformação", "desinformacao",
    "atos antidemocráticos", "atos antidemocraticos",
    "cpi da covid", "relatório final",
    "reforma da previdência", "reforma tributária",
    "vacinação", "vacinacao", "pandemia",
    "privatização", "privatizacao", "petrobras",
    "lavagem de dinheiro", "inquérito", "inquerito",
}
RE_BOLSONARO = re.compile(
    r"\b(bolsonaro|bolsonarista|bolsonarismo|"
    r"jair\s+bolsonaro|clã\s+bolsonaro|cla\s+bolsonaro)\b",
    re.IGNORECASE,
)


# ========================= LOG =========================

log = logging.getLogger("pipeline")


def setup_log(verbose=False):
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    log.addHandler(ch)


# ========================= ESTADO NO BANCO =========================

def db_conn():
    c = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=120)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA cache_size=-128000")
    c.execute("PRAGMA busy_timeout=120000")
    return c


def init_state_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _pipeline_state (
            fase INTEGER PRIMARY KEY,
            nome TEXT,
            status TEXT DEFAULT 'pending',
            total INTEGER,
            processados INTEGER DEFAULT 0,
            erros INTEGER DEFAULT 0,
            iniciado_em TEXT,
            concluido_em TEXT,
            observacoes TEXT
        )
    """)
    # Registra as 6 fases
    for fase, nome in [
        (1, "recuperar_texto_bruto"),
        (2, "limpeza_trafilatura"),
        (3, "sentimento_bert"),
        (4, "ner_bert"),
        (5, "topicos_bertopic"),
        (6, "fts5_rebuild"),
    ]:
        conn.execute("""
            INSERT OR IGNORE INTO _pipeline_state (fase, nome)
            VALUES (?, ?)
        """, (fase, nome))
    conn.commit()


def get_estado(conn, fase):
    return conn.execute("""
        SELECT status, processados, total FROM _pipeline_state WHERE fase=?
    """, (fase,)).fetchone()


def set_estado(conn, fase, **kwargs):
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [fase]
    conn.execute(f"UPDATE _pipeline_state SET {sets} WHERE fase=?", vals)
    conn.commit()


def reset_fase(conn, fase):
    conn.execute("""
        UPDATE _pipeline_state SET
            status='pending', processados=0, erros=0,
            iniciado_em=NULL, concluido_em=NULL, observacoes=NULL
        WHERE fase=?
    """, (fase,))
    conn.commit()


# ========================= UTILITÁRIOS =========================

def hash_conteudo(texto):
    base = re.sub(r"\s+", " ", (texto or "")[:1000].lower()).strip()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def agora_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def limpar_nan(v):
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return None
    return s


# ========================= FASE 1 — Recuperar texto_bruto =========================

def _fase1_worker(args):
    """Processa um parquet e retorna updates."""
    path, hashes_pendentes = args
    resultados = []
    try:
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(path)
        cols = [c for c in ("plain_text",) if c in pf.schema_arrow.names]
        if not cols:
            return resultados
        for batch in pf.iter_batches(batch_size=5000, columns=cols):
            textos = batch.column("plain_text").to_pylist()
            for texto in textos:
                if not texto or not isinstance(texto, str):
                    continue
                h = hash_conteudo(texto)
                if h in hashes_pendentes:
                    resultados.append((texto, h))
    except Exception as e:
        return [("__ERRO__", f"{path}|{e}")]
    return resultados


def fase1_recuperar_texto(conn, n_workers):
    log.info("=" * 70)
    log.info("FASE 1 — Recuperar texto_bruto dos parquets")
    log.info("=" * 70)

    cur = conn.cursor()
    cur.execute("""
        SELECT hash FROM articles
        WHERE (texto_bruto IS NULL OR length(texto_bruto) < 50)
          AND hash IS NOT NULL
    """)
    pendentes = {row[0] for row in cur.fetchall()}
    log.info(f"  Hashes pendentes: {len(pendentes):,}")

    if not pendentes:
        set_estado(conn, 1, status="done", concluido_em=agora_iso(),
                   observacoes="Nada a fazer")
        return

    parquets = sorted(glob.glob(os.path.join(DADOS_DIR, "*.parquet")))
    if not parquets:
        log.error(f"  Nenhum parquet em {DADOS_DIR}")
        set_estado(conn, 1, status="erro",
                   observacoes="sem parquets")
        return

    log.info(f"  {len(parquets)} parquets para varrer")
    set_estado(conn, 1, status="running", iniciado_em=agora_iso(),
               total=len(pendentes))

    t0 = time.time()
    total_ok = 0

    # Processa 1 parquet por vez com workers paralelos nas linhas
    for i, path in enumerate(parquets, 1):
        nome = os.path.basename(path)

        # Cada worker recebe o parquet inteiro + o set de hashes pendentes
        # (o set é copiado via pickle; ~10 MB por worker, aceitável)
        chunk = (path, pendentes)
        try:
            resultados = _fase1_worker(chunk)
        except Exception as e:
            log.error(f"  [{i}/{len(parquets)}] {nome}: {e}")
            continue

        buffer = []
        for texto, h in resultados:
            if texto == "__ERRO__":
                log.error(f"  {h}")
                continue
            buffer.append((texto, h))
            pendentes.discard(h)

        if buffer:
            cur.executemany("""
                UPDATE articles SET texto_bruto = ? WHERE hash = ?
            """, buffer)
            conn.commit()
            total_ok += len(buffer)

        dt = time.time() - t0
        eta = dt / i * (len(parquets) - i) if i else 0
        log.info(f"  [{i}/{len(parquets)}] {nome}: +{len(buffer)} "
                 f"| total {total_ok:,} | faltam {len(pendentes):,} "
                 f"| ETA {eta/60:.1f}min")

        set_estado(conn, 1, processados=total_ok)

        if not pendentes:
            break

    set_estado(conn, 1, status="done", concluido_em=agora_iso(),
               processados=total_ok)
    log.info(f"  [FASE 1] concluída em {(time.time()-t0)/60:.1f} min "
             f"| recuperados {total_ok:,}")


# ========================= FASE 2 — Limpeza =========================

def _fase2_worker(lote):
    import trafilatura
    resultados = []
    for id_, texto_bruto, url in lote:
        try:
            limpo = trafilatura.extract(
                texto_bruto,
                url=url,
                include_comments=False,
                include_tables=False,
                include_links=False,
                include_formatting=False,
                favor_precision=True,
                target_language="pt",
                deduplicate=True,
            )
        except Exception:
            limpo = None

        # Fallback heurístico se Trafilatura falhar
        if not limpo or len(limpo) < 100:
            t = texto_bruto or ""
            t = re.sub(r"https?://\S+", "", t)
            t = re.sub(r"\S+@\S+\.\S+", "", t)
            t = re.sub(r"\s+", " ", t).strip()
            limpo = t if len(t) > 100 else (texto_bruto or "")

        resultados.append((limpo, id_))
    return resultados


def fase2_limpeza(conn, n_workers):
    log.info("=" * 70)
    log.info("FASE 2 — Limpeza com Trafilatura")
    log.info("=" * 70)

    cur = conn.cursor()
    cur.execute("""
        SELECT id, texto_bruto, url FROM articles
        WHERE processed_at_limpeza IS NULL
          AND texto_bruto IS NOT NULL
          AND length(texto_bruto) >= 100
    """)
    rows = cur.fetchall()
    total = len(rows)

    if not total:
        set_estado(conn, 2, status="done", concluido_em=agora_iso())
        return

    log.info(f"  {total:,} artigos para limpar | {n_workers} workers")
    set_estado(conn, 2, status="running", iniciado_em=agora_iso(),
               total=total)

    t0 = time.time()
    processados = 0
    lote_size = 500

    with mp.Pool(n_workers) as pool:
        for i in range(0, total, lote_size):
            lote = rows[i:i+lote_size]
            try:
                resultados = pool.apply(_fase2_worker, (lote,))
            except Exception as e:
                log.error(f"  lote {i}: {e}")
                continue

            cur.executemany("""
                UPDATE articles SET
                    texto_limpo = ?,
                    processed_at_limpeza = ?,
                    limpeza_versao = ?
                WHERE id = ?
            """, [(limpo, agora_iso(), "trafilatura-precision", id_)
                  for limpo, id_ in resultados])

            conn.commit()
            processados += len(resultados)

            dt = time.time() - t0
            eta = dt / processados * (total - processados) if processados else 0
            if i % (lote_size * 4) == 0:
                log.info(f"  [{processados:,}/{total:,}] ETA {eta/60:.1f}min")
                set_estado(conn, 2, processados=processados)

    # Recalcula Bolsonaro com base no texto limpo
    log.info("  Recalculando relevance_bolsonaro...")
    _recalcular_bolsonaro(conn)

    set_estado(conn, 2, status="done", concluido_em=agora_iso(),
               processados=processados)
    log.info(f"  [FASE 2] concluída em {(time.time()-t0)/60:.1f} min")


def _recalcular_bolsonaro(conn):
    """Recalcula mention/relevance para todos os artigos."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, titulo, texto_limpo, entidades_per, entidades_org
        FROM articles
    """)
    rows = cur.fetchall()
    log.info(f"  {len(rows):,} artigos para reclassificar")

    buffer = []
    for id_, titulo, texto, per_json, org_json in rows:
        try:
            per = {p.lower() for p in (json.loads(per_json) if per_json else [])}
            org = {o.lower() for o in (json.loads(org_json) if org_json else [])}
        except Exception:
            per, org = set(), set()

        titulo_l = (titulo or "").lower()
        texto_l = (texto or "").lower()[:10000]
        corpo = titulo_l + " " + texto_l

        score = 0.0
        if RE_BOLSONARO.search(titulo_l):
            score += 5.0
        if RE_BOLSONARO.search(texto_l[:2000]):
            score += 2.0
        per_match = per & PER_BOLSONARO
        if per_match:
            if any("bolsonaro" in p for p in per_match):
                score += 3.0
            else:
                score += 1.5
        score += min(2.0, len(org & ORG_GOVERNO) * 0.7)
        score += min(3.0, sum(1 for t in TERMOS_CONTEXTO if t in titulo_l) * 1.5)
        score += min(2.0, sum(1 for t in TERMOS_CONTEXTO if t in texto_l[:5000]) * 0.3)

        mention = 1 if score >= 1.0 else 0
        relevance = 1 if score >= 5.0 else 0

        buffer.append((mention, relevance, round(score, 2), id_))

        if len(buffer) >= 5000:
            cur.executemany("""
                UPDATE articles SET
                    mention_bolsonaro = ?,
                    relevance_bolsonaro = ?,
                    bolsonaro_score = ?
                WHERE id = ?
            """, buffer)
            conn.commit()
            buffer.clear()

    if buffer:
        cur.executemany("""
            UPDATE articles SET
                mention_bolsonaro = ?,
                relevance_bolsonaro = ?,
                bolsonaro_score = ?
            WHERE id = ?
        """, buffer)
        conn.commit()

    # Recalcula quality_score baseado no texto_limpo
    cur.execute("""
        UPDATE articles SET quality_score = (
            MIN(1.0,
                CASE
                    WHEN length(texto_limpo) >= 3000 THEN 0.4
                    WHEN length(texto_limpo) >= 1500 THEN 0.3
                    WHEN length(texto_limpo) >= 500  THEN 0.15
                    ELSE 0.05
                END
                + CASE
                    WHEN length(titulo) >= 30 THEN 0.2
                    WHEN length(titulo) >= 15 THEN 0.1
                    ELSE 0
                END
                + CASE
                    WHEN length(resumo) >= 100 THEN 0.2
                    WHEN length(resumo) >= 50  THEN 0.1
                    ELSE 0
                END
                + CASE WHEN autor IS NOT NULL AND length(autor) > 2 THEN 0.1 ELSE 0 END
                + CASE WHEN categoria != 'outros' THEN 0.1 ELSE 0 END
            )
        )
    """)
    conn.commit()


# ========================= FASE 3 — Sentimento =========================

_SENT_PIPE = None


def _init_sentimento():
    global _SENT_PIPE
    import torch
    torch.set_num_threads(TORCH_THREADS_PER_WORKER)
    from transformers import pipeline
    try:
        _SENT_PIPE = pipeline(
            "sentiment-analysis",
            model=MODEL_SENTIMENTO,
            device=-1,
            top_k=None,
        )
        # Força o limite na tokenizer (evita o buffer de posição estourar)
        _SENT_PIPE.tokenizer.model_max_length = 126
        log.info(f"[worker] sentimento carregado: {MODEL_SENTIMENTO}")
    except Exception as e:
        log.error(f"[worker] erro carregando sentimento: {e}")
        _SENT_PIPE = None


def _fase3_worker(lote):
    """
    lote: lista de (id, texto).
    Com top_k=None, o pipeline retorna lista de 3 dicts:
        [{"label":"POS","score":0.99}, {"label":"NEU","score":0.006}, {"label":"NEG","score":0.001}]
    Retorna: lista de (id, label, compound, pos, neg, neu)
    compound = pos - neg (igual ao padrão VADER/LeIA)
    """
    if _SENT_PIPE is None:
        return []

    textos = [t[:2000] if t else "" for _, t in lote]
    try:
        results = _SENT_PIPE(
            textos,
            truncation=True,
            max_length=126,   # 126 + 2 speciais = 128 < 130
            padding=False,
        )
    except Exception as e:
        log.error(f"[worker] erro inferência: {e}")
        return []

    out = []
    for (id_, _), r in zip(lote, results):
        # r é uma lista de 3 dicts. Extrai scores por label.
        scores = {"POS": 0.0, "NEG": 0.0, "NEU": 0.0}
        for item in r:
            lab = (item.get("label") or "").upper()
            if lab in scores:
                scores[lab] = float(item.get("score") or 0.0)

        pos, neg, neu = scores["POS"], scores["NEG"], scores["NEU"]
        compound = pos - neg   # equivalente a VADER: -1..1

        # Label final: maior probabilidade
        maior = max((pos, "positivo"), (neg, "negativo"), (neu, "neutro"))
        label = maior[1]

        out.append((id_, label, round(compound, 4),
                    round(pos, 4), round(neg, 4), round(neu, 4)))
    return out

def fase3_sentimento(conn, n_workers):
    log.info("=" * 70)
    log.info("FASE 3 — Sentimento com BERTimbau")
    log.info("=" * 70)

    cur = conn.cursor()
    cur.execute("""
        SELECT id, texto_limpo FROM articles
        WHERE processed_at_sentimento IS NULL
            AND texto_limpo IS NOT NULL
            AND length(texto_limpo) >= 100
            AND (mention_bolsonaro = 1 OR relevance_bolsonaro = 1)
    """)
    rows = cur.fetchall()
    total = len(rows)

    if not total:
        set_estado(conn, 3, status="done", concluido_em=agora_iso())
        return

    log.info(f"  {total:,} artigos | {n_workers} workers")
    log.info(f"  Modelo: {MODEL_SENTIMENTO}")

    set_estado(conn, 3, status="running", iniciado_em=agora_iso(), total=total)

    t0 = time.time()
    processados = 0
    lote_size = BATCH_BERT * n_workers

    with mp.Pool(n_workers, initializer=_init_sentimento) as pool:
        for i in range(0, total, lote_size):
            lote = rows[i:i+lote_size]
            try:
                resultados = pool.apply(_fase3_worker, (lote,))
            except Exception as e:
                log.error(f"  lote {i}: {e}")
                continue

            cur.executemany("""
                UPDATE articles SET
                    sentimento_label = ?,
                    sentimento_compound = ?,
                    sentimento_pos = ?,
                    sentimento_neg = ?,
                    sentimento_neu = ?,
                    model_version_sentimento = ?,
                    processed_at_sentimento = ?
                WHERE id = ?
            """, [(l, s, p, n, u, MODEL_SENTIMENTO, agora_iso(), id_)
                  for id_, l, s, p, n, u in resultados])

            conn.commit()
            processados += len(resultados)

            dt = time.time() - t0
            taxa = processados / dt if dt else 0
            eta = (total - processados) / taxa if taxa else 0

            if i % (lote_size * 4) == 0:
                log.info(f"  [{processados:,}/{total:,}] "
                         f"{taxa:.1f}/s | ETA {eta/60:.1f}min")
                set_estado(conn, 3, processados=processados)

    set_estado(conn, 3, status="done", concluido_em=agora_iso(),
               processados=processados)
    log.info(f"  [FASE 3] concluída em {(time.time()-t0)/60:.1f} min")


# ========================= FASE 4 — NER =========================

_NER_PIPE = None

def _init_ner():
    global _NER_PIPE
    import torch
    torch.set_num_threads(TORCH_THREADS_PER_WORKER)
    from transformers import pipeline
    try:
        _NER_PIPE = pipeline(
            "ner",
            model=MODEL_NER,
            device=-1,
            aggregation_strategy="first",   # agrupa subwords no primeiro token
        )
        log.info(f"[worker] NER carregado: {MODEL_NER}")
    except Exception as e:
        log.error(f"[worker] erro carregando NER: {e}")
        _NER_PIPE = None


# Filtros de qualidade para entidades
_BLACKLIST_ENT = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "a", "o", "e",
    "casa", "un", "i", "p", "b", "fi", "rece", "de", "i",
    "avenida", "rua", "bairro",
}
_PREFIXOS_RUIDO = ("##", "##")

def _limpar_entidade(w):
    """Remove fragmentos e termos genéricos. Retorna None se rejeitar."""
    if not w:
        return None
    w = w.strip()
    # Fragmentos WordPiece
    if w.startswith("##"):
        return None
    # Muito curto
    if len(w) < 4:
        return None
    # Muito longo (provavelmente capturou frase inteira)
    if len(w) > 60:
        return None
    # Blacklist exata
    if w.lower() in _BLACKLIST_ENT:
        return None
    # Só números
    if w.isdigit():
        return None
    return w


def _fase4_worker(lote):
    """lote: lista de (id, texto). Retorna lista de (id, per, org, loc, misc)."""
    if _NER_PIPE is None:
        return []
    out = []
    for id_, texto in lote:
        try:
            ents = _NER_PIPE(texto[:2000])
        except Exception:
            ents = []
        per, org, loc, misc = set(), set(), set(), set()
        for e in ents:
            g = (e.get("entity_group") or "").upper()
            w = _limpar_entidade(e.get("word") or "")
            if w is None:
                continue
                        # Mapeamento HAREM (pt) → padrão CoNLL
            g_low = g.lower()
            if g_low in ("pessoa", "per"):
                per.add(w)
            elif g_low in ("organizacao", "organização", "org"):
                org.add(w)
            elif g_low in ("local", "loc", "lugar"):
                loc.add(w)
            elif g_low in ("misc", "outro", "obra", "acontecimento",
                           "coisa", "abstrato", "tempo", "valor"):
                misc.add(w)
                
        out.append((
            id_,
            json.dumps(sorted(per)[:25], ensure_ascii=False) if per else None,
            json.dumps(sorted(org)[:25], ensure_ascii=False) if org else None,
            json.dumps(sorted(loc)[:25], ensure_ascii=False) if loc else None,
            json.dumps(sorted(misc)[:25], ensure_ascii=False) if misc else None,
        ))
    return out

def fase4_ner(conn, n_workers):
    log.info("=" * 70)
    log.info("FASE 4 — NER com BERTimbau HAREM")
    log.info("=" * 70)

    cur = conn.cursor()
    cur.execute("""
        SELECT id, texto_limpo FROM articles
        WHERE processed_at_ner IS NULL
          AND texto_limpo IS NOT NULL
          AND length(texto_limpo) >= 100
          AND (mention_bolsonaro = 1 OR relevance_bolsonaro = 1)
    """)
    rows = cur.fetchall()
    total = len(rows)

    if not total:
        set_estado(conn, 4, status="done", concluido_em=agora_iso())
        return

    log.info(f"  {total:,} artigos | {n_workers} workers")
    log.info(f"  Modelo: {MODEL_NER}")

    set_estado(conn, 4, status="running", iniciado_em=agora_iso(), total=total)

    t0 = time.time()
    processados = 0
    lote_size = BATCH_BERT * n_workers

    with mp.Pool(n_workers, initializer=_init_ner) as pool:
        for i in range(0, total, lote_size):
            lote = rows[i:i+lote_size]
            try:
                resultados = pool.apply(_fase4_worker, (lote,))
            except Exception as e:
                log.error(f"  lote {i}: {e}")
                continue

            cur.executemany("""
                UPDATE articles SET
                    entidades_per = ?,
                    entidades_org = ?,
                    entidades_loc = ?,
                    entidades_misc = ?,
                    model_version_ner = ?,
                    processed_at_ner = ?
                WHERE id = ?
            """, [(p, o, l, m, MODEL_NER, agora_iso(), id_)
                  for id_, p, o, l, m in resultados])

            conn.commit()
            processados += len(resultados)

            dt = time.time() - t0
            taxa = processados / dt if dt else 0
            eta = (total - processados) / taxa if taxa else 0

            if i % (lote_size * 4) == 0:
                log.info(f"  [{processados:,}/{total:,}] "
                         f"{taxa:.1f}/s | ETA {eta/60:.1f}min")
                set_estado(conn, 4, processados=processados)

    # Recalcula Bolsonaro com as novas entidades
    log.info("  Recalculando relevance com entidades atualizadas...")
    _recalcular_bolsonaro(conn)

    set_estado(conn, 4, status="done", concluido_em=agora_iso(),
               processados=processados)
    log.info(f"  [FASE 4] concluída em {(time.time()-t0)/60:.1f} min")


# ========================= FASE 5 — Tópicos (BERTopic) =========================

def fase5_topicos(conn):
    log.info("=" * 70)
    log.info("FASE 5 — Tópicos com BERTopic")
    log.info("=" * 70)

    try:
        from bertopic import BERTopic
        from sentence_transformers import SentenceTransformer
        from sklearn.feature_extraction.text import CountVectorizer
    except ImportError as e:
        log.error(f"  Importação falhou: {e}")
        set_estado(conn, 5, status="erro",
                   observacoes=f"import: {e}")
        return

    cur = conn.cursor()
    cur.execute("""
        SELECT id, titulo, resumo FROM articles
        WHERE relevance_bolsonaro = 1
           OR (mention_bolsonaro = 1 AND quality_score >= 0.5)
    """)
    rows = cur.fetchall()
    total = len(rows)

    if total < 100:
        log.warning(f"  Apenas {total} docs — pulando BERTopic")
        set_estado(conn, 5, status="done",
                   observacoes=f"corpus pequeno ({total})",
                   concluido_em=agora_iso())
        return

    log.info(f"  {total:,} documentos para BERTopic")
    set_estado(conn, 5, status="running", iniciado_em=agora_iso(), total=total)

    ids = [r[0] for r in rows]
    docs = [
        ((r[1] or "") + ". " + (r[2] or ""))[:1000]
        for r in rows
    ]

    t0 = time.time()

    log.info(f"  Carregando embeddings ({MODEL_EMBEDDINGS})...")
    try:
        embedding = SentenceTransformer(MODEL_EMBEDDINGS)
    except Exception as e:
        log.error(f"  Erro embeddings: {e}")
        set_estado(conn, 5, status="erro", observacoes=str(e))
        return

    # Vetorização para português
    vectorizer = CountVectorizer(
        stop_words=[
            "a", "o", "e", "de", "da", "do", "das", "dos", "em", "no",
            "na", "nos", "nas", "um", "uma", "para", "por", "com", "sem",
            "que", "qual", "quais", "quando", "onde", "como", "porque",
            "se", "ao", "aos", "à", "às", "é", "são", "foi", "foram",
            "ser", "está", "estão", "ter", "tem", "tinha", "mais", "menos",
        ],
        ngram_range=(1, 2),
        min_df=3,
    )

    log.info("  Treinando BERTopic...")
    try:
        topic_model = BERTopic(
            embedding_model=embedding,
            vectorizer_model=vectorizer,
            language="portuguese",
            nr_topics="auto",
            min_topic_size=15,
            calculate_probabilities=False,
            verbose=True,
        )
        topicos, _ = topic_model.fit_transform(docs)
    except Exception as e:
        log.error(f"  BERTopic falhou: {e}")
        log.debug(traceback.format_exc())
        set_estado(conn, 5, status="erro", observacoes=str(e))
        return

    # Info dos tópicos
    info = topic_model.get_topic_info()
    topicos_meta = {}
    for _, row in info.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            continue
        words = topic_model.get_topic(tid) or []
        topicos_meta[str(tid)] = [w[0] for w in words[:10]]

    # Atualiza banco
    log.info("  Salvando tópicos no banco...")
    buffer = []
    for id_, tid in zip(ids, topicos):
        tid_int = int(tid)
        palavras = topicos_meta.get(str(tid_int), [])
        buffer.append((
            tid_int if tid_int >= 0 else None,
            json.dumps(palavras, ensure_ascii=False) if palavras else None,
            "bertopic-minilm-v1",
            agora_iso(),
            id_,
        ))
        if len(buffer) >= 5000:
            cur.executemany("""
                UPDATE articles SET
                    topico_id = ?,
                    topico_palavras = ?,
                    model_version_topicos = ?,
                    processed_at_topicos = ?
                WHERE id = ?
            """, buffer)
            conn.commit()
            buffer.clear()

    if buffer:
        cur.executemany("""
            UPDATE articles SET
                topico_id = ?,
                topico_palavras = ?,
                model_version_topicos = ?,
                processed_at_topicos = ?
            WHERE id = ?
        """, buffer)
        conn.commit()

    # Salva metadados
    with open("_topicos.json", "w", encoding="utf-8") as f:
        json.dump({
            "n_topicos": len(topicos_meta),
            "modelo": "bertopic-minilm",
            "topicos": topicos_meta,
        }, f, ensure_ascii=False, indent=2)

    set_estado(conn, 5, status="done", concluido_em=agora_iso(),
               processados=total)
    log.info(f"  [FASE 5] concluída em {(time.time()-t0)/60:.1f} min "
             f"| {len(topicos_meta)} tópicos")


# ========================= FASE 6 — FTS5 + Stats =========================

def fase6_fts(conn):
    log.info("=" * 70)
    log.info("FASE 6 — Rebuild FTS5 + estatísticas")
    log.info("=" * 70)

    cur = conn.cursor()
    t0 = time.time()

    log.info("  Rebuild FTS5...")
    cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
    conn.commit()

    log.info("  Otimizando banco...")
    cur.execute("ANALYZE")
    cur.execute("PRAGMA optimize")
    conn.commit()

    # Estatísticas finais
    stats = {}
    for label, q in [
        ("total", "SELECT COUNT(*) FROM articles"),
        ("com_texto_limpo", "SELECT COUNT(*) FROM articles WHERE texto_limpo IS NOT NULL"),
        ("mention_bolsonaro", "SELECT COUNT(*) FROM articles WHERE mention_bolsonaro=1"),
        ("relevance_bolsonaro", "SELECT COUNT(*) FROM articles WHERE relevance_bolsonaro=1"),
        ("sentimento_ok", "SELECT COUNT(*) FROM articles WHERE processed_at_sentimento IS NOT NULL"),
        ("ner_ok", "SELECT COUNT(*) FROM articles WHERE processed_at_ner IS NOT NULL"),
        ("topicos_ok", "SELECT COUNT(*) FROM articles WHERE processed_at_topicos IS NOT NULL"),
    ]:
        stats[label] = cur.execute(q).fetchone()[0]

    with open("_stats_final.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    log.info(f"  Estatísticas finais:")
    for k, v in stats.items():
        log.info(f"    {k:<25} {v:>10,}")

    set_estado(conn, 6, status="done", concluido_em=agora_iso())
    log.info(f"  [FASE 6] concluída em {(time.time()-t0)/60:.1f} min")


# ========================= ORQUESTRADOR =========================

FASES = {
    1: ("Recuperar texto_bruto", fase1_recuperar_texto, True),
    2: ("Limpeza Trafilatura",   fase2_limpeza,          True),
    3: ("Sentimento BERT",       fase3_sentimento,       True),
    4: ("NER BERT",              fase4_ner,              True),
    5: ("Tópicos BERTopic",      fase5_topicos,          False),
    6: ("FTS5 + Stats",          fase6_fts,              False),
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--apenas-fase", type=int, default=0,
                   help="Executa só esta fase")
    p.add_argument("--reset-fase", type=int, default=0,
                   help="Apaga estado desta fase e refaz")
    p.add_argument("--reset-tudo", action="store_true",
                   help="Apaga estado de todas as fases")
    p.add_argument("--workers-texto", type=int, default=N_WORKERS_TEXTO)
    p.add_argument("--workers-bert", type=int, default=N_WORKERS_BERT)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def pre_check():
    """Verificações antes de rodar."""
    log.info("=" * 70)
    log.info("PRÉ-CHECAGEM")
    log.info("=" * 70)

    ok = True

    if not os.path.exists(DB_FILE):
        log.error(f"  [X] {DB_FILE} não existe")
        ok = False
    else:
        conn = sqlite3.connect(DB_FILE)
        n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        conn.close()
        log.info(f"  [OK] {DB_FILE} — {n:,} artigos")

    parquets = glob.glob(os.path.join(DADOS_DIR, "*.parquet"))
    if not parquets:
        log.error(f"  [X] Nenhum parquet em {DADOS_DIR}")
        ok = False
    else:
        log.info(f"  [OK] {len(parquets)} parquets")

    # Python
    log.info(f"  Python: {sys.version.split()[0]}")

    return ok
def ensure_columns(conn):
    """
    Garante que todas as colunas usadas pelo pipeline existam.
    SQLite não tem ADD COLUMN IF NOT EXISTS, então usamos try/except.
    """
    colunas = [
        ("texto_bruto",            "TEXT"),
        ("texto_limpo",            "TEXT"),
        ("processed_at_limpeza",   "TEXT"),
        ("limpeza_versao",         "TEXT"),
        ("processed_at_sentimento","TEXT"),
        ("processed_at_ner",       "TEXT"),
        ("processed_at_topicos",   "TEXT"),
        ("model_version_sentimento","TEXT"),
        ("model_version_ner",      "TEXT"),
        ("model_version_topicos",  "TEXT"),
        ("mention_bolsonaro",      "INTEGER DEFAULT 0"),
        ("relevance_bolsonaro",    "INTEGER DEFAULT 0"),
        ("bolsonaro_score",        "REAL DEFAULT 0"),
        ("quality_score",          "REAL DEFAULT 0"),
        ("status",                 "TEXT DEFAULT 'accepted'"),
    ]
    cur = conn.cursor()
    criadas = []
    for nome, tipo in colunas:
        try:
            cur.execute(f"ALTER TABLE articles ADD COLUMN {nome} {tipo}")
            criadas.append(nome)
        except sqlite3.OperationalError:
            pass  # já existe
    conn.commit()
    if criadas:
        log.info(f"  Colunas criadas: {', '.join(criadas)}")



def main():
    args = parse_args()
    setup_log(args.verbose)

    log.info("=" * 70)
    log.info("PIPELINE COMPLETO — Corpus Bolsonaro 2019-2022")
    log.info(f"Início: {agora_iso()}")
    log.info("=" * 70)

    if not pre_check():
        log.error("Pré-checagem falhou. Abortando.")
        sys.exit(1)

    conn = db_conn()
    init_state_table(conn)
    ensure_columns(conn)      # <-- ADICIONE ESTA LINHA
    

    # Reset
    if args.reset_tudo:
        log.warning("  --reset-tudo: apagando estado de todas as fases")
        for fase in FASES:
            reset_fase(conn, fase)

    if args.reset_fase:
        log.warning(f"  --reset-fase {args.reset_fase}")
        reset_fase(conn, args.reset_fase)

    t0 = time.time()

    # Executa fases
    fases_a_rodar = (
        [args.apenas_fase] if args.apenas_fase else list(FASES.keys())
    )

    for fase in fases_a_rodar:
        nome, func, usa_workers = FASES[fase]
        estado = get_estado(conn, fase)
        status = estado[0] if estado else "pending"

        if status == "done" and not args.reset_fase:
            log.info(f"\n[FASE {fase}] {nome} — JÁ CONCLUÍDA, pulando")
            continue

        log.info("")
        try:
            if usa_workers:
                n_workers = args.workers_texto if fase <= 2 else args.workers_bert
                func(conn, n_workers)
            else:
                func(conn)
        except KeyboardInterrupt:
            log.warning(f"\n[FASE {fase}] interrompida pelo usuário")
            set_estado(conn, fase, status="interrompida",
                       observacoes="Ctrl+C")
            break
        except Exception as e:
            log.error(f"\n[FASE {fase}] ERRO FATAL: {e}")
            log.debug(traceback.format_exc())
            set_estado(conn, fase, status="erro", observacoes=str(e)[:500])
            # Continua para a próxima fase se não for crítica
            if fase <= 2:
                log.error("  Fase crítica falhou — abortando")
                break
            else:
                log.warning("  Fase não crítica — pulando para a próxima")

    dt = time.time() - t0

    # Relatório final
    log.info("")
    log.info("=" * 70)
    log.info(f"PIPELINE CONCLUÍDO em {dt/60:.1f} min ({dt/3600:.2f}h)")
    log.info("=" * 70)

    log.info("\nEstado das fases:")
    for fase in sorted(FASES.keys()):
        nome, _, _ = FASES[fase]
        estado = get_estado(conn, fase)
        if estado:
            status, proc, tot = estado
            log.info(f"  Fase {fase} [{nome}]: {status} "
                     f"({proc:,}/{tot or 0:,})")

    conn.close()


if __name__ == "__main__":
    main()