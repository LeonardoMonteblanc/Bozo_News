"""Cruza julgamentos humanos com validação do LLM."""

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
from src.paths import PROJECT_ROOT, DB_FILE
import os as _os
_os.chdir(PROJECT_ROOT)
import json

with open(PROJECT_ROOT / "data" / "_validacao_llm.json", encoding="utf-8") as f:
    llm = json.load(f)
with open(PROJECT_ROOT / "data" / "_validacao_humana.json", encoding="utf-8") as f:
    humano = json.load(f)

print(f"{'ID':<5} {'Nome':<40} {'Total':>7} {'Humano':<10} {'Ação'}")
print("-" * 90)

acoes = []
for tid, info in sorted(llm.items(), key=lambda x: -x[1]["total"]):
    j = humano.get(tid, {})
    julg = j.get("julgamento", "pendente")
    nome_novo = j.get("nome_alternativo", "")

    if julg == "correto":
        acao = "manter"
    elif julg == "parcial":
        acao = f"renomear → {nome_novo}" if nome_novo else "revisar"
    elif julg == "errado":
        acao = "DESMEMBRAR"
    else:
        acao = "pendente"

    acoes.append({
        "id": tid,
        "nome_atual": info["nome"],
        "nome_novo": nome_novo,
        "total": info["total"],
        "julgamento": julg,
        "acao": acao,
    })

    print(f"{tid:<5} {info['nome']:<40} {info['total']:>7,} {julg:<10} {acao}")

with open(PROJECT_ROOT / "data" / "_reconciliacao.json", "w", encoding="utf-8") as f:
    json.dump(acoes, f, ensure_ascii=False, indent=2)

print(f"\n[FIM] {len(acoes)} tópicos reconciliados → _reconciliacao.json")