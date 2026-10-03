"""Machine-readable CLI shared by Codex, Claude Code, and people."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

from .store import Store, Error, require
from . import __version__

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def open_runtime(home, browser=True):
    runtime = home / "runtime.json"

    def check():
        try:
            meta = load(runtime)
            from urllib.parse import urlparse

            url = urlparse(meta["url"])
            if url.scheme != "http" or url.hostname != "127.0.0.1":
                return None
            request = urllib.request.Request(
                meta["url"] + "/api/health",
                headers={"Authorization": "Bearer " + meta["token"]},
            )
            with urllib.request.urlopen(request, timeout=1) as response:
                data = json.load(response)
            if (
                data.get("application") == "study-workspace"
                and data.get("version") == __version__
            ):
                return meta
        except (OSError, ValueError, KeyError):
            pass
        return None

    # A file lock serializes simultaneous startup from two agent hosts.
    import fcntl

    with open(home / "startup.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        meta = check()
        if not meta:
            log = open(home / "runtime.log", "ab")
            try:
                proc = subprocess.Popen(
                    [
                        sys.executable,
                        str(ROOT / "scripts/study.py"),
                        "--home",
                        str(home),
                        "serve",
                    ],
                    stdout=log,
                    stderr=log,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
            finally:
                log.close()
            for _ in range(80):
                meta = check()
                if meta:
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            require(meta is not None, f"Runtime failed; see {home/'runtime.log'}", 500)
    if browser:
        webbrowser.open(meta["url"])
    return {"url": meta["url"], "home": str(home), "version": meta["version"]}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Local project-based learning for Codex and Claude Code"
    )
    parser.add_argument("--home", help="Data directory (or STUDY_WORKSPACE_HOME)")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("projects")
    p = sub.add_parser("create")
    p.add_argument("title")
    p.add_argument("--description", default="")
    p.add_argument(
        "--profile",
        default="general",
        choices=["general", "school", "university", "certification", "aws-aif"],
    )
    p = sub.add_parser("import")
    p.add_argument("project")
    p.add_argument("file")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("source")
    p.add_argument("project")
    p.add_argument("file")
    p = sub.add_parser("demo")
    p.add_argument(
        "--kind", choices=["biology", "linear-algebra", "aws"], default="biology"
    )
    p = sub.add_parser("start")
    p.add_argument("project")
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--mode", choices=["practice", "review", "exam"], default="practice")
    p.add_argument("--topic")
    p.add_argument("--request-key")
    p = sub.add_parser("session")
    p.add_argument("session")
    p = sub.add_parser("answer")
    p.add_argument("session")
    p.add_argument("item")
    p.add_argument("file", help="JSON object containing answer and version")
    p = sub.add_parser("submit")
    p.add_argument("session")
    p = sub.add_parser("assess")
    p.add_argument("session")
    p.add_argument("item")
    p.add_argument("score", type=float)
    p.add_argument("--feedback", default="")
    for command in [
        "progress",
        "review",
        "topics",
        "questions",
        "sources",
        "history",
        "export",
    ]:
        p = sub.add_parser(command)
        p.add_argument("project")
        if command == "export":
            p.add_argument("--output")
    p = sub.add_parser("mark")
    p.add_argument("project")
    p.add_argument("question")
    p.add_argument("file")
    p = sub.add_parser("backup")
    p.add_argument("destination")
    p = sub.add_parser("migrate-aws")
    p.add_argument("directory")
    p.add_argument("--title", default="AWS AI Practitioner")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("open")
    p.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    store = None
    try:
        store = Store(args.home)
        cmd = args.command
        if cmd == "doctor":
            import shutil, sqlite3

            result = {
                "version": __version__,
                "python": sys.version.split()[0],
                "sqlite": sqlite3.sqlite_version,
                "home": str(store.home),
                "pdfTextExtraction": bool(shutil.which("pdftotext")),
                "database": "ok",
            }
        elif cmd == "create":
            result = store.create_project(args.title, args.description, args.profile)
        elif cmd == "projects":
            result = store.projects()
        elif cmd == "import":
            result = store.import_pack(args.project, load(args.file), args.dry_run)
        elif cmd == "source":
            result = store.add_source(args.project, args.file)
        elif cmd == "demo":
            pack = load(ROOT / "examples" / (args.kind + ".json"))
            p = store.create_project(
                pack["project"]["title"],
                pack["project"].get("description", ""),
                pack["project"].get("profile", "general"),
            )
            result = {"project": p, "import": store.import_pack(p["id"], pack)}
        elif cmd == "start":
            config = {"count": args.count, "mode": args.mode, "topic": args.topic}
            if args.request_key:
                config["requestKey"] = args.request_key
            result = store.start_session(args.project, config)
        elif cmd == "session":
            result = store.session(args.session)
        elif cmd == "answer":
            result = store.answer(args.session, args.item, load(args.file))
        elif cmd == "submit":
            result = store.submit(args.session)
        elif cmd == "assess":
            result = store.assess(args.session, args.item, args.score, args.feedback)
        elif cmd == "mark":
            result = store.mark(args.project, args.question, load(args.file))
        elif cmd == "backup":
            result = store.backup(args.destination)
        elif cmd == "migrate-aws":
            from .migration import migrate

            result = migrate(store, args.directory, args.title, args.dry_run)
        elif cmd == "serve":
            from .server import serve

            home = store.home
            store.close()
            store = None
            serve(home, args.port)
            return 0
        elif cmd == "open":
            result = open_runtime(store.home, not args.no_browser)
        else:
            method = {"review": "marks"}.get(cmd, cmd)
            result = getattr(store, method)(args.project)
            if cmd == "export" and args.output:
                destination = Path(args.output).expanduser()
                with destination.open("x", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                result = {"output": str(destination.resolve())}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (Error, OSError, ValueError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if store:
            store.close()
