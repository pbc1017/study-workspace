"""Loopback-only HTTP UI and API with same-origin and session authentication."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
import json
import mimetypes
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse, parse_qs

from . import __version__
from .store import Store, Error, require

WEB = Path(__file__).resolve().parent.parent / "web"


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, home, port=8765):
        self.home = Path(home)
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        # Cookies are host-scoped, not port-scoped. Separate concurrent data homes.
        self.cookie_name = f"study_session_{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(
        self, status, body, content_type="application/json; charset=utf-8", cookie=False
    ):
        raw = (
            body
            if isinstance(body, bytes)
            else json.dumps(body, ensure_ascii=False).encode()
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        if cookie:
            self.send_header(
                "Set-Cookie",
                f"{self.server.cookie_name}={self.server.token}; HttpOnly; SameSite=Strict; Path=/",
            )
        self.end_headers()
        self.wfile.write(raw)

    def handle_request(self):
        store = None
        try:
            require(
                self.headers.get("Host") == self.server.origin.split("//")[1],
                "Invalid host",
                403,
            )
            origin = self.headers.get("Origin")
            require(
                not origin or origin == self.server.origin,
                "Cross-origin request denied",
                403,
            )
            require(
                self.headers.get("Sec-Fetch-Site") not in ("cross-site", "same-site"),
                "Cross-site request denied",
                403,
            )
            parsed = urlparse(self.path)
            path = parsed.path
            if self.command == "GET" and not path.startswith("/api/"):
                if path in ("/app.js", "/style.css"):
                    file = WEB / path[1:]
                    return self.send(
                        200,
                        file.read_bytes(),
                        mimetypes.guess_type(file.name)[0] + "; charset=utf-8",
                    )
                require(path == "/" or path.startswith("/projects/"), "Not found", 404)
                return self.send(
                    200,
                    (WEB / "index.html").read_bytes(),
                    "text/html; charset=utf-8",
                    cookie=True,
                )
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            token = (
                cookie[self.server.cookie_name].value
                if self.server.cookie_name in cookie
                else ""
            )
            bearer = self.headers.get("Authorization", "").removeprefix("Bearer ")
            require(
                secrets.compare_digest(token, self.server.token)
                or secrets.compare_digest(bearer, self.server.token),
                "Local session required; open the app first",
                401,
            )
            body = {}
            if self.command in ("POST", "PUT"):
                require(
                    self.headers.get("Content-Type", "").split(";")[0]
                    == "application/json",
                    "Expected JSON body",
                    415,
                )
                length = int(self.headers.get("Content-Length", "0"))
                require(
                    0 < length <= 16 * 1024 * 1024, "Body must be 1 byte–16 MB", 413
                )
                body = json.loads(self.rfile.read(length))
                require(isinstance(body, dict), "Expected JSON object")
            if path == "/api/health" and self.command == "GET":
                return self.send(
                    200, {"version": __version__, "application": "study-workspace"}
                )
            store = Store(self.server.home)
            parts = path.strip("/").split("/")
            query = parse_qs(parsed.query)
            method = self.command
            result = None
            if parts == ["api", "projects"]:
                if method == "GET":
                    result = store.projects()
                elif method == "POST":
                    result = store.create_project(
                        body.get("title"),
                        body.get("description", ""),
                        body.get("profile", "general"),
                    )
            elif len(parts) >= 3 and parts[:2] == ["api", "projects"]:
                pid = parts[2]
                if len(parts) == 3 and method == "GET":
                    result = store.project(pid)
                elif len(parts) == 4:
                    resource = parts[3]
                    if method == "GET":
                        handlers = {
                            "topics": store.topics,
                            "sources": store.sources,
                            "history": store.history,
                            "progress": store.progress,
                            "marks": store.marks,
                            "export": store.export,
                        }
                        if resource in handlers:
                            result = handlers[resource](pid)
                        elif resource == "questions":
                            result = store.questions(pid, query.get("topic", [None])[0])
                    elif method == "POST":
                        if resource == "imports":
                            result = store.import_pack(
                                pid, body.get("pack"), body.get("dryRun", False)
                            )
                        elif resource == "sessions":
                            result = store.start_session(pid, body)
                elif len(parts) == 5 and parts[3] == "marks" and method == "PUT":
                    result = store.mark(pid, parts[4], body)
            elif len(parts) >= 3 and parts[:2] == ["api", "sessions"]:
                sid = parts[2]
                if len(parts) == 3 and method == "GET":
                    result = store.session(sid)
                elif len(parts) == 4 and parts[3] == "submit" and method == "POST":
                    result = store.submit(sid)
                elif len(parts) == 5 and parts[3] == "answers" and method == "PUT":
                    result = store.answer(sid, parts[4], body)
                elif len(parts) == 5 and parts[3] == "assess" and method == "POST":
                    result = store.assess(
                        sid, parts[4], body.get("score"), body.get("feedback", "")
                    )
            require(result is not None, "Not found", 404)
            self.send(200, result)
        except Error as e:
            self.send(e.status, {"error": str(e)})
        except (ValueError, TypeError, KeyError) as e:
            self.send(422, {"error": "Malformed request: " + str(e)})
        except Exception:
            import traceback

            traceback.print_exc()
            self.send(500, {"error": "Internal error; inspect the local runtime log"})
        finally:
            if store:
                store.close()

    do_GET = handle_request
    do_POST = handle_request
    do_PUT = handle_request


def serve(home, port=8765):
    store = Store(home)
    home = store.home
    store.close()
    try:
        server = Server(home, port)
    except OSError:
        if not port:
            raise
        server = Server(home, 0)
    runtime = home / "runtime.json"
    with open(
        runtime, "w", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)
    ) as f:
        json.dump(
            {
                "url": server.origin,
                "token": server.token,
                "pid": os.getpid(),
                "version": __version__,
            },
            f,
        )
    os.chmod(runtime, 0o600)
    print(json.dumps({"url": server.origin, "home": str(home)}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        try:
            if json.loads(runtime.read_text())["pid"] == os.getpid():
                runtime.unlink()
        except (FileNotFoundError, ValueError, KeyError):
            pass
