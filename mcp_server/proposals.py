"""The human-approval boundary.

An agent may *propose* a payment or a purchase. A proposal is inert: it moves
no money and changes no stock. It becomes an executed action only when a human
approves that specific proposal, quoting its approval token and its exact
amount.

Proposals live in `output/proposals.json`, deliberately outside the business
database, so that preparing a proposal cannot touch operational tables and the
assignment's schema stays exactly as Problem 2 documented it.

A proposal becomes executable only when `approval.grant()` attaches a
signature this server issued with its secret key — see `approval.py`. This
module stores that state; it never issues approvals itself.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Overridable for tests, like the database path. Unset in normal operation.
PROPOSALS_PATH = Path(
    os.environ.get(
        "CAMPUS_CUSTOMS_PROPOSALS_PATH",
        Path(__file__).resolve().parent.parent / "output" / "proposals.json",
    )
)

STATUS_PENDING = "pending_human_approval"
STATUS_APPROVED = "approved"
STATUS_EXECUTED = "executed"
STATUS_REJECTED = "rejected"


class ApprovalError(RuntimeError):
    """Raised when an approval is missing, mismatched, or already spent."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> list[dict]:
    if not PROPOSALS_PATH.is_file():
        return []
    try:
        data = json.loads(PROPOSALS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save(items: list[dict]) -> None:
    PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROPOSALS_PATH.write_text(
        json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def next_id(prefix: str) -> str:
    existing = _load()
    n = sum(1 for p in existing if p["proposal_id"].startswith(prefix)) + 1
    # Guarantee uniqueness even if an id was removed by hand.
    while any(p["proposal_id"] == f"{prefix}-{n:04d}" for p in existing):
        n += 1
    return f"{prefix}-{n:04d}"


def create(kind: str, target: str, amount: float, account: str, detail: dict[str, Any]) -> dict:
    """Record a pending proposal and return it."""
    prefix = "PAY" if kind == "payment" else "PUR"
    proposal_id = next_id(prefix)
    proposal = {
        "proposal_id": proposal_id,
        "kind": kind,
        "target": target,
        "amount": round(float(amount), 2),
        "account": account,
        "detail": detail,
        "status": STATUS_PENDING,
        "approval": None,
        "created_at": _now(),
        "decided_at": None,
        "decided_by": None,
    }
    items = _load()
    items.append(proposal)
    _save(items)
    return proposal


def get(proposal_id: str) -> dict | None:
    for item in _load():
        if item["proposal_id"] == proposal_id:
            return item
    return None


def list_all(status: str | None = None) -> list[dict]:
    items = _load()
    if status:
        items = [p for p in items if p["status"] == status]
    return items


def attach_approval(proposal_id: str, approval: dict) -> dict:
    """Move a pending proposal to approved, carrying the server-issued signature."""
    items = _load()
    for item in items:
        if item["proposal_id"] == proposal_id:
            item["approval"] = approval
            item["status"] = STATUS_APPROVED
            _save(items)
            return item
    raise ApprovalError(f"No such proposal: {proposal_id}")


def verify_for_execution(proposal_id: str) -> dict:
    """Check that this exact proposal carries a genuine, unspent approval.

    The caller supplies only the proposal id. Nothing an agent can pass in
    contributes to the decision: authorization lives in persisted state signed
    with the server's secret key, so a caller that knows every public field of
    a proposal still cannot manufacture one.

    Raises ApprovalError on anything suspicious. Returns the proposal on success.
    """
    # Imported here: approval.py imports this module, so a top-level import
    # would be circular.
    from mcp_server import approval

    proposal = get(proposal_id)
    if proposal is None:
        raise ApprovalError(f"No such proposal: {proposal_id}")

    if proposal["status"] == STATUS_EXECUTED:
        raise ApprovalError(
            f"Proposal {proposal_id} was already executed at {proposal['decided_at']}. "
            "Refusing to run it twice."
        )
    if proposal["status"] == STATUS_REJECTED:
        raise ApprovalError(f"Proposal {proposal_id} was rejected and cannot be executed.")
    if proposal["status"] != STATUS_APPROVED:
        raise ApprovalError(
            f"Proposal {proposal_id} has not been approved by a human. "
            "An agent cannot authorize its own proposal."
        )

    if not approval.verify(proposal):
        raise ApprovalError(
            f"Proposal {proposal_id} carries no valid server-issued approval signature. "
            "Refusing to execute."
        )

    return proposal


def mark(proposal_id: str, status: str, decided_by: str, outcome: dict | None = None) -> dict:
    items = _load()
    for item in items:
        if item["proposal_id"] == proposal_id:
            item["status"] = status
            item["decided_at"] = _now()
            item["decided_by"] = decided_by
            if outcome:
                item["outcome"] = outcome
            _save(items)
            return item
    raise ApprovalError(f"No such proposal: {proposal_id}")
