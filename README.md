# kos-memory v4

**Per-project primary memory for Claude Code. MEMORY.md as truth-anchor, auto-recall on triggers, zero dependencies.**

[![Tests](https://img.shields.io/badge/tests-229%2F229-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](#requirements)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#license)
[![Dependencies](https://img.shields.io/badge/deps-zero-brightgreen)](#requirements)
[![Mode](https://img.shields.io/badge/default-primary-blueviolet)](#modes)

When you start a Claude Code session, kos-memory automatically injects this:

```
[kos-memory PRIMARY] Memory reconstruction (1,247 chunks, 52 sessions, last ingest: today)

## MEMORY.md anchors (operator-curated truth)
### project_memory_md (MEMORY.md, 14m ago, 256892 bytes)
  # 🌐 LANGUAGE MIGRATION ROADMAP
  # 🚨 RESUME-HERE POINTER
  # ⚠️ FEEDBACK NOTES
  ...

## Recent session catalog (auto-extracted)
- 2026-05-03 · a3f2b1c0 [auth, refactor] → fix oauth flow ...
- 2026-05-02 · 9e1d8c44 [bugfix] → race condition in cache ...
- (3 more)

## Drift
- (no drift detected — MEMORY.md aligns with chunks)
```

When you ask "where did we leave off", kos-memory auto-runs Stage 0+1+2 of the recall pipeline and emits the actual passages inline — no waiting for Claude to invoke a tool.

## Install (60 seconds)

**Requirements:** Python 3.9+ and Claude Code. Nothing else.

```bash
git clone https://github.com/skvcool-rgb/KOS-MemoryV4.git
cd KOS-MemoryV4
python scripts/install.py            # use python3 on Mac/Linux if needed
```

That's it. Restart Claude Code, then in any project type `/memory-status`. The installer:

1. Detects which Python interpreter you used and bakes its absolute path into the plugin manifest (no `python` vs `python3` PATH hassles).
2. Registers the plugin and MCP server in `~/.claude/settings.json` (atomic write, with backup).
3. Runs a smoke test: creates a temp `.kos-memory/`, ingests a chunk, recalls it.

Re-run `python scripts/install.py` any time — it's idempotent.

**Uninstall:** delete the `kos-memory` entries from `~/.claude/settings.json`. Per-project data lives in each project's `.kos-memory/` directory (delete to wipe).

## What it does

**Capture** (silent, automatic):
- `Stop` hook — ingests transcript at end of every session.
- `PreCompact` hook (auto only, never manual `/compact`) — saves state before auto-compaction.

**Inject** (primary mode default — what makes it "primary"):
- `SessionStart` hook — emits **memory reconstruction**: rendered Stage-1 catalog of recent sessions + MEMORY.md heading skeleton + drift warnings. Bounded at ~2 KB.
- `UserPromptSubmit` hook on trigger phrases ("where we left off", "as we discussed", etc.) — auto-runs Stage 0+1+2 and emits top passages **inline** (no tool round-trip).

**Recall** (explicit, on demand):
- `/recall <query>` — full 4-stage pipeline with synthesis prompt.
- `recall_project_memory` MCP tool — Claude self-invokes when it senses missing context (5/session, 50/day, $0.50/day caps).
- `/remember <fact>` — pin a user-asserted chunk (weighted higher in recall ranking).

**Indexing** (local SQLite, zero processes between sessions):
- `.kos-memory/chunks.db` per project (or `~/.config/kos-memory/user/` for cross-project pins).
- BM25 + tiny synonym cache + per-chunk `asserted_by_user` and `contradicted_by_later_session` flags.

## MEMORY.md as truth-anchor

kos-memory treats `MEMORY.md` (and `CLAUDE.md`) as **operator-curated authoritative truth**. The reconstruction layer cross-references it on every session start:

**Search order** (first match wins for each kind):
1. `<project>/MEMORY.md`
2. `<project>/.claude/MEMORY.md`
3. `<project>/CLAUDE.md`
4. `~/.claude/projects/<encoded>/memory/MEMORY.md` ← Claude Code auto-memory
5. `~/.claude/CLAUDE.md` ← user-global

**Drift detection:** if MEMORY.md is 12+ hours older than the most recent chunk AND ≥5 chunks have been ingested since, you'll see a warning at session start. If MEMORY.md is missing entirely while the store has data, you get a friendly nudge to create one.

**Conflict resolution:** during recall synthesis, MEMORY.md anchors win over auto-extracted chunks. User-asserted chunks (`/remember`) win over auto-extracted. Most-recent wins among auto-extracted unless explicitly contradicted.

## Modes

| Mode | SessionStart | UserPromptSubmit (trigger) | Default? |
|---|---|---|---|
| **primary** | Catalog + MEMORY.md + drift inline | Auto-runs Stage 0+1+2 inline | ✓ v4.1+ |
| **backup** | 1-line marker only | 1-line hint only | v4.0 legacy |

Switch modes:

```bash
/memory-mode backup        # for this project
/memory-mode primary       # back to default
/memory-mode --user backup # for the user-level cross-project store
```

Or set `KOS_MEMORY_MODE=backup` in your shell env (highest priority — overrides config files).

## Testing

```bash
python -m unittest discover tests    # 229 tests, ~30 seconds
```

Tests cover: store schema migration, chunker boundary cases (incl. 1MB inputs and unicode), BM25 epsilon-floor for tiny corpora, BOM-encoded settings.json, schema-mismatch refusal, hook subprocess invocation in both modes, MCP JSON-RPC handshake + throttling, MEMORY.md detection across all 5 search locations, drift detection thresholds, mode resolution priority, fresh-clone install end-to-end, real-document ingest+recall on a 19 KB .docx (69 chunks → 16 ms recall).

## Quick use

After install, restart Claude Code in any project, then:

```
> /recall what did we decide about the auth module?
```

Or just talk normally — the `[kos-memory hint]` line will nudge Claude to recall when it spots a trigger phrase.

To pin a fact you don't want to lose:

```
> /remember The team chose Postgres over MySQL because of JSONB indexing.
```

To inspect the store:

```
> /memory-status
```

## Architecture

```
.kos-memory/                    (per project, in cwd)
├── chunks.db                   SQLite WAL, all chunks + sessions
├── catalog.json                hierarchical session catalog
├── synonyms.json               LRU-bounded query expansion cache
├── budget.json                 daily/session throttle state
├── ingest_log.jsonl            WAL — appended before SQLite write
└── last_ingest_marker          plain text Unix ts

~/.config/kos-memory/user/      (cross-project user store, optional)
└── (same structure)
```

### The 4-stage recall pipeline

```
Stage 0: Query expansion           local synonym cache, ~free
Stage 1: Catalog scan              SQLite read, hand to Claude
Stage 2: Targeted grep             SQLite + Python regex, ~50ms
Stage 3: Synthesis                 Claude does this, ~$0.01
```

Stages 0 and 3 *can* be LLM-augmented (caller's choice). Stage 0 falls back to local synonyms; Stage 3 falls back to raw passage display.

### The 4 ingest triggers

| Trigger | When | Mechanism |
|---|---|---|
| A: explicit | User types `/recall` or matching natural language | Slash command + UserPromptSubmit hint |
| B: heuristic | UserPromptSubmit regex matches one of 8 patterns | UserPromptSubmit.py → hint line |
| C: PreCompact | Claude Code is about to auto-compact context | PreCompact.py with matcher: "auto" |
| D: self-invoke | Claude decides via skill judgment | recall_project_memory MCP tool |

Stop hook fires on every session end, regardless of trigger. PreCompact fires only on auto (not /compact, which is user-intended compression).

### Two-boolean chunk model

Instead of a float `confidence`, every chunk has:
- `asserted_by_user: bool` — pinned via `/remember` or marked in `lib/store.py`
- `contradicted_by_later_session: bool` — set lazily during recall when synthesis detects supersession

Conflict resolution: prefer the most recent unless explicitly contradicted by even-newer. User-asserted outweighs auto-extracted.

## File layout

```
kos-memory-v4/
├── .claude-plugin/
│   └── plugin.json              # registers hooks + MCP server
├── lib/
│   ├── paths.py                 # cross-platform path resolution
│   ├── store.py                 # SQLite schema + CRUD
│   ├── chunker.py               # prose+code splitter, file-ref extractor
│   ├── search.py                # BM25, synonyms, grep
│   ├── budget.py                # daily/session throttle
│   ├── catalog.py               # hierarchical recent/mid/archive view
│   └── recall.py                # 4-stage pipeline orchestrator
├── hooks/
│   ├── SessionStart.py          # backup-availability marker
│   ├── Stop.py                  # WAL-first ingest at end of session
│   ├── PreCompact.py            # WAL-first ingest before auto-compact
│   └── UserPromptSubmit.py      # regex trigger detection
├── commands/
│   ├── recall.md                # /recall slash command
│   ├── remember.md              # /remember slash command
│   ├── memory-status.md         # /memory-status slash command
│   ├── memory-export.md         # /memory-export slash command
│   └── memory-import.md         # /memory-import slash command
├── mcp/
│   ├── cli.py                   # subcommand entry point for slash commands
│   └── server.py                # JSON-RPC stdio MCP server
├── skills/
│   └── memory-recovery/SKILL.md # tells Claude when/how to recall
├── scripts/
│   └── install.py               # registers plugin in ~/.claude/settings.json
├── tests/
│   └── (unit + integration tests)
├── README.md                    (this file)
├── DEPLOYMENT.md                (operator install + ops guide)
└── HANDOVER.md                  (build-time handover doc)
```

## Throttling

| Surface | Per-session cap | Daily cap |
|---|---|---|
| `recall_project_memory` (MCP) | 5 | 50 calls / 50k tokens / $0.50 |
| `/recall` (slash) | none | 50 calls / 50k tokens / $0.50 |
| `remember_fact` (MCP) | none | none |
| `/remember` (slash) | none | none |

State at `.kos-memory/budget.json`. Resets daily UTC.

## Privacy

- All data stays local — no network calls from any hook or library code.
- The MCP server runs only on stdio under Claude Code; no listening sockets.
- Secrets guard: `/remember` and `remember_fact` refuse content matching API-key/password/token patterns under 200 chars.
- To wipe a project's memory: delete `.kos-memory/`. To wipe user-level: delete `~/.config/kos-memory/user/`.

## Migration from v3

v3 had a daemon. v4 has none. Migration steps:

1. Stop any v3 daemon (`pkill -f kos-memory-daemon` or kill the PyInstaller exe).
2. v3 stored data in `~/.kos-memory/` (project-level was buggy, mostly empty).
3. v4 stores per-project at `<project>/.kos-memory/` and user-level at `~/.config/kos-memory/user/`.
4. If v3 had any extractable data, use v3's CLI to export to JSON, then `/memory-import <path>` in any project.
5. v4 will not touch `~/.kos-memory/` — safe to delete after migration.

## Why v4

v3 broke chat history, daemon died silently, no recovery, 700 MB RAM, killed by accidental Python process cleanup, never saved data across 4 projects. v4 axes the daemon entirely. Claude is the intelligence; the plugin is dumb storage.

## License

MIT.

## Repo

https://github.com/skvcool-rgb/KOS-MemoryV4
