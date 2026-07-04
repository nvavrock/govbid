"""Environment and paths for Counsel."""

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
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
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
    return os.environ.get("COUNSEL_LLM_MODEL", "gpt-4o-mini")


def embedding_model() -> str:
    load_env()
    return os.environ.get("COUNSEL_EMBEDDING_MODEL", "text-embedding-3-small")


def chroma_path() -> Path:
    load_env()
    raw = os.environ.get("COUNSEL_DATA_DIR", "data/counsel_index")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def top_k() -> int:
    load_env()
    return int(os.environ.get("COUNSEL_TOP_K", "6"))


def review_defaults() -> dict:
    """Queue params from config/match-profile.yaml."""
    load_env()
    try:
        import sys

        scripts = ROOT / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from lib.match_profile import load_profile

        return load_profile()["review"]
    except Exception:
        return {"days_ahead": 30, "min_score": 0, "top_n": 25}
