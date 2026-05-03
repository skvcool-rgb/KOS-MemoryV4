# kos-memory v5

Per-project memory + reality-sync for Claude Code. Auto-injects MEMORY.md, git state, and session history at session start so you don't have to feed context manually. Pure-stdlib, zero dependencies, local-only.

[![Tests](https://img.shields.io/badge/tests-268%2F268-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](#install-60-seconds)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#license)
[![Dependencies](https://img.shields.io/badge/deps-zero-brightgreen)](#install-60-seconds)
[![Mode](https://img.shields.io/badge/default-primary-blueviolet)](#modes)

## What it does

Every session you start in Claude Code, kos-memory does three things automatically:

1. **Reads MEMORY.md / CLAUDE.md** from up to 5 standard locations and surfaces the heading skeleton.
2. **Surveys live project state** — git branch / head / tags / last commits, dirty files, package versions, top-level tree.
3. **Cross-references chunks vs filesystem** to flag drift: claimed-but-missing, version skew, built-but-undocumented.

All of it lands in Claude's context window before you type your first prompt. If you then ask "is X built" or "what's the status of Y", a separate hook auto-runs a reality-sync verdict so Claude has filesystem + git evidence in front of it before answering.

The intent is to reduce the "Claude says we haven't built X when we shipped X last week" failure mode by injecting current ground truth automatically — not to eliminate hallucinations entirely, just to remove the most common source of them on long-running projects.

## What you see at session start

```
[kos-memory PRIMARY] Memory reconstruction (1,247 chunks, 52 sessions, last ingest: today)

## MEMORY.md anchors (operator-curated truth)
### project_memory_md (MEMORY.md, 14m ago, 256892 bytes)
  # 🚨 RESUME-HERE POINTER
  # 🌐 LANGUAGE MIGRATION ROADMAP
  ...

## Live project state (filesystem + git, surveyed now)
  branch:        main (clean)
  head:          3cd8fbe "v5.0.0 release"
  vs upstream:   origin/main (0 ahead, 0 behind)
  tags:          v5.0.0, v4.1.0, v4.0.0, ...
  last commits:
    3cd8fbe  v5.0.0 — full automation: reality-sync + native primary memory
    4ae35ec  v4.1.0 — primary mode + MEMORY.md as truth-anchor
    ede9b47  fix(installer): bake sys.executable into manifest
  versions:
    .claude-plugin/plugin.json: 5.0.0
    lib/__init__.py: 5.0.0
  tree:          .claude-plugin/, lib/ (12 .py), hooks/ (4 .py), ...

## Recent session catalog (auto-extracted)
- 2026-05-03 · 3cd8fbe [v5, reality-sync] → ...
- 2026-05-03 · 4ae35ec [primary, memory-md] → ...
- (3 more)

## Build-status reconciliation (chunks vs filesystem)
  ✓ confirmed (chunks + filesystem agree): lib/store.py, hooks/Stop.py, ...

## Drift
- (no drift; MEMORY.md aligns with chunks)

Authority order for any claim about project state:
  1. Live project state (filesystem + git) — ground truth
  2. MEMORY.md anchors — operator-curated truth
  3. User-asserted chunks (/remember) — explicit pins
  4. Auto-extracted chunks — high-recall, may be stale
```

When you ask "is the auth module built", the UserPromptSubmit hook auto-runs:

```
[reality check] 'auth module' is BUILT — confirmed by 12 chunks,
filesystem evidence, and git (commit abc123 "fix oauth flow").
  evidence: chunks=claimed_built, filesystem=confirms,
            git=committed (confidence: high)
```

Claude reads the verdict and answers based on it instead of guessing from chunks alone.

## Compared to other approaches

This is a deliberately narrow tool — local files + git + chunks, no embeddings, no daemon. Different tools serve different needs:

| Tool | Approach | How kos-memory differs |
|---|---|---|
| **Cursor / Windsurf built-in memory** | Vendor-managed, embedding-based | Local SQLite; per-project; portable JSON export; works inside Claude Code rather than as a separate IDE |
| **claude-mem** | Auto-summarization, chunked recall | Adds reality-sync layer (git + filesystem cross-reference), treats MEMORY.md as authority, surfaces context proactively at session start |
| **mem0 / supermemory** | Embedding store + LLM extraction | Pure-stdlib BM25 — no embedding model, no inference cost, no external service to depend on |
| **OpenAI ChatGPT memory** | Server-side, opaque, single-app | Local-only, multi-project, you can read/edit the SQLite directly |
| **Manual MEMORY.md / CLAUDE.md** | You write it, Claude Code loads it | kos-memory still reads these files (treats them as authority); adds auto-extracted session history + git survey on top |

Pick kos-memory if you want: local-first, auditable, per-project isolation, no ML inference cost, and explicit operator control via MEMORY.md. Pick something else if you want: cross-app memory, semantic clustering, or vendor-managed convenience.

## Install (60 seconds)

**Requirements:** Python 3.9+ and Claude Code. Nothing else.

```bash
git clone https://github.com/skvcool-rgb/KOS-MemoryV4.git
cd KOS-MemoryV4
python scripts/install.py            # use python3 on Mac/Linux if python isn't on PATH
```

Restart Claude Code. In any project, type `/memory-status` to verify the install.

The installer:
1. Detects which Python interpreter you used and bakes its absolute path into the plugin manifest.
2. Registers the plugin and MCP server in `~/.claude/settings.json` (atomic write, with backup of any existing file).
3. Runs a smoke test (creates a temp `.kos-memory/`, ingests a chunk, recalls it).

Re-run `python scripts/install.py` any time — it's idempotent.

**Uninstall:** delete the `kos-memory` entries from `~/.claude/settings.json`. Per-project data lives in each project's `.kos-memory/` directory; delete the directory to wipe history.

## How it works under the hood

**Capture** (silent, automatic):
- `Stop` hook ingests transcripts at end of every session.
- `PreCompact` hook (auto-only) saves state before auto-compaction. Manual `/compact` is intentionally not intercepted — that's user-initiated compression.

**Inject at session start** (primary mode default):
- `SessionStart` hook emits the reconstruction block above. Includes MEMORY.md anchors, live git/filesystem state, recent session catalog, build-status reconciliation, drift warnings, and an authority-order instruction. Bounded at ~16 KB.

**Inject on user prompt** (primary mode):
- Past-tense triggers ("where did we leave off") → auto-runs Stage 0+1+2 of recall, emits passages inline.
- Present-tense build-status triggers ("is X built", "what's the status of Y", "did we ship Z") → auto-runs reality-sync verdict and emits it inline.

**Manual surfaces** (rarely needed in v5; available for power-users):
- `/recall <query>` — full 4-stage pipeline.
- `recall_project_memory` MCP tool — Claude self-invokes when needed (5/session, 50/day, $0.50/day caps).
- `/remember <fact>` — pin a user-asserted chunk.
- `/memory-mode primary|backup` — toggle modes.
- `/memory-status`, `/memory-export`, `/memory-import` — admin operations.

**Storage** (local SQLite, zero processes between sessions):
- `.kos-memory/chunks.db` per project.
- `~/.config/kos-memory/user/` for cross-project pins (opt-in only).
- BM25 + synonym cache + per-chunk `asserted_by_user` and `contradicted_by_later_session` flags.

## MEMORY.md as truth-anchor

The reconstruction layer treats `MEMORY.md` (and `CLAUDE.md`) as operator-curated authority. Search order — first match wins for each kind:

1. `<project>/MEMORY.md`
2. `<project>/.claude/MEMORY.md`
3. `<project>/CLAUDE.md`
4. `~/.claude/projects/<encoded>/memory/MEMORY.md` (Claude Code auto-memory location)
5. `~/.claude/CLAUDE.md` (user-global)

Drift detection: if MEMORY.md is 12+ hours older than the most recent chunk AND ≥5 chunks have been ingested since, you'll see a warning at session start. If MEMORY.md is missing entirely while the store has data, you get a nudge to create one.

Conflict resolution: live state > MEMORY.md > user-asserted chunks > auto-extracted chunks. Documented in the SessionStart "Authority order" block so Claude follows it.

## Modes

| Mode | SessionStart | UserPromptSubmit (trigger) | Default |
|---|---|---|---|
| **primary** | Catalog + MEMORY.md + Live state + Reconciliation | Auto-runs Stage 0+1+2 OR build-status verdict inline | ✓ v5.0+ |
| **backup** | 1-line marker only | 1-line hint only | v4.0 legacy |

Switch modes:

```bash
/memory-mode backup        # for this project
/memory-mode primary       # back to default
/memory-mode --user backup # for the user-level cross-project store
```

Or set `KOS_MEMORY_MODE=backup` in your shell env (highest priority — overrides config files).

## Architecture

```
.kos-memory/                    (per project, in cwd)
├── chunks.db                   SQLite WAL, all chunks + sessions
├── catalog.json                hierarchical session catalog
├── synonyms.json               LRU-bounded query expansion cache
├── budget.json                 daily/session throttle state
├── ingest_log.jsonl            WAL — appended before SQLite write
├── survey_cache.json           60s-TTL cache of git/tree/version survey
├── config.json                 mode override (primary|backup)
└── last_ingest_marker          plain text Unix ts

~/.config/kos-memory/user/      (cross-project user store, opt-in)
└── (same structure)
```

### Recall pipeline

```
Stage 0: Query expansion           local synonym cache, ~free
Stage 1: Catalog scan              SQLite read
Stage 2: Targeted grep             SQLite + Python regex, ~50ms
Stage 3: Synthesis                 Claude does this when invoked
```

### Repository layout

```
kos-memory/
├── .claude-plugin/plugin.json   plugin manifest (hooks + MCP server registration)
├── lib/
│   ├── paths.py                 cross-platform path resolution + mode config
│   ├── store.py                 SQLite schema + CRUD
│   ├── chunker.py               prose+code splitter, file-ref extractor
│   ├── search.py                BM25, synonyms, grep
│   ├── budget.py                daily/session throttle
│   ├── catalog.py               recent/mid/archive view
│   ├── recall.py                4-stage pipeline orchestrator
│   ├── memory_md.py             MEMORY.md / CLAUDE.md detection + parsing
│   ├── codebase_survey.py       git + tree + version + test-cache survey
│   ├── reality_sync.py          chunks ↔ filesystem cross-reference
│   └── stdio_utf8.py            Windows cp1252 fix for hook stdout
├── hooks/
│   ├── SessionStart.py          memory reconstruction at session start
│   ├── Stop.py                  WAL-first ingest at end of session
│   ├── PreCompact.py            WAL-first ingest before auto-compact
│   └── UserPromptSubmit.py      regex triggers + auto-recall + auto-build-status
├── commands/
│   ├── recall.md                /recall slash command
│   ├── remember.md              /remember slash command
│   ├── memory-status.md         /memory-status slash command
│   ├── memory-mode.md           /memory-mode slash command (toggle modes)
│   ├── memory-export.md         /memory-export slash command
│   └── memory-import.md         /memory-import slash command
├── mcp/
│   ├── cli.py                   subcommand entry point for slash commands
│   └── server.py                JSON-RPC stdio MCP server
├── skills/memory-recovery/SKILL.md     contract telling Claude how to use the preamble
├── scripts/install.py           registers plugin in ~/.claude/settings.json
├── tests/                       14 test files, 268 tests
├── README.md                    this file
├── DEPLOYMENT.md                operator install + ops guide
└── HANDOVER.md                  build-time notes
```

## Throttling

Throttles only apply to the explicit recall surfaces. Auto-injection at SessionStart and inline build-status verdicts on UserPromptSubmit are not throttled.

| Surface | Per-session cap | Daily cap |
|---|---|---|
| `recall_project_memory` (MCP) | 5 | 50 calls / 50K tokens / $0.50 |
| `/recall` (slash) | none | 50 calls / 50K tokens / $0.50 |
| `remember_fact` (MCP) | none | none |
| `/remember` (slash) | none | none |
| SessionStart hook | runs every session start, no throttle |
| UserPromptSubmit auto-recall / build-status | no per-call cap, but counts against the daily token budget |

State at `.kos-memory/budget.json`. Resets daily UTC.

## Privacy

- All data stays local. No network calls from any hook or library code.
- The MCP server runs on stdio under Claude Code; no listening sockets.
- Secrets guard: `/remember` and `remember_fact` refuse content matching API-key/password/token patterns under 200 chars.
- The codebase survey runs `git` subcommands as subprocesses (read-only) — no remote calls.
- To wipe a project's memory: delete `.kos-memory/`. To wipe user-level: delete `~/.config/kos-memory/user/`.

## Limitations

Honest list of things this tool does NOT do:

- **No inference.** No embeddings, no LLM calls inside the plugin. Recall ranking is BM25 + grep — surprisingly effective for project history but not "semantic" the way embedding stores are.
- **Claude-Code-only.** If you also use Cursor, ChatGPT, etc., they each have their own (or no) memory. No cross-tool standardization.
- **Doesn't auto-update MEMORY.md.** That stays operator-curated. The plugin reads it, doesn't write it.
- **Doesn't survey deeply nested filesystem.** Tree summary is 3 levels deep, ~60 entries — enough for top-level reconciliation, not a full project index.
- **Doesn't run tests.** Reads cached pytest artifacts if they exist, but doesn't invoke tests itself.
- **Single-machine.** No cross-machine sync. Use `/memory-export` + `/memory-import` for manual portability.
- **Token cost.** Primary mode adds ~500-1500 tokens to every session start. Across 50 sessions/month that's ~25-75K tokens of memory-injection overhead. Cheap but not free; switch to `backup` mode if it bothers you.
- **First-session bootstrap.** On a fresh project with no chunks and no MEMORY.md, the SessionStart preamble is empty. Memory accrues over a few sessions before reconciliation has signal.

## Testing

```bash
python -m unittest discover tests    # 268 tests, ~40 seconds
```

Tests cover: store schema migration, chunker boundary cases (1MB inputs and unicode), BM25 epsilon-floor for tiny corpora, BOM-encoded settings.json, schema-mismatch refusal, hook subprocess invocation in both modes, MCP JSON-RPC handshake + throttling, MEMORY.md detection across all 5 search locations, drift detection thresholds, mode resolution priority, fresh-clone install end-to-end, real-document ingest+recall on a 19 KB .docx (69 chunks → 16 ms recall), codebase survey on real git repos, reality_sync reconciliation classification, build-status verdict generation across confidence levels, trigger ordering (past-tense recall vs present-tense build-status), and SessionStart v5 output integration.

## Migration

**From v3 (the daemon-based release):**
1. Stop any v3 daemon (`pkill -f kos-memory-daemon` or kill the PyInstaller exe).
2. v3 stored data in `~/.kos-memory/`. v5 uses `<project>/.kos-memory/` and `~/.config/kos-memory/user/` — separate paths, no collision.
3. If v3 has extractable data, use v3's CLI to export to JSON, then `/memory-import <path>` per-project.
4. v5 will not touch `~/.kos-memory/` — safe to delete after migration.

**From v4.0 / v4.1:**
- No schema changes. Just `git pull && python scripts/install.py`.
- v4.0 default behavior (1-line marker only) is preserved as `/memory-mode backup`.
- v5 default flips to primary mode automatically; switch back if you preferred the old behavior.

## License

MIT.

## Repository

- Code: https://github.com/skvcool-rgb/KOS-MemoryV4
- Issues / discussions: same repo, Issues tab

**Suggested GitHub topic tags** (set on the repo's About panel):

```
claude-code  claude-plugin  mcp  mcp-server  memory  context-management
local-first  python  sqlite  bm25  developer-tools  ai-tools
```
