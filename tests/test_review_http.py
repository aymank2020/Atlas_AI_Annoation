"""Actual library -> CLI subprocess -> HTTP route equivalence and boundaries."""

import hashlib
from http.client import HTTPConnection
from importlib.resources import files
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from atlas_annotation import parse_segments, review_snapshot_json
from atlas_annotation.review import MAX_FILE_BYTES, MAX_SEGMENTS, read_raw_json
from atlas_annotation.web import MAX_BODY_BYTES, create_review_server

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CASES = json.loads((FIXTURES / "review-cases.json").read_text(encoding="utf-8"))


class ReviewHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_review_server(port=0)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, data=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            defaults = {"Content-Type": "application/json"} if data is not None else {}
            defaults.update(headers or {})
            connection.request(method, path, body=data, headers=defaults)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def run_cli(self, inputs):
        with tempfile.TemporaryDirectory() as directory:
            arguments = [sys.executable, "-m", "atlas_annotation"]
            for key, flag in (("live_json", "--live"), ("source_json", "--source"), ("plan_json", "--plan")):
                if key in inputs:
                    path = Path(directory) / (key + ".json")
                    path.write_bytes(inputs[key].encode("utf-8"))
                    arguments.extend((flag, str(path)))
            arguments.extend(("--tolerance-sec", str(inputs.get("tolerance_sec", 0.25))))
            process = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.stderr, "")
        return process.returncode, json.loads(process.stdout)

    def test_fourteen_raw_fixtures_match_library_cli_and_http(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                inputs = {key: value for key, value in case.items() if key.endswith("_json") or key == "tolerance_sec"}
                expected = review_snapshot_json(**inputs)
                code, cli = self.run_cli(inputs)
                status, _, body = self.request("POST", "/api/review", json.dumps(inputs).encode())
                self.assertEqual(status, 200)
                http = json.loads(body)
                self.assertEqual(code, case["exit_code"])
                self.assertEqual(expected["exit_code"], case["exit_code"])
                self.assertEqual(cli, expected)
                self.assertEqual(http, expected)
                self.assertFalse(http["submit_authorized"])
                self.assertEqual(http["files"]["live"]["raw_sha256"], hashlib.sha256(inputs["live_json"].encode()).hexdigest())
                self.assertEqual(http["files"]["source"]["raw_sha256"], hashlib.sha256(inputs["source_json"].encode()).hexdigest())
                if "reason" in case:
                    reasons = " ".join(http.get("blocking_mismatches", [])) + http.get("error", "")
                    self.assertIn(case["reason"], reasons)
                if "warning" in case:
                    self.assertIn(case["warning"], " ".join(http["warnings"]))
                if "row_state" in case:
                    self.assertIn(case["row_state"], {item["state"] for item in http["rows"]})
                # The final result is strict JSON even when the raw inputs contain NaN/Infinity.
                json.dumps(http, allow_nan=False)

    def test_windows_bom_and_linux_formats_keep_raw_provenance(self):
        windows = read_raw_json(FIXTURES / "windows-snapshot.json")
        linux = read_raw_json(FIXTURES / "linux-snapshot.json")
        self.assertTrue(windows.startswith("\ufeff"))
        self.assertFalse(linux.startswith("\ufeff"))
        for raw in (windows, windows.replace("\r\n", "\n").replace("\n", "\r\n")):
            with self.subTest(raw_windows_line_endings=repr(raw[-2:])):
                inputs = {"live_json": raw, "source_json": linux}
                code, cli = self.run_cli(inputs)
                status, _, body = self.request("POST", "/api/review", json.dumps(inputs).encode())
                self.assertEqual((code, status), (0, 200))
                self.assertEqual(json.loads(body), cli)
                self.assertEqual(cli["live_checksum"], cli["source_checksum"])
                self.assertNotEqual(cli["files"]["live"]["raw_sha256"], cli["files"]["source"]["raw_sha256"])
                self.assertEqual(cli["files"]["live"]["raw_sha256"], hashlib.sha256(raw.encode("utf-8")).hexdigest())
        self.assertEqual(parse_segments(windows)[0]["start_sec"], "0")

    def test_table_retains_duplicates_missing_drift_and_invalid_values(self):
        reports = {case["name"]: review_snapshot_json(**{key: value for key, value in case.items() if key.endswith("_json") or key == "tolerance_sec"}) for case in CASES}
        duplicate = reports["duplicate"]["rows"][0]
        self.assertEqual(len(duplicate["live"]), 2)
        missing = reports["count_missing"]["rows"][1]
        self.assertEqual(missing["segment_index"], "2")
        self.assertEqual(missing["state"], "missing_live")
        self.assertTrue(missing["blocking_mismatches"])
        self.assertEqual(reports["drift"]["rows"][0]["drift"]["end_sec"], 1)
        self.assertEqual(reports["nan"]["rows"][0]["live"][0]["start_sec"], "nan")

    def test_size_row_and_nested_input_limits(self):
        valid = CASES[0]["live_json"]
        for raw in (" " * (MAX_FILE_BYTES + 1), json.dumps([{"segment_index": 1}] * (MAX_SEGMENTS + 1)), "[" * 1100 + "]" * 1100):
            result = review_snapshot_json(live_json=raw, source_json=valid)
            self.assertEqual(result["exit_code"], 2)
            status, _, body = self.request("POST", "/api/review", json.dumps({"live_json": raw, "source_json": valid}).encode())
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), result)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            path.write_bytes(b" " * (MAX_FILE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "exceeds"):
                read_raw_json(path)
        status, _, _ = self.request("POST", "/api/review", b"", {"Content-Length": str(MAX_BODY_BYTES + 1)})
        self.assertEqual(status, 413)

    def test_host_origin_types_and_content_length_are_checked(self):
        request = json.dumps({"live_json": "[]", "source_json": "[]"}).encode()
        for headers in ({"Host": "evil.example"}, {"Host": f"127.0.0.1:{self.port + 1}"}, {"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            status, _, _ = self.request("POST", "/api/review", request, headers)
            self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/api/review", request, {"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)
        for payload in ({"live_json": [], "source_json": []}, {"live_json": "[]", "source_json": "[]", "path": "README.md"}, {"live_json": "[]", "source_json": "[]", "plan_json": []}):
            status, _, _ = self.request("POST", "/api/review", json.dumps(payload).encode())
            self.assertEqual(status, 400)
        status, _, _ = self.request("POST", "/api/review", request, {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        status, _, _ = self.request("POST", "/api/review", b"", {"Content-Length": "-1"})
        self.assertEqual(status, 400)

    def test_only_packaged_assets_are_served(self):
        for route, filename in (("/", "index.html"), ("/app.js", "app.js"), ("/style.css", "style.css")):
            status, headers, body = self.request("GET", route)
            self.assertEqual(status, 200)
            self.assertEqual(body, files("atlas_annotation").joinpath("ui", filename).read_bytes())
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        for path in ("/../README.md", "/%2e%2e/README.md", "/C:/Windows/win.ini", "/api/review?file=README.md", "/PROVENANCE.md"):
            status, _, _ = self.request("GET", path)
            self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
