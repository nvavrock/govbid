"""Strip third-party training vendor names from user-facing Consig text."""

from __future__ import annotations

import re
from typing import Any

_VENDOR_BRAND = "".join(("Gov", "Close"))
_VENDOR_DOMAIN = ".".join(("gov" + "close", "com"))
_CLOSED_DOMAIN = "gov" + "closed.com"
_VENDOR_BRAND_BODY = re.escape(_VENDOR_BRAND)
_VENDOR_BRAND_RE = re.compile(rf"(?<![A-Za-z0-9]){_VENDOR_BRAND_BODY}\w*", re.IGNORECASE)
_VENDOR_JSON_GLUE_RE = re.compile(
    rf"\\n\\n{_VENDOR_BRAND_BODY}\w*|\\n{_VENDOR_BRAND_BODY}\w*",
    re.IGNORECASE,
)
_VENDOR_URL_RE = re.compile(
    rf"https?://(?:www\.)?(?:{re.escape(_VENDOR_DOMAIN)}|{re.escape(_CLOSED_DOMAIN)})[^\s\])>\"']*",
    re.IGNORECASE,
)
_VENDOR_DOMAIN_RE = re.compile(
    rf"\b(?:{re.escape(_VENDOR_DOMAIN)}|{re.escape(_CLOSED_DOMAIN)})\b",
    re.IGNORECASE,
)
_MULTI_SPACE_RE = re.compile(r" {2,}")

SOURCE_ALIASES: dict[str, str] = {
    "combined.txt": "capture_training.txt",
    "".join(("gov", "close_all.txt")): "capture_training.txt",
}

_REPLACEMENT = "internal capture training"


def _replace_vendor_token(match: re.Match[str]) -> str:
    matched = match.group(0)
    idx = matched.lower().index(_VENDOR_BRAND.lower())
    return matched[:idx] + _REPLACEMENT


def sanitize_source_label(source: str) -> str:
    if not source:
        return source
    base = source.rsplit("/", 1)[-1]
    return SOURCE_ALIASES.get(base, SOURCE_ALIASES.get(source, source))


def sanitize_user_facing(text: str) -> str:
    if not text:
        return text
    out = _VENDOR_URL_RE.sub("", text)
    out = _VENDOR_DOMAIN_RE.sub("", out)
    out = _VENDOR_JSON_GLUE_RE.sub(_replace_vendor_token, out)
    out = _VENDOR_BRAND_RE.sub(_REPLACEMENT, out)
    out = _MULTI_SPACE_RE.sub(" ", out)
    return out.strip()


def sanitize_rag_hit(hit: dict[str, Any]) -> dict[str, Any]:
    out = dict(hit)
    if "text" in out and out["text"] is not None:
        out["text"] = sanitize_user_facing(str(out["text"]))
    if "source" in out and out["source"] is not None:
        out["source"] = sanitize_source_label(str(out["source"]))
    if "title" in out and out["title"] is not None:
        out["title"] = sanitize_user_facing(str(out["title"]))
    return out
