# Pipeline agents

One directory per pipeline node, each containing a `CLAUDE.md` prompt. Workflows invoke nodes as:

```bash
claude -p "$(cat agents/<name>/CLAUDE.md)" \
  --allowedTools "<explicit whitelist>" \
  --max-turns <cap>
```

Every node is a separate `claude -p` process with a scoped context load — reviewers and judges never see an implementer transcript.

Planned nodes by phase:

| Node | Phase | Model |
|---|---|---|
| `spec-drafter` | 2 | sonnet |
| `implementer` | 2 | sonnet |
| `pr-reviewer` (fresh-context, runs `pr-review` + `founder-voice-pr-reviewer`) | 2 | opus for founder-voice-pr-reviewer |
| `code-judge` | 3 | opus |
| `dream-orchestrator` (+ 3 miner subagents) | 4 | sonnet |
