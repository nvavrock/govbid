#!/usr/bin/env python3
"""Chunk and index training corpus + playbooks into Chroma for Consig RAG."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from consig.config import ROOT as PROJECT_ROOT, load_env  # noqa: E402
from consig import rag  # noqa: E402

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

SOURCES = [
    (PROJECT_ROOT / "transcripts" / "corpus" / "combined.txt", "combined.txt"),
    (PROJECT_ROOT / "docs" / "federal_contracting_playbook.md", "federal_contracting_playbook.md"),
    (PROJECT_ROOT / "docs" / "sam_gov_procurement_framework.md", "sam_gov_procurement_framework.md"),
]


def chunk_text(text: str, source: str, title: str) -> list[dict]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []
    chunks: list[dict] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            break_at = text.rfind("\n", start, end)
            if break_at > start + CHUNK_SIZE // 2:
                end = break_at
        piece = text[start:end].strip()
        if len(piece) > 80:
            chunk_id = hashlib.sha256(f"{source}:{idx}:{piece[:64]}".encode()).hexdigest()[:24]
            chunks.append(
                {
                    "id": chunk_id,
                    "text": piece,
                    "source": source,
                    "title": title,
                }
            )
            idx += 1
        start = max(end - CHUNK_OVERLAP, end)
        if start >= len(text):
            break
    return chunks


def collect_chunks() -> list[dict]:
    all_chunks: list[dict] = []
    for path, label in SOURCES:
        if not path.is_file():
            print(f"  skip (missing): {path}", file=sys.stderr)
            continue
        print(f"  chunking {label} ({path.stat().st_size // 1024} KB)...")
        text = path.read_text(encoding="utf-8", errors="replace")
        all_chunks.extend(chunk_text(text, label, label))
    return all_chunks


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Consig Chroma index")
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild collection")
    args = parser.parse_args()

    load_env()
    try:
        from consig.config import openai_api_key

        openai_api_key()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    chunks = collect_chunks()
    if not chunks:
        print("No chunks to index.", file=sys.stderr)
        return 1

    print(f"Indexing {len(chunks)} chunks...")
    n = rag.index_chunks(chunks, reset=args.reset)
    print(f"Done. {n} chunks in index at {rag.chroma_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
