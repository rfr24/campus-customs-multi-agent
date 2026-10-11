"""Persistence for ticket-processing runs.

Each run of the Boss against a ticket is appended to `output/ticket_runs.json`
so the later dashboard can show history without re-running agents — a run costs
real model calls, so it must not be thrown away.

Uses the same append-only, lock-guarded, atomically-committed pattern as the
audit trail (harness §B5), for the same reason: concurrent requests must not
overwrite each other's records.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNS_PATH = Path(
    os.environ.get(
        "CAMPUS_CUSTOMS_RUNS_PATH",
        Path(__file__).resolve().parent.parent / "output" / "ticket_runs.json",
    )
)


def _lock_path() -> Path:
    return RUNS_PATH.with_name(RUNS_PATH.name + ".lock")


def _load() -> list[dict]:
    if not RUNS_PATH.is_file():
        return []
    raw = RUNS_PATH.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        stamp = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
        try:
            RUNS_PATH.replace(RUNS_PATH.with_name(f"{RUNS_PATH.stem}.corrupt-{stamp}.json"))
        except OSError:
            pass
        return []
    return data if isinstance(data, list) else []


def append(record: dict[str, Any]) -> dict[str, Any]:
    """Append one run record. Never overwrites earlier runs."""
    RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_lock_path(), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            runs = _load()
            runs.append(record)
            tmp = RUNS_PATH.with_name(f"{RUNS_PATH.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(runs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, RUNS_PATH)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return record


def list_runs(ticket_id: int | None = None) -> list[dict]:
    runs = _load()
    if ticket_id is not None:
        runs = [r for r in runs if r.get("ticket_id") == ticket_id]
    return runs


def get_run(run_id: str) -> dict | None:
    for run in _load():
        if run.get("run_id") == run_id:
            return run
    return None
