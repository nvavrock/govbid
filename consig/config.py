"""Environment and paths for Consig."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES_DIR = ROOT / "db" / "queries"
MATCH_PROFILE = ROOT / "config" / "match-profile.yaml"
MATCH_PROFILE_EXAMPLE = ROOT / "config" / "match-profile.example.yaml"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def postgres_params() -> dict:
    load_env()
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD not set in .env")
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5433")),
        "user": os.environ.get("POSTGRES_USER", "govbid"),
        "password": password,
        "dbname": os.environ.get("POSTGRES_DB", "govbid"),
    }


def openai_api_key() -> str:
    load_env()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    return key


def llm_model() -> str:
    load_env()
    return os.environ.get("CONSIG_LLM_MODEL", "gpt-4o-mini")


def embedding_model() -> str:
    load_env()
    return os.environ.get("CONSIG_EMBEDDING_MODEL", "text-embedding-3-small")


def chroma_path() -> Path:
    load_env()
    raw = os.environ.get("CONSIG_DATA_DIR", "data/consig_index")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def top_k() -> int:
    load_env()
    return int(os.environ.get("CONSIG_TOP_K", "6"))


def review_defaults() -> dict:
    """Queue params from match-profile.yaml or hardcoded defaults."""
    load_env()
    try:
        import yaml

        profile_path = MATCH_PROFILE if MATCH_PROFILE.is_file() else MATCH_PROFILE_EXAMPLE
        if profile_path.is_file():
            data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
            review = data.get("review") or {}
            return {
                "days_ahead": int(review.get("days_ahead", 30)),
                "min_score": int(review.get("min_score", 25)),
                "top_n": int(review.get("top_n", 25)),
            }
    except Exception:
        pass
    return {"days_ahead": 30, "min_score": 25, "top_n": 25}
