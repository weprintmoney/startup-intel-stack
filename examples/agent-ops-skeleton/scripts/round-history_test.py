#!/usr/bin/env python3
"""Unit tests for scripts/round-history.py (run by schema-validate.yml)."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rh", HERE / "round-history.py")
rh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rh)


class Payload(unittest.TestCase):
    def test_empty_body_reads_defaults(self):
        p = rh.read_payload("Closes #1.\n")
        self.assertEqual(p["rounds"], [])
        self.assertEqual(p["cap"], 3)
        self.assertEqual(p["ceiling_usd"], 50.0)

    def test_roundtrip_and_position_preserved(self):
        body = "Closes #1.\n\n## Reviews\nstuff\n"
        p = rh.read_payload(body)
        p["rounds"].append(rh.validate_entry(entry(0, "implement", cost=2.29)))
        b1 = rh.write_block(body, rh.render(p))
        self.assertTrue(b1.startswith("Closes #1."))
        self.assertIn(rh.START, b1)
        # second append replaces in place, body text before it untouched, one block only
        p2 = rh.read_payload(b1)
        self.assertEqual(p2["rounds"][0]["cost_usd"], 2.29)
        p2["rounds"].append(rh.validate_entry(entry(1, "judge", "fail", 70, 0.61)))
        b2 = rh.write_block("PREFIX\n" + b1[len("Closes #1.\n"):] if False else b1, rh.render(p2))
        self.assertEqual(b2.count(rh.START), 1)
        self.assertEqual(b2.count(rh.END), 1)
        self.assertEqual(len(rh.read_payload(b2)["rounds"]), 2)
        self.assertIn("## Reviews\nstuff", b2)

    def test_gt_escaped_in_data_comment(self):
        p = rh.read_payload("")
        p["rounds"].append(rh.validate_entry(entry(1, "judge", "fail", 50, 1, note="a -> b")))
        block = rh.render(p)
        data_line = [line for line in block.splitlines() if "agent-ops:rounds:data" in line][0]
        self.assertNotIn("->", data_line.split("agent-ops:rounds:data ", 1)[1].rsplit(" -->", 1)[0])
        self.assertEqual(rh.read_payload(block)["rounds"][0]["note"], "a -> b")

    def test_validate_entry_rejects_bad(self):
        for bad in ({"round": -1, "stage": "judge"}, {"round": 1, "stage": "nope"},
                    {"round": 1, "stage": "judge", "verdict": "maybe"},
                    {"round": 1, "stage": "judge", "cost_usd": -3}):
            with self.assertRaises(SystemExit):
                rh.validate_entry(bad)


def entry(rnd, stage, verdict=None, score=None, cost=1.0, sha="abcdef0123456789", url="https://x/run/1", note=""):
    return {"round": rnd, "stage": stage, "verdict": verdict, "score": score,
            "cost_usd": cost, "sha": sha, "run_url": url, "at": "2026-09-12T00:00:00Z", "note": note}


class Decide(unittest.TestCase):
    def payload(self, *entries, cap=3, ceiling=50.0):
        return {"cap": cap, "ceiling_usd": ceiling, "rounds": [rh.validate_entry(e) for e in entries]}

    def test_pass(self):
        self.assertEqual(rh.decide(self.payload(entry(1, "judge", "pass", 95)), 1, "pass"), "judge-pass")

    def test_fail_under_cap_and_ceiling_revises(self):
        p = self.payload(entry(0, "implement", cost=2.3), entry(1, "judge", "fail", 60, 0.6))
        self.assertEqual(rh.decide(p, 1, "fail"), "revise")

    def test_fail_at_cap(self):
        p = self.payload(entry(3, "judge", "fail", 60))
        self.assertEqual(rh.decide(p, 3, "fail"), "needs-human:cap")
        self.assertEqual(rh.decide(p, 4, "fail"), "needs-human:cap")

    def test_fail_over_ceiling(self):
        p = self.payload(entry(0, "implement", cost=30), entry(1, "judge", "fail", 60, 21))
        self.assertEqual(rh.decide(p, 1, "fail"), "needs-human:cost")

    def test_cap_checked_before_cost(self):
        p = self.payload(entry(0, "implement", cost=60), entry(3, "judge", "fail", 60, 1))
        self.assertEqual(rh.decide(p, 3, "fail"), "needs-human:cap")

    def test_rejected_halts(self):
        self.assertEqual(rh.decide(self.payload(), 1, "rejected"), "halt:rejected-verdict")

    def test_cli_overrides(self):
        p = self.payload(entry(1, "judge", "fail", 60, 5))
        self.assertEqual(rh.decide(p, 1, "fail", cap=1), "needs-human:cap")
        self.assertEqual(rh.decide(p, 1, "fail", ceiling=4.0), "needs-human:cost")


class NextRoundAndTotals(unittest.TestCase):
    def test_next_round(self):
        self.assertEqual(rh.next_round({"rounds": []}), 1)
        p = {"rounds": [rh.validate_entry(entry(0, "implement")), rh.validate_entry(entry(1, "judge", "fail", 1)),
                        rh.validate_entry(entry(1, "revise")), rh.validate_entry(entry(2, "judge", "fail", 1))]}
        self.assertEqual(rh.next_round(p), 3)

    def test_total_cost(self):
        p = {"rounds": [rh.validate_entry(entry(0, "implement", cost=2.294)),
                        rh.validate_entry(entry(1, "judge", "fail", 1, cost=0.606))]}
        self.assertEqual(rh.total_cost(p), 2.9)


class Cli(unittest.TestCase):
    def run_cli(self, body_path, *args):
        return subprocess.run([sys.executable, str(HERE / "round-history.py"), "--body", str(body_path), *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    def test_append_is_idempotent_per_round_stage(self):
        with tempfile.TemporaryDirectory() as d:
            body = Path(d) / "body.md"
            body.write_text("Closes example-org/example-app-core#1.\n")
            self.run_cli(body, "append", "--entry", json.dumps(entry(1, "judge", "fail", 60, 0.5)))
            # re-dispatch, same round
            self.run_cli(body, "append", "--entry", json.dumps(entry(1, "judge", "fail", 65, 0.7)))
            self.run_cli(body, "append", "--entry", json.dumps(entry(1, "revise", cost=1.1, sha="9d8e7f6a9d8e7f6a")))
            payload = json.loads(self.run_cli(body, "read"))
            self.assertEqual(len(payload["rounds"]), 2)
            self.assertEqual(payload["rounds"][0]["score"], 65)
            self.assertEqual(self.run_cli(body, "total-cost"), "1.80")
            self.assertEqual(self.run_cli(body, "next-round"), "2")
            self.assertEqual(self.run_cli(body, "decide", "--round", "1", "--verdict", "fail"), "revise")
            text = body.read_text()
            self.assertTrue(text.startswith("Closes example-org/example-app-core#1."))
            self.assertIn("| 1 | judge | fail | 65 | 0.70 | `abcdef0` |", text)
            summary = self.run_cli(body, "summary")
            self.assertIn("round 1 judge · fail 65/100 · $0.70", summary)
            self.assertIn("total $1.80 / $50.00 ceiling, cap 3", summary)

    def test_cap_and_ceiling_persist_in_block(self):
        with tempfile.TemporaryDirectory() as d:
            body = Path(d) / "body.md"
            body.write_text("")
            self.run_cli(
                body, "append", "--cap", "2", "--ceiling", "10",
                "--entry", json.dumps(entry(1, "judge", "fail", 60, 4)),
            )
            self.assertEqual(self.run_cli(body, "decide", "--round", "1", "--verdict", "fail"), "revise")
            self.run_cli(body, "append", "--entry", json.dumps(entry(1, "revise", cost=7)))
            self.assertEqual(self.run_cli(body, "decide", "--round", "2", "--verdict", "fail"), "needs-human:cap")
            self.assertEqual(self.run_cli(body, "decide", "--round", "1", "--verdict", "fail"), "needs-human:cost")


if __name__ == "__main__":
    unittest.main(verbosity=1)
