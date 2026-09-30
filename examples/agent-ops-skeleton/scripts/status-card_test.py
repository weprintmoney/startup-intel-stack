#!/usr/bin/env python3
"""Unit tests for scripts/status-card.py (run by schema-validate.yml)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sc", HERE / "status-card.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

ISSUE, IMPL, REPO = 1468, "example-org/example-app-sdk-py", "example-org/example-app-core"
RUN = "https://github.com/example-org/agent-ops/actions/runs/1"


def fresh(**sets):
    p = sc.new_payload(ISSUE, IMPL)
    return sc.apply(p, "claimed", "claimed", "next: spec draft", RUN,
                    {"branch": "agent/1468-async", **sets}, at="2026-09-21T16:56:23Z")


class Payload(unittest.TestCase):
    def test_empty_body_reads_defaults(self):
        p = sc.read_payload("", ISSUE, IMPL)
        self.assertEqual(p["status"], "claimed")
        self.assertEqual(p["history"], [])
        self.assertEqual(p["impl_repo"], IMPL)

    def test_roundtrip_through_render(self):
        p = fresh()
        p = sc.apply(p, "spec-pr-opened", "spec-pending", "PR open", RUN,
                     {"spec_pr": "https://github.com/example-org/internal-docs/pull/706",
                      "claim_verification": "verified"}, at="2026-09-21T17:06:58Z")
        body = sc.render(p)
        back = sc.read_payload(body, ISSUE, IMPL)
        self.assertEqual(back, p)
        self.assertEqual(body.count("agent-ops:status-card issue="), 1)
        self.assertEqual(body.count("agent-ops:status-card:data"), 1)

    def test_gt_escaped_in_data_comment(self):
        p = sc.apply(fresh(), "note", "-", "a -> b -->", RUN)
        data_line = [line for line in sc.render(p).splitlines() if "status-card:data" in line][0]
        self.assertNotIn("-->", data_line[len("<!-- agent-ops:status-card:data "):-len(" -->")])
        self.assertEqual(sc.read_payload(sc.render(p), ISSUE, IMPL)["history"][-1]["note"], "a -> b -->")

    def test_corrupt_data_block_starts_fresh_not_crash(self):
        body = "<!-- agent-ops:status-card issue=1468 impl_repo=x -->\n<!-- agent-ops:status-card:data {nope -->"
        self.assertEqual(sc.read_payload(body, ISSUE, IMPL)["status"], "claimed")


class Apply(unittest.TestCase):
    def test_history_appends_and_status_moves(self):
        p = fresh()
        p = sc.apply(p, "implementing", "implementing", "", RUN + "2")
        self.assertEqual(p["status"], "implementing")
        self.assertEqual([h["event"] for h in p["history"]], ["claimed", "implementing"])
        self.assertEqual(p["history"][-1]["run_url"], RUN + "2")

    def test_dash_keeps_status(self):
        p = sc.apply(fresh(), "retry", "-", "attempt 1 failed", RUN, {"retry_count": 1})
        self.assertEqual(p["status"], "claimed")
        self.assertEqual(p["retry_count"], 1)

    def test_abandoned_records_where_it_fell_from(self):
        p = sc.apply(fresh(), "spec-pr-opened", "spec-pending", "", RUN)
        p = sc.apply(p, "abandoned", "abandoned", "", RUN, {"abandoned_reason": "spec rejected"})
        self.assertEqual(p["abandoned_from"], "spec-pending")
        # a second abandon event does not overwrite the origin
        p = sc.apply(p, "abandoned", "abandoned", "", RUN)
        self.assertEqual(p["abandoned_from"], "spec-pending")

    def test_reclaim_after_abandon_resets_live_fields_keeps_history(self):
        p = sc.apply(fresh(), "spec-pr-opened", "spec-pending", "", RUN, {"spec_pr": "https://x/pull/1"})
        p = sc.apply(p, "abandoned", "abandoned", "", RUN, {"abandoned_reason": "gave up", "retry_count": 3})
        p = sc.apply(p, "claimed", "claimed", "re-queued", RUN, {"branch": "agent/1468-async"})
        self.assertEqual(p["status"], "claimed")
        self.assertEqual(p["abandoned_from"], "")
        self.assertEqual(p["spec_pr"], "")
        self.assertEqual(p["abandoned_reason"], "")
        self.assertEqual(p["retry_count"], 0)
        self.assertEqual(len(p["history"]), 4)

    def test_unknown_status_rejected(self):
        with self.assertRaises(SystemExit):
            sc.apply(fresh(), "x", "done", "", RUN)

    def test_history_capped(self):
        p = fresh()
        for i in range(sc.HISTORY_KEEP + 10):
            p = sc.apply(p, f"e{i}", "-", "", "")
        self.assertEqual(len(p["history"]), sc.HISTORY_KEEP)
        self.assertEqual(p["history"][-1]["event"], f"e{sc.HISTORY_KEEP + 9}")

    def test_set_coercion(self):
        self.assertEqual(sc.parse_sets(["retry_count=2", "spec_fast_path=true", "pr_url=u"]),
                         {"retry_count": 2, "spec_fast_path": True, "pr_url": "u"})
        with self.assertRaises(SystemExit):
            sc.parse_sets(["colour=red"])
        with self.assertRaises(SystemExit):
            sc.parse_sets(["retry_count=two"])


class Render(unittest.TestCase):
    def marks(self, p):
        return {stage: mark for stage, mark, _s, _l in sc.stage_rows(p)}

    def test_claimed_card(self):
        body = sc.render(fresh())
        self.assertIn("<!-- agent-ops:status-card issue=1468 impl_repo=example-org/example-app-sdk-py -->", body)
        self.assertIn("`claimed`", body)
        self.assertIn("branch `agent/1468-async`", body)
        m = self.marks(fresh())
        self.assertEqual(m["Claim"], sc.DONE)
        self.assertEqual(m["Spec"], sc.ACTIVE)
        self.assertEqual(m["Implement"], sc.TODO)

    def test_retry_count_shown(self):
        p = sc.apply(fresh(), "retry", "-", "", RUN, {"retry_count": 2})
        self.assertIn("2/3 retries used", sc.render(p))

    def test_spec_pending_links_pr_and_verdict(self):
        p = sc.apply(fresh(), "spec-pr-opened", "spec-pending", "", RUN,
                     {"spec_pr": "https://github.com/example-org/internal-docs/pull/706",
                      "claim_verification": "contradicted"})
        body = sc.render(p)
        self.assertIn("[internal-docs#706](https://github.com/example-org/internal-docs/pull/706)",
                      body)
        self.assertIn("claims `contradicted`", body)
        self.assertIn("merging it is the approval", body)

    def test_parked_row(self):
        p = sc.apply(fresh(), "clarify", "spec-clarify-pending", "", RUN, {"clarify_reason": "which repos?"})
        self.assertEqual(self.marks(p)["Spec"], sc.PARKED)
        self.assertIn("which repos?", sc.render(p))

    def test_full_happy_path_marks(self):
        p = sc.apply(fresh(), "spec-pr-opened", "spec-pending", "", RUN, {"spec_pr": "https://g/o/r/pull/1"})
        p = sc.apply(p, "spec-approved", "spec-approved", "", RUN)
        self.assertEqual(self.marks(p)["Spec"], sc.DONE)
        self.assertEqual(self.marks(p)["Implement"], sc.ACTIVE)
        p = sc.apply(p, "implementing", "implementing", "", RUN + "9")
        self.assertIn("[run](" + RUN + "9)", sc.render(p))
        p = sc.apply(p, "pr-open", "pr-open", "", RUN, {"pr_url": "https://github.com/example-org/example-app-sdk-py/pull/130"})
        m = self.marks(p)
        self.assertEqual((m["Implement"], m["PR"], m["Merged"]), (sc.DONE, sc.ACTIVE, sc.TODO))
        self.assertIn("[example-app-sdk-py#130]", sc.render(p))
        p = sc.apply(p, "merged", "merged", "", RUN, {"merge_sha": "63d3e63abcdef"})
        m = self.marks(p)
        self.assertEqual(set(m.values()), {sc.DONE})
        self.assertIn("`63d3e63`", sc.render(p))

    def test_fast_path_wording(self):
        p = sc.apply(fresh(), "fast-path", "spec-approved", "", RUN, {"spec_fast_path": True})
        self.assertIn("fast path — no spec needed", sc.render(p))

    def test_abandoned_marks_origin_stage(self):
        p = sc.apply(fresh(), "implementing", "spec-approved", "", RUN)
        p = sc.apply(p, "implementing", "implementing", "", RUN)
        p = sc.apply(p, "abandoned", "abandoned", "", RUN, {"abandoned_reason": "implement pipeline failed"})
        m = self.marks(p)
        self.assertEqual(m["Spec"], sc.DONE)
        self.assertEqual(m["Implement"], sc.FAILED)
        self.assertEqual(m["PR"], sc.TODO)
        self.assertIn("abandoned — implement pipeline failed", sc.render(p))
        self.assertIn("`abandoned` (from `implementing`)", sc.render(p))

    def test_history_table_escapes_pipes(self):
        p = sc.apply(fresh(), "note", "-", "a | b", RUN)
        self.assertIn("a \\| b", sc.render(p))
        self.assertIn("History · 2 events", sc.render(p))


class FakeGh:
    """Records calls; serves a comment list; returns '' for writes."""

    def __init__(self, comments=None, fail=None):
        self.comments = comments or []
        self.calls = []
        self.fail = fail or set()

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == "api" and args[1] == "--paginate":
            if "list" in self.fail:
                raise sc.GhError("boom")
            return "\n".join(json.dumps({"id": c["id"], "body": c["body"]}) for c in self.comments)
        if args[:2] == ("api", "-X"):
            if args[2] in self.fail:
                raise sc.GhError(f"{args[2]} failed")
            body = Path(args[-1][len("body=@"):]).read_text(encoding="utf-8")
            if args[2] == "POST":
                self.comments.append({"id": 100 + len(self.comments), "body": body})
            else:
                cid = int(args[3].rsplit("/", 1)[1])
                for c in self.comments:
                    if c["id"] == cid:
                        c["body"] = body
            return ""
        raise AssertionError(f"unexpected gh call {args}")


class Upsert(unittest.TestCase):
    def setUp(self):
        self.orig = sc.gh

    def tearDown(self):
        sc.gh = self.orig

    def test_creates_then_patches_same_comment(self):
        fake = FakeGh([{"id": 1, "body": "human chatter"}])
        sc.gh = fake
        sc.upsert(REPO, ISSUE, IMPL, [{"event": "claimed", "status": "claimed", "run_url": RUN,
                                        "sets": {"branch": "agent/1468-a"}}])
        self.assertEqual(len(fake.comments), 2)
        card_id = fake.comments[1]["id"]
        sc.upsert(REPO, ISSUE, IMPL, [{"event": "spec-pr-opened", "status": "spec-pending",
                                        "sets": {"spec_pr": "https://g/o/r/pull/7"}}])
        self.assertEqual(len(fake.comments), 2, "second upsert must edit, not add")
        p = sc.read_payload(fake.comments[1]["body"], ISSUE, IMPL)
        self.assertEqual(p["status"], "spec-pending")
        self.assertEqual([h["event"] for h in p["history"]], ["claimed", "spec-pr-opened"])
        self.assertEqual(fake.comments[1]["id"], card_id)
        methods = [c[2] for c in fake.calls if c[:2] == ("api", "-X")]
        self.assertEqual(methods, ["POST", "PATCH"])

    def test_one_card_per_impl_repo(self):
        fake = FakeGh()
        sc.gh = fake
        sc.upsert(REPO, ISSUE, "example-org/example-app-sdk-go", [{"event": "claimed", "status": "claimed"}])
        sc.upsert(REPO, ISSUE, "example-org/example-app-sdk-js", [{"event": "claimed", "status": "claimed"}])
        sc.upsert(REPO, ISSUE, "example-org/example-app-sdk-go", [{"event": "implementing", "status": "implementing"}])
        self.assertEqual(len(fake.comments), 2)
        go = sc.find_card(fake.comments, ISSUE, "example-org/example-app-sdk-go")
        js = sc.find_card(fake.comments, ISSUE, "example-org/example-app-sdk-js")
        self.assertEqual(sc.read_payload(go["body"], ISSUE, "example-org/example-app-sdk-go")["status"], "implementing")
        self.assertEqual(sc.read_payload(js["body"], ISSUE, "example-org/example-app-sdk-js")["status"], "claimed")

    def test_gh_failures_never_raise(self):
        sc.gh = FakeGh(fail={"list"})
        self.assertEqual(sc.upsert(REPO, ISSUE, IMPL, [{"event": "claimed", "status": "claimed"}]), {})
        sc.gh = FakeGh(fail={"POST"})
        p = sc.upsert(REPO, ISSUE, IMPL, [{"event": "claimed", "status": "claimed"}])
        self.assertEqual(p["status"], "claimed")


PEOPLE_YAML = """people:
  - handle: founder-handle
    name: Founder Name
  - handle: eng-lead-handle
    name: Eng Lead
"""


class Outbox(unittest.TestCase):
    def setUp(self):
        self.orig = sc.gh
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "outbox"
        self.dir.mkdir()
        self.people_file = Path(self.tmp.name) / "people.yaml"
        self.people_file.write_text(PEOPLE_YAML)
        self.people = sc.load_people(str(self.people_file))

    def tearDown(self):
        sc.gh = self.orig
        self.tmp.cleanup()

    def put(self, name, body):
        (self.dir / name).write_text(body, encoding="utf-8")

    def test_people_loaded_case_insensitive(self):
        self.assertEqual(self.people, {"founder-handle", "eng-lead-handle"})
        self.assertIsNotNone(sc.classify("question-Founder-Handle.md", "SPEC_PR", self.people))

    def test_classify_rules(self):
        c = sc.classify
        self.assertEqual(c("question-founder-handle.md", "SPEC_PR", self.people), ("question", "founder-handle"))
        self.assertIsNone(c("question-stranger.md", "SPEC_PR", self.people))
        self.assertEqual(c("intent-note.md", "FAST_PATH", self.people), ("intent-note", ""))
        self.assertIsNone(c("intent-note.md", "SPEC_PR", self.people))
        self.assertEqual(c("clarify.md", "CLARIFY_NEEDED", self.people), ("clarify", ""))
        self.assertIsNone(c("clarify.md", "SPEC_PR", self.people))
        for r in ("GROOMING_BLOCKER", "DEPENDENCY_BLOCKED", "UNFIT"):
            self.assertEqual(c("blocker.md", r, self.people), ("blocker", ""))
        self.assertIsNone(c("blocker.md", "SPEC_PR", self.people))
        self.assertIsNone(c("spec-pr-opened.md", "SPEC_PR", self.people))
        self.assertIsNone(c("progress.md", "SPEC_PR", self.people))

    def test_defang_unknown_handles_keeps_known_and_code_refs(self):
        body, dropped = sc.defang_handles("@founder-handle see @stranger; uses actions/checkout@v4 and a@b.c",
                                          self.people)
        self.assertEqual(body, "@founder-handle see stranger; uses actions/checkout@v4 and a@b.c")
        self.assertEqual(dropped, ["stranger"])

    def test_question_without_mention_dropped(self):
        self.put("question-founder-handle.md", "Which SOC 2 format do we ship?")
        self.assertEqual(sc.select_outbox(self.dir, "SPEC_PR", self.people, []), [])

    def test_selection_gates_and_dedups(self):
        self.put("question-founder-handle.md", "@founder-handle — SOC 2 report format?")
        self.put("question-eng-lead-handle.md", "@eng-lead-handle — keep the sync client?")
        self.put("intent-note.md", "not a fast path run")
        self.put("spec-pr-opened.md", "Spec PR opened: https://x")
        self.put("empty.md", "")
        chosen = sc.select_outbox(self.dir, "SPEC_PR", self.people, ["@eng-lead-handle — keep the sync client?"])
        self.assertEqual([c["name"] for c in chosen], ["question-founder-handle.md"])
        self.assertEqual(chosen[0]["handle"], "founder-handle")

    def test_cap(self):
        people = {f"p{i}" for i in range(20)}
        for i in range(20):
            self.put(f"question-p{i}.md", f"@p{i} question {i}")
        self.assertEqual(len(sc.select_outbox(self.dir, "SPEC_PR", people, [])), sc.MAX_OUTBOX)

    def test_post_outbox_posts_and_records_on_card(self):
        fake = FakeGh()
        sc.gh = fake
        sc.upsert(REPO, ISSUE, IMPL, [{"event": "claimed", "status": "claimed", "run_url": RUN}])
        self.put("question-founder-handle.md", "@founder-handle — one open question.")
        self.put("blocker.md", "should not post on SPEC_PR")
        n = sc.post_outbox(REPO, ISSUE, IMPL, self.dir, "SPEC_PR", str(self.people_file), RUN + "3")
        self.assertEqual(n, 1)
        bodies = [c["body"] for c in fake.comments]
        self.assertIn("@founder-handle — one open question.", bodies)
        self.assertEqual(len(fake.comments), 2, "card + one question, nothing else")
        card = sc.find_card(fake.comments, ISSUE, IMPL)
        p = sc.read_payload(card["body"], ISSUE, IMPL)
        self.assertEqual(p["status"], "claimed")
        self.assertEqual(p["history"][-1]["event"], "comment")
        self.assertIn("@founder-handle", p["history"][-1]["note"])
        # a retry run with the same outbox posts nothing new
        n2 = sc.post_outbox(REPO, ISSUE, IMPL, self.dir, "SPEC_PR", str(self.people_file), RUN + "4")
        self.assertEqual(n2, 0)
        self.assertEqual(len(fake.comments), 2)

    def test_missing_dir_is_a_noop(self):
        sc.gh = FakeGh()
        self.assertEqual(sc.post_outbox(REPO, ISSUE, IMPL, self.dir / "nope", "SPEC_PR", str(self.people_file), ""), 0)


if __name__ == "__main__":
    unittest.main()
