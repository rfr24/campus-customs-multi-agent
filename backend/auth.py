"""Operator authentication for the privileged approval routes.

The trust boundary from Problem 3 says `approval.grant()` trusts its caller and
that whatever exposes it **must authenticate the human operator**. This module
is that authentication.

Mechanism: a bearer token generated once into `.secrets/operator_token`
(mode 0600, git-ignored) and presented as `Authorization: Bearer <token>`.
Comparison is constant-time. The token is never returned by any route and never
written to the audit log.

`approved_by` is derived from the **authenticated principal**, never from the
request body — a client cannot name itself. Problem 3's lesson applies here too:
a string a caller supplies is not evidence of identity.

This is deliberately minimal and appropriate for a local, single-operator
assignment. A deployment with multiple operators would want per-user accounts
and sessions; see harness §F5.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException, status

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_PATH = Path(
    os.environ.get("CAMPUS_CUSTOMS_OPERATOR_TOKEN_PATH", PROJECT_ROOT / ".secrets" / "operator_token")
)

# The identity recorded for anything this operator approves.
OPERATOR_PRINCIPAL = os.environ.get("CAMPUS_CUSTOMS_OPERATOR_NAME", "operator (local)")


def load_or_create_token() -> str:
    """Read the operator token, generating it on first use."""
    if TOKEN_PATH.is_file():
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, token.encode("utf-8"))
    finally:
        os.close(fd)
    return token


def require_operator(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency. Returns the authenticated principal, or raises 401.

    The returned principal — not anything in the request body — is what gets
    recorded as the approver.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator authentication required: send 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = authorization.removeprefix("Bearer ").strip()
    expected = load_or_create_token()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return OPERATOR_PRINCIPAL
