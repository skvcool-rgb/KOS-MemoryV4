"""Filesystem path helpers — single source of truth.

Per-project memory:   <project>/.kos-memory/
User-level memory:    ~/.config/kos-memory/user/  (XDG; %APPDATA%/kos-memory/user/ on Windows)
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR_NAME = ".kos-memory"


def project_cache_dir(project_root: str | Path) -> Path:
    """Return absolute <project>/.kos-memory/ path. Creates if missing."""
    p = Path(project_root).resolve() / PROJECT_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_cache_dir() -> Path:
    """Return cross-project user-level memory dir.

    Uses %APPDATA% on Windows, ~/.config on POSIX (XDG-compliant).
    Distinct from any v3 path to avoid collision.
    """
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    p = base / "kos-memory" / "user"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_kos_dir(project_root: str | Path | None = None, user_level: bool = False) -> Path:
    """Pick the correct cache dir for project- vs user-level operation."""
    if user_level:
        return user_cache_dir()
    if project_root is None:
        project_root = os.getcwd()
    return project_cache_dir(project_root)


# Standard files inside a kos-memory dir
FILE_CHUNKS_DB = "chunks.db"
FILE_CATALOG = "catalog.json"
FILE_SYNONYMS = "synonyms.json"
FILE_LAST_INGEST = "last_ingest_marker"
FILE_BUDGET = "budget.json"
FILE_INGEST_LOG = "ingest_log.jsonl"
