"""Shared persistence and learning rules. Python standard library only."""

import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Error(Exception):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def require(condition, message, status=422):
    if not condition:
        raise Error(message, status)


def text(value, name, limit=100000):
    require(
        isinstance(value, str) and value.strip() and len(value) <= limit,
        f"Invalid {name}",
    )
    return value.strip()


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


AWS_POLICY = {
    "count": 65,
    "scored": 50,
    "minutes": 90,
    "minScore": 100,
    "maxScore": 1000,
    "passingScore": 700,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 profile TEXT NOT NULL DEFAULT 'general', policy TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL,
 content_hash TEXT NOT NULL, relative_path TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(project_id, content_hash));
CREATE TABLE IF NOT EXISTS topics (
 id TEXT NOT NULL, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL,
 body TEXT NOT NULL, objectives TEXT NOT NULL DEFAULT '[]', source_refs TEXT NOT NULL DEFAULT '[]',
 position INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(project_id,id));
CREATE TABLE IF NOT EXISTS questions (
 id TEXT NOT NULL, project_id TEXT NOT NULL REFERENCES projects(id), number TEXT NOT NULL,
 revision INTEGER NOT NULL, payload TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(project_id,id));
CREATE TABLE IF NOT EXISTS question_revisions (
 project_id TEXT NOT NULL, question_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(project_id,question_id,revision),
 FOREIGN KEY(project_id,question_id) REFERENCES questions(project_id,id));
CREATE TABLE IF NOT EXISTS imports (
 project_id TEXT NOT NULL REFERENCES projects(id), content_hash TEXT NOT NULL, report TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(project_id,content_hash));
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), mode TEXT NOT NULL,
 policy TEXT NOT NULL, started_at TEXT NOT NULL, expires_at TEXT, finished_at TEXT,
 status TEXT NOT NULL, result TEXT, request_key TEXT NOT NULL,
 UNIQUE(project_id,request_key));
CREATE TABLE IF NOT EXISTS items (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), question_id TEXT NOT NULL,
 snapshot TEXT NOT NULL, position INTEGER NOT NULL, scored INTEGER NOT NULL,
 answer TEXT NOT NULL DEFAULT 'null', flagged INTEGER NOT NULL DEFAULT 0,
 hints INTEGER NOT NULL DEFAULT 0, confidence INTEGER, version INTEGER NOT NULL DEFAULT 0,
 score REAL, feedback TEXT NOT NULL DEFAULT '', grade_status TEXT NOT NULL DEFAULT 'ungraded',
 UNIQUE(session_id,position));
CREATE TABLE IF NOT EXISTS marks (
 project_id TEXT NOT NULL, question_id TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]',
 memo TEXT NOT NULL DEFAULT '', resolved INTEGER NOT NULL DEFAULT 0, due_at TEXT,
 streak INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id,question_id),
 FOREIGN KEY(project_id,question_id) REFERENCES questions(project_id,id));
CREATE INDEX IF NOT EXISTS sessions_project ON sessions(project_id,started_at);
CREATE INDEX IF NOT EXISTS items_session ON items(session_id,position);
CREATE INDEX IF NOT EXISTS marks_due ON marks(project_id,resolved,due_at);
"""


class Store:
    def __init__(self, home=None):
        self.home = (
            Path(
                home
                or os.environ.get(
                    "STUDY_WORKSPACE_HOME", Path.home() / ".local/share/study-workspace"
                )
            )
            .expanduser()
            .resolve()
        )
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.home / "study.db", timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        require(
            version <= 1,
            "Database belongs to a newer runtime; upgrade before opening",
            409,
        )
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA user_version=1")
        self.db.commit()

    def close(self):
        self.db.close()

    def row(self, sql, args=()):
        r = self.db.execute(sql, args).fetchone()
        require(r is not None, "Not found", 404)
        return dict(r)

    def rows(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args)]

    def project(self, project_id):
        p = self.row("SELECT * FROM projects WHERE id=?", (project_id,))
        p["policy"] = json.loads(p["policy"])
        return p

    def projects(self):
        return self.rows(
            """SELECT p.*, (SELECT count(*) FROM questions q WHERE q.project_id=p.id AND q.active=1) question_count,
          (SELECT count(*) FROM topics t WHERE t.project_id=p.id) topic_count
          FROM projects p ORDER BY created_at DESC"""
        )

    def create_project(self, title, description="", profile="general"):
        title = text(title, "title", 200)
        require(
            profile in ("general", "school", "university", "certification", "aws-aif"),
            "Invalid profile",
        )
        p = uid()
        with self.db:
            self.db.execute(
                "INSERT INTO projects VALUES (?,?,?,?,?,?)",
                (
                    p,
                    title,
                    str(description)[:10000],
                    profile,
                    dump(AWS_POLICY if profile == "aws-aif" else {}),
                    now(),
                ),
            )
        return self.project(p)

    def validate_pack(self, pack):
        require(
            isinstance(pack, dict) and pack.get("schemaVersion") == 1,
            "Expected schemaVersion: 1",
        )
        topics, questions = pack.get("topics", []), pack.get("questions", [])
        require(
            isinstance(topics, list) and isinstance(questions, list),
            "topics/questions must be arrays",
        )
        require(len(topics) <= 1000 and len(questions) <= 10000, "Pack too large")
        seen = set()
        for t in topics:
            require(isinstance(t, dict), "Invalid topic")
            key = text(t.get("id"), "topic.id", 150)
            require(key not in seen, "Duplicate topic id")
            seen.add(key)
            text(t.get("title"), "topic.title", 300)
            require(isinstance(t.get("body", ""), str), "Invalid topic body")
            require(
                isinstance(t.get("objectives", []), list)
                and all(isinstance(x, str) for x in t.get("objectives", [])),
                "Invalid objectives",
            )
        qids = set()
        for q in questions:
            require(isinstance(q, dict), "Invalid question")
            key = text(q.get("id"), "question.id", 150)
            require(key not in qids, "Duplicate question id")
            qids.add(key)
            text(q.get("prompt"), "question.prompt")
            require(
                q.get("type") in ("single", "multiple", "short", "essay"),
                "Unsupported question type",
            )
            require(
                q.get("status", "active") in ("draft", "active"),
                "Invalid question status",
            )
            require(
                q.get("origin", "generated") in ("original", "generated"),
                "Invalid origin",
            )
            require(
                isinstance(q.get("topics", []), list)
                and all(isinstance(x, str) for x in q.get("topics", [])),
                "Invalid topics",
            )
            require(
                isinstance(q.get("sourceRefs", []), list)
                and all(isinstance(x, str) for x in q.get("sourceRefs", [])),
                "Invalid sourceRefs",
            )
            require(
                isinstance(q.get("points", 1), (int, float))
                and 0 < q.get("points", 1) <= 1000,
                "Invalid points",
            )
            if q["type"] in ("single", "multiple"):
                opts = q.get("options", [])
                require(
                    isinstance(opts, list) and 2 <= len(opts) <= 20, "Need 2–20 options"
                )
                labels = [
                    text(o.get("label"), "option.label", 10)
                    for o in opts
                    if isinstance(o, dict)
                ]
                require(
                    len(labels) == len(opts) == len(set(labels)),
                    "Invalid or duplicate options",
                )
                for o in opts:
                    text(o.get("text"), "option.text")
                answers = q.get("answer", [])
                require(
                    isinstance(answers, list)
                    and answers
                    and all(isinstance(a, str) for a in answers),
                    "Answer labels required",
                )
                require(
                    len(answers) == len(set(answers)) and set(answers) <= set(labels),
                    "Invalid answer labels",
                )
                require(
                    q["type"] != "single" or len(answers) == 1,
                    "Single choice requires one answer",
                )
            elif q["type"] == "short":
                require(
                    isinstance(q.get("answer"), list)
                    and q["answer"]
                    and all(isinstance(a, str) and a.strip() for a in q["answer"]),
                    "Short answer requires accepted strings",
                )
            else:
                text(q.get("rubric"), "essay rubric")
        return {
            "topics": len(topics),
            "questions": len(questions),
            "drafts": sum(q.get("status") == "draft" for q in questions),
        }

    def import_pack(self, project_id, pack, dry_run=False):
        self.project(project_id)
        report = self.validate_pack(pack)
        topic_ids = {
            r["id"]
            for r in self.rows(
                "SELECT id FROM topics WHERE project_id=?", (project_id,)
            )
        } | {t["id"] for t in pack.get("topics", [])}
        require(
            all(
                set(q.get("topics", [])) <= topic_ids for q in pack.get("questions", [])
            ),
            "Unknown topic reference",
        )
        digest = hashlib.sha256(
            json.dumps(pack, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        if dry_run:
            return {**report, "dryRun": True, "hash": digest}
        try:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute(
                "SELECT report FROM imports WHERE project_id=? AND content_hash=?",
                (project_id, digest),
            ).fetchone()
            if old:
                self.db.rollback()
                return {**json.loads(old[0]), "unchanged": True}
            for i, t in enumerate(pack.get("topics", [])):
                self.db.execute(
                    """INSERT INTO topics VALUES (?,?,?,?,?,?,?) ON CONFLICT(project_id,id) DO UPDATE SET
                 title=excluded.title,body=excluded.body,objectives=excluded.objectives,source_refs=excluded.source_refs,position=excluded.position""",
                    (
                        t["id"],
                        project_id,
                        t["title"],
                        t.get("body", ""),
                        dump(t.get("objectives", [])),
                        dump(t.get("sourceRefs", [])),
                        i,
                    ),
                )
            for q in pack.get("questions", []):
                payload = dump(q)
                old = self.db.execute(
                    "SELECT revision,payload FROM questions WHERE project_id=? AND id=?",
                    (project_id, q["id"]),
                ).fetchone()
                if old and old[1] == payload:
                    continue
                revision = old[0] + 1 if old else 1
                self.db.execute(
                    """INSERT INTO questions VALUES (?,?,?,?,?,?) ON CONFLICT(project_id,id) DO UPDATE SET
                number=excluded.number,revision=excluded.revision,payload=excluded.payload,active=excluded.active""",
                    (
                        q["id"],
                        project_id,
                        str(q.get("number", q["id"])),
                        revision,
                        payload,
                        int(q.get("status", "active") == "active"),
                    ),
                )
                self.db.execute(
                    "INSERT INTO question_revisions VALUES (?,?,?,?)",
                    (project_id, q["id"], revision, payload),
                )
            report["hash"] = digest
            self.db.execute(
                "INSERT INTO imports VALUES (?,?,?,?)",
                (project_id, digest, dump(report), now()),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return report

    def topics(self, project_id):
        self.project(project_id)
        result = self.rows(
            "SELECT * FROM topics WHERE project_id=? ORDER BY position,id",
            (project_id,),
        )
        for t in result:
            t["objectives"] = json.loads(t["objectives"])
            t["source_refs"] = json.loads(t["source_refs"])
        return result

    def questions(self, project_id, topic=None, include_drafts=False):
        self.project(project_id)
        rows = self.rows(
            "SELECT * FROM questions WHERE project_id=? "
            + ("" if include_drafts else "AND active=1 ")
            + "ORDER BY rowid",
            (project_id,),
        )
        qs = [{**json.loads(r["payload"]), "revision": r["revision"]} for r in rows]
        return [q for q in qs if topic is None or topic in q.get("topics", [])]

    def add_source(self, project_id, source):
        import shutil
        import subprocess

        self.project(project_id)
        source = Path(source).expanduser().resolve()
        require(source.is_file(), "Source file not found", 404)
        require(source.stat().st_size <= 50 * 1024 * 1024, "Source exceeds 50 MB")
        ext = source.suffix.lower()
        require(
            ext in (".md", ".txt", ".pdf", ".json"),
            "Supported sources: md, txt, pdf, json",
        )
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        existing = self.db.execute(
            "SELECT * FROM sources WHERE project_id=? AND content_hash=?",
            (project_id, digest),
        ).fetchone()
        if existing:
            return dict(existing)
        if ext == ".pdf":
            require(
                shutil.which("pdftotext"), "Install Poppler (pdftotext) to extract PDFs"
            )
            try:
                content = subprocess.run(
                    ["pdftotext", "-layout", str(source), "-"],
                    check=True,
                    capture_output=True,
                    timeout=60,
                ).stdout.decode("utf-8")
            except (subprocess.SubprocessError, UnicodeError) as e:
                raise Error("PDF extraction failed; supply a text export") from e
            require(content.strip(), "No PDF text found; OCR is required")
        else:
            try:
                content = raw.decode("utf-8")
            except UnicodeError as e:
                raise Error("Source must be UTF-8") from e
        folder = self.home / "sources" / project_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (digest + ext)
        target.write_bytes(raw)
        (folder / (digest + ".extracted.txt")).write_text(content, encoding="utf-8")
        sid = uid()
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?,?,?)",
                (
                    sid,
                    project_id,
                    source.name,
                    digest,
                    str(target.relative_to(self.home)),
                    ext[1:],
                    now(),
                ),
            )
        return self.row(
            "SELECT * FROM sources WHERE project_id=? AND content_hash=?",
            (project_id, digest),
        )

    def sources(self, project_id):
        self.project(project_id)
        return self.rows(
            "SELECT * FROM sources WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        )

    def start_session(self, project_id, config):
        p = self.project(project_id)
        mode = config.get("mode", "practice")
        require(mode in ("practice", "exam", "review"), "Invalid session mode")
        count = config.get("count", 20)
        require(type(count) is int and 1 <= count <= 1000, "count must be 1–1000")
        policy = dict(p["policy"]) if mode == "exam" else {}
        if mode == "exam":
            require(policy, "This project has no exam preset; use practice")
            count = policy["count"]
        qs = self.questions(project_id, config.get("topic"))
        if mode == "review":
            marked = {
                m["question_id"] for m in self.marks(project_id) if not m["resolved"]
            }
            qs = [q for q in qs if q["id"] in marked]
        if config.get("questionIds") is not None:
            require(mode != "exam", "Exam presets cannot override question selection")
            ids = config["questionIds"]
            require(
                isinstance(ids, list) and ids and all(isinstance(x, str) for x in ids),
                "Invalid questionIds",
            )
            qs = [q for q in qs if q["id"] in ids]
            require(len(qs) == len(set(ids)), "Unknown question in selection")
            count = len(qs)
        key = text(config.get("requestKey", uid()), "requestKey", 200)
        # Repeated request keys return the original session even if content later changes.
        old = self.db.execute(
            "SELECT id FROM sessions WHERE project_id=? AND request_key=?",
            (project_id, key),
        ).fetchone()
        if old:
            return self.session(old[0])
        require(
            len(qs) >= count, f"Requested {count} questions, only {len(qs)} available"
        )
        selected = random.SystemRandom().sample(qs, count)
        unscored = set(
            random.SystemRandom().sample(
                range(count), count - policy.get("scored", count)
            )
        )
        sid, started = uid(), now()
        expires = (
            (
                datetime.fromisoformat(started) + timedelta(minutes=policy["minutes"])
            ).isoformat()
            if policy.get("minutes")
            else None
        )
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            # Another host may have started the same request while content was selected.
            existing = self.db.execute(
                "SELECT id FROM sessions WHERE project_id=? AND request_key=?",
                (project_id, key),
            ).fetchone()
            if existing:
                self.db.commit()
                return self.session(existing[0])
            self.db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    sid,
                    project_id,
                    mode,
                    dump(policy),
                    started,
                    expires,
                    None,
                    "in_progress",
                    None,
                    key,
                ),
            )
            for i, q in enumerate(selected):
                self.db.execute(
                    "INSERT INTO items (id,session_id,question_id,snapshot,position,scored) VALUES (?,?,?,?,?,?)",
                    (uid(), sid, q["id"], dump(q), i, int(i not in unscored)),
                )
        return self.session(sid)

    def session(self, session_id):
        s = self.row("SELECT * FROM sessions WHERE id=?", (session_id,))
        if (
            s["status"] == "in_progress"
            and s["expires_at"]
            and now() >= s["expires_at"]
        ):
            self.submit(session_id)
            s = self.row("SELECT * FROM sessions WHERE id=?", (session_id,))
        s["policy"] = json.loads(s["policy"])
        s["result"] = json.loads(s["result"]) if s["result"] else None
        s["items"] = self.rows(
            "SELECT * FROM items WHERE session_id=? ORDER BY position", (session_id,)
        )
        for item in s["items"]:
            q = json.loads(item.pop("snapshot"))
            item["answer"] = json.loads(item["answer"])
            if s["status"] == "in_progress":
                for name in ("answer", "explanation", "rubric"):
                    q.pop(name, None)
                item.pop("scored")
            item["question"] = q
        return s

    def answer(self, session_id, item_id, data):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            s = self.row("SELECT * FROM sessions WHERE id=?", (session_id,))
            require(s["status"] == "in_progress", "Session already submitted", 409)
            require(
                not s["expires_at"] or now() < s["expires_at"],
                "Time expired; submit session",
                409,
            )
            item = self.row(
                "SELECT * FROM items WHERE id=? AND session_id=?", (item_id, session_id)
            )
            require(
                type(data.get("version")) is int and item["version"] == data["version"],
                "Answer changed in another window; reload",
                409,
            )
            q = json.loads(item["snapshot"])
            answer = data.get("answer", json.loads(item["answer"]))
            if q["type"] in ("single", "multiple"):
                require(
                    isinstance(answer, list)
                    and all(isinstance(a, str) for a in answer),
                    "Expected answer labels",
                )
                require(
                    len(answer) == len(set(answer))
                    and set(answer) <= {o["label"] for o in q["options"]},
                    "Invalid option",
                )
                require(q["type"] != "single" or len(answer) <= 1, "Select one answer")
            else:
                require(
                    isinstance(answer, str) and len(answer) <= 100000,
                    "Expected text answer",
                )
            hints = data.get("hints", item["hints"])
            confidence = data.get("confidence", item["confidence"])
            require(type(hints) is int and 0 <= hints <= 100, "Invalid hint count")
            require(
                confidence is None or type(confidence) is int and 1 <= confidence <= 5,
                "Invalid confidence",
            )
            self.db.execute(
                "UPDATE items SET answer=?,flagged=?,hints=?,confidence=?,version=version+1 WHERE id=?",
                (
                    dump(answer),
                    int(bool(data.get("flagged", item["flagged"]))),
                    hints,
                    confidence,
                    item_id,
                ),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"version": item["version"] + 1}

    @staticmethod
    def grade(q, answer):
        points = q.get("points", 1)
        if answer is None or answer == [] or answer == "":
            return 0, "confirmed", "No answer"
        if q["type"] == "essay":
            return None, "pending", "Self-assessment required using the rubric"
        if q["type"] in ("single", "multiple"):
            correct = set(answer) == set(q["answer"])
        else:
            correct = normalize(answer) in {normalize(a) for a in q["answer"]}
        return (
            points if correct else 0,
            "confirmed",
            "Correct" if correct else "Review this concept",
        )

    def _result(self, session_id):
        s = self.row("SELECT * FROM sessions WHERE id=?", (session_id,))
        policy = json.loads(s["policy"])
        items = self.rows("SELECT * FROM items WHERE session_id=?", (session_id,))
        scored = [i for i in items if i["scored"]]
        pending = sum(i["score"] is None for i in scored)
        earned = sum(i["score"] or 0 for i in scored)
        maximum = sum(json.loads(i["snapshot"]).get("points", 1) for i in scored)
        percent = round(100 * earned / maximum, 2) if maximum else 0
        # The legacy AWS app uses Math.round: explicitly avoid Python's bankers' rounding.
        scaled = (
            int(
                (
                    policy["minScore"]
                    + (policy["maxScore"] - policy["minScore"]) * earned / maximum
                )
                + 0.5
            )
            if policy and maximum
            else None
        )
        result = {
            "earned": earned,
            "maximum": maximum,
            "percentage": percent,
            "pending": pending,
            "correct": sum(
                i["score"] == json.loads(i["snapshot"]).get("points", 1) for i in scored
            ),
            "scoredCount": len(scored),
            "totalCount": len(items),
            "scaledScore": None if pending else scaled,
            "passed": (
                None if pending or not policy else scaled >= policy["passingScore"]
            ),
        }
        self.db.execute(
            "UPDATE sessions SET result=? WHERE id=?", (dump(result), session_id)
        )
        return result

    def _review_after_grade(self, project_id, item, score):
        q = json.loads(item["snapshot"])
        if score is None:
            return
        wrong = score < q.get("points", 1)
        old = self.db.execute(
            "SELECT * FROM marks WHERE project_id=? AND question_id=?",
            (project_id, item["question_id"]),
        ).fetchone()
        if not wrong and not old and not item["hints"]:
            return
        tags = json.loads(old["tags"]) if old else []
        if wrong and "wrong" not in tags:
            tags.append("wrong")
        if item["hints"] and "assisted" not in tags:
            tags.append("assisted")
        streak = 0 if wrong or item["hints"] else (old["streak"] if old else 0) + 1
        days = [1, 3, 7, 14, 30][min(streak, 4)]
        due = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        self.db.execute(
            """INSERT INTO marks VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(project_id,question_id) DO UPDATE SET
          tags=excluded.tags,resolved=0,due_at=excluded.due_at,streak=excluded.streak,updated_at=excluded.updated_at""",
            (
                project_id,
                item["question_id"],
                dump(tags),
                old["memo"] if old else "",
                0,
                due,
                streak,
                now(),
            ),
        )

    def submit(self, session_id):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            s = self.row("SELECT * FROM sessions WHERE id=?", (session_id,))
            if s["status"] != "in_progress":
                self.db.rollback()
                return json.loads(s["result"])
            for item in self.rows(
                "SELECT * FROM items WHERE session_id=?", (session_id,)
            ):
                score, status, feedback = self.grade(
                    json.loads(item["snapshot"]), json.loads(item["answer"])
                )
                self.db.execute(
                    "UPDATE items SET score=?,grade_status=?,feedback=? WHERE id=?",
                    (score, status, feedback, item["id"]),
                )
                self._review_after_grade(s["project_id"], item, score)
            finished = now()
            self.db.execute(
                "UPDATE sessions SET status=?,finished_at=? WHERE id=?",
                (
                    (
                        "timed_out"
                        if s["expires_at"] and finished >= s["expires_at"]
                        else "completed"
                    ),
                    finished,
                    session_id,
                ),
            )
            result = self._result(session_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return result

    def assess(self, session_id, item_id, score, feedback=""):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            s = self.row("SELECT * FROM sessions WHERE id=?", (session_id,))
            require(s["status"] != "in_progress", "Submit first", 409)
            item = self.row(
                "SELECT * FROM items WHERE id=? AND session_id=?", (item_id, session_id)
            )
            q = json.loads(item["snapshot"])
            require(q["type"] == "essay", "Self-assessment is for essay questions")
            require(
                isinstance(score, (int, float)) and 0 <= score <= q.get("points", 1),
                "Invalid score",
            )
            require(item["grade_status"] == "pending", "Already assessed", 409)
            self.db.execute(
                "UPDATE items SET score=?,feedback=?,grade_status='self' WHERE id=?",
                (score, str(feedback)[:10000], item_id),
            )
            self._review_after_grade(s["project_id"], item, score)
            return self._result(session_id)

    def marks(self, project_id):
        self.project(project_id)
        result = self.rows(
            """SELECT m.*,q.payload FROM marks m JOIN questions q ON q.project_id=m.project_id AND q.id=m.question_id
            WHERE m.project_id=? ORDER BY resolved,due_at,updated_at DESC""",
            (project_id,),
        )
        for m in result:
            m["tags"] = json.loads(m["tags"])
            m["question"] = json.loads(m.pop("payload"))
        return result

    def mark(self, project_id, question_id, data):
        self.row(
            "SELECT id FROM questions WHERE project_id=? AND id=?",
            (project_id, question_id),
        )
        tags = data.get("tags", [])
        require(
            isinstance(tags, list)
            and all(isinstance(t, str) and len(t) <= 50 for t in tags),
            "Invalid tags",
        )
        memo = data.get("memo", "")
        require(isinstance(memo, str) and len(memo) <= 100000, "Invalid memo")
        with self.db:
            self.db.execute(
                """INSERT INTO marks VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(project_id,question_id) DO UPDATE SET
            tags=excluded.tags,memo=excluded.memo,resolved=excluded.resolved,updated_at=excluded.updated_at""",
                (
                    project_id,
                    question_id,
                    dump(tags),
                    memo,
                    int(bool(data.get("resolved", False))),
                    now(),
                    0,
                    now(),
                ),
            )
        return {"saved": True}

    def history(self, project_id):
        self.project(project_id)
        result = self.rows(
            "SELECT * FROM sessions WHERE project_id=? ORDER BY started_at DESC",
            (project_id,),
        )
        for s in result:
            s["result"] = json.loads(s["result"]) if s["result"] else None
            s["policy"] = json.loads(s["policy"])
        return result

    def progress(self, project_id):
        history = self.history(project_id)
        topics = self.topics(project_id)
        evidence = self.rows(
            """SELECT i.* FROM items i JOIN sessions s ON s.id=i.session_id
         WHERE s.project_id=? AND s.status!='in_progress'""",
            (project_id,),
        )
        summary = []
        for t in topics:
            items = [
                i
                for i in evidence
                if t["id"] in json.loads(i["snapshot"]).get("topics", [])
            ]
            confirmed = [i for i in items if i["score"] is not None]
            total = sum(json.loads(i["snapshot"]).get("points", 1) for i in confirmed)
            summary.append(
                {
                    "id": t["id"],
                    "title": t["title"],
                    "attempts": len(items),
                    "uniqueQuestions": len({i["question_id"] for i in items}),
                    "assisted": sum(i["hints"] > 0 for i in items),
                    "pending": len(items) - len(confirmed),
                    "percentage": (
                        round(100 * sum(i["score"] for i in confirmed) / total, 1)
                        if total
                        else None
                    ),
                }
            )
        marks = self.marks(project_id)
        return {
            "topics": summary,
            "sessions": len(history),
            "completed": sum(s["status"] != "in_progress" for s in history),
            "reviewCount": sum(not m["resolved"] for m in marks),
            "dueCount": sum(
                not m["resolved"] and (not m["due_at"] or m["due_at"] <= now())
                for m in marks
            ),
        }

    def export(self, project_id):
        return {
            "schemaVersion": 1,
            "project": self.project(project_id),
            "topics": self.topics(project_id),
            "questions": self.questions(project_id, include_drafts=True),
            "sources": self.sources(project_id),
            "history": [self.session(s["id"]) for s in self.history(project_id)],
            "marks": self.marks(project_id),
        }

    def backup(self, destination):
        target = Path(destination).expanduser().resolve()
        require(not target.exists(), "Backup destination already exists", 409)
        target.mkdir(parents=True, mode=0o700)
        import shutil

        db = sqlite3.connect(target / "study.db")
        try:
            self.db.backup(db)
        finally:
            db.close()
        if (self.home / "sources").exists():
            shutil.copytree(self.home / "sources", target / "sources")
        return {
            "backup": str(target),
            "restore": "Use --home with this directory, or copy it into a new data home while stopped.",
        }
