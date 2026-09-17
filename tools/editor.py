"""Serve the map editor.

    python tools/editor.py            http://127.0.0.1:8765/

The editor is a static page (editor/) that reads the same manifest and sheets
the game does, so what you place is what the game draws. A browser cannot
write to the repo, so this small server does two things for it:

    POST /api/save?map=<id>   write content/maps/<name>.json
    POST /api/build           run tools/build.py and return its output

Local only. It serves the repository root, so the editor can fetch
build/manifest.json, assets/atlases/*.png and content/maps/*.json directly.
"""

import json
import os
import subprocess
import sys
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
PORT = int(os.environ.get("EDITOR_PORT", "8765"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # always the latest build
        super().end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/editor", "/editor/"):
            self.path = "/editor/index.html"
        elif url.path == "/api/maps":
            d = os.path.join(ROOT, "content", "maps")
            maps = sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))
            return self._json(HTTPStatus.OK, {"maps": maps})
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""

        if url.path == "/api/save":
            name = parse_qs(url.query).get("map", [""])[0]
            if not name or not all(c.isalnum() or c in "_-" for c in name):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad map name"})
            try:
                data = json.loads(raw.decode("utf-8"))
            except ValueError as e:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": f"not JSON: {e}"})
            path = os.path.join(ROOT, "content", "maps", f"{name}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            return self._json(HTTPStatus.OK, {"ok": True, "path": os.path.relpath(path, ROOT)})

        if url.path == "/api/build":
            proc = subprocess.run([sys.executable, os.path.join(TOOLS, "build.py")],
                                  capture_output=True, text=True, cwd=ROOT)
            out = (proc.stdout + proc.stderr).strip()
            return self._json(HTTPStatus.OK, {"ok": proc.returncode == 0, "output": out})

        return self._json(HTTPStatus.NOT_FOUND, {"error": "no such endpoint"})


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"map editor at {url}   (Ctrl+C to stop)")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
