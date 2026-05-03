#!/usr/bin/env python
"""SessionStart hook — backup mode availability marker.

Pure stdlib. SQLite read only. NO LLM calls. <50 ms typical.

Prints exactly one line if memory exists for this project, otherwise
exits silently. Claude reads the line, knows the backup is available,
and can fall back to /recall on demand.
"""
from __future__ import annotations

import json
import os
import sys
import sqlite3
import time
from pathlib import Path

# Add plugin lib to path
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

try:
    from lib.stdio_utf8 import force_utf8_io
    force_utf8_io()
except Exception:
    pass

try:
    from lib.paths import (
        FILE_CHUNKS_DB,
        FILE_LAST_INGEST,
        ensure_kos_dir,
    )
except Exception:
    sys.exit(0)


def main() -> int:
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        kos_dir = ensure_kos_dir(project, user_level=False)
    except Exception:
        sys.exit(0)

    db = kos_dir / FILE_CHUNKS_DB
    if not db.exists():
        sys.exit(0)

    try:
        c = sqlite3.connect(str(db), timeout=1.0)
        n = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        latest = c.execute("SELECT MAX(ts) FROM chunks").fetchone()[0]
        sessions = c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        c.close()
    except Exception:
        sys.exit(0)

    if n == 0:
        sys.exit(0)

    last_ingest = "never"
    if latest:
        days_ago = (int(time.time()) - latest) / 86400
        if days_ago < 1:
            last_ingest = "today"
        elif days_ago < 2:
            last_ingest = "yesterday"
        else:
            last_ingest = f"{int(days_ago)}d ago"

    # Single line, ≤50 tokens, never injects content
    print(
        f"[kos-memory BACKUP] {n} chunks, {sessions} sessions for this project "
        f"(last ingest: {last_ingest}). "
        f"Use /recall when current context is missing past detail."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
