"""Append-only audit trail for MCP tool calls.

Every MCP tool call is recorded to `output/audit_trail.json` as one entry with
the time, the tool, short arguments, a short result summary, and a stop reason.
The format matches the project's existing audit convention.

Deliberately *not* recorded: model reasoning or chain-of-thought, API keys or
any secret, full prompts. Only short operational facts that explain what the
system did.

The file is only ever appended to, and the read-modify-write is guarded by an
exclusive file lock and committed with an atomic replace. That matters because
the MCP server can run as several concurrent agents and as a stdio subprocess
at the same time: without the lock, two writers could each read the array, and
the slower one would overwrite the other's entries. An unparseable file is set
aside rather than discarded, so genuine records are never silently dropped.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Overridable so stress tests can hammer a throwaway file instead of the real
# history. Unset in normal operation.
AUDIT_PATH = Path(
    os.environ.get(
        "CAMPUS_CUSTOMS_AUDIT_PATH",
        Path(__file__).resolve().parent.parent / "output" / "audit_trail.json",
    )
)


def _lock_path() -> Path:
    """A stable sibling file that is never replaced.

    The lock must NOT be the JSON file: that one is swapped out by os.replace on
    every write, so a second writer could hold a lock on an unlinked inode while
    a third locks the new one, and both would proceed at once.
    """
    return AUDIT_PATH.with_name(AUDIT_PATH.name + ".lock")

MAX_FIELD = 120

# Argument names that must never reach the log even if a caller passes them.
REDACT_KEYS = {"api_key", "password", "token", "secret", "authorization"}


def _short(value: Any) -> Any:
    """Keep recorded values short; never store a large payload."""
    if isinstance(value, str):
        return value if len(value) <= MAX_FIELD else value[: MAX_FIELD - 1] + "…"
    if isinstance(value, (list, tuple)):
        return f"<{len(value)} item(s)>"
    if isinstance(value, dict):
        return f"<{len(value)} field(s)>"
    return value


def _clean(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in args.items():
        if key.lower() in REDACT_KEYS:
            out[key] = "<redacted>"
        else:
            out[key] = _short(value)
    return out


def _load() -> list[dict]:
    if not AUDIT_PATH.is_file():
        return []
    raw = AUDIT_PATH.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    try:
        existing = json.loads(raw)
    except json.JSONDecodeError:
        # Never destroy records we cannot parse. Preserve the file alongside the
        # new log so a human can recover it, then start a fresh array.
        stamp = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
        salvage = AUDIT_PATH.with_name(f"{AUDIT_PATH.stem}.corrupt-{stamp}.json")
        try:
            AUDIT_PATH.replace(salvage)
        except OSError:
            return []
        # Start the fresh log with a record of what happened, so a reader can
        # never mistake a truncated history for a quiet one.
        return [{
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": "audit.salvage",
            "args": {"preserved_as": salvage.name},
            "result": "prior audit file was unparseable and was preserved, not discarded",
            "stop_reason": "recovered",
        }]
    return existing if isinstance(existing, list) else []


def record(
    tool: str,
    args: dict[str, Any] | None = None,
    result: str = "",
    stop_reason: str = "completed",
) -> None:
    """Append one audit entry. Never raises into the tool call path."""
    entry = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "args": _clean(args or {}),
        "result": _short(result),
        "stop_reason": stop_reason,
    }
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_path = _lock_path()
        # One writer at a time across processes: concurrent agents and the stdio
        # subprocess all append to this same file. Opened "a" so acquiring the
        # lock never truncates anything, even transiently.
        with open(lock_path, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                entries = _load()
                entries.append(entry)
                payload = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
                # Atomic commit: a reader never sees a half-written array.
                # Per-process temp name: two writers can never collide on it,
                # even if one somehow proceeds without the lock.
                tmp = AUDIT_PATH.with_name(f"{AUDIT_PATH.name}.{os.getpid()}.tmp")
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, AUDIT_PATH)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    except OSError:
        # Auditing must never take the MCP server down.
        pass
