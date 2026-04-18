"""
Evidence Store — Agnes AI Supply Chain Manager.

In-memory + on-disk cache for EvidenceItem objects across cascade runs.
Keys by (source_type, url_or_query). TTL-aware, persisted to JSON.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from backend.schemas import EvidenceItem
from backend.config import EVIDENCE_CACHE_TTL_HOURS

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "evidence_cache.json")

# Runtime store: evidence_id → EvidenceItem
_store: dict[str, EvidenceItem] = {}
# Dedup index: cache_key → evidence_id
_key_index: dict[str, str] = {}

_loaded = False


def _load_from_disk() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        if not os.path.exists(_CACHE_PATH):
            return
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            raw: list[dict] = json.load(f)
        cutoff = datetime.utcnow() - timedelta(hours=EVIDENCE_CACHE_TTL_HOURS)
        for item_dict in raw:
            try:
                item = EvidenceItem(**item_dict)
                ts = datetime.fromisoformat(item.timestamp.rstrip("Z"))
                if ts >= cutoff:
                    _store[item.evidence_id] = item
                    key = _make_key(item.source_type, item.source_url or item.excerpt[:80])
                    _key_index[key] = item.evidence_id
            except Exception:
                continue
    except Exception:
        pass


def _save_to_disk() -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        data = [item.model_dump() for item in _store.values()]
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _make_key(source_type: str, url_or_query: str) -> str:
    return hashlib.sha256(f"{source_type}|{url_or_query}".encode()).hexdigest()[:24]


def hash_excerpt(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def record(evidence: EvidenceItem) -> str:
    """Store an evidence item. Returns evidence_id."""
    _load_from_disk()
    if not evidence.content_hash and evidence.excerpt:
        evidence = evidence.model_copy(update={"content_hash": hash_excerpt(evidence.excerpt)})
    _store[evidence.evidence_id] = evidence
    key = _make_key(evidence.source_type, evidence.source_url or evidence.excerpt[:80])
    _key_index[key] = evidence.evidence_id
    _save_to_disk()
    return evidence.evidence_id


def get_by_id(evidence_id: str) -> Optional[EvidenceItem]:
    _load_from_disk()
    return _store.get(evidence_id)


def get_by_cache_key(source_type: str, url_or_query: str) -> Optional[EvidenceItem]:
    """Return a cached evidence item if it exists and is within TTL."""
    _load_from_disk()
    key = _make_key(source_type, url_or_query)
    eid = _key_index.get(key)
    if not eid:
        return None
    item = _store.get(eid)
    if not item:
        return None
    try:
        ts = datetime.fromisoformat(item.timestamp.rstrip("Z"))
        if datetime.utcnow() - ts > timedelta(hours=EVIDENCE_CACHE_TTL_HOURS):
            return None
    except Exception:
        return None
    return item


def get_by_claim(claim: str) -> list[EvidenceItem]:
    _load_from_disk()
    return [e for e in _store.values() if e.claim and claim.lower() in e.claim.lower()]


def list_all(source_type: Optional[str] = None) -> list[EvidenceItem]:
    _load_from_disk()
    items = list(_store.values())
    if source_type:
        items = [e for e in items if e.source_type == source_type]
    return items


def clear() -> None:
    """Clear in-memory store (cache stays on disk)."""
    _store.clear()
    _key_index.clear()
