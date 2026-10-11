"""Rotas de notícias."""
import json
from fastapi import APIRouter, HTTPException, Query

from src.api.cache import cache_get, cache_set
from src.api.db import db, row_to_dict
