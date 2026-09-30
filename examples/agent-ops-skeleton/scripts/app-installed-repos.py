#!/usr/bin/env python3
"""Which repos is the example-app-bot App installed on, with which permissions?

Nothing about an App installation is visible to a user token; the only way to
know is to mint an App JWT and ask /repos/{owner}/{repo}/installation. Two
callers share this:

  install-preflight.yml   --strict: exit 1 when any repo is uninstalled or
                          under-scoped (diagnostic, run after installs)
  dependabot-triage.yml   default: never fails; writes `installed=` and
                          `missing=` to $GITHUB_OUTPUT so the job mints its
                          token for the installed subset only (fail closed
                          per repo, not per run)

Repo list = union of --impl-repos, --policy (its `repos` keys) and --repos,
in that order. --needed is perm:level pairs; `read` is satisfied by write.
Requires PyJWT with crypto (pip install "pyjwt[crypto]").
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "<YOUR_ORG>"


def mint_jwt(client_id: str, key: str) -> str:
    import jwt  # PyJWT

    now = int(time.time())
    return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": client_id}, key, algorithm="RS256")


def api(token: str, path: str):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None


def collect_repos(a) -> list[str]:
    repos: list[str] = []

    def add(r: str):
        r = r.strip()
        if r and r not in repos:
            repos.append(r)

    if a.impl_repos:
        for r in json.loads(Path(a.impl_repos).read_text())["repos"]:
            add(r)
    if a.policy:
        for r in json.loads(Path(a.policy).read_text())["repos"]:
            add(r)
    for r in (a.repos or "").split(","):
        add(r)
    return repos


def main(argv=None) -> int:  # noqa: C901 — pre-existing, not a lint-floor refactor
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--impl-repos", help="state/impl-repos.json")
    ap.add_argument("--policy", help="state/dependabot-repos.json")
    ap.add_argument("--repos", help="extra comma-separated short names")
    ap.add_argument("--needed", default="contents:write,pull_requests:write,issues:write",
                    help="perm:level pairs the caller will mint")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any uninstalled/under-scoped repo")
    ap.add_argument("--github-output", action="store_true", help="write installed=/missing= to $GITHUB_OUTPUT")
    ap.add_argument("--title", default="example-app-bot install check")
    a = ap.parse_args(argv)

    client_id = os.environ.get("CLIENT_ID") or os.environ.get("BOT_APP_CLIENT_ID") or ""
    key = os.environ.get("PRIVATE_KEY") or os.environ.get("BOT_APP_PRIVATE_KEY") or ""
    if not client_id or not key:
        sys.exit("BOT_APP_CLIENT_ID / BOT_APP_PRIVATE_KEY not set (SETUP.md §2)")
    needed = dict(p.split(":", 1) for p in a.needed.split(",") if p.strip())
    repos = collect_repos(a)
    if not repos:
        sys.exit("no repos to check — pass --impl-repos, --policy or --repos")

    token = mint_jwt(client_id, key)
    rows, missing, underscoped, installed = [], [], [], []
    app_perms: dict = {}
    for repo in repos:
        status, body = api(token, f"/repos/{OWNER}/{repo}/installation")
        if status == 200:
            perms = (body or {}).get("permissions", {})
            app_perms = app_perms or perms
            short, ok = [], True
            for p, want in needed.items():
                got = perms.get(p, "none")
                short.append(f"{p}:{got}")
                if (want == "write" and got != "write") or (want == "read" and got not in ("read", "write")):
                    underscoped.append(f"{repo} — {p} is `{got}`, needs `{want}`")
                    ok = False
            rows.append((repo, "installed" if ok else "under-scoped", ", ".join(short)))
            if ok:
                installed.append(repo)
        elif status == 404:
            rows.append((repo, "NOT INSTALLED", "—"))
            missing.append(repo)
        else:
            rows.append((repo, f"error HTTP {status}", "—"))
            missing.append(repo)

    width = max(len(r[0]) for r in rows)
    for repo, state, perms in rows:
        print(f"{repo.ljust(width)}  {state.ljust(14)}  {perms}")

    summary = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    with summary.open("a") as f:
        f.write(f"### {a.title}\n\n| Repo | State | Permissions |\n|---|---|---|\n")
        for repo, state, perms in rows:
            mark = "✅" if state == "installed" else "❌"
            f.write(f"| `{repo}` | {mark} {state} | {perms} |\n")
        if underscoped:
            f.write("\n**Installed but under-scoped**\n\n" + "".join(f"- {u}\n" for u in underscoped))
        if missing:
            f.write("\nInstall at: https://github.com/organizations/<YOUR_ORG>/settings/installations\n")

    if a.github_output:
        with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
            f.write(f"installed={','.join(installed)}\n")
            f.write(f"missing={','.join(missing + [u.split(' — ')[0] for u in underscoped])}\n")
            # Installation permissions are App-wide; callers use this to decide
            # whether they may request permission-checks at mint time.
            f.write(f"checks={app_perms.get('checks', 'none')}\n")

    if missing:
        print("\nNot installed: " + ", ".join(missing))
    for u in underscoped:
        print(f"Under-scoped: {u}")
    if a.strict and (missing or underscoped):
        return 1
    print(f"\n{len(installed)}/{len(rows)} repos installed with the needed permissions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
