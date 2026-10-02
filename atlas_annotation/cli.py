"""Validate exported snapshots without browser access or external side effects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .review import parse_segments, read_raw_json, review_snapshot_json


def read_segments(path: Path) -> list[dict]:
    return parse_segments(read_raw_json(path), label=str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=Path, required=True, help="Exported live DOM segments JSON")
    parser.add_argument("--source", type=Path, required=True, help="Previously extracted source segments JSON")
    parser.add_argument("--plan", type=Path, help="Optional AI segment plan; time differences are warnings")
    parser.add_argument("--tolerance-sec", type=float, default=0.25)
    args = parser.parse_args(argv)
    try:
        result = review_snapshot_json(
            live_json=read_raw_json(args.live), source_json=read_raw_json(args.source),
            plan_json=read_raw_json(args.plan) if args.plan is not None else None,
            tolerance_sec=args.tolerance_sec,
        )
        status = result["exit_code"]
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        result = {"scope": "snapshot_integrity", "submit_authorized": False, "ok": False, "error": str(exc)}
        status = 2
    # ASCII JSON also works on Windows consoles whose encoding is not UTF-8.
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
    return status
