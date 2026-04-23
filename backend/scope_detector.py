"""
scope_detector.py — Out-of-scope question detector.

is_out_of_scope(question) returns True when the question is clearly
unrelated to procurement / purchasing / spending data.

Strategy (in order):
  1. Explicit out-of-scope regex patterns  → True
  2. Any procurement keyword present       → False (in scope)
  3. Very short input (greeting, "yes")    → False (let agent handle it)
  4. Default                               → True  (unknown = out of scope)
"""
from __future__ import annotations

import re

# ── Procurement domain keywords ───────────────────────────────────────────────
_PROCUREMENT_KEYWORDS: frozenset[str] = frozenset({
    # Core domain
    "order", "orders", "purchase", "purchases", "procurement",
    "spend", "spending", "spent", "expenditure", "expense",
    "supplier", "suppliers", "vendor", "vendors", "contractor",
    "department", "departments", "agency", "agencies",
    "contract", "contracts", "bid", "bids",
    "invoice", "receipt",
    # Items
    "item", "items", "goods", "services", "acquisition",
    # Financial
    "price", "cost", "amount", "total", "budget", "unit price",
    "quantity", "quantities",
    # Time
    "fiscal", "fiscal year",
    "quarter", "quarterly", "q1", "q2", "q3", "q4",
    "month", "monthly", "year", "annual", "yearly",
    "2012", "2013", "2014", "2015",
    # Analytical
    "top", "highest", "lowest", "most", "least", "average",
    "trend", "compare", "analysis", "breakdown", "summary",
    "how many", "how much",
    # California / dataset context
    "california", "state of california", "statewide",
    "calcard", "it goods", "non-it", "health care",
    "transportation", "medi-cal",
})

# ── Explicit out-of-scope patterns ────────────────────────────────────────────
_OUT_OF_SCOPE_PATTERNS: list[str] = [
    r"\bwho (is|was|are|were) (the )?governor\b",
    r"\bwhat (is|are) (mongodb|python|sql|ai|ml|machine learning|langchain|llm|gpt)\b",
    r"\bexplain (ai|machine learning|neural network|blockchain|cryptocurrency)\b",
    r"\bwrite (a |an )?(poem|story|essay|joke|song|code|function|script)\b",
    r"\btell me (a )?joke\b",
    r"\bweather (in|for|today|tomorrow)\b",
    r"\bstock (price|market|ticker)\b",
    r"\brecipe\b",
    r"\btranslate\b",
    r"\bsocial media\b",
    r"\bnews (about|today|this week)\b",
    r"\bsports (score|result|team)\b",
    r"\bwho won (the )?(game|election|match)\b",
    r"\bpresident of\b",
    r"\bcapital (city|of)\b",
    r"\bpopulation of\b",
    r"\bhow do (i|you|we) (cook|make|build|install)\b",
]

_OUT_OF_SCOPE_RE = re.compile(
    "|".join(_OUT_OF_SCOPE_PATTERNS),
    re.IGNORECASE,
)

_OUT_OF_SCOPE_REPLY = (
    "This assistant only answers questions about the California State "
    "procurement dataset (orders, spending, suppliers, departments, items, "
    "dates). Please ask a procurement-related question."
)


def is_out_of_scope(question: str) -> bool:
    """
    Return True if the question is unrelated to procurement data.
    """
    q = question.lower().strip()

    # Explicit negative patterns
    if _OUT_OF_SCOPE_RE.search(q):
        return True

    # Any procurement keyword → in scope
    for kw in _PROCUREMENT_KEYWORDS:
        if kw in q:
            return False

    # Very short input: greetings, acknowledgements — pass through to agent
    if len(q.split()) <= 4:
        return False

    # Unknown multi-word question with no procurement signal
    return True


def out_of_scope_reply() -> str:
    """Standard reply returned when is_out_of_scope() is True."""
    return _OUT_OF_SCOPE_REPLY
