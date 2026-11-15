"""Small web server for the Graduation Planner page.

Run from the project root:
    python frontend/server.py
then open http://127.0.0.1:8000

It serves the three files in this folder and answers the form's POST to
/user_submission with the plan as JSON. It only listens on this computer.
"""
import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

FRONTEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FRONTEND_DIR.parent))  # so planner_service can be imported

# Only these files can be requested; nothing else on disk is ever served.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/script.js": ("script.js", "application/javascript; charset=utf-8"),
    "/campus-background-v2.svg": ("campus-background-v2.svg", "image/svg+xml"),
}

MAX_BODY_BYTES = 10_000
MAX_UNITS = 30
SUPPORTED_SCHOOLS = {"", "csus"}  # only Sacramento State has course data

# Making a plan takes minutes and uses the local model, so only one runs at a time.
_planner_busy = threading.Lock()


class RequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _units(fields: dict[str, str], name: str, label: str) -> int | None:
    text = fields.get(name, "").strip()
    if text == "":
        return None
    if not text.isascii() or not text.isdigit() or int(text) > MAX_UNITS:
        raise RequestError(400, f"{label} must be a whole number from 0 to {MAX_UNITS}.")
    return int(text)


def read_form(fields: dict[str, str]) -> dict:
    """Check the submitted form again on the server (the page's checks can be bypassed)."""
    student_id = fields.get("sid", "").strip()
    if not student_id:
        raise RequestError(400, "Enter your student ID.")
    if len(student_id) > 64:
        raise RequestError(400, "Student ID is too long.")
    if fields.get("school", "").strip() not in SUPPORTED_SCHOOLS:
        raise RequestError(400, "Only California State University, Sacramento is supported right now.")

    min_units = _units(fields, "min_unit_load", "Minimum units")
    max_units = _units(fields, "max_unit_load", "Maximum units")
    if min_units is not None and max_units is not None and min_units > max_units:
        raise RequestError(400, "Minimum units cannot be greater than maximum units.")
    return {"student_id": student_id, "min_units": min_units, "max_units": max_units}


def make_server(host: str, port: int, planner=None) -> ThreadingHTTPServer:
    """Build the server. `planner` is only replaced in tests."""
    if planner is None:
        from planner_service import run_planner as planner

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def do_GET(self):
            entry = STATIC_FILES.get(self.path.split("?", 1)[0])
            if entry is None:
                self._json(404, {"error": "Page not found."})
                return
            filename, content_type = entry
            try:
                body = (FRONTEND_DIR / filename).read_bytes()
            except OSError:
                self._json(404, {"error": f"{filename} is missing."})
                return
            self._send(200, body, content_type)

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/user_submission":
                self._json(404, {"error": "Not found."})
                return
            try:
                self._handle_submission()
            except RequestError as exc:
                self._json(exc.status, {"error": exc.message})
            except Exception as exc:  # PlannerError and anything unexpected
                status = getattr(exc, "status", 500)
                message = getattr(exc, "message", None) or f"Unexpected server error: {type(exc).__name__}"
                self._json(status, {"error": message})

        def _handle_submission(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise RequestError(400, "Bad request.")
            if length <= 0:
                raise RequestError(400, "The form was empty.")
            if length > MAX_BODY_BYTES:
                raise RequestError(413, "The form data is too large.")

            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            fields = {key: values[0] for key, values in parse_qs(raw, keep_blank_values=True).items()}
            form = read_form(fields)

            if not _planner_busy.acquire(blocking=False):
                raise RequestError(429, "A plan is already being created. Try again in a minute.")
            try:
                result = planner(**form)
            finally:
                _planner_busy.release()
            self._json(200, result)

        def log_message(self, format, *args):  # one short line per request
            sys.stderr.write(f"{self.address_string()} {format % args}\n")

    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the Graduation Planner page.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = make_server("127.0.0.1", args.port)
    print(f"Graduation Planner running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
