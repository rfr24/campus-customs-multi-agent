"""Regression check: no test suite may write to the production audit trail.

This exists because three suites once did. They exercised real MCP tools while
redirecting only the database, so genuine-looking events — including
`execute_payment` entries marked `completed` — landed in `output/audit_trail.json`
despite no real database being touched.

The check is empirical rather than structural: it records the production audit
file's checksum, runs each suite as a subprocess, and compares. A suite that
regresses is caught no matter how it is written.

Run:  .venv/bin/python tests/verify_audit_isolation.py [--all]

By default it runs only the suites that need no model credentials and no
network. Pass --all to include the live-agent suites too.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_AUDIT = PROJECT_ROOT / "output" / "audit_trail.json"

# (suite, needs a live model / network)
SUITES = [
    ("tests/verify_mcp.py", False),
    ("tests/verify_purchase_permissions.py", False),
    ("tests/verify_backend.py", False),
    ("tests/verify_audit_integrity.py", False),
    ("tests/verify_pydanticai.py", True),
    ("tests/verify_team.py", True),
]

PASS, FAIL, SKIP = [], [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry_count(path: Path) -> int:
    try:
        return len(json.loads(path.read_text()))
    except Exception:  # noqa: BLE001
        return -1


def main() -> int:
    run_all = "--all" in sys.argv

    before = sha256(PRODUCTION_AUDIT)
    n_before = entry_count(PRODUCTION_AUDIT)
    print(f"\nproduction audit before: {before[:16]}…  ({n_before} entries)")

    print("\n[1] each suite leaves the production audit trail byte-identical")
    for suite, needs_model in SUITES:
        if needs_model and not run_all:
            SKIP.append(suite)
            print(f"  SKIP  {suite} leaves the audit trail untouched  — pass --all to include it")
            continue
        subprocess.run(
            [sys.executable, suite], cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        after = sha256(PRODUCTION_AUDIT)
        n_after = entry_count(PRODUCTION_AUDIT)
        check(f"{suite} leaves the audit trail untouched", after == before,
              "unchanged" if after == before
              else f"MODIFIED: {n_before} -> {n_after} entries")

    print("\n[2] the production audit trail survived this check intact")
    check("checksum identical to the start of this run",
          sha256(PRODUCTION_AUDIT) == before, sha256(PRODUCTION_AUDIT)[:16] + "…")
    check("entry count unchanged", entry_count(PRODUCTION_AUDIT) == n_before,
          f"{entry_count(PRODUCTION_AUDIT)} entries")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
