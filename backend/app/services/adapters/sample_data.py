import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_sample() -> dict:
    path = Path(__file__).resolve().parents[2] / "data" / "sample_dossier.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_sample_entry(query: str) -> dict | None:
    data = load_sample()
    key = query.upper()
    return data.get(key)
