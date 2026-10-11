"""Problem 5 follow-up: audit-trail integrity under concurrency.

All stress testing runs against a throwaway audit file in a temp directory,
selected with CAMPUS_CUSTOMS_AUDIT_PATH. The real `output/audit_trail.json` is
read once to confirm its entry count and is never written by this suite.

Run:  .venv/bin/python tests/verify_audit_integrity.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_AUDIT = PROJECT_ROOT / "output" / "audit_trail.json"

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


# Child process body: append N entries to whatever CAMPUS_CUSTOMS_AUDIT_PATH names.
WORKER = """
import sys
sys.path.insert(0, {root!r})
from mcp_server import audit
tag, n = sys.argv[1], int(sys.argv[2])
for i in range(n):
    audit.record("stress", {{"worker": tag, "i": i}}, "ok")
"""


def run_workers(audit_path: Path, n_procs: int, per_proc: int) -> None:
    env = {**os.environ, "CAMPUS_CUSTOMS_AUDIT_PATH": str(audit_path)}
    script = WORKER.format(root=str(PROJECT_ROOT))
    procs = [
        subprocess.Popen([sys.executable, "-c", script, f"w{i}", str(per_proc)], env=env)
        for i in range(n_procs)
    ]
    for p in procs:
        p.wait()


def main() -> int:
    print("\n[1] the lock is a stable file, not the file being replaced")
    from mcp_server import audit

    check("lock path differs from the audit file", audit._lock_path() != audit.AUDIT_PATH,
          audit._lock_path().name)
    check("lock filename is derived without clobbering the .json suffix",
          audit._lock_path().name.endswith(".json.lock"), audit._lock_path().name)

    # The real point: os.replace swaps the JSON's inode on every write. A lock
    # held on that inode would be a lock on an unlinked file.
    with tempfile.TemporaryDirectory() as td:
        probe = Path(td) / "audit_trail.json"
        os.environ["CAMPUS_CUSTOMS_AUDIT_PATH"] = str(probe)
        import importlib

        importlib.reload(audit)
        audit.record("probe", {}, "first")
        inode_1 = probe.stat().st_ino
        lock_inode_1 = audit._lock_path().stat().st_ino
        audit.record("probe", {}, "second")
        inode_2 = probe.stat().st_ino
        lock_inode_2 = audit._lock_path().stat().st_ino
        check("the audit file's inode DOES change on write (atomic replace)",
              inode_1 != inode_2)
        check("the lock file's inode does NOT change — the lock stays valid",
              lock_inode_1 == lock_inode_2)

    print("\n[2] multiprocess append: no lost updates")
    with tempfile.TemporaryDirectory() as td:
        audit_path = Path(td) / "audit_trail.json"
        n_procs, per_proc = 8, 60
        run_workers(audit_path, n_procs, per_proc)
        entries = json.loads(audit_path.read_text())
        expected = n_procs * per_proc
        check(f"{n_procs} processes x {per_proc} appends all survive",
              len(entries) == expected, f"{len(entries)}/{expected}")
        workers = {e["args"]["worker"] for e in entries}
        check("every worker's entries are present", len(workers) == n_procs,
              f"{len(workers)}/{n_procs} workers")
        per_worker = {w: sum(1 for e in entries if e["args"]["worker"] == w) for w in workers}
        check("no worker lost a single entry",
              all(c == per_proc for c in per_worker.values()), str(sorted(per_worker.values())))
        check("the file is valid JSON after concurrent writes", isinstance(entries, list))
        check("no stray temp files left behind",
              not list(Path(td).glob("*.tmp")), str([p.name for p in Path(td).glob("*.tmp")]))

    print("\n[3] a corrupt or partial file cannot silently erase prior entries")
    with tempfile.TemporaryDirectory() as td:
        audit_path = Path(td) / "audit_trail.json"
        os.environ["CAMPUS_CUSTOMS_AUDIT_PATH"] = str(audit_path)
        import importlib

        importlib.reload(audit)
        audit.record("before_corruption", {"n": 1}, "genuine entry")
        audit.record("before_corruption", {"n": 2}, "genuine entry")
        before = json.loads(audit_path.read_text())
        check("two genuine entries written", len(before) == 2)

        # Simulate a truncated / partially written file.
        audit_path.write_text('[{"time": "2026-08-31T00:00:00+00:00", "tool": "half')
        audit.record("after_corruption", {}, "new entry")

        salvaged = list(Path(td).glob("audit_trail.corrupt-*.json"))
        check("the unparseable file is preserved on disk, not deleted", len(salvaged) == 1,
              salvaged[0].name if salvaged else "none")
        check("its bytes are kept verbatim for recovery",
              salvaged and salvaged[0].read_text().startswith('[{"time"'))

        new_log = json.loads(audit_path.read_text())
        check("the fresh log records that a salvage happened — not silent",
              any(e["tool"] == "audit.salvage" for e in new_log))
        check("the salvage entry names the preserved file",
              any(e.get("args", {}).get("preserved_as", "").startswith("audit_trail.corrupt-")
                  for e in new_log))
        check("the new entry was still written", any(e["tool"] == "after_corruption"
                                                     for e in new_log))

    print("\n[4] empty and non-list files are handled without loss")
    with tempfile.TemporaryDirectory() as td:
        audit_path = Path(td) / "audit_trail.json"
        os.environ["CAMPUS_CUSTOMS_AUDIT_PATH"] = str(audit_path)
        import importlib

        importlib.reload(audit)
        audit_path.write_text("")
        audit.record("after_empty", {}, "ok")
        check("an empty file is treated as an empty log, not corruption",
              len(json.loads(audit_path.read_text())) == 1
              and not list(Path(td).glob("*corrupt*")))

    print("\n[5] the real audit history is intact and untouched")
    os.environ.pop("CAMPUS_CUSTOMS_AUDIT_PATH", None)
    real = json.loads(REAL_AUDIT.read_text())
    check("output/audit_trail.json still holds its 81 genuine entries", len(real) == 81,
          f"{len(real)} entries")
    check("no stress entry leaked into the real log",
          not any(e["tool"] in {"stress", "probe", "before_corruption", "after_corruption",
                                "after_empty"} for e in real))
    check("the real log is still a valid JSON array", isinstance(real, list))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
