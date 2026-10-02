"""Bounded raw-JSON adapter shared by the library, existing CLI, and local UI.

The extracted snapshot guard remains the sole authority for snapshot decisions.
Table rows explain that decision; they do not implement another validator.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .snapshots import (
    build_segment_snapshot, compare_segment_snapshots, warn_on_plan_vs_live,
)

MAX_FILE_BYTES = 256 * 1024
MAX_SEGMENTS = 1000


def read_raw_json(path: Path) -> str:
    """Read at most one bounded UTF-8 file, preserving BOM for its raw digest."""
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{path}: file exceeds {MAX_FILE_BYTES} bytes")
    return data.decode("utf-8")


def parse_segments(raw_json: str, *, label: str = "snapshot") -> list[dict]:
    """Accept the existing list / segments-wrapper format, including UTF-8 BOM.

    NaN and Infinity remain visible to Python's extracted finite-number guard.
    Numeric timestamp strings remain supported, as in the original CLI.
    """
    if not isinstance(raw_json, str):
        raise ValueError(f"{label}: expected raw JSON text")
    if len(raw_json) > MAX_FILE_BYTES or len(raw_json.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(f"{label}: file exceeds {MAX_FILE_BYTES} bytes")
    value = json.loads(raw_json.removeprefix("\ufeff"))
    segments = value.get("segments") if isinstance(value, dict) else value
    if not isinstance(segments, list) or any(not isinstance(item, dict) for item in segments):
        raise ValueError(f"{label}: expected a segment list or an object with a segments list")
    if len(segments) > MAX_SEGMENTS:
        raise ValueError(f"{label}: at most {MAX_SEGMENTS} segments are allowed")
    for item in segments:
        index = item.get("segment_index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError(f"{label}: segment_index must be an integer")
        for field in ("start_sec", "end_sec"):
            if isinstance(item.get(field), bool):
                raise ValueError(f"{label}: {field} must be numeric, not boolean")
    return segments


def _file_info(raw: Any) -> dict:
    if not isinstance(raw, str) or len(raw) > MAX_FILE_BYTES:
        return {"raw_sha256": None, "bytes": None, "utf8_bom": False}
    try:
        data = raw.encode("utf-8")
    except UnicodeError:
        return {"raw_sha256": None, "bytes": None, "utf8_bom": False}
    if len(data) > MAX_FILE_BYTES:
        return {"raw_sha256": None, "bytes": len(data), "utf8_bom": raw.startswith("\ufeff")}
    return {"raw_sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "utf8_bom": raw.startswith("\ufeff")}


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _display(value: Any) -> str:
    text = str(value) if value is not None else "missing"
    return text if len(text) <= 2000 else text[:2000] + "… [truncated]"


def _segment_view(segment: dict) -> dict:
    return {"start_sec": _display(segment.get("start_sec")),
            "end_sec": _display(segment.get("end_sec")),
            "label": _display(segment.get("current_label", segment.get("label", "")))}


def _messages_for_index(messages: list[str], index: int) -> list[str]:
    result = []
    for message in messages:
        match = re.search(r"\bsegment (-?\d+)\b|\bindex: (-?\d+)\b", message)
        if match and int(match.group(1) or match.group(2)) == index:
            result.append(message)
    return result


def _review_rows(live: list[dict], source: list[dict], plan: list[dict] | None,
                 blocking: list[str], warnings: list[str]) -> list[dict]:
    grouped = []
    for segments in (live, source, plan or []):
        rows = defaultdict(list)
        for segment in segments:
            rows[segment["segment_index"]].append(segment)
        grouped.append(rows)
    live_rows, source_rows, plan_rows = grouped
    result = []
    for index in sorted(set(live_rows) | set(source_rows) | set(plan_rows)):
        live_items, source_items, plan_items = live_rows[index], source_rows[index], plan_rows[index]
        reasons = _messages_for_index(blocking, index)
        notes = _messages_for_index(warnings, index)
        state = "matched"
        if index > 0 and source_items and not live_items:
            state = "missing_live"
            reasons.extend(item for item in blocking if item.startswith("source snapshot has segments missing"))
        elif index > 0 and live_items and not source_items:
            state = "missing_source"
            reasons.extend(item for item in blocking if item.startswith("live DOM has unexpected extra"))
        elif len(live_items) > 1 or len(source_items) > 1:
            state = "duplicate"
        elif reasons:
            state = "blocked"
        elif notes:
            state = "warning"
        drift = {"start_sec": None, "end_sec": None}
        if len(live_items) == len(source_items) == 1:
            for field in drift:
                left, right = _finite_number(live_items[0].get(field)), _finite_number(source_items[0].get(field))
                if left is not None and right is not None:
                    delta = left - right
                    drift[field] = delta if math.isfinite(delta) else None
        result.append({"segment_index": str(index), "state": state,
                       "live": [_segment_view(item) for item in live_items],
                       "source": [_segment_view(item) for item in source_items],
                       "plan": [_segment_view(item) for item in plan_items],
                       "drift": drift, "blocking_mismatches": list(dict.fromkeys(reasons)),
                       "warnings": list(dict.fromkeys(notes))})
    return result


def _plan_warnings(plan: list[dict], live_snapshot) -> list[str]:
    warnings = warn_on_plan_vs_live(
        plan_segments={item["segment_index"]: item for item in plan}, live_snapshot=live_snapshot,
    )
    seen = set()
    live = {item["segment_index"]: item for item in live_snapshot.segments}
    for item in plan:
        index = item["segment_index"]
        if index in seen:
            warnings.append(f"AI plan contains duplicate segment index: {index}; plan times are advisory only")
        seen.add(index)
        start, end = _finite_number(item.get("start_sec")), _finite_number(item.get("end_sec"))
        if start is None or end is None or start < 0 or end <= start:
            warnings.append(f"segment {index}: AI plan timestamps are invalid; plan times are advisory only")
            continue
        if index in live:
            live_start, live_end = _finite_number(live[index].get("start_sec")), _finite_number(live[index].get("end_sec"))
            if live_start is not None and live_end is not None:
                if (abs(start - live_start) > 0.5 or abs(end - live_end) > 0.5) and abs((end - start) - (live_end - live_start)) <= 0.5:
                    warnings.append(f"segment {index}: AI plan timestamps differ from live DOM; plan times are advisory only")
    return list(dict.fromkeys(warnings))


def review_snapshot_json(*, live_json: str, source_json: str, plan_json: str | None = None,
                         tolerance_sec: float = 0.25) -> dict:
    """Return a strict-JSON-safe review report and the unchanged CLI exit semantics.

    Raw SHA256 digests cover the UTF-8 text, including BOM/newlines. The existing
    core checksums describe segment signatures and are not authenticity proofs.
    """
    files = {"live": _file_info(live_json), "source": _file_info(source_json)}
    if plan_json is not None:
        files["plan"] = _file_info(plan_json)
    result = {"schema_version": 1, "scope": "snapshot_integrity", "submit_authorized": False,
              "files": files, "live_checksum": None, "source_checksum": None,
              "rows": [], "reasons": [], "blocking_mismatches": [], "warnings": []}
    try:
        if isinstance(tolerance_sec, bool):
            raise ValueError("tolerance-sec must be a finite nonnegative number")
        tolerance = float(tolerance_sec)
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError("tolerance-sec must be a finite nonnegative number")
        live_segments = parse_segments(live_json, label="live")
        source_segments = parse_segments(source_json, label="source")
        plan = parse_segments(plan_json, label="plan") if plan_json is not None else None
        live = build_segment_snapshot(segments=live_segments, source_kind="live_dom_export")
        source = build_segment_snapshot(segments=source_segments, source_kind="extracted_source")
        decision = compare_segment_snapshots(live_snapshot=live, source_snapshot=source, tolerance_sec=tolerance)
        if plan is not None:
            decision.warnings.extend(_plan_warnings(plan, live))
        result.update(decision.to_dict())
        result["reasons"] = list(decision.blocking_mismatches)
        result.update({"live_checksum": live.checksum, "source_checksum": source.checksum,
                       "tolerance_sec": tolerance, "segment_counts": {"live": len(live_segments), "source": len(source_segments)},
                       "rows": _review_rows(live_segments, source_segments, plan, decision.blocking_mismatches, decision.warnings),
                       "status": "matched" if decision.ok else "blocked", "exit_code": 0 if decision.ok else 1})
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        result.update({"ok": False, "error": str(exc), "reason": str(exc), "reasons": [str(exc)],
                       "status": "input_error", "exit_code": 2})
    return result
