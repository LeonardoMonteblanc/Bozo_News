"""Configurações centralizadas do pipeline."""
import os
from pathlib import Path

# Caminhos
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "corpus.db"
DADOS_DIR = PROJECT_ROOT / "cc_news_pt" / "data"
SHARDS_DIR = PROJECT_ROOT / "cc_news_pt" / "_shards"
LOG_FILE = PROJECT_ROOT / "pipeline.log"
CKPT_DIR = PROJECT_ROOT / ".pipeline_ckpt"
OUTPUT_DIR = PROJECT_ROOT / "cc_news_pt"

# Recursos
N_WORKERS_TEXTO = 4
N_WORKERS_BERT = 2
TORCH_THREADS_PER_WORKER = 2

# Batch sizes
BATCH_TEXTO = 500
BATCH_BERT = 16
BATCH_DB = 500

# Modelos
MODEL_SENTIMENTO = "pysentimiento/bertweet-pt-sentiment"
MODEL_NER = "lfcc/bert-portuguese-ner"
MODEL_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

# BERTopic
N_TOPICOS_MIN = 20
N_TOPICOS_MAX = 40
