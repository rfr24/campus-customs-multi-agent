"""Keep test runs out of the production audit trail.

`mcp_server.audit` resolves its path once, at import time, from
`CAMPUS_CUSTOMS_AUDIT_PATH` (falling back to `output/audit_trail.json`). A test
that exercises real MCP tools therefore appends to the **production** log unless
that variable is set *before* `mcp_server` is imported.

That is exactly what happened: suites that redirected the database to a
disposable copy but left the audit path alone wrote genuine-looking tool
events — including `execute_payment` entries marked `completed` — into the real
audit trail, even though no real database was touched. The entries were honest
records of sandboxed calls, but a reader scanning the log could mistake them for
production activity.

Call `isolate_audit()` at the top of a test module, before importing anything
from `mcp_server`, `agents`, or `backend`.

Note what this deliberately does *not* do: it leaves `CAMPUS_CUSTOMS_DB_PATH`
alone. Several suites read the real working database on purpose to assert that
its contents match the documented facts. Only the audit *write* path is
redirected.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_AUDIT = PROJECT_ROOT / "output" / "audit_trail.json"


def isolate_audit(prefix: str = "cc-audit-") -> Path:
    """Point audit writes at a throwaway file; return that path.

    The temp directory is removed at interpreter exit. Cleanup only ever
    touches the directory this function created, so it cannot reach the real
    audit trail.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix=prefix))
    audit_path = tmpdir / "audit_trail.json"
    os.environ["CAMPUS_CUSTOMS_AUDIT_PATH"] = str(audit_path)
    atexit.register(shutil.rmtree, tmpdir, ignore_errors=True)
    return audit_path


def assert_audit_isolated() -> None:
    """Fail loudly if the audit module resolved to the production log.

    Guards against the ordering mistake that caused the original problem:
    importing `mcp_server.audit` before calling `isolate_audit()`.
    """
    from mcp_server import audit

    if audit.AUDIT_PATH.resolve() == PRODUCTION_AUDIT.resolve():
        raise RuntimeError(
            "Audit isolation failed: mcp_server.audit is pointed at the production "
            f"trail ({PRODUCTION_AUDIT}). Call isolate_audit() before importing "
            "mcp_server."
        )
