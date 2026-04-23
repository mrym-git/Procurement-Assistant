"""
query_explainer.py — Rule-based pipeline explanation layer.

explain_query(user_question, pipeline) returns a one-sentence natural
language description of what the pipeline does.  This is prepended to
the tool result so the LLM can include the reasoning in its final answer.
"""
from __future__ import annotations


def explain_query(user_question: str, pipeline: list) -> str:
    """
    Return a short natural-language description of what a pipeline does.

    Example output:
        "Reasoning: filtered orders where total_price > 0, year = 2014,
         quarter = 3 -> grouped by (year, quarter) and summed total_price
         -> sorted by total (highest first) -> limited to top 1 results."
    """
    steps: list[str] = []

    for stage in pipeline:
        if not isinstance(stage, dict):
            continue
        op = next(iter(stage))
        body = stage[op]

        if op == "$match":
            desc = _describe_match(body)
            if desc:
                steps.append(f"filtered orders where {desc}")

        elif op == "$group":
            steps.append(_describe_group(body))

        elif op == "$sort":
            if body:
                field, direction = next(iter(body.items()))
                steps.append(
                    f"sorted by {field} "
                    f"({'highest first' if direction == -1 else 'lowest first'})"
                )

        elif op == "$limit":
            steps.append(f"limited to top {body} results")

        elif op == "$count":
            steps.append("counted all matching orders")

        elif op == "$project":
            kept = [k for k, v in body.items() if v and k != "_id"]
            if kept:
                steps.append(f"selected fields: {', '.join(kept[:4])}")
            else:
                steps.append("projected fields")

        elif op == "$unwind":
            field = body if isinstance(body, str) else body.get("path", str(body))
            steps.append(f"expanded {field.lstrip('$')}")

        elif op == "$skip":
            steps.append(f"skipped first {body} results")

        elif op == "$addFields":
            steps.append("computed additional fields")

    if not steps:
        return ""

    return "Reasoning: " + " -> ".join(steps) + "."


# ── Private helpers ───────────────────────────────────────────────────────────

def _describe_match(body: dict) -> str:
    parts: list[str] = []
    for field, condition in body.items():
        if field == "total_price":
            if isinstance(condition, dict):
                for op, val in condition.items():
                    parts.append(f"total_price {_op_symbol(op)} {val}")
            else:
                parts.append(f"total_price = {condition}")

        elif field in ("year", "month", "quarter"):
            parts.append(f"{field} = {condition}")

        elif field == "supplier_name":
            val = condition if isinstance(condition, str) else str(condition)
            parts.append(f"supplier = {val}")

        elif field == "department_name":
            val = condition if isinstance(condition, str) else str(condition)
            parts.append(f"department = {val}")

        elif field == "acquisition_type":
            val = condition if isinstance(condition, str) else str(condition)
            parts.append(f"type = {val}")

        elif field in ("$and", "$or"):
            parts.append(f"combined conditions ({field})")

        else:
            parts.append(f"{field} matches condition")

    return ", ".join(parts)


def _describe_group(body: dict) -> str:
    group_by = body.get("_id")
    accumulators = {k: v for k, v in body.items() if k != "_id"}

    # Grouping key description
    if group_by is None:
        group_desc = "all orders"
    elif isinstance(group_by, str):
        group_desc = f"each {group_by.lstrip('$')}"
    elif isinstance(group_by, dict):
        keys = list(group_by.keys())
        group_desc = f"each ({', '.join(keys)})" if keys else "date groups"
    else:
        group_desc = str(group_by)

    # Accumulator description
    agg_parts: list[str] = []
    for name, expr in accumulators.items():
        if isinstance(expr, dict):
            op = next(iter(expr))
            raw_field = next(iter(expr.values()), "")
            field = str(raw_field).lstrip("$") if raw_field != 1 else "orders"
            if op == "$sum":
                agg_parts.append(f"summed {field}" if field != "orders" else "counted orders")
            elif op == "$avg":
                agg_parts.append(f"averaged {field}")
            elif op == "$max":
                agg_parts.append(f"max {field}")
            elif op == "$min":
                agg_parts.append(f"min {field}")
            elif op == "$first":
                agg_parts.append(f"first {field}")
            elif op == "$push":
                agg_parts.append(f"collected {field}")

    agg_str = ", ".join(agg_parts) if agg_parts else "aggregated"
    return f"grouped by {group_desc} and {agg_str}"


def _op_symbol(op: str) -> str:
    return {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<=",
            "$eq": "=", "$ne": "!="}.get(op, op)
