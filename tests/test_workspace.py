import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from study_workspace.store import Store, Error, AWS_POLICY
from study_workspace.server import Server
from study_workspace.migration import migrate

ROOT = Path(__file__).resolve().parent.parent


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.project = self.store.create_project("Biology", profile="school")["id"]
        self.pack = json.loads((ROOT / "examples/biology.json").read_text())
        self.store.import_pack(self.project, self.pack)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def session(self, ids=None, **config):
        return self.store.start_session(
            self.project,
            {"count": 1, **({"questionIds": ids} if ids else {}), **config},
        )

    def test_all_examples_validate(self):
        for path in (ROOT / "examples").glob("*.json"):
            self.store.validate_pack(json.loads(path.read_text()))

    def test_import_is_idempotent_and_invalid_pack_is_atomic(self):
        self.assertTrue(self.store.import_pack(self.project, self.pack)["unchanged"])
        bad = copy.deepcopy(self.pack)
        bad["topics"][0]["title"] = "Should not persist"
        bad["questions"][-1]["topics"] = ["missing"]
        with self.assertRaises(Error):
            self.store.import_pack(self.project, bad)
        self.assertEqual(
            self.store.topics(self.project)[0]["title"], self.pack["topics"][0]["title"]
        )

    def test_project_isolation(self):
        other = self.store.create_project("Math")["id"]
        self.assertEqual(self.store.questions(other), [])
        with self.assertRaises(Error):
            self.store.mark(other, "bio-1", {})
        self.store.import_pack(other, self.pack)
        self.store.mark(self.project, "bio-1", {"tags": ["wrong"]})
        self.assertEqual(self.store.marks(other), [])

    def test_content_revision_does_not_change_started_session(self):
        s = self.session(["bio-1"])
        self.assertNotIn("answer", s["items"][0]["question"])
        self.assertNotIn("scored", s["items"][0])
        changed = copy.deepcopy(self.pack)
        changed["questions"][0]["answer"] = ["B"]
        self.store.import_pack(self.project, changed)
        item = s["items"][0]
        self.store.answer(s["id"], item["id"], {"version": 0, "answer": ["A"]})
        self.assertEqual(self.store.submit(s["id"])["percentage"], 100)
        self.assertEqual(self.store.questions(self.project)[0]["revision"], 2)

    def test_submission_is_idempotent_and_answers_close(self):
        s = self.session(["bio-1"])
        first = self.store.submit(s["id"])
        self.assertEqual(first, self.store.submit(s["id"]))
        self.assertEqual(len(self.store.marks(self.project)), 1)
        with self.assertRaises(Error) as err:
            self.store.answer(
                s["id"], s["items"][0]["id"], {"version": 0, "answer": ["A"]}
            )
        self.assertEqual(err.exception.status, 409)

    def test_answer_version_prevents_lost_update(self):
        s = self.session(["bio-1"])
        item = s["items"][0]
        self.store.answer(s["id"], item["id"], {"version": 0, "answer": ["A"]})
        with self.assertRaises(Error) as err:
            self.store.answer(s["id"], item["id"], {"version": 0, "answer": ["B"]})
        self.assertEqual(err.exception.status, 409)
        self.assertEqual(self.store.session(s["id"])["items"][0]["answer"], ["A"])

    def test_multiple_choices_and_normalization(self):
        q = self.pack["questions"][1]
        self.assertEqual(self.store.grade(q, ["B", "A"])[0], 1)
        self.assertEqual(self.store.grade(q, ["A"])[0], 0)
        self.assertEqual(
            self.store.grade(self.pack["questions"][2], "  ａｔｐ  ")[0], 1
        )

    def test_manual_rubric_is_pending_until_self_assessment(self):
        s = self.session(["bio-4"])
        item = s["items"][0]
        self.store.answer(
            s["id"], item["id"], {"version": 0, "answer": "My explanation"}
        )
        result = self.store.submit(s["id"])
        self.assertEqual(result["pending"], 1)
        self.assertIsNone(result["passed"])
        result = self.store.assess(s["id"], item["id"], 1, "I met one criterion")
        self.assertEqual((result["pending"], result["percentage"]), (0, 50))
        with self.assertRaises(Error):
            self.store.assess(s["id"], item["id"], 2)

    def test_drafts_and_insufficient_question_count(self):
        pack = copy.deepcopy(self.pack)
        for q in pack["questions"]:
            q["status"] = "draft"
        self.store.import_pack(self.project, pack)
        self.assertEqual(self.store.questions(self.project), [])
        with self.assertRaises(Error):
            self.session()

    def test_exam_preset_65_50_90_and_score(self):
        pid = self.store.create_project("AWS", profile="aws-aif")["id"]
        qs = []
        for i in range(65):
            q = copy.deepcopy(self.pack["questions"][0])
            q["id"] = str(i)
            q["topics"] = []
            qs.append(q)
        self.store.import_pack(pid, {"schemaVersion": 1, "questions": qs})
        s = self.store.start_session(pid, {"mode": "exam"})
        self.assertEqual(len(s["items"]), 65)
        self.assertEqual(s["policy"]["minutes"], 90)
        for item in s["items"]:
            self.store.answer(s["id"], item["id"], {"version": 0, "answer": ["A"]})
        r = self.store.submit(s["id"])
        self.assertEqual(
            (r["scoredCount"], r["scaledScore"], r["passed"]), (50, 1000, True)
        )
        self.assertEqual(
            sum(not i["scored"] for i in self.store.session(s["id"])["items"]), 15
        )

    def test_expiration_uses_persisted_deadline(self):
        s = self.session(["bio-1"])
        with self.store.db:
            self.store.db.execute(
                "UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?",
                (s["id"],),
            )
        expired = self.store.session(s["id"])
        self.assertEqual(expired["status"], "timed_out")
        self.assertEqual(expired["result"]["percentage"], 0)

    def test_review_records_assistance_and_spaced_retry(self):
        s = self.session(["bio-1"])
        self.store.answer(
            s["id"], s["items"][0]["id"], {"version": 0, "answer": ["A"], "hints": 1}
        )
        self.store.submit(s["id"])
        m = self.store.marks(self.project)[0]
        self.assertEqual(m["streak"], 0)
        self.assertIn("assisted", m["tags"])
        retry = self.session(["bio-1"])
        self.store.answer(
            retry["id"], retry["items"][0]["id"], {"version": 0, "answer": ["A"]}
        )
        self.store.submit(retry["id"])
        self.assertEqual(self.store.marks(self.project)[0]["streak"], 1)
        self.assertEqual(self.store.progress(self.project)["topics"][0]["assisted"], 1)

    def test_start_idempotency(self):
        a = self.session(requestKey="same")
        b = self.session(requestKey="same")
        self.assertEqual(a["id"], b["id"])

    def test_concurrent_agent_answer_conflict(self):
        s = self.session(["bio-1"])

        def save(answer):
            store = Store(self.temp.name)
            try:
                store.answer(
                    s["id"], s["items"][0]["id"], {"version": 0, "answer": [answer]}
                )
                return 200
            except Error as e:
                return e.status
            finally:
                store.close()

        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(save, ["A", "B"])), [200, 409])

    def test_source_and_backup_restore(self):
        source = Path(self.temp.name) / "lecture; $(test).md"
        source.write_text("A learner's private note.")
        first = self.store.add_source(self.project, source)
        second = self.store.add_source(self.project, source)
        self.assertEqual(first["id"], second["id"])
        with tempfile.TemporaryDirectory() as parent:
            path = Path(parent) / "restored"
            self.store.backup(path)
            restored = Store(path)
            try:
                self.assertEqual(len(restored.questions(self.project)), 4)
                self.assertTrue((path / first["relative_path"]).exists())
            finally:
                restored.close()

    def test_legacy_migration_preserves_questions_marks_and_results(self):
        with tempfile.TemporaryDirectory() as directory:
            db = sqlite3.connect(Path(directory) / "data.db")
            db.executescript(
                """
            CREATE TABLE questions(id,number,text,type,required_answers,explanation);
            CREATE TABLE options(id,question_id,label,text,is_correct);
            CREATE TABLE exam_sessions(id,mode,question_count,time_limit_minutes,started_at,finished_at,status);
            CREATE TABLE exam_questions(id,exam_session_id,question_id,order_index,is_scored,selected_options,is_flagged);
            CREATE TABLE exam_results(id,exam_session_id,mode,total_questions,scored_questions,correct_count,scaled_score,passed,time_taken_seconds,completed_at);
            CREATE TABLE study_marks(question_number,tags,memo,resolved,resolved_at,created_at,updated_at);
            INSERT INTO questions VALUES(1,7,'Sample?','single',1,'Explanation');
            INSERT INTO options VALUES(1,1,'A','Yes',1),(2,1,'B','No',0);
            INSERT INTO exam_sessions VALUES('old','practice',1,NULL,'2026-01-01T00:00:00Z','2026-01-01T00:01:00Z','completed');
            INSERT INTO exam_questions VALUES(1,'old',1,0,1,'["A"]',1);
            INSERT INTO exam_results VALUES('result','old','practice',1,1,1,100,NULL,60,'2026-01-01T00:01:00Z');
            INSERT INTO study_marks VALUES(7,'["confused"]','Original memo',0,NULL,'2026-01-01','2026-01-01');
            """
            )
            db.commit()
            db.close()
            report = migrate(self.store, directory, "Migrated", True)
            self.assertEqual(report["sessions"], 1)
            migrated = migrate(self.store, directory, "Migrated")
            pid = migrated["projectId"]
            self.assertEqual(self.store.marks(pid)[0]["memo"], "Original memo")
            self.assertEqual(self.store.history(pid)[0]["result"]["percentage"], 100)
            self.assertTrue(migrate(self.store, directory, "Again")["alreadyMigrated"])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        store = Store(self.temp.name)
        store.close()
        self.server = Server(self.temp.name, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, headers=None, data=None):
        req = urllib.request.Request(
            self.server.origin + path,
            headers=headers or {},
            data=json.dumps(data).encode() if data is not None else None,
        )
        return urllib.request.urlopen(req)

    def test_session_authentication_and_origin_guard(self):
        with self.request("/") as response:
            self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.request("/api/projects")
        self.assertEqual(err.exception.code, 401)
        err.exception.close()
        headers = {"Authorization": "Bearer " + self.server.token}
        with self.request("/api/projects", headers) as response:
            self.assertEqual(json.load(response), [])
        for hostile in [
            {"Origin": "https://example.com"},
            {"Host": "evil.example"},
            {"Sec-Fetch-Site": "cross-site"},
        ]:
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.request("/api/projects", {**headers, **hostile})
            self.assertEqual(err.exception.code, 403)
            err.exception.close()

    def test_create_and_import_through_http(self):
        headers = {
            "Authorization": "Bearer " + self.server.token,
            "Content-Type": "application/json",
        }
        with self.request(
            "/api/projects", headers, {"title": "Browser project"}
        ) as response:
            p = json.load(response)
        pack = json.loads((ROOT / "examples/linear-algebra.json").read_text())
        with self.request(
            f'/api/projects/{p["id"]}/imports', headers, {"pack": pack}
        ) as response:
            self.assertEqual(json.load(response)["questions"], 3)

    def test_two_local_runtimes_keep_independent_browser_sessions(self):
        from http.cookiejar import CookieJar

        other = Server(self.temp.name, 0)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        browser = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )
        try:
            for server in (self.server, other):
                with browser.open(server.origin + "/") as response:
                    self.assertEqual(response.status, 200)
            for server in (self.server, other):
                with browser.open(server.origin + "/api/projects") as response:
                    self.assertEqual(json.load(response), [])
        finally:
            other.shutdown()
            other.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
