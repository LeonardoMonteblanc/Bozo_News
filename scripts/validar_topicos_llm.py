"""
Agente validador de tópicos — versão sem framework.

Usa Ollama local via HTTP direto. Simula o padrão "crew" com dois papéis:
- Validador: avalia cada tópico
- Auditor: consolida veredito

Saída: _validacao_llm.json
"""
import json
import time
import sqlite3
import requests
from datetime import datetime

# ========================= CONFIG =========================

DB_FILE = "corpus.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"
AMOSTRAS_POR_TOPICO = 30
TIMEOUT = 240  # 4 min por chamada (7B em CPU é lento)

TOPICOS_ALVO = [100, 11, 13, 9, 1, 5, 4, 7, 3, 12, 10, 8]


# ========================= PROMPTS =========================

PROMPT_VALIDADOR = """Você é um analista editorial experiente avaliando a coerência de um tópico.

TÓPICO: "{nome}"

Abaixo estão {n} notícias amostradas. Avalie quantas realmente pertencem ao tópico.

Critérios:
- A notícia trata do tema central do tópico (não só menciona de passagem).
- Publicações genéricas ou periféricas não contam.

Responda EXATAMENTE neste formato:

SCORE: <número de 0 a {n}>
FORA: <até 3 títulos que claramente NÃO pertencem, ou "nenhuma">
AVALIACAO: <uma frase curta>

NOTÍCIAS:
{lista}"""


PROMPT_AUDITOR = """Você é um auditor que consolida avaliações de tópicos.

TÓPICO: "{nome}"

Relatório do validador:
{relatorio}

Classifique em um veredito. Responda EXATAMENTE neste formato:

VEREDITO: <manter|revisar|descartar>
JUSTIFICATIVA: <uma frase curta>

Regras:
- "manter" se score >= 60% das amostras
- "revisar" se score entre 30% e 60%
- "descartar" se score < 30%"""


# ========================= OLLAMA =========================

def chamar_llm(prompt, tentativas=3):
    for i in range(tentativas):
        try:
            r = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 400,
                    },
                },
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
        except Exception as e:
            print(f"      [tentativa {i+1}] erro: {e}")
            time.sleep(3)
    return ""


# ========================= AGENTES =========================

def agente_validador(nome, amostras):
    """Avalia quantas amostras pertencem ao tópico."""
    lista = "\n".join(
        f"{i+1}. [{a['data']}] {a['titulo']}"
        for i, a in enumerate(amostras)
    )
    prompt = PROMPT_VALIDADOR.format(
        nome=nome,
        n=len(amostras),
        lista=lista,
    )
    return chamar_llm(prompt)


def agente_auditor(nome, relatorio):
    """Consolida o veredito final."""
    prompt = PROMPT_AUDITOR.format(
        nome=nome,
        relatorio=relatorio[:3000],  # trunca para não estourar contexto
    )
    return chamar_llm(prompt)


# ========================= AMOSTRAGEM =========================

def amostrar_topicos():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    resultado = {}
    for tid in TOPICOS_ALVO:
        row = cur.execute(
            "SELECT topico_nome_v3 FROM articles WHERE topico_id_v3 = ? LIMIT 1",
            (tid,)
        ).fetchone()
        if not row:
            continue
        nome = row["topico_nome_v3"]

        total = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE topico_id_v3 = ?", (tid,)
        ).fetchone()[0]

        # Amostragem estratificada: início + meio + fim
        amostras = []
        pontos = [0, total // 3, 2 * total // 3]
        for p in pontos:
            rows = cur.execute("""
                SELECT id, data, titulo
                FROM articles
                WHERE topico_id_v3 = ?
                ORDER BY data
                LIMIT 10 OFFSET ?
            """, (tid, p)).fetchall()
            amostras.extend([dict(r) for r in rows])

        resultado[tid] = {
            "id": tid,
            "nome": nome,
            "total": total,
            "amostras": amostras[:AMOSTRAS_POR_TOPICO],
        }

    conn.close()
    return resultado


# ========================= PARSE =========================

def parse_score(texto):
    for linha in texto.split("\n"):
        l = linha.strip().upper()
        if l.startswith("SCORE:"):
            digits = "".join(c for c in l if c.isdigit())
            if digits:
                try:
                    return min(int(digits[:2]), AMOSTRAS_POR_TOPICO)
                except ValueError:
                    pass
    return None


def parse_veredito(texto):
    for linha in texto.split("\n"):
        l = linha.strip().upper()
        if l.startswith("VEREDITO:"):
            v = linha.split(":", 1)[1].strip().lower()
            if v in ("manter", "revisar", "descartar"):
                return v
    return "revisar"


# ========================= MAIN =========================

def main():
    print("[1] Amostrando tópicos...")
    dados = amostrar_topicos()
    total_noticias = sum(len(t["amostras"]) for t in dados.values())
    print(f"    {len(dados)} tópicos × até {AMOSTRAS_POR_TOPICO} amostras = "
          f"{total_noticias} notícias")

    resultado = {}
    t0 = time.time()

    for tid, info in dados.items():
        print(f"\n[{tid}] '{info['nome']}' ({info['total']} no total)")

        # Etapa 1 — Validador
        print(f"    → validador...")
        relatorio = agente_validador(info["nome"], info["amostras"])
        score = parse_score(relatorio)
        print(f"      score: {score}/{len(info['amostras'])}")

        # Etapa 2 — Auditor
        print(f"    → auditor...")
        auditoria = agente_auditor(info["nome"], relatorio)
        veredito = parse_veredito(auditoria)
        print(f"      veredito: {veredito}")

        # Flag para revisão humana
        limiar = len(info["amostras"]) * 0.6
        flaggado = (
            veredito != "manter"
            or (score is not None and score < limiar)
        )

        resultado[str(tid)] = {
            "id": tid,
            "nome": info["nome"],
            "total": info["total"],
            "amostras": info["amostras"],
            "score_llm": score,
            "score_max": len(info["amostras"]),
            "veredito": veredito,
            "relatorio_validador": relatorio,
            "relatorio_auditor": auditoria,
            "flaggado": flaggado,
        }

        dt = time.time() - t0
        print(f"    ({dt/60:.1f} min acumulado)")

    with open("_validacao_llm.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    n_flag = sum(1 for r in resultado.values() if r["flaggado"])
    print(f"\n[FIM] {len(resultado)} tópicos em {(time.time()-t0)/60:.1f} min")
    print(f"      {n_flag} flaggados para revisão humana")
    print(f"      → _validacao_llm.json")


if __name__ == "__main__":
    main()