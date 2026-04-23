"""
query_validator.py — Pipeline validation and sanitization layer.

validate_pipeline(pipeline) is called inside query_orders before any
MongoDB execution.  It enforces safety rules so that bad LLM-generated
pipelines cannot damage or over-scan the database.
"""
from __future__ import annotations

import json

# Stages that could write data, join collections, or execute arbitrary JS
DISALLOWED_STAGES = frozenset({"$lookup", "$out", "$merge", "$function", "$accumulator"})

# Fields considered "scoping" — their presence means the query targets a
# meaningful subset, so a blanket $limit:5000 guard is not needed.
_DATE_FIELDS  = frozenset({"year", "month", "quarter", "creation_date"})
_SCOPE_FIELDS = _DATE_FIELDS | frozenset({"supplier_name", "department_name",
                                          "acquisition_type", "fiscal_year"})


def validate_pipeline(pipeline: list) -> list:
    """
    Validate and sanitize a MongoDB aggregation pipeline.

    Guarantees after this function returns:
      1. No disallowed stages ($lookup, $out, $merge, $function, $accumulator).
      2. First stage is $match containing {total_price: {$gt: 0}}.
      3. If the pipeline has no scoping filter (date / supplier / dept) and no
         existing $limit, a soft {$limit: 5000} is appended to cap scan size.

    Raises ValueError for structurally invalid pipelines.
    """
    if not isinstance(pipeline, list) or len(pipeline) == 0:
        raise ValueError("Pipeline must be a non-empty list of stage dicts.")

    # ── 1. Check every stage ──────────────────────────────────────────────────
    for i, stage in enumerate(pipeline):
        if not isinstance(stage, dict) or len(stage) != 1:
            raise ValueError(
                f"Stage {i} must be a single-key dict, got: {stage!r}"
            )
        op = next(iter(stage))
        if op in DISALLOWED_STAGES:
            raise ValueError(f"Stage '{op}' is not permitted in this context.")

    # ── 2. Ensure first stage is $match with total_price guard ────────────────
    if "$match" not in pipeline[0]:
        # No leading $match at all — inject one
        pipeline = [{"$match": {"total_price": {"$gt": 0}}}] + pipeline
    else:
        match_body = pipeline[0]["$match"]
        tp = match_body.get("total_price")
        guard_present = isinstance(tp, dict) and tp.get("$gt") == 0
        if not guard_present:
            # Merge the guard into the existing $match
            match_body["total_price"] = {"$gt": 0}

    # ── 3. Soft limit when no scoping filter is present ───────────────────────
    pipeline_str = json.dumps(pipeline)
    has_scope = any(f in pipeline_str for f in _SCOPE_FIELDS)
    has_limit = any("$limit" in stage for stage in pipeline)

    if not has_scope and not has_limit:
        pipeline.append({"$limit": 5000})

    return pipeline
