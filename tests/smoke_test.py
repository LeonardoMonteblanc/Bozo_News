"""
Smoke test da API local — valida os 9 endpoints antes de qualquer mudança.
"""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

TESTES = [
    ("GET", "/health",                      None, ["status", "artigos_no_banco"]),
    ("GET", "/api/categorias",              None, "list"),
    ("GET", "/api/dominios?limite=5",       None, "list"),
    ("GET", "/api/timeline",                None, "list"),
    ("GET", "/api/topicos",                 None, "list"),
    ("GET", "/api/entidades?limite=5",      None, ["per", "org"]),
    ("GET", "/api/rede?limite=10",          None, ["nos", "arestas"]),
    ("GET", "/api/noticias?limit=3",        None, ["total", "itens"]),
    ("GET", "/api/noticias?q=cloroquina&limit=2", None, ["total", "itens"]),
]

def chamar(rota):
    try:
        with urllib.request.urlopen(BASE + rota, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 60)
    print("SMOKE TEST — API local")
    print("=" * 60)

    falhas = 0
    for metodo, rota, _, esperado in TESTES:
        status, corpo = chamar(rota)

        if status != 200:
            print(f"[X] {rota:<45} HTTP {status}")
            falhas += 1
            continue

        # Valida campos-chave
        if isinstance(esperado, list):
            faltando = [c for c in esperado if c not in corpo]
            if faltando:
                print(f"[X] {rota:<45} campos ausentes: {faltando}")
                falhas += 1
                continue

        # Valida se retornou dados
        n = None
        if isinstance(corpo, list):
            n = len(corpo)
        elif isinstance(corpo, dict) and "total" in corpo:
            n = corpo["total"]

        print(f"[OK] {rota:<45} {n if n is not None else 'ok'}")

    print("=" * 60)
    if falhas:
        print(f"[FALHA] {falhas}/{len(TESTES)} testes falharam")
        raise SystemExit(1)
    print(f"[PASS] {len(TESTES)}/{len(TESTES)} testes OK")

if __name__ == "__main__":
    main()