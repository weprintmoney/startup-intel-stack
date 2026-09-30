#!/usr/bin/env python3
"""Unit tests for scripts/dependabot-triage.py.

Stdlib-only (unittest). Run: `python3 scripts/dependabot-triage_test.py`.
Real Dependabot PRs captured 2026-09-12 live in evals/dependabot-cases/<case>/
(pr.json = `gh pr view --json …` with release notes stripped; expected.json =
the outcome a human confirmed). Synthetic cases cover the branches the live
set does not reach.
"""

from __future__ import annotations

import importlib.util as _iu
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_SPEC = _iu.spec_from_file_location("dependabot_triage", HERE / "dependabot-triage.py")
dt = _iu.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(dt)

POLICY = json.loads((ROOT / "state" / "dependabot-repos.json").read_text())
DEFAULTS = POLICY["defaults"]
REVIEWERS = POLICY["reviewers"]
CASES = ROOT / "evals" / "dependabot-cases"

GREEN = lambda n: "green"  # noqa: E731
RED = lambda n: "red"  # noqa: E731
UNKNOWN = lambda n: "unknown"  # noqa: E731


def run(name, conclusion="SUCCESS", status="COMPLETED", at="2026-09-12T00:00:00Z"):
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion,
            "startedAt": at, "detailsUrl": f"https://github.com/example-org/x/actions/runs/1/job/{len(name)}",
            "workflowName": "CI"}


def pr(**over):
    base = {
        "number": 42, "url": "https://github.com/example-org/x/pull/42",
        "title": "Bump foo from 1.2.3 to 1.2.4",
        "body": (
            "Bumps [foo](https://github.com/foo/foo) from 1.2.3 to 1.2.4.\n<details>\n"
            "<summary>Release notes</summary>\n<li>Bump bar from 1.0.0 to 9.0.0</li>\n</details>"
        ),
        "author": {"login": "app/dependabot", "is_bot": True},
        "isDraft": False, "state": "OPEN", "labels": [], "headRefOid": "abc123",
        "mergeable": "MERGEABLE", "mergeStateStatus": "BLOCKED",
        "statusCheckRollup": [run("lint"), run("test"), run("deploy", "FAILURE"), run("CodeQL", "NEUTRAL")],
        "reviewRequests": [], "latestReviews": [],
    }
    base.update(over)
    return base


REPO = {"verify_checks": ["lint", "test"], "automerge": True}


def decide(p, repo=REPO, main=GREEN, defaults=DEFAULTS):
    return dt.decide(p, repo, defaults, main, reviewers=REVIEWERS)


class VersionClassification(unittest.TestCase):
    def test_table(self):
        cases = [
            ("1.2.3", "1.2.4", "patch"), ("1.2.3", "1.3.0", "minor"), ("1.2.3", "2.0.0", "major"),
            ("4", "7", "major"), ("4", "4.1", "minor"), ("v1.2.3", "v1.2.4", "patch"),
            ("0.29.0", "0.33.4", "major"), ("0.35.3", "0.35.4", "patch"), ("0.0.3", "0.0.4", "major"),
            ("1.2.3-beta.1", "1.2.3", "patch"), ("1.2.3", "1.2.4+build.7", "patch"),
            ("1.2.3.4", "1.2.3.5", "patch"), ("abcdef0", "1234567", "unparseable"), ("", "1.0.0", "unparseable"),
        ]
        for a, b, want in cases:
            with self.subTest(a=a, b=b):
                self.assertEqual(dt.classify_version(a, b), want)

    def test_zero_x_knob_off(self):
        self.assertEqual(dt.classify_version("0.29.0", "0.33.4", zero_x_minor_is_major=False), "minor")
        self.assertEqual(dt.classify_version("0.0.3", "0.0.4", zero_x_minor_is_major=False), "patch")

    def test_pr_class_is_worst(self):
        bumps = [{"name": "a", "from": "1.0.0", "to": "1.0.1"}, {"name": "b", "from": "2.0.0", "to": "3.0.0"},
                 {"name": "c", "from": "1.1.0", "to": "1.2.0"}]
        self.assertEqual(dt.pr_class(bumps), "major")
        self.assertEqual([b["class"] for b in bumps], ["patch", "major", "minor"])
        self.assertEqual(dt.pr_class([]), "unparseable")


class BumpParsing(unittest.TestCase):
    def test_single_with_link_and_release_notes_ignored(self):
        b = dt.parse_bumps("Bump foo from 1.2.3 to 1.2.4", pr()["body"])
        self.assertEqual(b, [{"name": "foo", "from": "1.2.3", "to": "1.2.4"}])

    def test_single_without_link(self):
        result = dt.parse_bumps("", "Bumps foo from 1.2.3 to 1.2.4.")
        self.assertEqual(result, [{"name": "foo", "from": "1.2.3", "to": "1.2.4"}])

    def test_title_fallback_with_conventional_prefix(self):
        self.assertEqual(dt.parse_bumps("build(deps): bump js-yaml from 4.3.1 to 4.3.2", "no body"),
                         [{"name": "js-yaml", "from": "4.3.1", "to": "4.3.2"}])
        self.assertEqual(dt.parse_bumps("Bump the prod-minor-patch group with 6 updates", ""), [])

    def test_grouped_updates_lines(self):
        body = ("Bumps the dev-dependencies group with 3 updates in the / directory:\n"
                "Updates `@biomejs/biome` from 2.5.1 to 2.5.12\n<details>..</details>\n"
                "Updates `typescript` from 6.0.2 to 7.0.2\nUpdates [`zod`](https://z) from 4.4.3 to 4.5.4\n")
        b = dt.parse_bumps("Bump the dev-dependencies group with 3 updates", body)
        self.assertEqual([x["name"] for x in b], ["@biomejs/biome", "typescript", "zod"])
        self.assertEqual(dt.pr_class(b), "major")

    def test_multi_dep_security_header_without_versions(self):
        body = ("Bumps [sharp](https://s) to 0.35.4 and updates ancestor dependency [wrangler](https://w). "
                "These dependencies need to be updated together.\n\nUpdates `sharp` from 0.35.3 to 0.35.4\n"
                "Updates `wrangler` from 4.125.0 to 4.131.0\n")
        b = dt.parse_bumps("Bump sharp and wrangler", body)
        self.assertEqual(len(b), 2)
        self.assertEqual(dt.pr_class(b), "minor")

    def test_body_wins_over_title(self):
        b = dt.parse_bumps("Bump foo from 1.0.0 to 9.0.0", "Bumps [foo](u) from 1.0.0 to 1.0.1.")
        self.assertEqual(b[0]["to"], "1.0.1")


class CheckNormalization(unittest.TestCase):
    def test_latest_duplicate_wins(self):
        c = dt.normalize_checks([run("lint", "FAILURE", at="2026-09-12T00:00:00Z"),
                                 run("lint", "SUCCESS", at="2026-09-12T01:00:00Z")])
        self.assertEqual(c["lint"]["state"], "green")

    def test_states(self):
        c = dt.normalize_checks([run("a", "SKIPPED"), run("b", None, status="IN_PROGRESS"), run("c", "CANCELLED"),
                                 run("d", "TIMED_OUT"), run("e", "NEUTRAL"),
                                 {"__typename": "StatusContext", "context": "ci/legacy", "state": "PENDING"},
                                 {"__typename": "StatusContext", "context": "ci/old", "state": "ERROR"}])
        self.assertEqual({k: v["state"] for k, v in c.items()},
                         {"a": "skipped", "b": "pending", "c": "red", "d": "red", "e": "skipped",
                          "ci/legacy": "pending", "ci/old": "red"})


class Decide(unittest.TestCase):
    def test_skips(self):
        self.assertEqual(decide(pr(author={"login": "other-eng-handle"}))["outcome"], "skip")
        self.assertEqual(decide(pr(), repo=None)["reason"], "repo not in policy")
        self.assertEqual(decide(pr(isDraft=True))["reason"], "draft")
        self.assertEqual(decide(pr(state="MERGED"))["outcome"], "skip")

    def test_major_needs_human_with_round_robin_reviewer(self):
        d = decide(pr(title="Bump foo from 1.2.3 to 2.0.0", body="Bumps [foo](u) from 1.2.3 to 2.0.0."))
        self.assertEqual((d["outcome"], d["class"]), ("needs-human", "major"))
        active = [p for p in REVIEWERS["pool"] if p not in REVIEWERS["out"]]
        self.assertEqual(d["reviewer"], active[42 % len(active)])
        self.assertIn("major version bump", d["reason"])

    def test_zero_x_reason_mentions_rule(self):
        d = decide(pr(body="Bumps [satori](u) from 0.29.0 to 0.33.4."))
        self.assertEqual(d["outcome"], "needs-human")
        self.assertIn("0.x", d["reason"])

    def test_unparseable_needs_human(self):
        d = decide(pr(title="Bump something", body="Bumps [x](u) from abc1234 to def5678."))
        self.assertEqual((d["outcome"], d["class"]), ("needs-human", "unparseable"))

    def test_existing_human_reviewer_blocks_assignment_unless_excluded(self):
        major = dict(body="Bumps [foo](u) from 1.0.0 to 2.0.0.")
        d = decide(pr(reviewRequests=[{"__typename": "User", "login": "other-eng-handle"}], **major))
        self.assertIsNone(d["reviewer"])
        d = decide(pr(reviewRequests=[{"__typename": "User", "login": "eng-lead-handle"}], **major))
        self.assertIsNotNone(d["reviewer"], "an excluded lead on the request list must not count")
        d = decide(pr(latestReviews=[{"author": {"login": "copilot-pull-request-reviewer[bot]"}}], **major))
        self.assertIsNotNone(d["reviewer"])
        d = decide(pr(latestReviews=[{"author": {"login": "reviewer-b-handle"}}], **major))
        self.assertIsNone(d["reviewer"])

    def test_conflict_rebase_before_ci(self):
        d = decide(pr(mergeable="CONFLICTING", statusCheckRollup=[run("lint", "FAILURE")]))
        self.assertEqual(d["outcome"], "rebase")

    def test_no_verify_checks_is_needs_human(self):
        d = decide(pr(), repo={"verify_checks": []})
        self.assertEqual(d["outcome"], "needs-human")
        self.assertIn("no verification checks", d["reason"])

    def test_wait_states(self):
        self.assertEqual(decide(pr(mergeable="UNKNOWN"))["outcome"], "wait")
        d = decide(pr(statusCheckRollup=[run("lint"), run("test", None, status="QUEUED")]))
        self.assertEqual(d["outcome"], "wait")
        self.assertIn("test", d["reason"])

    def test_blocked_missing_and_skipped(self):
        self.assertEqual(decide(pr(statusCheckRollup=[run("lint")]))["outcome"], "blocked:missing")
        skipped = decide(pr(statusCheckRollup=[run("lint"), run("test", "SKIPPED")]))
        self.assertEqual(skipped["outcome"], "blocked:missing")

    def test_only_a_confirmed_red_on_main_exonerates(self):
        red = pr(statusCheckRollup=[run("lint"), run("test", "FAILURE")])
        self.assertEqual(decide(red, main=RED)["outcome"], "blocked:main-red")
        for state in ("unknown", "skipped", "pending"):
            d = decide(red, main=lambda n, s=state: s)
            self.assertEqual(d["outcome"], "blocked:regression", state)
            self.assertIn(state, d["reason"])

    def test_regression_when_main_is_green(self):
        d = decide(pr(statusCheckRollup=[run("lint"), run("test", "FAILURE")]), main=GREEN)
        self.assertEqual(d["outcome"], "blocked:regression")
        self.assertEqual(d["regression"]["check"], "test")
        self.assertIn("/job/", d["regression"]["url"])

    def test_red_upstream_beats_skipped_downstream(self):
        d = decide(pr(statusCheckRollup=[run("lint", "FAILURE"), run("test", "SKIPPED")]), main=GREEN)
        self.assertEqual(d["outcome"], "blocked:regression")
        self.assertEqual(d["regression"]["check"], "lint")
        self.assertEqual(d["regression"]["downstream_skipped"], ["test"])
        self.assertIn("skipped downstream: test", d["reason"])

    def test_regression_wins_over_a_second_check_red_on_main(self):
        d = decide(pr(statusCheckRollup=[run("lint", "FAILURE"), run("test", "FAILURE")]),
                   main=lambda n: "green" if n == "test" else "red")
        self.assertEqual(d["outcome"], "blocked:regression")
        self.assertEqual(d["regression"]["also_red_on_main"], ["lint"])

    def test_checks_unreadable_waits_but_majors_still_route(self):
        d = decide(pr(_checks_unavailable=True, statusCheckRollup=[]))
        self.assertEqual(d["outcome"], "wait")
        self.assertIn("Checks: read", d["reason"])
        d = decide(pr(_checks_unavailable=True, body="Bumps [foo](u) from 1.0.0 to 2.0.0."))
        self.assertEqual(d["outcome"], "needs-human")
        self.assertIsNotNone(d["reviewer"])
        d = decide(pr(_checks_unavailable=True, mergeable="CONFLICTING"))
        self.assertEqual(d["outcome"], "rebase")

    def test_merge_ignores_unlisted_red_checks(self):
        d = decide(pr())  # deploy is FAILURE but not a verify check
        self.assertEqual((d["outcome"], d["class"]), ("merge", "patch"))
        self.assertEqual(d["verify"], {"lint": "green", "test": "green"})


class Actions(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.orig_gh = dt.gh

    def tearDown(self):
        dt.gh = self.orig_gh

    def policy(self, **repo_over):
        p = json.loads(json.dumps(POLICY))
        p["repos"] = {"x": {"verify_checks": ["lint", "test"], **repo_over}}
        return p

    def observe(self, p, d, policy, frozen=False, counters=None):
        dt.gh = lambda *a, **k: self.fail(f"observe mode issued a gh call: {a[:3]}")
        dt.act_on("x", p, d, policy, "observe", counters or {"repo": {}, "all": 0}, frozen)
        return d

    def test_observe_mode_writes_nothing(self):
        for p in (pr(), pr(body="Bumps [foo](u) from 1.0.0 to 2.0.0."), pr(mergeable="CONFLICTING"),
                  pr(statusCheckRollup=[run("lint")])):
            d = decide(p)
            self.observe(p, d, self.policy(automerge=True))
            self.assertTrue(d["action"])

    def test_actions_by_outcome(self):
        d = self.observe(pr(), decide(pr()), self.policy(automerge=True))
        self.assertEqual(d["action"], "approve + squash merge")
        d = self.observe(pr(), decide(pr()), self.policy())  # automerge default false
        self.assertTrue(d["action"].startswith("label deps:needs-human (automerge disabled"))
        self.assertIsNotNone(d["reviewer"])
        d = self.observe(pr(), decide(pr()), self.policy(automerge=True), frozen=True)
        self.assertEqual(d["action"], "hold (AUTO_MERGE_FROZEN)")
        d = self.observe(pr(), decide(pr()), self.policy(automerge=True), counters={"repo": {"x": 3}, "all": 3})
        self.assertEqual(d["action"], "hold (merge cap reached this run)")
        d = self.observe(pr(), decide(pr()), self.policy(automerge=True), counters={"repo": {}, "all": 10})
        self.assertEqual(d["action"], "hold (merge cap reached this run)")
        major = pr(body="Bumps [foo](u) from 1.0.0 to 2.0.0.")
        d = self.observe(major, decide(major), self.policy())
        self.assertTrue(d["action"].startswith("label deps:needs-human, request @"))
        reg = pr(statusCheckRollup=[run("lint"), run("test", "FAILURE")])
        d = self.observe(reg, decide(reg), self.policy())
        self.assertEqual(d["action"], "label deps:blocked")
        d = self.observe(reg, decide(reg, main=RED), self.policy())
        self.assertEqual(d["action"], "none")

    def fake_gh(self, head_after="abc123", fail_merge=False):
        def gh(*args, **kw):
            self.calls.append(args)
            if args[:2] == ("pr", "view"):
                return json.dumps({**pr(), "headRefOid": head_after})
            if args[:2] == ("api", "repos/example-org/x/issues/42/comments"):
                return ""  # no marker comment yet
            if args[:2] == ("pr", "merge") and fail_merge:
                raise dt.GhError("merge failed: 405")
            return ""
        return gh

    def test_act_merge_path(self):
        dt.gh = self.fake_gh()
        p, d = pr(), decide(pr())
        counters = {"repo": {}, "all": 0}
        dt.act_on("x", p, d, self.policy(automerge=True), "act", counters, False)
        kinds = [c[:2] for c in self.calls]
        self.assertIn(("pr", "edit"), kinds)     # deps:auto label
        self.assertIn(("pr", "review"), kinds)
        merge = [c for c in self.calls if c[:2] == ("pr", "merge")][0]
        self.assertIn("--squash", merge)
        self.assertIn("--match-head-commit", merge)
        self.assertIn("abc123", merge)
        self.assertLess(kinds.index(("pr", "review")), kinds.index(("pr", "merge")))
        self.assertTrue(d["action"].endswith("→ merged"))
        self.assertEqual(counters, {"repo": {"x": 1}, "all": 1})

    def test_act_merge_aborts_when_head_moved(self):
        dt.gh = self.fake_gh(head_after="def456")
        d = decide(pr())
        dt.act_on("x", pr(), d, self.policy(automerge=True), "act", {"repo": {}, "all": 0}, False)
        self.assertNotIn(("pr", "merge"), [c[:2] for c in self.calls])
        self.assertNotIn(("pr", "review"), [c[:2] for c in self.calls])
        self.assertIn("head moved", d["action"])

    def test_act_merge_failure_is_reported_not_raised(self):
        dt.gh = self.fake_gh(fail_merge=True)
        d = decide(pr())
        counters = {"repo": {}, "all": 0}
        dt.act_on("x", pr(), d, self.policy(automerge=True), "act", counters, False)
        self.assertIn("merge failed", d["action"])
        self.assertEqual(counters["all"], 0)

    def test_act_needs_human_labels_requests_and_comments_once(self):
        dt.gh = self.fake_gh()
        major = pr(body="Bumps [foo](u) from 1.0.0 to 2.0.0.")
        d = decide(major)
        dt.act_on("x", major, d, self.policy(), "act", {"repo": {}, "all": 0}, False)
        edits = [c for c in self.calls if c[:2] == ("pr", "edit")]
        self.assertTrue(any("--add-label" in c and "deps:needs-human" in c for c in edits))
        self.assertTrue(any("--add-reviewer" in c for c in edits))
        posts = [c for c in self.calls if c[:3] == ("api", "-X", "POST")]
        self.assertEqual(len(posts), 1)
        self.assertIn(dt.MARKER_PREFIX, posts[0][-1])

    def test_act_rebase_requested_once_per_head(self):
        dt.gh = self.fake_gh()
        conflict = pr(mergeable="CONFLICTING")
        dt.act_on("x", conflict, decide(conflict), self.policy(), "act", {"repo": {}, "all": 0}, False)
        posts = [c[-1] for c in self.calls if c[:3] == ("api", "-X", "POST")]
        self.assertIn("body=@dependabot rebase", posts)
        # second run: marker says this head was already asked
        self.calls.clear()
        marker_body = (
            f"{dt.MARKER_PREFIX}"
            + json.dumps({"sha": "abc123", "rebase_requested_sha": "abc123"})
            + " -->"
        )
        marker = json.dumps({"id": 7, "body": marker_body})
        orig = dt.gh
        dt.gh = lambda *a, **k: marker if a[:2] == ("api", f"repos/{dt.OWNER}/x/issues/42/comments") else orig(*a, **k)
        d = decide(conflict)
        dt.act_on("x", conflict, d, self.policy(), "act", {"repo": {}, "all": 0}, False)
        self.assertEqual(d["action"], "rebase already requested for this head")
        self.assertFalse([c for c in self.calls if c[:3] == ("api", "-X", "POST")])


class ListingFallback(unittest.TestCase):
    def tearDown(self):
        dt.gh = self.orig

    def test_private_repo_without_checks_permission_lists_without_rollup(self):
        self.orig = dt.gh
        calls = []

        def gh(*args, **kw):
            calls.append(args)
            if "statusCheckRollup" in args[-1]:
                raise dt.GhError(
                    "GraphQL: Resource not accessible by integration "
                    "(search.nodes.0.statusCheckRollup.nodes.0)"
                )
            one = {**pr(), "statusCheckRollup": None}
            return json.dumps(one if args[:2] == ("pr", "view") else [one])

        dt.gh = gh
        prs = dt.list_dependabot_prs("example-app-web")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("statusCheckRollup", calls[1][-1])
        self.assertTrue(prs[0]["_checks_unavailable"])
        one = dt.refresh_pr("example-app-web", 42)
        self.assertTrue(one["_checks_unavailable"])

    def test_other_errors_still_raise(self):
        self.orig = dt.gh
        dt.gh = lambda *a, **k: (_ for _ in ()).throw(dt.GhError("HTTP 404: Not Found"))
        with self.assertRaises(dt.GhError):
            dt.list_dependabot_prs("nope")


class LiveFixtures(unittest.TestCase):
    def test_every_case_matches_expected(self):
        dirs = sorted(p for p in CASES.iterdir() if (p / "expected.json").exists())
        self.assertGreaterEqual(len(dirs), 8, "captured fixtures went missing")
        for case in dirs:
            with self.subTest(case=case.name):
                p = json.loads((case / "pr.json").read_text())
                exp = json.loads((case / "expected.json").read_text())
                main_checks_path = case / "main-checks.json"
                main = json.loads(main_checks_path.read_text()) if main_checks_path.exists() else {}
                repo_policy = exp.get("policy_override", POLICY["repos"].get(p["repo"]))
                d = dt.decide(
                    p, repo_policy, DEFAULTS,
                    lambda n, main=main: main.get(n, "unknown"),
                    reviewers=REVIEWERS,
                )
                self.assertEqual(d["outcome"], exp["outcome"], d["reason"])
                self.assertEqual(d["class"], exp["class"])
                if "bumps" in exp:
                    self.assertEqual(len(d["bumps"]), exp["bumps"])
                if "verify" in exp:
                    self.assertEqual(d["verify"], exp["verify"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
