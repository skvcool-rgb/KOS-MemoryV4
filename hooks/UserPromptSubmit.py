#!/usr/bin/env python
"""UserPromptSubmit hook — detect natural-language recall triggers.

Pure regex. Sub-2ms. NO LLM. NO state mutations.

If the user's message matches a recall trigger pattern, prints a
single-line marker telling Claude that the user is implicitly asking
for memory recall. Claude then decides whether to invoke the
recall_project_memory MCP tool.

Trigger discipline: max 1 implicit recall per session (Claude itself
should decide when to actually call the tool — this hook just signals).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

try:
    from lib.stdio_utf8 import force_utf8_io
    force_utf8_io()
except Exception:
    pass

# Patterns indicating user wants past context
TRIGGER_PATTERNS = [
    r"\b(check|look at|recall|find|remember)\b.*\b(past|last|previous|earlier)\b",
    r"\bwhat did (we|i) (discuss|decide|do|build|ship|fix)\b",
    r"\b(left off|leave off|leaving off|where we (were|stopped|left))\b",
    r"\bas (we|i) (discussed|mentioned|said)\b",
    r"\bthe (project|spec|design|thing|feature) we (built|made|worked on)\b",
    r"\b(remember|recall) (when|that|the time)\b",
    r"\bsince (yesterday|last (week|session|time))\b",
    r"\b/recall|\b/recover|\b/check[- ]history\b",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in TRIGGER_PATTERNS]


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)

    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    if not isinstance(prompt, str) or not prompt:
        sys.exit(0)

    matched = None
    for pat in COMPILED:
        m = pat.search(prompt)
        if m:
            matched = m.group(0)
            break

    if not matched:
        sys.exit(0)

    # Detect explicit slash commands separately — they go through commands/, not via this hook
    if prompt.lstrip().startswith("/"):
        sys.exit(0)

    print(
        f"[kos-memory hint] User prompt matched recall pattern "
        f"(\"{matched[:60]}\"). Consider calling the "
        f"recall_project_memory MCP tool if you sense missing context."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
