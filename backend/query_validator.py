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


def confidence_score(pipeline: list, results: list | None = None) -> str:
    """
    Return "High", "Medium", or "Low" based on BOTH query structure and result quality.

    High   — clear aggregation ($group+$sort or $sum/$count) AND non-empty valid results
    Medium — partial aggregation OR results exist but have quality issues
    Low    — no aggregation, empty results, NaN/null in key fields, or invalid pipeline
    """
    import json, math

    if not pipeline:
        return "Low"

    pipeline_str = json.dumps(pipeline).lower()
    stage_ops = [next(iter(s)) for s in pipeline if isinstance(s, dict)]

    has_group = "$group" in stage_ops
    has_count = "$count" in stage_ops
    has_sort  = "$sort"  in stage_ops

    # ── Structure score ───────────────────────────────────────────────────────
    if not has_group and not has_count:
        structure = "low"
    elif (has_group and has_sort) or (has_group and ("$sum" in pipeline_str or "$count" in pipeline_str)):
        structure = "high"
    else:
        structure = "medium"

    # ── Result quality score ──────────────────────────────────────────────────
    if not results:
        result_quality = "low"
    else:
        # Check for NaN / null in any numeric field of any result document
        has_bad = False
        for doc in results:
            for k, v in doc.items():
                if k == "_id":
                    continue
                if v is None:
                    has_bad = True
                    break
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    has_bad = True
                    break
            if has_bad:
                break
        result_quality = "low" if has_bad else "high"

    # ── Combine ───────────────────────────────────────────────────────────────
    if structure == "high" and result_quality == "high":
        return "High"
    if structure == "low" or result_quality == "low":
        return "Low"
    return "Medium"
