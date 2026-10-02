"""Offline Atlas annotation snapshot validation core."""

from .snapshots import (
    DesyncDecision,
    SegmentSnapshot,
    build_segment_snapshot,
    compare_segment_snapshots,
    warn_on_plan_vs_live,
)

__all__ = [
    "DesyncDecision", "SegmentSnapshot", "build_segment_snapshot",
    "compare_segment_snapshots", "warn_on_plan_vs_live",
]
