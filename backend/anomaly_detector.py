"""
anomaly_detector.py — IQR-based outlier detection for query result sets.

detect_anomalies(results) returns a list of flagged values that significantly
exceed the group using the standard IQR fence: value > Q3 + 1.5 * IQR.

Requires at least 4 data points for IQR to be statistically meaningful.
Does not depend on numpy — uses a pure-Python percentile implementation.
"""
from __future__ import annotations

import math

_MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def detect_anomalies(results: list) -> list[dict]:
    """
    Scan numeric fields in aggregation results for IQR outliers.

    Returns a list of:
        { "label": str, "field": str, "value": float, "threshold": float }

    Returns [] if there are fewer than 4 results or no numeric fields.
    """
    if not results or len(results) < 4:
        return []

    first = results[0]
    numeric_fields = [
        k for k, v in first.items()
        if k != "_id" and isinstance(v, (int, float)) and _finite(v)
    ]

    if not numeric_fields:
        return []

    anomalies: list[dict] = []

    for field in numeric_fields:
        values = [
            float(r[field]) for r in results
            if isinstance(r.get(field), (int, float)) and _finite(r[field])
        ]
        if len(values) < 4:
            continue

        q1     = _percentile(values, 25)
        q3     = _percentile(values, 75)
        median = _percentile(values, 50)
        upper  = q3 + 1.5 * (q3 - q1)

        for r in results:
            v = r.get(field)
            if not isinstance(v, (int, float)) or not _finite(v):
                continue
            _id = r.get("_id")
            # Skip documents with no meaningful _id — they are summary/count
            # rows (no grouping), not individual entities worth flagging.
            if _id is None:
                continue
            fv = float(v)
            # Require both: above IQR fence AND at least 3× the median.
            # This prevents flagging items that are technically above the fence
            # but not dramatically different from the rest of the group.
            if fv > upper and median > 0 and fv >= 3 * median:
                label = _format_label(_id)
                anomalies.append({
                    "label":     label,
                    "field":     field,
                    "value":     fv,
                    "threshold": round(upper, 2),
                })

    # Cap at 5 most extreme outliers to avoid noisy banners
    anomalies.sort(key=lambda a: a["value"], reverse=True)
    return anomalies[:5]


def _format_label(_id) -> str:
    if not isinstance(_id, dict):
        return str(_id)
    parts = []
    year    = _id.get("year", "")
    quarter = _id.get("quarter")
    month   = _id.get("month")
    if quarter:
        parts.append(f"Q{quarter} {year}".strip())
    elif month:
        name = _MONTH_NAMES[month] if 1 <= month <= 12 else str(month)
        parts.append(f"{name} {year}".strip())
    elif year:
        parts.append(str(year))
    for k, v in _id.items():
        if k not in ("year", "quarter", "month"):
            parts.append(str(v))
    return " / ".join(parts) if parts else str(_id)


def _finite(v) -> bool:
    return not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def _percentile(data: list, pct: float) -> float:
    """Compute the pct-th percentile without numpy."""
    s = sorted(data)
    n = len(s)
    k = (pct / 100) * (n - 1)
    lo, hi = int(k), min(int(k) + 1, n - 1)
    return s[lo] + (k - lo) * (s[hi] - s[lo])
