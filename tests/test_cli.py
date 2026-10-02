import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SnapshotCliTests(unittest.TestCase):
    def run_cli(self, live, source=None, plan=None, extra=()):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for name, value in (("live", live), ("source", live if source is None else source)):
                (directory / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            command = [sys.executable, "-m", "atlas_annotation", "--live", str(directory / "live.json"), "--source", str(directory / "source.json")]
            if plan is not None:
                (directory / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
                command.extend(["--plan", str(directory / "plan.json")])
            process = subprocess.run(command + list(extra), cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.stderr, "")
        return process.returncode, json.loads(process.stdout)

    def valid(self):
        return [{"segment_index": 1, "start_sec": 0, "end_sec": 4, "current_label": "pick up cup"}]

    def test_valid_snapshot_roundtrip(self):
        code, result = self.run_cli(self.valid())
        self.assertEqual(code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["live_checksum"], result["source_checksum"])
        self.assertFalse(result["submit_authorized"])

    def test_matching_corrupt_or_empty_snapshots_are_blocked(self):
        for segments in ([], self.valid() * 2, [{"segment_index": 0, "start_sec": 0, "end_sec": 4}], [{"segment_index": 1, "start_sec": -1, "end_sec": 4}], [{"segment_index": 1, "start_sec": 4, "end_sec": 4}]):
            with self.subTest(segments=segments):
                code, result = self.run_cli(segments)
                self.assertEqual(code, 1)
                self.assertFalse(result["ok"])
                self.assertTrue(result["requires_reextract"])

    def test_nonfinite_or_missing_timestamps_are_blocked(self):
        for value in (float("nan"), float("inf"), float("-inf"), None, "invalid"):
            for field in ("start_sec", "end_sec"):
                with self.subTest(value=value, field=field):
                    segments = self.valid()
                    segments[0][field] = value
                    code, result = self.run_cli(segments)
                    self.assertEqual(code, 1)
                    self.assertTrue(any("finite numbers" in item for item in result["blocking_mismatches"]))

    def test_source_drift_is_blocked(self):
        source = self.valid()
        source[0]["end_sec"] = 5
        code, result = self.run_cli(self.valid(), source)
        self.assertEqual(code, 1)
        self.assertTrue(any("drifted" in item for item in result["blocking_mismatches"]))

    def test_ai_timestamps_are_warnings(self):
        plan = self.valid()
        plan[0]["end_sec"] = 99
        code, result = self.run_cli(self.valid(), plan=plan)
        self.assertEqual(code, 0)
        self.assertTrue(result["warnings"])

    def test_invalid_tolerance_is_an_input_error(self):
        for value in ("nan", "inf", "-1"):
            code, result = self.run_cli(self.valid(), extra=("--tolerance-sec", value))
            self.assertEqual(code, 2)
            self.assertIn("nonnegative", result["error"])

    def test_invalid_shape_or_index_is_an_input_error(self):
        for value in ({}, [1], [{}], [{"segment_index": "invalid"}], [{"segment_index": True}], [{"segment_index": 1, "start_sec": True, "end_sec": 4}]):
            code, result = self.run_cli(value)
            self.assertEqual(code, 2)
            self.assertFalse(result["ok"])

    def test_missing_input_is_reported_without_traceback(self):
        process = subprocess.run([sys.executable, "-m", "atlas_annotation", "--live", "missing.json", "--source", "missing.json"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stderr, "")
        self.assertFalse(json.loads(process.stdout)["ok"])

    def test_invalid_json_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{invalid", encoding="utf-8")
            process = subprocess.run([sys.executable, "-m", "atlas_annotation", "--live", str(path), "--source", str(path)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stderr, "")
        self.assertFalse(json.loads(process.stdout)["ok"])

    def test_library_cannot_bypass_drift_with_nonfinite_tolerance(self):
        from atlas_annotation import build_segment_snapshot, compare_segment_snapshots
        snapshot = build_segment_snapshot(segments=self.valid())
        for value in (float("nan"), float("inf"), -1):
            decision = compare_segment_snapshots(live_snapshot=snapshot, source_snapshot=snapshot, tolerance_sec=value)
            self.assertFalse(decision.ok)
            self.assertTrue(decision.requires_reextract)


if __name__ == "__main__":
    unittest.main()
