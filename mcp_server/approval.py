"""The trusted approval surface — deliberately *not* an MCP tool.

Trust boundary
--------------
Agents reach this process only through the MCP tool surface in `server.py`.
Nothing in this module is registered with `@mcp.tool`, so an agent cannot call
`grant()` no matter what it decides to do. Granting authorization is reserved
for a privileged caller in the same process: today the operator CLI
(`python -m mcp_server.approve`), later the FastAPI route that will serve the
dashboard's approve/reject control.

Why a secret key
----------------
An approval is recorded as an HMAC-SHA256 signature over the exact proposal
fields, keyed with a server-side secret held in `.secrets/approval_key` (mode
0600, generated on first use, git-ignored). The secret is never returned by any
MCP tool and never written to the audit log. An agent that knows every public
field of a proposal still cannot produce a valid signature, which is precisely
what the previous reproducible SHA-256-of-public-fields scheme failed to
guarantee.

Requirement for the future human-facing route
---------------------------------------------
`grant()` performs no authentication of its own — it trusts its caller. The
FastAPI route that exposes it MUST authenticate the human operator (session or
signed token tied to a real account) and pass that verified identity as
`approved_by`. Do not expose `grant()` as an unauthenticated endpoint, and do
not re-export it through the MCP server.
"""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from mcp_server import audit, proposals

KEY_PATH = Path(__file__).resolve().parent.parent / ".secrets" / "approval_key"


class ApprovalError(RuntimeError):
    """Raised when approval is refused."""


def _load_key() -> bytes:
    """Read the server-side approval secret, creating it on first use."""
    if KEY_PATH.is_file():
        return KEY_PATH.read_bytes()
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    # Write with owner-only permissions from the start.
    fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    return key


def sign(proposal: dict, approved_by: str, approved_at: str, nonce: str) -> str:
    """HMAC over the fields that define the authorized action."""
    payload = "|".join(
        [
            proposal["proposal_id"],
            proposal["kind"],
            proposal["target"],
            f"{proposal['amount']:.2f}",
            proposal["account"],
            approved_by,
            approved_at,
            nonce,
        ]
    )
    return hmac.new(_load_key(), payload.encode("utf-8"), sha256).hexdigest()


def verify(proposal: dict) -> bool:
    """True if the proposal carries an approval this server actually issued."""
    approval = proposal.get("approval")
    if not isinstance(approval, dict):
        return False
    for field in ("approved_by", "approved_at", "nonce", "signature"):
        if not approval.get(field):
            return False
    expected = sign(proposal, approval["approved_by"], approval["approved_at"], approval["nonce"])
    # Constant-time compare so a forged signature leaks nothing by timing.
    return hmac.compare_digest(expected, approval["signature"])


def grant(proposal_id: str, approved_amount: float, approved_by: str) -> dict:
    """Record a human's authorization for one exact proposal. PRIVILEGED.

    The caller is responsible for having authenticated `approved_by`.
    """
    proposal = proposals.get(proposal_id)
    if proposal is None:
        raise ApprovalError(f"No such proposal: {proposal_id}")
    if proposal["status"] == proposals.STATUS_EXECUTED:
        raise ApprovalError(f"Proposal {proposal_id} was already executed.")
    if proposal["status"] == proposals.STATUS_REJECTED:
        raise ApprovalError(f"Proposal {proposal_id} was rejected.")
    if proposal["status"] == proposals.STATUS_APPROVED:
        raise ApprovalError(f"Proposal {proposal_id} is already approved and awaiting execution.")
    if not str(approved_by or "").strip():
        raise ApprovalError("approved_by must carry the authenticated human's identity.")
    if round(float(approved_amount), 2) != proposal["amount"]:
        raise ApprovalError(
            f"Approved amount {float(approved_amount):.2f} does not match the proposed "
            f"amount {proposal['amount']:.2f}. Approval must match the amount exactly."
        )

    approved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nonce = secrets.token_hex(8)
    approval = {
        "approved_by": approved_by,
        "approved_at": approved_at,
        "nonce": nonce,
        "signature": sign(proposal, approved_by, approved_at, nonce),
    }
    updated = proposals.attach_approval(proposal_id, approval)
    audit.record(
        "approval.grant",
        {"proposal_id": proposal_id, "amount": proposal["amount"], "approved_by": approved_by},
        f"{proposal_id} approved for {proposal['amount']:.2f}",
        "completed",
    )
    return updated
