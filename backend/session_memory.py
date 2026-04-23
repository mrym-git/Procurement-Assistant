"""
session_memory.py — Stateful per-session result store.

A module-level singleton `memory` is imported by agent.py.
The query_orders tool saves key facts after each execution so follow-up
questions like "who were the top suppliers in that quarter?" can resolve
"that quarter" from stored context rather than asking the user to repeat it.

Standard keys
-------------
highest_spend_quarter   → {"year": int, "quarter": int, "total": float}
highest_order_quarter   → {"year": int, "quarter": int, "count": int}
last_supplier_result    → [{"supplier": str, ...}, ...]
last_department_result  → [{"department": str, ...}, ...]
last_query_pipeline     → list  (the last executed pipeline)
last_result_raw         → list  (raw deserialized result documents)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class SessionMemory:

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    # ── Basic CRUD ─────────────────────────────────────────────────────────────

    def save_result(self, session_id: str, key: str, value: Any) -> None:
        self._store.setdefault(session_id, {})[key] = value

    def get_result(self, session_id: str, key: str) -> Optional[Any]:
        return self._store.get(session_id, {}).get(key)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return dict(self._store.get(session_id, {}))

    def clear_session(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    # ── Smart save — called after every query_orders execution ────────────────

    def extract_and_save(self, session_id: str, pipeline: list, results: list) -> None:
        """
        Inspect pipeline + results and save any recognisable key facts.
        Safe to call even when results is empty.
        """
        if not session_id or not results:
            return

        self.save_result(session_id, "last_query_pipeline", pipeline)
        self.save_result(session_id, "last_result_raw", results)

        pipeline_str = json.dumps(pipeline).lower()
        first = results[0]

        # ── Quarterly spend result ────────────────────────────────────────────
        if "quarter" in pipeline_str:
            _id = first.get("_id")
            total = first.get("total")
            if isinstance(_id, dict) and "year" in _id and "quarter" in _id:
                if isinstance(total, (int, float)) and total > 0:
                    self.save_result(session_id, "highest_spend_quarter", {
                        "year":    _id["year"],
                        "quarter": _id["quarter"],
                        "total":   total,
                    })
            # Order count variant
            count = first.get("count") or first.get("order_count")
            if isinstance(_id, dict) and "year" in _id and isinstance(count, int):
                self.save_result(session_id, "highest_order_quarter", {
                    "year":    _id["year"],
                    "quarter": _id["quarter"],
                    "count":   count,
                })

        # ── Supplier result ───────────────────────────────────────────────────
        if "supplier_name" in pipeline_str:
            supplier_data: List[Dict] = []
            for r in results[:10]:
                _id = r.get("_id")
                if isinstance(_id, str):
                    entry: Dict[str, Any] = {"supplier": _id}
                    entry.update({k: v for k, v in r.items() if k != "_id"})
                    supplier_data.append(entry)
            if supplier_data:
                self.save_result(session_id, "last_supplier_result", supplier_data)

        # ── Department result ─────────────────────────────────────────────────
        if "department_name" in pipeline_str:
            dept_data: List[Dict] = []
            for r in results[:10]:
                _id = r.get("_id")
                if isinstance(_id, str):
                    entry = {"department": _id}
                    entry.update({k: v for k, v in r.items() if k != "_id"})
                    dept_data.append(entry)
            if dept_data:
                self.save_result(session_id, "last_department_result", dept_data)

    # ── Context injection ─────────────────────────────────────────────────────

    def context_summary(self, session_id: str) -> str:
        """
        Return a short text block summarising stored facts for this session.
        Injected as a SystemMessage before the user's next question so the
        LLM can resolve references like 'that quarter' or 'the same supplier'
        without re-querying MongoDB.
        """
        data = self._store.get(session_id, {})
        if not data:
            return ""

        lines: list[str] = ["[Stored context from earlier in this session]"]

        if "highest_spend_quarter" in data:
            r = data["highest_spend_quarter"]
            lines.append(
                f"- Highest-spend quarter found so far: "
                f"{r['year']}-Q{r['quarter']} (${r['total']:,.2f})"
            )

        if "highest_order_quarter" in data:
            r = data["highest_order_quarter"]
            lines.append(
                f"- Highest order-count quarter found so far: "
                f"{r['year']}-Q{r['quarter']} ({r['count']:,} orders)"
            )

        if "last_supplier_result" in data:
            top = data["last_supplier_result"][0]
            lines.append(f"- Last top supplier result: {top.get('supplier', 'unknown')}")

        if "last_department_result" in data:
            top = data["last_department_result"][0]
            lines.append(f"- Last top department result: {top.get('department', 'unknown')}")

        return "\n".join(lines) if len(lines) > 1 else ""


# Module-level singleton imported by agent.py
memory = SessionMemory()
