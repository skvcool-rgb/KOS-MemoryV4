---
name: memory-recovery
description: Decide when and how to use kos-memory backup recall. Use this skill when the user references prior context, asks about past decisions, or the current chat feels like it's missing history that another session would have had.
---

# memory-recovery — when to use the kos-memory backup

This skill teaches you when (and just as importantly, when *not*) to invoke `recall_project_memory` and the `/recall` slash command.

## Mental model

kos-memory is a **backup**, not a primary context source. The current chat already has:
- The user's message
- Files in the workspace (read them with `Read`)
- The conversation so far

kos-memory adds:
- Snippets from prior sessions on this project
- User-pinned facts (`/remember` → `asserted_by_user=true`)
- Auto-extracted summaries from Stop and PreCompact hooks

You should only reach for the backup when the current sources are **insufficient**.

## When to invoke

**STRONG signals — invoke without hesitation:**

1. The user says one of:
   - "what did we decide about X"
   - "where did we leave off"
   - "as we discussed earlier"
   - "remember the thing we built last week"
   - "/recall ..." (explicit slash command)

2. SessionStart hook printed `[kos-memory BACKUP]` and the user references something the current chat doesn't cover.

3. UserPromptSubmit hook printed `[kos-memory hint]` with a matched pattern AND the current context can't answer the question.

4. The user mentions a file/decision/feature you've never seen in this session AND the project clearly has more history (the SessionStart line said "N chunks, M sessions").

**WEAK signals — pause and think first:**

- The user asks an open-ended question that *could* benefit from history but doesn't reference it.
- You're stuck on a problem and want to know if a past session solved it.

For weak signals, prefer `Read` on workspace files first. Only fall back to `recall_project_memory` if the workspace doesn't have the answer.

**DO NOT invoke when:**

- The user just opened a file and is asking what it does — read the file.
- The current message is self-contained (e.g. "write a sort function").
- The throttle is exhausted (5/session, 50/day, $0.50/day) — tell the user, don't keep trying.
- The store is empty (`SessionStart` printed nothing) — there's nothing to recall yet.
- The query would just summarize the current chat — wait for the Stop hook.

## How to invoke

### Path A — explicit `/recall` (user-driven)

The user types `/recall <query>`. The slash command runs Stage 0+1 via the CLI helper, hands you the catalog, you pick sessions, then Stage 2 + Stage 3 synthesis. Follow the steps in `commands/recall.md`.

### Path B — implicit `recall_project_memory` MCP tool (you-driven)

You decide a recall is needed mid-conversation. Call the tool:

```json
{
  "name": "recall_project_memory",
  "arguments": {
    "query": "auth refactor decisions",
    "window_days": 30,
    "user": false
  }
}
```

The tool returns:
- A catalog block (Stage 1)
- Selected passages (Stage 2 — already filtered)
- Synthesis instructions

You then produce sections (a)–(e) in your reply. **Always** cite source dates (`[2026-04-15]`).

## Synthesis rules (Stage 3)

- DO NOT reproduce raw passage text. Synthesize.
- Use **exactly** these sections:
  - **(a) NEW ITEMS** — bullets, with source date
  - **(b) POTENTIALLY STALE** — what current context believes that past content updated
  - **(c) SUGGESTED UPDATED STATE** — concise integrated paragraph
  - **(d) UNCERTAINTY** — what's ambiguous; ask the user
  - **(e) CONTRADICTIONS DETECTED** — `superseded_chunk_ids: [...]` (empty if none)
- Conflict resolution: prefer the most recent unless explicitly contradicted by even-newer.
- User-asserted (`asserted_by_user=true`) outweighs auto-extracted, all else equal.
- If section (e) is non-empty, the slash command will writeback via `mark_contradicted`. The MCP tool path doesn't auto-writeback — mention this to the user and they can run `/recall` to commit.

## Throttle awareness

| Path | Cap |
|---|---|
| `recall_project_memory` MCP tool | 5/session, 50/day, $0.50/day |
| `/recall` slash command | 50/day, $0.50/day (no per-session cap) |
| `remember_fact` MCP tool | none (cheap, write-only) |
| `/remember` slash command | none |

If a recall is throttled, tell the user the limit and suggest `/recall` (which has the higher cap).

## Hook signals you'll see

- `[kos-memory BACKUP] N chunks, M sessions for this project (last ingest: today). Use /recall when current context is missing past detail.` → from SessionStart, treat as background info.
- `[kos-memory hint] User prompt matched recall pattern ("..."). Consider calling the recall_project_memory MCP tool if you sense missing context.` → from UserPromptSubmit, this is a *suggestion* not an order. Decide based on whether you actually need history.

## What this skill does NOT cover

- How to seed the store. That happens automatically via Stop and PreCompact hooks. Users can also run `/remember <fact>`.
- How to migrate stores between machines. See `commands/memory-export.md` and `commands/memory-import.md`.
- Cross-project recall. Add `--user` (slash command) or `user: true` (MCP tool).
