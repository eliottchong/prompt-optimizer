"""
Serve the HTML dashboard and POST /api/optimize → prompt_optimizer.clean_prompt.

Stdlib only: run from this directory:
    python server.py
Then open http://127.0.0.1:8765/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from wsgiref.simple_server import make_server

from prompt_optimizer import clean_prompt

ROOT = Path(__file__).resolve().parent
DASHBOARD_PATH = ROOT / "static" / "dashboard.html"
MAX_BODY = 500_000  # bytes


def _read_body(environ: dict) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH", 0))
    except (TypeError, ValueError):
        length = 0
    if length > MAX_BODY:
        raise ValueError("payload too large")
    return environ["wsgi.input"].read(length) if length else b""


def application(environ: dict, start_response):
    path = environ.get("PATH_INFO", "") or "/"
    method = environ.get("REQUEST_METHOD", "GET")

    if path == "/" and method == "GET":
        if not DASHBOARD_PATH.is_file():
            msg = b"dashboard.html not found. Expected: static/dashboard.html"
            start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
            return [msg]
        html = DASHBOARD_PATH.read_text(encoding="utf-8")
        body = html.encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    if path == "/api/optimize" and method == "POST":
        try:
            raw = _read_body(environ)
            data = json.loads(raw.decode("utf-8") or "{}")
            prompt = data.get("prompt", "")
            if not isinstance(prompt, str):
                prompt = str(prompt)
            out = clean_prompt(prompt)
            payload = json.dumps({"ok": True, "output": out}).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Content-Length", str(len(payload))),
                ],
            )
            return [payload]
        except json.JSONDecodeError:
            err = json.dumps({"ok": False, "error": "invalid JSON"}).encode("utf-8")
            start_response(
                "400 Bad Request",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Content-Length", str(len(err))),
                ],
            )
            return [err]
        except ValueError as e:
            err = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            start_response(
                "413 Payload Too Large",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Content-Length", str(len(err))),
                ],
            )
            return [err]
        except Exception as e:  # noqa: BLE001 — last-resort API error
            err = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            start_response(
                "500 Internal Server Error",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Content-Length", str(len(err))),
                ],
            )
            return [err]

    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"Not Found"]


def main() -> None:
    host = "127.0.0.1"
    port = 8765
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])
    print(f"Prompt Optimizer dashboard: http://{host}:{port}/")
    print("Press Ctrl+C to stop.")
    with make_server(host, port, application) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
