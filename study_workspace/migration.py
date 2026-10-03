"""Read-only import of a private alf-c01-practice database. Never bundles its content."""

import ast
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from datetime import datetime, timedelta

from .store import Store, AWS_POLICY, dump, uid, now, require


def migrate(destination, directory, title, dry_run=False):
    directory = Path(directory).expanduser().resolve()
    path = directory / "data.db"
    require(path.is_file(), "Expected data.db in the legacy application folder", 404)
    key = "legacy:" + hashlib.sha256(str(path).encode()).hexdigest()
    existing = destination.db.execute(
        "SELECT value FROM metadata WHERE key=?", (key,)
    ).fetchone()
    if existing:
        return {"projectId": existing[0], "alreadyMigrated": True}
    source = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    snapshot = sqlite3.connect(":memory:")
    snapshot.row_factory = sqlite3.Row
    try:
        source.backup(snapshot)
    finally:
        source.close()
    try:
        questions = [
            dict(r) for r in snapshot.execute("SELECT * FROM questions ORDER BY number")
        ]
        sessions = [dict(r) for r in snapshot.execute("SELECT * FROM exam_sessions")]
        marks = [dict(r) for r in snapshot.execute("SELECT * FROM study_marks")]
        results = {
            r["exam_session_id"]: dict(r)
            for r in snapshot.execute("SELECT * FROM exam_results")
        }
        md_path = directory / "AIF-C01-핵심정리.md"
        md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        topics = []
        for match in re.finditer(
            r"^### (\d+-\d+)\. ([^\n]+)\n(.*?)(?=^### |^## |\Z)", md, re.M | re.S
        ):
            topics.append(
                {
                    "id": match[1],
                    "title": match[2],
                    "body": match[3].strip(),
                    "sourceRefs": [md_path.name + "#" + match[1]],
                }
            )
        keyword_path = directory / "packages/server/src/data/concept-sections.ts"
        keyword_source = (
            keyword_path.read_text(encoding="utf-8") if keyword_path.exists() else ""
        )
        keywords = {}
        for block in re.finditer(
            r"id:\s*'([^']+)'[\s\S]*?keywords:\s*\[([\s\S]*?)\]", keyword_source
        ):
            keywords[block[1]] = [
                ast.literal_eval(s) for s in re.findall(r"'(?:\\.|[^'\\])*'", block[2])
            ]
        topic_ids = {t["id"] for t in topics}
        pack = {"schemaVersion": 1, "topics": topics, "questions": []}
        qmap = {}
        for q in questions:
            options = [
                dict(r)
                for r in snapshot.execute(
                    "SELECT * FROM options WHERE question_id=? ORDER BY id", (q["id"],)
                )
            ]
            search = (q["text"] + " " + q["explanation"]).lower()
            scores = []
            for tid, words in keywords.items():
                score = sum(
                    (
                        5
                        if w[0].upper() == w[0] and w[0].lower() != w[0]
                        else 3 if len(w) >= 10 else 1
                    )
                    for w in words
                    if w.lower() in search
                )
                if score and tid in topic_ids:
                    scores.append((tid, score))
            scores.sort(key=lambda x: -x[1])
            item = {
                "id": "aws-" + str(q["number"]),
                "number": str(q["number"]),
                "type": q["type"],
                "prompt": q["text"],
                "options": [{"label": o["label"], "text": o["text"]} for o in options],
                "answer": [o["label"] for o in options if o["is_correct"]],
                "explanation": q["explanation"],
                "origin": "original",
                "topics": [t for t, _ in scores[:3]],
                "sourceRefs": ["legacy database: question " + str(q["number"])],
            }
            pack["questions"].append(item)
            qmap[q["id"]] = item
        report = {
            "questions": len(questions),
            "topics": len(topics),
            "sessions": len(sessions),
            "results": len(results),
            "marks": len(marks),
            "mappedQuestions": sum(bool(q["topics"]) for q in pack["questions"]),
        }
        destination.validate_pack(pack)
        if dry_run:
            return {**report, "dryRun": True}
        with tempfile.TemporaryDirectory(prefix="study-migration-") as temp:
            stage = Store(temp)
            try:
                project = stage.create_project(
                    title, "Imported personal AWS study project", "aws-aif"
                )
                pid = project["id"]
                stage.import_pack(pid, pack)
                with stage.db:
                    for s in sessions:
                        sid = uid()
                        policy = AWS_POLICY if s["mode"] == "real" else {}
                        expires = (
                            (
                                datetime.fromisoformat(
                                    s["started_at"].replace("Z", "+00:00")
                                )
                                + timedelta(minutes=s["time_limit_minutes"])
                            ).isoformat()
                            if s["time_limit_minutes"]
                            else None
                        )
                        stage.db.execute(
                            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (
                                sid,
                                pid,
                                "exam" if policy else "practice",
                                dump(policy),
                                s["started_at"],
                                expires,
                                s["finished_at"],
                                s["status"],
                                None,
                                "legacy:" + s["id"],
                            ),
                        )
                        for item in snapshot.execute(
                            "SELECT * FROM exam_questions WHERE exam_session_id=? ORDER BY order_index",
                            (s["id"],),
                        ):
                            require(
                                item["question_id"] in qmap,
                                "Legacy session references a missing question",
                            )
                            q = qmap[item["question_id"]]
                            score, status, feedback = (
                                stage.grade(q, json.loads(item["selected_options"]))
                                if s["status"] != "in_progress"
                                else (None, "ungraded", "")
                            )
                            stage.db.execute(
                                """INSERT INTO items (id,session_id,question_id,snapshot,position,scored,answer,flagged,score,grade_status,feedback)
                              VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                                (
                                    uid(),
                                    sid,
                                    q["id"],
                                    dump(q),
                                    item["order_index"],
                                    item["is_scored"],
                                    item["selected_options"],
                                    item["is_flagged"],
                                    score,
                                    status,
                                    feedback,
                                ),
                            )
                        if s["status"] != "in_progress":
                            calculated = stage._result(sid)
                            if s["id"] in results:
                                old = results[s["id"]]
                                require(
                                    calculated["correct"] == old["correct_count"]
                                    and calculated["scoredCount"]
                                    == old["scored_questions"],
                                    "Legacy score mismatch; migration aborted",
                                )
                                if policy:
                                    require(
                                        calculated["scaledScore"]
                                        == old["scaled_score"],
                                        "AWS scaled score mismatch; migration aborted",
                                    )
                                calculated["legacyResult"] = old
                                stage.db.execute(
                                    "UPDATE sessions SET result=? WHERE id=?",
                                    (dump(calculated), sid),
                                )
                    by_number = {q["number"]: q["id"] for q in pack["questions"]}
                    for m in marks:
                        require(
                            str(m["question_number"]) in by_number,
                            "Legacy mark references a missing question",
                        )
                        stage.db.execute(
                            "INSERT INTO marks VALUES (?,?,?,?,?,?,?,?)",
                            (
                                pid,
                                by_number[str(m["question_number"])],
                                m["tags"],
                                m["memo"],
                                m["resolved"],
                                m.get("resolved_at") or m["updated_at"],
                                0,
                                m["updated_at"],
                            ),
                        )
                # Copy the fully validated staging database in one destination transaction.
                destination.db.execute(
                    "ATTACH DATABASE ? AS migration", (str(stage.home / "study.db"),)
                )
                try:
                    with destination.db:
                        for table in [
                            "projects",
                            "topics",
                            "questions",
                            "question_revisions",
                            "imports",
                            "sessions",
                            "items",
                            "marks",
                        ]:
                            destination.db.execute(
                                f"INSERT INTO main.{table} SELECT * FROM migration.{table}"
                            )
                        destination.db.execute(
                            "INSERT INTO metadata VALUES (?,?)", (key, pid)
                        )
                finally:
                    destination.db.execute("DETACH DATABASE migration")
                return {**report, "projectId": pid, "sourceUnchanged": True}
            finally:
                stage.close()
    finally:
        snapshot.close()
