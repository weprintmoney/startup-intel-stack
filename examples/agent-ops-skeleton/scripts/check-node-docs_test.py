#!/usr/bin/env python3
"""Unit tests for scripts/check-node-docs.py (run by schema-validate.yml)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cnd", HERE / "check-node-docs.py")
cnd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cnd)

GOOD_README = "\n".join(f"## {h}\ncontent\n" for h in cnd.EXPECTED_HEADINGS)


def make_tree(tmp: Path, *, root_readme: str, workflows: list[str], nodes: dict[str, dict]):
    """nodes: {name: {"claude": bool, "readme": str | None}}"""
    (tmp / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    for wf in workflows:
        (tmp / ".github" / "workflows" / wf).write_text("name: x\non: workflow_dispatch\njobs: {}\n")
    (tmp / "README.md").write_text(root_readme)
    (tmp / "agents").mkdir(exist_ok=True)
    for name, cfg in nodes.items():
        node_dir = tmp / "agents" / name
        node_dir.mkdir(parents=True, exist_ok=True)
        if cfg.get("claude", True):
            (node_dir / "CLAUDE.md").write_text("# persona\n")
        if cfg.get("readme") is not None:
            (node_dir / "README.md").write_text(cfg["readme"])


class WorkflowReadmeParity(unittest.TestCase):
    def test_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            make_tree(
                tmp,
                root_readme="mentions foo.yml and bar.yml here",
                workflows=["foo.yml", "bar.yml"],
                nodes={"alpha": {"readme": GOOD_README}},
            )
            self.assertEqual(cnd.check(tmp), [])

    def test_missing_workflow_mention_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            make_tree(
                tmp,
                root_readme="mentions only foo.yml",
                workflows=["foo.yml", "bar.yml"],
                nodes={},
            )
            failures = cnd.check(tmp)
            self.assertEqual(len(failures), 1)
            self.assertIn("bar.yml", failures[0])

    def test_missing_root_readme_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / ".github" / "workflows").mkdir(parents=True)
            (tmp / ".github" / "workflows" / "foo.yml").write_text("name: x\n")
            failures = cnd.check(tmp)
            self.assertTrue(any("MISSING README.md" in f for f in failures))


class NodeReadmeHeadings(unittest.TestCase):
    def test_clean_node_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            make_tree(tmp, root_readme="", workflows=[], nodes={"alpha": {"readme": GOOD_README}})
            self.assertEqual(cnd.check(tmp), [])

    def test_missing_node_readme_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            make_tree(tmp, root_readme="", workflows=[], nodes={"alpha": {"readme": None}})
            failures = cnd.check(tmp)
            self.assertEqual(len(failures), 1)
            self.assertIn("agents/alpha/README.md missing", failures[0])

    def test_out_of_order_headings_fail(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            shuffled = cnd.EXPECTED_HEADINGS[1:] + cnd.EXPECTED_HEADINGS[:1]
            bad_readme = "\n".join(f"## {h}\ncontent\n" for h in shuffled)
            make_tree(tmp, root_readme="", workflows=[], nodes={"alpha": {"readme": bad_readme}})
            failures = cnd.check(tmp)
            self.assertEqual(len(failures), 1)
            self.assertIn("Purpose", failures[0])

    def test_missing_heading_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            missing_owner = "\n".join(f"## {h}\ncontent\n" for h in cnd.EXPECTED_HEADINGS[:-1])
            make_tree(tmp, root_readme="", workflows=[], nodes={"alpha": {"readme": missing_owner}})
            failures = cnd.check(tmp)
            self.assertEqual(len(failures), 1)
            self.assertIn("Owner", failures[0])

    def test_extra_headings_are_fine(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            extra = "## Table of contents\nnot required\n" + GOOD_README
            make_tree(tmp, root_readme="", workflows=[], nodes={"alpha": {"readme": extra}})
            self.assertEqual(cnd.check(tmp), [])

    def test_fenced_example_heading_is_ignored(self):
        # A README whose real headings are correct, but which also quotes an
        # example containing a fake "## Purpose" inside a fenced block
        # (the code-judge/CLAUDE.md:55 case) must not double-count or
        # confuse the order check.
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            readme = (
                "## Purpose\n\nExample output shape:\n\n"
                "```markdown\n## Purpose\nthis is a fake heading inside an example\n```\n\n"
                + "\n".join(f"## {h}\ncontent\n" for h in cnd.EXPECTED_HEADINGS[1:])
            )
            make_tree(tmp, root_readme="", workflows=[], nodes={"alpha": {"readme": readme}})
            self.assertEqual(cnd.check(tmp), [])

    def test_two_nodes_one_broken_reports_only_the_broken_one(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            make_tree(
                tmp,
                root_readme="",
                workflows=[],
                nodes={"alpha": {"readme": GOOD_README}, "beta": {"readme": None}},
            )
            failures = cnd.check(tmp)
            self.assertEqual(len(failures), 1)
            self.assertIn("beta", failures[0])


if __name__ == "__main__":
    unittest.main()
