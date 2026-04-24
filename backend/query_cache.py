"""
query_cache.py — Session-level semantic question cache.

Uses Jaccard similarity on normalized token sets to detect semantically
equivalent questions (threshold 0.80).  Avoids redundant MongoDB + LLM calls
when the user rephrases a question they already asked in the same session.

Numbers (years, quarters, months) are kept as tokens so "Q3 2014" and
"Q2 2014" do NOT produce a cache hit.

Module-level singleton `query_cache` is imported by agent.py.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

_STOP = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "and", "or", "but", "not",
    "what", "which", "who", "how", "when", "where", "why",
    "many", "much", "did", "does", "do", "has", "have", "had",
    "show", "me", "i", "want", "please", "tell", "give", "get",
    "can", "could", "would", "should", "will",
    "by", "with", "from", "as", "this", "that", "these", "those",
    "all", "any", "some", "most", "more", "less",
})

_THRESHOLD = 0.55

# Light stemming map — normalises common variants so Jaccard sees them as the same token
_STEM: dict[str, str] = {
    "spending": "spend", "spent": "spend", "expenditure": "spend", "expenses": "spend",
    "orders": "order", "ordered": "order", "ordering": "order",
    "suppliers": "supplier", "vendors": "supplier", "vendor": "supplier",
    "departments": "department", "dept": "department",
    "items": "item", "goods": "item",
    "purchases": "purchase", "purchasing": "purchase",
    "highest": "high", "lowest": "low",
    "monthly": "month", "quarterly": "quarter", "yearly": "year", "annual": "year",
    "total": "total", "totals": "total",
}


def _tokenize(text: str) -> frozenset:
    tokens = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return frozenset(
        _STEM.get(t, t) for t in tokens
        if t not in _STOP and len(t) > 1
    )


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


class SemanticCache:

    def __init__(self) -> None:
        # session_id → [(tokens, entry), ...]
        self._store: Dict[str, List[Tuple[frozenset, dict]]] = defaultdict(list)

    def lookup(self, session_id: str, question: str) -> Optional[dict]:
        """Return cached entry if a semantically similar question was already answered."""
        tokens = _tokenize(question)
        for cached_tokens, entry in self._store[session_id]:
            if _jaccard(tokens, cached_tokens) >= _THRESHOLD:
                return entry
        return None

    def store(self, session_id: str, question: str, answer: str, **kwargs: Any) -> None:
        """Cache the answer and any supplementary data (chart, suggestions, etc.)."""
        tokens = _tokenize(question)
        entry = {"answer": answer, **kwargs}
        # Update in place if a similar entry exists
        for i, (t, _) in enumerate(self._store[session_id]):
            if _jaccard(tokens, t) >= _THRESHOLD:
                self._store[session_id][i] = (tokens, entry)
                return
        self._store[session_id].append((tokens, entry))

    def clear_session(self, session_id: str) -> None:
        self._store.pop(session_id, None)


# Module-level singleton
query_cache = SemanticCache()
