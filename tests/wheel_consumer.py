"""Exercise installed console commands and packaged UI from outside the checkout."""

import argparse
import hashlib
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, help="Existing pip --target installation")
    parser.add_argument("--evidence", type=Path, help="Optional JSON receipt path")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if args.target:
        env["PYTHONPATH"] = str(args.target.resolve())
        suffix = ".exe" if os.name == "nt" else ""
        server_command = str(args.target.resolve() / "bin" / ("atlas-snapshot-review" + suffix))
        cli_command = str(args.target.resolve() / "bin" / ("atlas-annotation" + suffix))
    else:
        env.pop("PYTHONPATH", None)
        server_command = shutil.which("atlas-snapshot-review")
        cli_command = shutil.which("atlas-annotation")
    assert server_command and cli_command, "Install the wheel before this check"
    payload = {"live_json": (root / "examples/live.json").read_text(encoding="utf-8"),
               "source_json": (root / "examples/source.json").read_text(encoding="utf-8"),
               "plan_json": (root / "examples/ai-plan.json").read_text(encoding="utf-8")}
    with tempfile.TemporaryDirectory() as directory:
        cli = subprocess.run([cli_command, "--live", str(root / "examples/live.json"),
                              "--source", str(root / "examples/source.json"),
                              "--plan", str(root / "examples/ai-plan.json")],
                             cwd=directory, env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
        assert cli.returncode == 0, cli.stderr
        cli_result = json.loads(cli.stdout)
        assert cli_result["submit_authorized"] is False and cli_result["warnings"]
        server = subprocess.Popen([server_command, "--port", "0"], cwd=directory, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            # The console command flushes its bound URL before accepting requests.
            startup = queue.Queue()
            threading.Thread(target=lambda: startup.put(server.stdout.readline()), daemon=True).start()
            line = startup.get(timeout=10).strip()
            assert line.startswith("Atlas snapshot review: http://127.0.0.1:"), line
            port = int(line.rsplit(":", 1)[1].removesuffix("/"))
            assets = {}
            for route, filename in (("/", "index.html"), ("/app.js", "app.js"), ("/style.css", "style.css")):
                connection = HTTPConnection("127.0.0.1", port, timeout=10)
                connection.request("GET", route)
                response = connection.getresponse()
                data = response.read()
                assert response.status == 200
                assert data == (root / "atlas_annotation/ui" / filename).read_bytes()
                assets[filename] = hashlib.sha256(data).hexdigest()
                connection.close()
            connection = HTTPConnection("127.0.0.1", port, timeout=10)
            connection.request("POST", "/api/review", json.dumps(payload).encode(), {"Content-Type": "application/json"})
            response = connection.getresponse()
            result = json.loads(response.read())
            connection.close()
            assert response.status == 200
            assert result == cli_result
            receipt = {"status": "passed", "entrypoint": server_command,
                       "cli_entrypoint": cli_command, "cwd_outside_checkout": True,
                       "assets_sha256": assets, "exit_code": result["exit_code"],
                       "submit_authorized": result["submit_authorized"],
                       "warnings": result["warnings"], "raw_digests": result["files"]}
            if args.evidence:
                args.evidence.parent.mkdir(parents=True, exist_ok=True)
                args.evidence.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(receipt, indent=2))
        finally:
            server.terminate()
            server.communicate(timeout=10)


if __name__ == "__main__":
    main()
