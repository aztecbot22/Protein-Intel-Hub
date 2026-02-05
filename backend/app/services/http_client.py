from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

DEFAULT_TIMEOUT = 15.0
DEFAULT_HEADERS = {
    "User-Agent": "ProteinIntelligenceHub/0.1 (+https://github.com/your-org/protein-intelligence-hub)",
    "accept": "application/json",
}
CACHE_TTL_SECONDS = 600
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_HITS = 0
_CACHE_MISSES = 0


def _cache_key(url: str, params: dict | None, headers: dict | None, payload: str | None = None) -> str:
    key_payload = {
        "url": url,
        "params": params or {},
        "headers": headers or {},
        "payload": payload or "",
    }
    raw = json.dumps(key_payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Any | None:
    cached = _CACHE.get(key)
    if not cached:
        _count_cache_miss()
        return None
    timestamp, value = cached
    if time.time() - timestamp > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        _count_cache_miss()
        return None
    _count_cache_hit()
    return value


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


def _count_cache_hit() -> None:
    global _CACHE_HITS
    _CACHE_HITS += 1


def _count_cache_miss() -> None:
    global _CACHE_MISSES
    _CACHE_MISSES += 1


def cache_stats() -> dict[str, float | int]:
    total = _CACHE_HITS + _CACHE_MISSES
    ratio = (_CACHE_HITS / total) if total else 0.0
    return {
        "hits": _CACHE_HITS,
        "misses": _CACHE_MISSES,
        "hit_ratio": round(ratio, 4),
        "entries": len(_CACHE),
        "ttl_seconds": CACHE_TTL_SECONDS,
    }


def get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict | list | None:
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    if params:
        params = {key: value for key, value in params.items() if value is not None}
    cache_key = _cache_key(url, params, request_headers)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url, params=params, headers=request_headers)
        if response.status_code != 200:
            return None
        data = response.json()
        _cache_set(cache_key, data)
        return data
    except (httpx.HTTPError, ValueError):
        return None


def get_text(url: str, params: dict | None = None, headers: dict | None = None) -> str | None:
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    if params:
        params = {key: value for key, value in params.items() if value is not None}
    cache_key = _cache_key(url, params, request_headers)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url, params=params, headers=request_headers)
        if response.status_code != 200:
            return None
        text = response.text
        _cache_set(cache_key, text)
        return text
    except httpx.HTTPError:
        return None


def post_text(
    url: str, data: str, params: dict | None = None, headers: dict | None = None
) -> dict | list | None:
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    if params:
        params = {key: value for key, value in params.items() if value is not None}
    cache_key = _cache_key(url, params, request_headers, payload=data)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.post(url, params=params, headers=request_headers, content=data)
        if response.status_code != 200:
            return None
        payload = response.json()
        _cache_set(cache_key, payload)
        return payload
    except (httpx.HTTPError, ValueError):
        return None
