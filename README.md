# Corpus Bolsonaro 2019-2022

Site público para consulta de notícias sobre o governo Bolsonaro (2019-2022).

## Visão geral

- **20.725 artigos** sobre Bolsonaro e o governo (subset do CC-News-PT v2)
- **Enriquecimento:** BERTweet-PT (sentimento), BERTimbau HAREM (NER), BERTopic (104 tópicos)
- **Stack local:** FastAPI + SQLite
- **Stack produção:** Cloudflare Workers + D1 + R2
- **Frontend:** HTML + Tailwind + Chart.js + vis-network + jsPDF

## Arquitetura
Navegador → Cloudflare Pages (frontend)
→ Cloudflare Worker (API)
→ D1 (metadados + FTS5)
→ R2 (textos completos)

## Estrutura

| Caminho | Função |
|---|---|
| `api.py` | API local (FastAPI) |
| `train.py` | Pipeline de processamento (6 fases) |
| `export_cloudflare.py` | Export SQLite → D1 + R2 |
| `index.html` | Frontend |
| `wrangler.toml` | Config Cloudflare |
| `urls.txt` | Lista de veículos-alvo |
| `tests/smoke_test.py` | Teste de fumaça da API |
| `_topicos.json` | Metadados dos tópicos BERTopic |
| `_stats_final.json` | Estatísticas do corpus |

## Pipeline (`train.py`)

1. **F1** Recuperar `texto_bruto` dos parquets
2. **F2** Limpeza com Trafilatura
3. **F3** Sentimento BERTweet-PT + recalibração
4. **F4** NER BERTimbau HAREM
5. **F5** Tópicos BERTopic
6. **F6** FTS5 + estatísticas

## Como rodar localmente

```bash
pip install -r requirements.txt
python api.py
# http://localhost:8000


Deploy

Cloudflare Worker + D1 + R2. Ver wrangler.toml.
Limitações conhecidas

    Cobertura limitada ao subset Bolsonaro do CC-News-PT

    Viés de veículos locais na fonte

    Mojibake residual em ~5% das entidades (mitigado no frontend)

Licença

Uso acadêmico e jornalístico.


### Ação 4 — Criar `requirements.txt`

Salvar na raiz:

```txt
fastapi>=0.110
uvicorn>=0.29