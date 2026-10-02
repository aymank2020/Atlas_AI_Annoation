"""Validate exported snapshots without browser access or external side effects."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .snapshots import build_segment_snapshot, compare_segment_snapshots, warn_on_plan_vs_live


def read_segments(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    segments = value.get("segments") if isinstance(value, dict) else value
    if not isinstance(segments, list) or any(not isinstance(item, dict) for item in segments):
        raise ValueError(f"{path}: expected a segment list or an object with a segments list")
    for item in segments:
        index = item.get("segment_index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError(f"{path}: segment_index must be an integer")
        for field in ("start_sec", "end_sec"):
            if isinstance(item.get(field), bool):
                raise ValueError(f"{path}: {field} must be numeric, not boolean")
    return segments


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=Path, required=True, help="Exported live DOM segments JSON")
    parser.add_argument("--source", type=Path, required=True, help="Previously extracted source segments JSON")
    parser.add_argument("--plan", type=Path, help="Optional AI segment plan; time differences are warnings")
    parser.add_argument("--tolerance-sec", type=float, default=0.25)
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.tolerance_sec) or args.tolerance_sec < 0:
            raise ValueError("tolerance-sec must be a finite nonnegative number")
        live = build_segment_snapshot(segments=read_segments(args.live), source_kind="live_dom_export")
        source = build_segment_snapshot(segments=read_segments(args.source), source_kind="extracted_source")
        plan = read_segments(args.plan) if args.plan is not None else None
        decision = compare_segment_snapshots(live_snapshot=live, source_snapshot=source, tolerance_sec=args.tolerance_sec)
        if plan is not None:
            decision.warnings.extend(warn_on_plan_vs_live(
                plan_segments={segment["segment_index"]: segment for segment in plan}, live_snapshot=live,
            ))
        result = {
            "scope": "snapshot_integrity",
            "submit_authorized": False,
            "live_checksum": live.checksum,
            "source_checksum": source.checksum,
            **decision.to_dict(),
        }
        status = 0 if decision.ok else 1
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        result = {"scope": "snapshot_integrity", "submit_authorized": False, "ok": False, "error": str(exc)}
        status = 2
    # ASCII JSON also works on Windows consoles whose encoding is not UTF-8.
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
    return status
