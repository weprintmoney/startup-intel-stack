#!/usr/bin/env python3
"""Claim-verify gate — deterministic pre-pass and aggregation around the
fresh-context `agents/claim-verifier/CLAUDE.md` node.

Agents that write prose about the product (spec-drafter, release-intelligence
-miner) can be right-shaped and wrong: a spec that cites a file that does not
exist, asserts a backing store the product dropped two releases ago, or leans
on a graph node nobody wrote. Turn caps and timeouts catch runaway retries; nothing
catches confident success with a wrong fact. This gate does, in two layers:

  1. deterministic (this script) — everything a grep can decide is decided
     here and never handed to a model: retired positioning phrases, cited
     `path:line` that do not exist, graph node ids missing from graph.json,
     evidence paths missing from internal-docs, evidence URLs outside
     <YOUR_ORG>/*, version tags against the public changelog.
  2. model (agents/claim-verifier) — fresh `claude -p` fed only the artifact,
     the pre-pass claims, and the canonical sources. Resolves the claims the
     pre-pass marked `pending` and enumerates the prose claims about current
     product behavior that no regex can find.

Verdict per claim: `verified` | `unverified` | `contradicted`.
Overall verdict: a material contradiction blocks. A contradiction the model
marks `material: false` — a measurement read off the checkout (line count,
line number, size) that is off by a little while the artifact's argument
holds at the corrected value — flags alongside `unverified` instead of
blocking (a 2-line `wc -l` delta once drafted a PR and cost two fixup PRs).
Pre-pass contradictions are never immaterial.

Subcommands (all stdlib):

  sources   --internal-docs DIR [--docs-repo DIR] --out DIR
      Materialize the canonical sources + manifest.json. features.json is
      picked up automatically when it exists; until then the
      retired-phrase list is parsed from claims-vetted.md.

  extract   --kind spec|release-findings --artifact PATH --artifact-ref REF
            --sources DIR [--product DIR] [--internal-docs DIR] --out claims.json
      Deterministic extraction. Emits claims with a final verdict where the
      grep decides, `pending` where the model must.

  aggregate --claims claims.json [--model-verdict verdict.json] --run-url URL
            --out final.json [--md final.md]
      Merge pre-pass + model output into one schema-valid claim-verdict
      (schemas/claim-verdict.schema.json) and an optional markdown block for
      PR bodies. A missing/unparseable model verdict never passes silently:
      pending claims become `unverified` and a placeholder claim records it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VERDICTS = ("verified", "unverified", "contradicted")
SEVERITY = {"verified": 0, "unverified": 1, "contradicted": 2}
KINDS = (
    "retired-phrase", "path-citation", "graph-node", "version",
    "evidence-source", "feature-status", "product-behavior",
    "doc-statement", "other",
)

# Citation roots `scan_path_citations` resolves cited `path:line`s against, in
# priority order — (root name, `Extractor` attribute). Single source of truth
# so the CI gate (scripts/check-citation-root-coverage.py) can
# enumerate them without re-parsing this file: it fails the build if any name
# here has no golden-set case in evals/claim-verify-cases/ that resolves a
# real path against it, closing the gap that let the `agent-ops` root ship
# with zero golden-set coverage.
CITATION_ROOTS: tuple[tuple[str, str], ...] = (
    ("product", "product"),
    ("internal-docs", "internal"),
    ("agent-ops", "agent_ops"),
)

# ---------------------------------------------------------------- sources ---

SOURCE_FILES = {
    # name -> (which checkout, relative path, required)
    "graph.json": ("internal-docs", ".claude/indexes/graph.json", True),
    "features.json": ("internal-docs", ".claude/indexes/features.json", False),
    "invariants.md": ("internal-docs", "07-engineering-docs/terminus/invariants.md", False),
    "behavior-matrix.yaml": ("internal-docs", "07-engineering-docs/backing-stores/behavior-matrix.yaml", False),
    "claims-vetted.md": ("internal-docs", "04-marketing/content-ops/reference/claims-vetted.md", False),
    "changelog.mdx": ("docs-repo", "versions/changelog.mdx", False),
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def _git_head(d: Path | None) -> str | None:
    """Short HEAD of the checkout at `d` — only when `d` is itself a git
    toplevel, so a fixture tree nested inside another repo reports None
    rather than the enclosing repo's commit."""
    if d is None or not d.is_dir():
        return None
    try:
        top = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--show-toplevel"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if Path(top).resolve() != d.resolve():
            return None
        return subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip() or None
    except Exception:
        return None


def _expand_slash_alternatives(phrase: str) -> list[str]:
    """'no new database to staff/operate/manage' -> three phrases.
    Only splits a/b/c runs with no surrounding spaces (a shorthand for
    alternatives in the claims-vetted table)."""
    m = re.search(r"(\S+?)/(\S+(?:/\S+)*)", phrase)
    if not m:
        return [phrase]
    head, tail = phrase[: m.start()], phrase[m.end():]
    return [f"{head}{alt}{tail}".strip() for alt in m.group(0).split("/")]


def parse_retired_phrases_md(text: str) -> list[str]:
    """Pull the first column of the `## Retired claims` table in
    claims-vetted.md: `"a" / "b" (qualifier) | why | say instead`."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.lower().startswith("## retired claims")), None)
    if start is None:
        return []
    phrases: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower().startswith("retired phrase") \
                or set(cells[0]) <= set("-: "):
            continue
        col = re.sub(r"\([^)]*\)", "", cells[0])            # drop qualifiers
        for piece in col.split(" / "):
            piece = piece.strip().strip("\"'“”‘’").strip()
            if not piece or piece == "—":
                continue
            phrases.extend(_expand_slash_alternatives(piece))
    # de-dup, keep order
    seen, out = set(), []
    for p in phrases:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def retired_phrases_from_features(features: object) -> list[str]:
    entries = features.get("features", features) if isinstance(features, dict) else features
    out: list[str] = []
    if isinstance(entries, dict):
        entries = list(entries.values())
    for e in entries or []:
        if isinstance(e, dict):
            for p in e.get("retired_claim_phrases") or []:
                if isinstance(p, str) and p.strip():
                    out.append(p.strip())
    return out


def cmd_sources(args: argparse.Namespace) -> int:
    internal = Path(args.internal_docs)
    docs_repo = Path(args.docs_repo) if args.docs_repo else None
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    manifest = {
        "generated_at": _now(),
        "internal_docs_dir": str(internal.resolve()),
        "internal_docs_ref": _git_head(internal),
        "docs_repo_dir": str(docs_repo.resolve()) if docs_repo else None,
        "docs_repo_ref": _git_head(docs_repo),
        "product_dir": None,   # filled by extract
        "sources": {},
        "retired_phrases_from": None,
    }
    roots = {"internal-docs": internal, "docs-repo": docs_repo}
    for name, (root_key, rel, required) in SOURCE_FILES.items():
        root = roots[root_key]
        src = (root / rel) if root else None
        present = bool(src and src.is_file())
        if present:
            shutil.copy(src, out / name)
        elif required:
            sys.exit(f"sources: required source missing: {rel} (in {root_key})")
        manifest["sources"][name] = {
            "present": present,
            "path": rel,
            "sha256": _sha256(src) if present else None,
        }

    phrases: list[str] = []
    if manifest["sources"]["features.json"]["present"]:
        try:
            phrases = retired_phrases_from_features(json.loads((out / "features.json").read_text()))
            manifest["retired_phrases_from"] = "features.json"
        except json.JSONDecodeError:
            phrases = []
    if not phrases and manifest["sources"]["claims-vetted.md"]["present"]:
        phrases = parse_retired_phrases_md((out / "claims-vetted.md").read_text())
        manifest["retired_phrases_from"] = "claims-vetted.md"
    (out / "retired-phrases.txt").write_text("\n".join(phrases) + ("\n" if phrases else ""))
    manifest["sources"]["retired-phrases.txt"] = {
        "present": bool(phrases), "path": "(derived)",
        "sha256": _sha256(out / "retired-phrases.txt") if phrases else None,
        "count": len(phrases),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    present = [n for n, s in manifest["sources"].items() if s["present"]]
    absent = [n for n, s in manifest["sources"].items() if not s["present"]]
    print(f"sources: {len(present)} present ({', '.join(present)})"
          + (f"; absent: {', '.join(absent)}" if absent else ""))
    return 0


# ---------------------------------------------------------------- extract ---

URL_RE = re.compile(r"https?://\S+")
PATH_CITE_RE = re.compile(
    r"(?<![\w/.-])((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}):(\d{1,6})(?:-(\d{1,6}))?(?![\w/])"
)
GRAPH_ID_RE = re.compile(
    r"(?<![\w/-])(adr-\d{4}|(?:claim|component|incident|q|req|terminus)/[a-z0-9][a-z0-9-]*)(?![\w/-])"
)
VERSION_RE = re.compile(r"(?<![\w.])v(0\.\d{1,2})(?:\.(\d{1,2}|x))?(?!\w)")   # trailing "." = sentence end
CHANGELOG_LABEL_RE = re.compile(r'<Update\s+label="v(\d+\.\d+)\.(\d+)"')
# Your GitHub org; set GITHUB_ORG in the workflow env (the default is the skeleton placeholder).
ORG = os.environ.get("GITHUB_ORG", "example-org")
ORG_URL_RE = re.compile(rf"^https://(?:www\.)?github\.com/{re.escape(ORG)}/[^\s/]+", re.I)


def phrase_regex(phrase: str) -> re.Pattern:
    parts = [re.escape(p) for p in phrase.split()]
    return re.compile(r"(?<![A-Za-z0-9])" + r"\s+".join(parts) + r"(?![A-Za-z0-9])", re.I)


SENTENCE_BOUNDARY_RE = re.compile(r"[.!?](?=\s)|\n")


def _sentence_at(text: str, pos: int) -> str:
    """The sentence containing `pos`. Boundaries are newlines or terminal
    punctuation followed by whitespace, so `v0.17.0` and `foo.py:12` stay whole."""
    start = 0
    for m in SENTENCE_BOUNDARY_RE.finditer(text, 0, pos):
        start = m.end()
    m_end = SENTENCE_BOUNDARY_RE.search(text, pos)
    end = m_end.start() if m_end else len(text)
    return " ".join(text[start:end].split())[:240]


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


class Extractor:
    def __init__(self, kind: str, sources: Path, product: Path | None, internal: Path | None,
                 agent_ops: Path | None = None):
        self.kind = kind
        self.sources = sources
        self.product = product
        self.internal = internal
        self.agent_ops = agent_ops
        self.manifest = json.loads((sources / "manifest.json").read_text())
        self.graph_nodes: dict = {}
        g = sources / "graph.json"
        if g.is_file():
            data = json.loads(g.read_text())
            self.graph_nodes = data.get("nodes", data) if isinstance(data, dict) else {}
        self.retired = []
        rp = sources / "retired-phrases.txt"
        if rp.is_file():
            self.retired = [line.strip() for line in rp.read_text().splitlines() if line.strip()]
        self.changelog_minors: set[str] = set()
        cl = sources / "changelog.mdx"
        if cl.is_file():
            self.changelog_minors = {m.group(1) for m in CHANGELOG_LABEL_RE.finditer(cl.read_text())}
        self.claims: list[dict] = []

    # -- helpers --
    def add(self, kind: str, claim: str, location: str | None, verdict: str,
            source: str | None, evidence: str | None = None, note: str | None = None,
            finding_pr: int | None = None) -> None:
        self.claims.append({
            "id": f"d-{len(self.claims) + 1:02d}",
            "kind": kind,
            "claim": claim,
            "location": location,
            "verdict": verdict,          # verified|unverified|contradicted|pending
            "checked_by": "deterministic",
            "source": source,
            "evidence": evidence,
            "note": note,
            "finding_pr": finding_pr,
        })

    # -- scanners (each takes text + a location prefix + optional finding pr) --
    def scan_retired(self, text: str, loc: str, finding_pr: int | None) -> None:
        for phrase in self.retired:
            for m in phrase_regex(phrase).finditer(text):
                sentence = _sentence_at(text, m.start())
                where = f"{loc}L{_line_no(text, m.start())}"
                if self.kind == "release-findings":
                    self.add("retired-phrase",
                             f"uses retired positioning phrase \"{phrase}\": {sentence}",
                             where, "contradicted", "retired-phrases.txt",
                             evidence=f"retired phrase list ({self.manifest.get('retired_phrases_from')})",
                             note="findings become prospect-facing tickets; retired phrases are never published",
                             finding_pr=finding_pr)
                else:
                    self.add("retired-phrase",
                             f"mentions retired positioning phrase \"{phrase}\": {sentence}",
                             where, "pending", "retired-phrases.txt",
                             note="model decides: asserted as current product behavior -> contradicted; "
                                  "historical or negated mention -> verified",
                             finding_pr=finding_pr)
                break  # one hit per phrase per text is enough

    def scan_path_citations(self, text: str, loc: str) -> None:
        clean = URL_RE.sub(" ", text)
        seen: set[str] = set()
        for m in PATH_CITE_RE.finditer(clean):
            rel, line = m.group(1), int(m.group(2))
            key = f"{rel}:{line}"
            if key in seen:
                continue
            seen.add(key)
            where = f"{loc}L{_line_no(clean, m.start())}"
            sentence = _sentence_at(clean, m.start())
            roots = [(name, getattr(self, attr)) for name, attr in CITATION_ROOTS]
            hit = next(((name, root / rel) for name, root in roots if root and (root / rel).is_file()), None)
            if self.product is None and self.internal is None and self.agent_ops is None:
                self.add("path-citation", f"cites `{key}`: {sentence}", where, "unverified",
                         None, note="no product/internal-docs/agent-ops checkout available to check the path")
                continue
            if hit is None:
                searched = ", ".join(n for n, r in roots if r)
                self.add("path-citation", f"cites `{key}` — path not found", where, "contradicted",
                         "checkout", evidence=f"not present in {searched} checkout",
                         note=sentence)
                continue
            name, path = hit
            try:
                n_lines = sum(1 for _ in path.open("rb"))
            except OSError:
                n_lines = 0
            if line > n_lines:
                self.add("path-citation", f"cites `{key}` — line beyond end of file", where,
                         "contradicted", f"{name}/{rel}",
                         evidence=f"file has {n_lines} lines", note=sentence)
            else:
                self.add("path-citation", f"cites `{key}`: {sentence}", where, "pending",
                         f"{name}/{rel}", evidence=f"file exists, {n_lines} lines",
                         note="model confirms the cited line supports the statement")

    def scan_graph_ids(self, text: str, loc: str, finding_pr: int | None) -> None:
        seen: set[str] = set()
        for m in GRAPH_ID_RE.finditer(text):
            gid = m.group(1)
            if gid in seen:
                continue
            seen.add(gid)
            where = f"{loc}L{_line_no(text, m.start())}"
            node = self.graph_nodes.get(gid)
            if node:
                self.add("graph-node", f"references graph node `{gid}`", where, "verified",
                         "graph.json", evidence=f"{gid} -> {node.get('path')}",
                         note="existence only; the model checks what the artifact says about it",
                         finding_pr=finding_pr)
            else:
                self.add("graph-node", f"references graph node `{gid}` — not in graph.json", where,
                         "unverified", "graph.json",
                         note="graph may lag an unmerged doc, or the id is invented",
                         finding_pr=finding_pr)

    def scan_versions(self, text: str, loc: str, finding_pr: int | None) -> None:
        if not self.changelog_minors:
            return
        seen: set[str] = set()
        for m in VERSION_RE.finditer(text):
            minor = m.group(1)
            if minor in seen:
                continue
            seen.add(minor)
            where = f"{loc}L{_line_no(text, m.start())}"
            tag = m.group(0)
            if minor in self.changelog_minors:
                self.add("version", f"references release `{tag}`", where, "verified",
                         "changelog.mdx", evidence=f"v{minor}.x present in changelog", finding_pr=finding_pr)
            else:
                latest = max(self.changelog_minors, key=lambda s: tuple(int(x) for x in s.split(".")))
                self.add("version", f"references `{tag}` — not in changelog: {_sentence_at(text, m.start())}",
                         where, "pending", "changelog.mdx",
                         evidence=f"latest released minor is v{latest}",
                         note="model decides: forward-looking target is fine; asserted as shipped is contradicted",
                         finding_pr=finding_pr)

    def scan_evidence_sources(self, finding: dict) -> None:
        pr = finding.get("pr_number")
        for i, ev in enumerate(finding.get("evidence") or []):
            src = str(ev.get("source", "")).strip()
            where = f"evidence[{i}]"
            if not src:
                self.add("evidence-source", "empty evidence source", where, "contradicted", None, finding_pr=pr)
                continue
            if re.match(r"^[a-z][a-z0-9+.-]*://", src, re.I):
                if ORG_URL_RE.match(src):
                    self.add("evidence-source", f"evidence URL {src}", where, "pending", src,
                             note="model fetches read-only and confirms it supports the finding", finding_pr=pr)
                else:
                    self.add("evidence-source", f"evidence URL outside {ORG}/*: {src}", where,
                             "contradicted", None,
                             note="miner rule: evidence is internal-docs paths or your-org URLs only",
                             finding_pr=pr)
                continue
            rel = src.split("#", 1)[0].lstrip("./")
            if self.internal and (self.internal / rel).is_file():
                self.add("evidence-source", f"evidence path `{src}`", where, "pending",
                         f"internal-docs/{rel}", evidence="path exists",
                         note="model confirms the doc supports the score it grounds", finding_pr=pr)
            elif self.internal:
                self.add("evidence-source", f"evidence path `{src}` — not found in internal-docs", where,
                         "contradicted", "internal-docs", evidence="path does not exist", finding_pr=pr)
            else:
                self.add("evidence-source", f"evidence path `{src}`", where, "unverified", None,
                         note="no internal-docs checkout available", finding_pr=pr)

    # -- drivers --
    def run_spec(self, text: str) -> None:
        self.scan_retired(text, "", None)
        self.scan_path_citations(text, "")
        self.scan_graph_ids(text, "", None)
        self.scan_versions(text, "", None)

    def run_release_findings(self, doc: dict) -> list[int]:
        worthy = [f for f in doc.get("findings", []) if f.get("verdict") == "market-worthy"]
        for f in worthy:
            pr = f.get("pr_number")
            text = "\n".join([
                str(f.get("pr_title", "")),
                str(f.get("summary", "")),
                *[str(e.get("note", "")) for e in (f.get("evidence") or [])],
            ])
            loc = ""   # finding_pr carries the PR; location is the line within the finding text
            self.scan_retired(text, loc, pr)
            self.scan_graph_ids(text, loc, pr)
            self.scan_versions(text, loc, pr)
            self.scan_evidence_sources(f)
        return [f.get("pr_number") for f in worthy]


def cmd_extract(args: argparse.Namespace) -> int:
    sources = Path(args.sources)
    product = Path(args.product) if args.product else None
    internal = Path(args.internal_docs) if args.internal_docs else None
    agent_ops = Path(args.agent_ops) if args.agent_ops else None
    if product and not product.is_dir():
        sys.exit(f"extract: --product {product} is not a directory")
    ex = Extractor(args.kind, sources, product, internal, agent_ops)
    artifact = Path(args.artifact)
    raw = artifact.read_text()
    scope = None
    if args.kind == "spec":
        ex.run_spec(raw)
    else:
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as e:
            sys.exit(f"extract: {artifact} is not JSON — {e}")
        scope = ex.run_release_findings(doc)

    # record checkouts in the manifest so the model reads the same paths
    ex.manifest["product_dir"] = str(product.resolve()) if product else None
    if internal:
        ex.manifest["internal_docs_dir"] = str(internal.resolve())
    if agent_ops:
        ex.manifest["agent_ops_dir"] = str(agent_ops.resolve())
    (sources / "manifest.json").write_text(json.dumps(ex.manifest, indent=2) + "\n")

    out = {
        "artifact_kind": args.kind,
        "artifact_path": str(artifact.resolve()),
        "artifact_ref": args.artifact_ref,
        "extracted_at": _now(),
        "scope_finding_prs": scope,
        "sources_manifest": ex.manifest,
        "claims": ex.claims,
    }
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    by = {}
    for c in ex.claims:
        by[c["verdict"]] = by.get(c["verdict"], 0) + 1
    print(f"extract: {len(ex.claims)} deterministic claims "
          + ", ".join(f"{k}={v}" for k, v in sorted(by.items())))
    return 0


# -------------------------------------------------------------- aggregate ---

MD_START = "<!-- claim-verify:start -->"
MD_END = "<!-- claim-verify:end -->"


def _coerce_verdict(v: object) -> str:
    return v if v in VERDICTS else "unverified"


def _material(c: dict, model_value: object = None) -> bool | None:
    """`material` is meaningful only on a contradicted claim. Only the model may
    call a contradiction immaterial, and only with an explicit JSON `false`;
    a deterministic contradiction (missing path, line past EOF, retired
    phrase) is always material."""
    if c["verdict"] != "contradicted":
        return None
    if c.get("checked_by") != "model":
        return True
    return model_value is not False


def blocks(c: dict) -> bool:
    return c["verdict"] == "contradicted" and c.get("material") is not False


def aggregate(  # noqa: C901 — pre-existing, not a lint-floor refactor
    claims_doc: dict, model: dict | None, run_url: str,
) -> dict:
    pre = {c["id"]: dict(c) for c in claims_doc.get("claims", [])}
    model_claims = (model or {}).get("claims") or []
    model_by_id = {c.get("id"): c for c in model_claims if isinstance(c, dict) and c.get("id")}

    final: list[dict] = []
    for cid, c in pre.items():
        if c["verdict"] == "pending":
            m = model_by_id.get(cid)
            if m is None:
                c["verdict"] = "unverified"
                c["checked_by"] = "deterministic"
                c["note"] = "claim-verifier did not resolve this claim"
            else:
                c["verdict"] = _coerce_verdict(m.get("verdict"))
                c["checked_by"] = "model"
                c["source"] = m.get("source") or c.get("source")
                c["evidence"] = m.get("evidence") or c.get("evidence")
                c["note"] = m.get("note") or None
                c["material"] = _material(c, m.get("material"))
        c["material"] = _material(c, c.get("material"))
        final.append(c)

    n_new = 0
    for m in model_claims:
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        if mid in pre:
            continue   # resolution of a pre-pass claim, handled above
        n_new += 1
        pr = m.get("finding_pr")
        new = {
            "id": mid if isinstance(mid, str) and mid else f"m-{n_new:02d}",
            "kind": m.get("kind") if m.get("kind") in KINDS else "other",
            "claim": str(m.get("claim") or "(unnamed claim)")[:500],
            "location": (str(m.get("location"))[:80] if m.get("location") else None),
            "verdict": _coerce_verdict(m.get("verdict")),
            "checked_by": "model",
            "source": (str(m.get("source"))[:300] if m.get("source") else None),
            "evidence": (str(m.get("evidence"))[:600] if m.get("evidence") else None),
            "note": (str(m.get("note"))[:600] if m.get("note") else None),
            "finding_pr": pr if isinstance(pr, int) else None,
        }
        new["material"] = _material(new, m.get("material"))
        final.append(new)

    if model is None:
        final.append({
            "id": "m-00", "kind": "other",
            "claim": "claim-verifier produced no verdict — prose claims were not checked",
            "location": None, "verdict": "unverified", "checked_by": "deterministic",
            "source": None, "evidence": None,
            "note": "model step errored or wrote no verdict.json; rerun or review by hand",
            "finding_pr": None,
        })

    if not final:
        final.append({
            "id": "d-00", "kind": "other", "claim": "artifact contains no verifiable claims",
            "location": None, "verdict": "verified", "checked_by": "deterministic",
            "source": None, "evidence": "n/a", "note": None, "finding_pr": None,
        })

    # strip pre-pass-only fields, normalise
    for c in final:
        for k in ("location", "source", "evidence", "note", "finding_pr", "material"):
            c.setdefault(k, None)
        c["verdict"] = _coerce_verdict(c["verdict"])
        c["material"] = _material(c, c.get("material"))

    counts = {v: sum(1 for c in final if c["verdict"] == v) for v in VERDICTS}
    if any(blocks(c) for c in final):
        overall = "contradicted"
    elif any(c["verdict"] != "verified" for c in final):
        overall = "unverified"
    else:
        overall = "verified"
    manifest = claims_doc.get("sources_manifest", {})
    sources = [
        {"name": n, "present": bool(s.get("present")), "ref": s.get("sha256")}
        for n, s in manifest.get("sources", {}).items()
    ]
    for key, label in (("internal_docs_ref", "internal-docs@"), ("docs_repo_ref", "example-app-docs@")):
        if manifest.get(key):
            sources.append({"name": label + manifest[key], "present": True, "ref": manifest[key]})
    return {
        "artifact_kind": claims_doc["artifact_kind"],
        "artifact_ref": claims_doc["artifact_ref"],
        "run_url": run_url,
        "verified_at": _now(),
        "verdict": overall,
        "counts": counts,
        "sources": sources,
        "claims": final,
    }


def render_md(final: dict) -> str:
    c = final["counts"]
    immaterial = [cl for cl in final["claims"] if cl["verdict"] == "contradicted" and not blocks(cl)]
    tail = f", {len(immaterial)} immaterial" if immaterial else ""
    head = (f"## Claim verification — **{final['verdict'].upper()}** "
            f"({c['contradicted']} contradicted{tail} · {c['unverified']} unverified · {c['verified']} verified)")
    present = [s["name"] for s in final["sources"] if s["present"] and not s["name"].endswith("@None")]
    absent = [s["name"] for s in final["sources"] if not s["present"]]
    lines = [MD_START, head, ""]
    lines.append("Checked against: " + ", ".join(f"`{n}`" for n in present) + ".")
    if absent:
        lines.append("Not available this run: " + ", ".join(f"`{n}`" for n in absent)
                     + (" (features.json is optional)." if "features.json" in absent else "."))
    lines.append("")

    def fmt(cl: dict) -> str:
        loc = f"`{cl['location']}` " if cl.get("location") else ""
        pr = f"PR #{cl['finding_pr']} · " if cl.get("finding_pr") else ""
        tail = []
        if cl.get("source"):
            tail.append(f"source: {cl['source']}")
        if cl.get("evidence"):
            tail.append(cl["evidence"])
        if cl.get("note") and cl["verdict"] != "verified":
            tail.append(cl["note"])
        t = f" — {'; '.join(tail)}" if tail else ""
        return f"- {pr}{loc}{cl['claim']}{t} _({cl['checked_by']})_"

    sections = (
        ("Contradicted — blocks approval until resolved", [cl for cl in final["claims"] if blocks(cl)]),
        ("Contradicted — immaterial, fix in a follow-up (does not block)", immaterial),
        ("Unverified — reviewer, please confirm", [cl for cl in final["claims"] if cl["verdict"] == "unverified"]),
    )
    for title, rows in sections:
        if rows:
            lines.append(f"**{title}**")
            lines.extend(fmt(cl) for cl in rows)
            lines.append("")
    ok = [cl for cl in final["claims"] if cl["verdict"] == "verified"]
    if ok:
        lines.append(f"<details><summary>Verified ({len(ok)})</summary>")
        lines.append("")
        lines.extend(fmt(cl) for cl in ok)
        lines.append("")
        lines.append("</details>")
        lines.append("")
    lines.append(f"_claim-verifier · [run]({final['run_url']})_")
    lines.append(MD_END)
    return "\n".join(lines) + "\n"


def replace_md_block(body: str, block: str) -> str:
    """Idempotent: drop a previous claim-verify block, append the new one."""
    pattern = re.compile(re.escape(MD_START) + r".*?" + re.escape(MD_END) + r"\n?", re.S)
    body = pattern.sub("", body).rstrip()
    return (body + "\n\n" if body else "") + block


def cmd_aggregate(args: argparse.Namespace) -> int:
    claims_doc = json.loads(Path(args.claims).read_text())
    model = None
    if args.model_verdict:
        p = Path(args.model_verdict)
        if p.is_file():
            try:
                model = json.loads(p.read_text())
                if not isinstance(model, dict):
                    model = None
            except json.JSONDecodeError:
                print(f"::warning::{p}: unparseable model verdict — treated as missing")
                model = None
    final = aggregate(claims_doc, model, args.run_url)
    Path(args.out).write_text(json.dumps(final, indent=2) + "\n")
    if args.md:
        Path(args.md).write_text(render_md(final))
    c = final["counts"]
    print(f"aggregate: {final['verdict'].upper()} — contradicted={c['contradicted']} "
          f"unverified={c['unverified']} verified={c['verified']}")
    return 0


def cmd_patch_body(args: argparse.Namespace) -> int:
    body = Path(args.body).read_text() if Path(args.body).is_file() else ""
    block = Path(args.md).read_text()
    Path(args.body).write_text(replace_md_block(body, block))
    return 0


# ------------------------------------------------------------------- main ---

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sources")
    s.add_argument("--internal-docs", required=True)
    s.add_argument("--docs-repo")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_sources)

    e = sub.add_parser("extract")
    e.add_argument("--kind", choices=["spec", "release-findings"], required=True)
    e.add_argument("--artifact", required=True)
    e.add_argument("--artifact-ref", required=True)
    e.add_argument("--sources", required=True)
    e.add_argument("--product")
    e.add_argument("--internal-docs")
    e.add_argument("--agent-ops")
    e.add_argument("--out", required=True)
    e.set_defaults(fn=cmd_extract)

    a = sub.add_parser("aggregate")
    a.add_argument("--claims", required=True)
    a.add_argument("--model-verdict")
    a.add_argument("--run-url", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--md")
    a.set_defaults(fn=cmd_aggregate)

    b = sub.add_parser("patch-body", help="replace/append the claim-verify block in a PR body file")
    b.add_argument("--body", required=True)
    b.add_argument("--md", required=True)
    b.set_defaults(fn=cmd_patch_body)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
