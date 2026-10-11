"""Cache TTL simples em memória."""
import time

_CACHE = {}
_CACHE_TTL = 300


def cache_get(chave):
    item = _CACHE.get(chave)
    if item and (time.time() - item["t"]) < _CACHE_TTL:
        return item["v"]
    return None


def cache_set(chave, valor):
    _CACHE[chave] = {"v": valor, "t": time.time()}


def clear_cache():
    _CACHE.clear()
