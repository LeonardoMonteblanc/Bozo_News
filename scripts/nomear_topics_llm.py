"""
Gera nomes curados via LLM (few-shot) para os tópicos consolidados.

Saída: cc_news_pt/_topicos_v4.json + corpus.db atualizado
"""

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from src.paths import PROJECT_ROOT, DB_FILE
import os as _os
_os.chdir(PROJECT_ROOT)
import json
import time
import sqlite3
import requests
from datetime import datetime


# ========================= CONFIG =========================

DB_FILE = str(DB_FILE)
INPUT = "cc_news_pt/_topicos_v3.json"
OUTPUT = "cc_news_pt/_topicos_v4.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"
TIMEOUT = 180


# ========================= PROMPT FEW-SHOT =========================

PROMPT_BASE = """Você nomeia tópicos de notícias brasileiras. Dado um conjunto de palavras-chave, responda com um nome curto de 2 a 5 palavras EM PORTUGUÊS NATURAL, separadas por espaço.

REGRAS OBRIGATÓRIAS:
1. Use espaços entre as palavras. NUNCA concatene (ex: escreva "Lula e o PT", não "LulaPt").
2. Use apenas palavras do vocabulário fornecido. NUNCA invente termos.
3. Se for sobre uma pessoa, use "Nome Sobrenome" (ex: "Sergio Moro").
4. Máximo 5 palavras.
5. Sem pontuação no final. Sem explicações.

EXEMPLOS:

Palavras: vacinação, covid, vacina, doses, pandemia, mortes
Nome: Pandemia e vacinação

Palavras: lula, pt, inácio, lula silva, luiz inácio
Nome: Lula e o PT

Palavras: stf, supremo, flávio, tribunal, flávio bolsonaro
Nome: STF e Flávio Bolsonaro

Palavras: petrobras, preço, gasolina, combustíveis, gás
Nome: Combustíveis e Petrobras

Palavras: moro, sergio moro, ex, justiça, sérgio
Nome: Sergio Moro e Justiça

Palavras: manifestantes, manifestações, ato, atos, protestos
Nome: Manifestações políticas

Palavras: fake, news, whatsapp, falsas, redes
Nome: Fake news e redes sociais

AGORA:

Palavras: {palavras}
Nome:"""


# ========================= OLLAMA =========================

def nomear_com_llm(palavras, tentativas=3):
    prompt = PROMPT_BASE.format(palavras=", ".join(palavras[:12]))

    for i in range(tentativas):
        try:
            r = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_predict": 30,
                        "stop": ["\n", ".", "Palavras:", "Nome:"],
                    },
                },
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                texto = r.json().get("response", "").strip()
                texto = texto.split("\n")[0].strip().strip('"').strip(".")
                # Valida: tem espaço E tamanho razoável
                if texto and " " in texto and 5 <= len(texto) <= 60:
                    return texto
                print(f"        [tentativa {i+1}] inválido: '{texto}'")
        except Exception as e:
            print(f"        [tentativa {i+1}] erro: {e}")
            time.sleep(3)
    return None


# ========================= MAIN =========================

def main():
    print("[1] Carregando tópicos consolidados...")
    with open(INPUT, encoding="utf-8") as f:
        dados = json.load(f)

    topicos = dados["topicos"]
    print(f"    {len(topicos)} tópicos")

    print(f"\n[2] Gerando nomes via {OLLAMA_MODEL}...")
    t0 = time.time()

    resultado = {}
    for tid_str, meta in sorted(topicos.items(), key=lambda x: -x[1]["total"]):
        tid = int(tid_str)
        palavras = meta.get("palavras_bertopic", [])[:12]
        print(f"\n    T{tid} ({meta['total']:>5} artigos): {', '.join(palavras[:6])}...")

        nome = nomear_com_llm(palavras)
        if nome:
            print(f"        → \"{nome}\"")
        else:
            nome = meta.get("nome", f"Tópico {tid}")
            print(f"        → fallback: \"{nome}\"")

        resultado[tid_str] = {
            "id": tid,
            "nome": nome,
            "total": meta["total"],
            "palavras_bertopic": palavras,
            "topicos_originais": meta.get("topicos_originais", []),
        }

    dt = time.time() - t0
    print(f"\n    Concluído em {dt/60:.1f} min")

    # Salva JSON
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({
            "versao": "bertopic-v2-consolidado-llm-7b",
            "modelo_llm": OLLAMA_MODEL,
            "n_topicos": len(resultado),
            "topicos": resultado,
            "gerado_em": datetime.utcnow().isoformat(),
        }, f, ensure_ascii=False, indent=2)

    # Atualiza corpus.db (topico_nome_v3)
    print("\n[3] Atualizando corpus.db...")
    conn = sqlite3.connect(DB_FILE, timeout=60)
    cur = conn.cursor()

    for tid_str, meta in resultado.items():
        cur.execute(
            "UPDATE articles SET topico_nome_v3 = ? WHERE topico_id_v3 = ?",
            (meta["nome"], meta["id"]),
        )

    conn.commit()
    conn.close()

    # Resumo
    print("\n" + "=" * 70)
    print("[FIM] Tópicos com nomes curados pelo LLM 7B:")
    print("=" * 70)
    for tid_str, meta in sorted(resultado.items(), key=lambda x: -x[1]["total"]):
        print(f"  T{meta['id']:>3} ({meta['total']:>5}) — {meta['nome']}")
    print("=" * 70)


if __name__ == "__main__":
    main()