"""
suggestion_generator.py — Rule-based follow-up question generator.

generate_suggestions(question, pipeline, results) → list[str]
Returns up to 3 contextual follow-up questions based on the executed pipeline
and its top result, without making extra LLM calls.
"""
from __future__ import annotations

import json
import re

_GENERIC = [
    "Who are the top 5 suppliers by total spend?",
    "Which quarter had the highest spending?",
    "Show monthly spending trend for 2014",
]


def generate_suggestions(question: str, pipeline: list, results: list) -> list[str]:
    if not pipeline or not results:
        return _GENERIC

    p = json.dumps(pipeline).lower()
    top = results[0]
    top_id = top.get("_id", "")

    # ── Quarterly ─────────────────────────────────────────────────────────────
    if "quarter" in p:
        if isinstance(top_id, dict):
            y  = top_id.get("year", 2014)
            qt = top_id.get("quarter", 2)
            return [
                f"Who were the top 5 suppliers in {y}-Q{qt}?",
                f"Which department spent the most in {y}-Q{qt}?",
                f"Show monthly breakdown for all of {y}",
            ]
        return [
            "Which department spent the most last quarter?",
            "Show quarterly spending for 2014",
            "Compare spending across all quarters",
        ]

    # ── Monthly ───────────────────────────────────────────────────────────────
    if "month" in p:
        if isinstance(top_id, dict):
            y = top_id.get("year", 2014)
            return [
                f"Who were the top 5 suppliers in {y}?",
                f"Show quarterly breakdown for {y}",
                f"Which department had the highest spend in {y}?",
            ]
        return [
            "Show quarterly breakdown for 2014",
            "Who were the top suppliers in 2014?",
            "Compare 2013 vs 2014 total spending",
        ]

    # ── Supplier ──────────────────────────────────────────────────────────────
    if "supplier_name" in p:
        if isinstance(top_id, str) and top_id:
            s = top_id[:40]
            return [
                f"What items did {s} supply?",
                f"Show quarterly trend for {s}",
                "Compare top 5 suppliers by order count",
            ]
        return [
            "Show monthly trend for the top supplier",
            "Compare top suppliers by order count vs spend",
            "Which department uses this supplier most?",
        ]

    # ── Department ────────────────────────────────────────────────────────────
    if "department_name" in p:
        if isinstance(top_id, str) and top_id:
            d = top_id[:40]
            return [
                f"What did {d} spend on IT Goods?",
                f"Show quarterly breakdown for {d}",
                "Compare top 5 departments by order count",
            ]
        return [
            "Show quarterly breakdown by department",
            "Compare IT vs NON-IT spend by department",
            "Which department placed the most orders?",
        ]

    # ── Item ──────────────────────────────────────────────────────────────────
    if "item_name" in p:
        if isinstance(top_id, str) and top_id:
            item = top_id[:40]
            return [
                f"Which department orders {item} the most?",
                f"Who are the top suppliers for {item}?",
                "Show most ordered items by total quantity",
            ]
        return [
            "Which department orders these items most?",
            "Show most ordered items by quantity",
            "Who supplies these items?",
        ]

    # ── Acquisition type ──────────────────────────────────────────────────────
    if "acquisition_type" in p:
        return [
            "Which department spends the most on IT Goods?",
            "Show IT vs NON-IT spending by year",
            "Who are the top suppliers for NON-IT Goods?",
        ]

    # ── Year filter ───────────────────────────────────────────────────────────
    if "year" in p:
        y = _extract_year(p) or 2014
        return [
            f"Show monthly breakdown for {y}",
            f"Who were the top 5 suppliers in {y}?",
            f"Compare {y} vs {y - 1} total spending" if y > 2012
            else f"Show quarterly breakdown for {y}",
        ]

    return _GENERIC


def _extract_year(text: str) -> int | None:
    m = re.search(r'\b(201[2-5])\b', text)
    return int(m.group(1)) if m else None
