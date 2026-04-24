"""
chart_builder.py — Builds Chart.js config objects from MongoDB aggregation results.

build_chart_spec(pipeline, results) → dict | None
Returns a Chart.js-compatible config or None if the results are not chartable.
The returned dict includes a top-level "format" key ("currency" | "count" | "number")
so the frontend can attach appropriate tooltip/tick callbacks without Python
trying to serialize JS functions.
"""
from __future__ import annotations

import json
import math
from typing import Any

MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Palette matches the dark glassmorphism theme
_PALETTE = [
    {"bg": "rgba(99,102,241,0.75)",  "border": "#6366f1"},
    {"bg": "rgba(139,92,246,0.75)",  "border": "#8b5cf6"},
    {"bg": "rgba(236,72,153,0.75)",  "border": "#ec4899"},
    {"bg": "rgba(34,211,238,0.75)",  "border": "#22d3ee"},
    {"bg": "rgba(34,197,94,0.75)",   "border": "#22c55e"},
    {"bg": "rgba(251,191,36,0.75)",  "border": "#fbbf24"},
    {"bg": "rgba(249,115,22,0.75)",  "border": "#f97316"},
    {"bg": "rgba(16,185,129,0.75)",  "border": "#10b981"},
]


def build_chart_spec(pipeline: list, results: list) -> dict | None:
    if not results or len(results) < 2:
        return None

    first = results[0]
    _id = first.get("_id")
    metric = _find_metric(first)
    if not metric:
        return None

    config = None

    # ── Time series: _id is a dict with time keys ─────────────────────────────
    if isinstance(_id, dict):
        if "month" in _id:
            config = _monthly_chart(results, metric)
        elif "quarter" in _id:
            config = _quarterly_chart(results, metric)
        elif list(_id.keys()) == ["year"]:
            config = _yearly_chart(results, metric)

    # ── Categorical: _id is a non-empty string ────────────────────────────────
    elif isinstance(_id, str) and _id:
        config = _categorical_chart(results, metric)

    # ── Single integer _id (year) ─────────────────────────────────────────────
    elif isinstance(_id, int):
        config = _yearly_chart(results, metric)

    if config is None:
        return None

    # Attach format hint for the frontend
    config["format"] = (
        "currency" if any(w in metric for w in ("total", "price", "spend", "amount"))
        else "count" if metric in ("count", "order_count", "orders")
        else "number"
    )
    return config


# ── Chart builders ────────────────────────────────────────────────────────────

def _monthly_chart(results: list, metric: str) -> dict:
    rows = sorted(results, key=lambda r: (
        r["_id"].get("year", 0), r["_id"].get("month", 0)
    ))
    labels = []
    for r in rows:
        m = r["_id"].get("month", 0)
        y = r["_id"].get("year", "")
        labels.append(f"{MONTH_NAMES[m] if 0 < m <= 12 else m} {y}")
    values = [_val(r.get(metric)) for r in rows]
    return _line_cfg(labels, values, _label(metric))


def _quarterly_chart(results: list, metric: str) -> dict:
    rows = sorted(results, key=lambda r: (
        r["_id"].get("year", 0), r["_id"].get("quarter", 0)
    ))
    labels = [f"Q{r['_id'].get('quarter','?')} {r['_id'].get('year','')}" for r in rows]
    values = [_val(r.get(metric)) for r in rows]
    return _bar_cfg(labels, values, _label(metric))


def _yearly_chart(results: list, metric: str) -> dict:
    def sort_key(r):
        _id = r["_id"]
        return _id.get("year", 0) if isinstance(_id, dict) else (_id or 0)

    rows = sorted(results, key=sort_key)
    labels = [
        str(r["_id"].get("year", r["_id"])) if isinstance(r["_id"], dict)
        else str(r["_id"])
        for r in rows
    ]
    values = [_val(r.get(metric)) for r in rows]
    return _bar_cfg(labels, values, _label(metric))


def _categorical_chart(results: list, metric: str) -> dict:
    top = results[:10]
    labels = [str(r.get("_id", "Unknown"))[:35] for r in top]
    values = [_val(r.get(metric)) for r in top]
    colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": _label(metric),
                "data": values,
                "backgroundColor": [c["bg"] for c in colors],
                "borderColor":     [c["border"] for c in colors],
                "borderWidth": 1,
                "borderRadius": 6,
            }],
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "x": _scale(),
                "y": {"ticks": {"color": "#94a3b8", "font": {"size": 11}},
                      "grid": {"display": False}},
            },
        },
    }


def _bar_cfg(labels, values, label):
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": label,
                "data": values,
                "backgroundColor": "rgba(99,102,241,0.7)",
                "borderColor": "#6366f1",
                "borderWidth": 1,
                "borderRadius": 6,
            }],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {"x": _scale_x(), "y": _scale()},
        },
    }


def _line_cfg(labels, values, label):
    return {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": label,
                "data": values,
                "borderColor": "#8b5cf6",
                "backgroundColor": "rgba(139,92,246,0.15)",
                "borderWidth": 2,
                "pointBackgroundColor": "#8b5cf6",
                "pointRadius": 4,
                "tension": 0.35,
                "fill": True,
            }],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {"x": _scale_x(), "y": _scale()},
        },
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_metric(doc: dict) -> str | None:
    for p in ("total", "count", "total_price", "avg", "average", "amount", "order_count"):
        if p in doc and isinstance(doc[p], (int, float)) and _ok(doc[p]):
            return p
    for k, v in doc.items():
        if k != "_id" and isinstance(v, (int, float)) and _ok(v):
            return k
    return None


def _ok(v: Any) -> bool:
    return not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def _val(v: Any) -> float:
    if isinstance(v, (int, float)) and _ok(v):
        return float(v)
    return 0.0


def _label(field: str) -> str:
    return {
        "total": "Total Spend ($)", "total_price": "Total Spend ($)",
        "count": "Order Count", "order_count": "Order Count",
        "avg": "Average Price ($)", "average": "Average Price ($)",
        "amount": "Amount ($)",
    }.get(field, field.replace("_", " ").title())


def _scale():
    return {"ticks": {"color": "#94a3b8"}, "grid": {"color": "rgba(255,255,255,0.05)"}}


def _scale_x():
    return {"ticks": {"color": "#94a3b8", "maxRotation": 45},
            "grid": {"color": "rgba(255,255,255,0.05)"}}
