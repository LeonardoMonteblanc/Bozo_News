# Corpus Bolsonaro 2019-2022

Site público para consulta de notícias sobre o governo Bolsonaro (2019-2022).

## Visão geral

- **20.725 artigos** sobre Bolsonaro e o governo (subset do CC-News-PT v2)
- **Enriquecimento:** BERTweet-PT (sentimento), BERTimbau HAREM (NER), BERTopic (104 tópicos → consolidados em 16)
- **Stack local:** FastAPI + SQLite
- **Stack produção:** Cloudflare Workers + D1 + R2
- **Frontend:** React + TypeScript + Tailwind CSS

## Arquitetura

```
Navegador → Cloudflare Pages (frontend)
          → Cloudflare Worker (API)
          → D1 (metadados + FTS5)
          → R2 (textos completos)
```

## Estrutura do Projeto

```
/
├── api.py                    # API local (FastAPI) - entry point
├── src/
│   ├── api/
│   │   ├── db.py             # Conexão com SQLite
│   │   ├── cache.py          # Cache TTL
│   │   └── routes/
│   │       ├── noticias.py   # Endpoints de notícias
│   │       ├── topicos.py    # Endpoints de tópicos
│   │       ├── entidades.py  # Endpoints de entidades/rede
│   │       ├── agregacoes.py # Timeline, categorias, etc.
│   │       └── sugestoes.py  # Autocomplete
│   ├── pipeline/
│   │   ├── train.py          # Pipeline completo
│   │   └── config.py         # Configurações centralizadas
│   └── paths.py              # Caminhos absolutos
├── scripts/                  # Scripts de manutenção
│   ├── resplit_t100.py       # Refatoração T100
│   ├── resplit_t202.py       # Refatoração T202
│   ├── retrain_topic.py      # Retreino BERTopic
│   ├── nomear_topics_llm.py  # Nomeação via LLM
│   ├── curadoria.py          # Curadoria manual
│   ├── finalizar_topics.py   # Finalização dos tópicos
│   ├── validador_topicos_llm.py
│   ├── reconciliar.py        # Reconciliação humano/LLM
│   ├── verificar_keyw.py     # Verificação de keywords
│   └── get_keywords.py       # Extração de keywords
├── src/export/
│   └── export_cloudflare.py  # Export DB → D1/R2
├── worker/
│   └── src/index.js          # Cloudflare Worker
├── web/                      # Frontend React + Tailwind
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   └── package.json
├── data/                     # Dados JSON
├── cc_news_pt/               # Dados de processamento
├── tests/
│   ├── test_api_endpoints.py # Testes pytest
│   └── test_smoke.py         # Smoke test
├── requirements.txt
└── worker/wrangler.toml
```

## Pipeline (`src/pipeline/train.py`)

Fases:
1. **F1** Recuperar `texto_bruto` dos parquets
2. **F2** Limpeza com Trafilatura
3. **F3** Sentimento BERTweet-PT + recalibração
4. **F4** NER BERTimbau HAREM
5. **F5** Tópicos BERTopic
6. **F6** FTS5 + estatísticas

Uso:
```bash
python src/pipeline/train.py                  # tudo
python src/pipeline/train.py --apenas-fase 3  # só a fase 3
python src/pipeline/train.py --reset-fase 3   # refaz a fase 3
python src/pipeline/train.py --reset-tudo     # apaga estado e refaz
```

## Como rodar localmente

### API
```bash
pip install -r requirements.txt
python api.py
# http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Frontend
```bash
cd web
npm install
npm run dev
# http://localhost:3000
```

### Testes
```bash
# Smoke test (API precisa estar rodando)
python tests/test_smoke.py

# Testes unitários
python -m pytest tests/test_api_endpoints.py -v
```

## Deploy

### Cloudflare Worker + D1 + R2
```bash
# Exportar para D1/R2
python src/export/export_cloudflare.py

# Deploy worker
cd worker
wrangler deploy

# Deploy frontend
cd ../web
npm run build
# Copiar dist/ para Cloudflare Pages
```

## Limitações conhecidas

- Cobertura limitada ao subset Bolsonaro do CC-News-PT
- Viés de veículos locais na fonte
- Mojibake residual em ~5% das entidades (mitigado no frontend)

## Licença

Uso acadêmico e jornalístico.
