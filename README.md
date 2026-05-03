# kos-memory v4

**Per-project, hybrid-retrieval memory backup for Claude Code. Pure-stdlib, zero dependencies. Backup mode — never primary.**

```
[kos-memory BACKUP] 1,247 chunks, 52 sessions for this project
                    (last ingest: today). Use /recall when current
                    context is missing past detail.
```

## What it does

- **Captures** session transcripts at end-of-session (`Stop` hook) and before auto-compact (`PreCompact` hook).
- **Indexes** them locally in SQLite (`.kos-memory/chunks.db`) — no daemon, no server, no ML.
- **Surfaces** them on demand via:
  - `/recall <query>` — explicit user-driven recovery
  - `recall_project_memory` MCP tool — Claude self-invokes when it senses missing context
  - `[kos-memory hint]` line on natural-language triggers like "where did we leave off"

## What it does NOT do

- It does **not** inject memory into every prompt. It's a backup, not primary context.
- It does **not** run a background daemon. v3 daemon lost data and was killed; v4 has zero processes between sessions.
- It does **not** use ML or embeddings. BM25 + grep + a tiny synonym cache.
- It does **not** auto-recall. You or Claude has to explicitly request it.

## Quick install

```bash
# Clone or download this repo, then:
python scripts/install.py

# Or, if Claude Code's plugin marketplace is configured:
# (manual instructions in DEPLOYMENT.md)
```

The installer:
1. Registers the plugin in `~/.claude/settings.json` (`mcpServers` and `plugins` blocks).
2. Verifies Python 3.9+ is available.
3. Runs a smoke test (creates a temp `.kos-memory/`, inserts a chunk, recalls it).

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

https://github.com/skvcool-rgb/KOS-Memory
