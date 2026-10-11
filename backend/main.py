"""FastAPI backend for Campus Customs ticket processing.

Layering, deliberately unchanged from earlier problems:

    HTTP  →  this app  →  PydanticAI team (Boss + 4 specialists)  →  MCP server  →  SQLite

The backend owns no business logic and opens no database handle of its own.
Every read goes through an MCP tool; every agent decision goes through the real
Boss. Nothing here duplicates a tool or a rule.

Two surfaces, kept apart on purpose:

* **Open routes** — read state, inspect tickets, run the team. Safe because
  nothing on this path can move money or stock.
* **Operator routes** (`/api/operator/...`) — approve, reject, execute. These
  require bearer authentication, and the approver's identity comes from the
  authenticated principal, never from the request body.

Run it:
    .venv/bin/uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.mcp_client import inprocess_toolset
from agents.schemas import TeamOutcome
from agents.team import CampusCustomsTeam
from backend import store
from backend.auth import require_operator
from mcp_server import approval, audit, proposals

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Built once per process: constructing a team builds five model clients.
_team: CampusCustomsTeam | None = None


def get_team() -> CampusCustomsTeam:
    """The real five-agent team. Overridable in tests via dependency_overrides."""
    global _team
    if _team is None:
        _team = CampusCustomsTeam.build()
    return _team


async def call_tool(name: str, args: dict[str, Any]) -> dict:
    """Read shop state through the shared MCP server — never a direct DB handle."""
    toolset = inprocess_toolset()
    async with toolset:
        return await toolset.direct_call_tool(name, args)


def _unwrap(result: dict, *, not_found_detail: str | None = None) -> dict:
    """Turn a tool refusal into the right HTTP status instead of a 200 with ok:false."""
    if result.get("ok") is False:
        reason = result.get("stop_reason", "error")
        code = {
            "not_found": status.HTTP_404_NOT_FOUND,
            "invalid_input": status.HTTP_400_BAD_REQUEST,
            "insufficient_funds": status.HTTP_409_CONFLICT,
            "duplicate_payment": status.HTTP_409_CONFLICT,
            "already_settled": status.HTTP_409_CONFLICT,
            "approval_rejected": status.HTTP_403_FORBIDDEN,
            "wrong_proposal_kind": status.HTTP_409_CONFLICT,
        }.get(reason, status.HTTP_500_INTERNAL_SERVER_ERROR)
        raise HTTPException(status_code=code,
                            detail={"error": not_found_detail or result.get("error"),
                                    "stop_reason": reason})
    return result


# --------------------------------------------------------------------------
# response models
# --------------------------------------------------------------------------

class ProcessRequest(BaseModel):
    """Options for a ticket-processing run."""

    instructions: str | None = Field(
        None, description="Optional extra context for the Boss. The ticket itself is always loaded."
    )
    mark_in_progress: bool = Field(
        False,
        description=(
            "Write status='in_progress' back to the ticket. Default false so a run "
            "leaves the database untouched."
        ),
    )


class TicketRun(BaseModel):
    """One processing run. This is what the dashboard renders."""

    run_id: str
    ticket_id: int
    started_at: str
    finished_at: str
    # Lifecycle stage — NOT the ticket's resolution. See `ticket_status`.
    stage: str = Field(
        description=(
            "investigated | awaiting_human_approval | failed. "
            "A run never reports 'resolved': resolution requires an executed, "
            "human-approved action."
        )
    )
    ticket_status: str = Field(description="The ticket's actual status in the database.")
    outcome: TeamOutcome | None = None
    error: str | None = None
    stop_reason: str | None = None


class ApprovalRequest(BaseModel):
    """A human's approval of one specific proposal.

    Note what is absent: there is no `approved_by`. Identity comes from the
    authenticated operator, so a caller cannot name itself.
    """

    approved_amount: float = Field(
        description="Must equal the proposed amount exactly. Binds the approval to the action."
    )


class RejectRequest(BaseModel):
    reason: str = ""


# --------------------------------------------------------------------------
# app
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    audit.record("backend.startup", {}, "FastAPI backend started", "completed")
    yield
    audit.record("backend.shutdown", {}, "FastAPI backend stopped", "completed")


app = FastAPI(
    title="Campus Customs Operations API",
    description="Ticket processing through the five-agent team, with a human approval boundary.",
    version="1.0.0",
    lifespan=lifespan,
)

# The dashboard is served from Vite in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------- read routes ---------------------------------

@app.get("/api/health", tags=["state"])
async def health() -> dict:
    """Liveness plus the shop's authoritative date."""
    today = await call_tool("get_today", {})
    return {"status": "ok", "shop_date": today.get("date_today")}


@app.get("/api/tickets", tags=["tickets"])
async def list_tickets(status_filter: str = Query("", alias="status")) -> dict:
    """All tickets, or those with a given status. Pass ?status=open for the queue."""
    return _unwrap(await call_tool("list_tickets", {"status": status_filter, "limit": 200}))


@app.get("/api/tickets/{ticket_id}", tags=["tickets"])
async def get_ticket(ticket_id: int) -> dict:
    """One ticket with its linked lease and invoice, plus any runs already recorded."""
    result = _unwrap(await call_tool("get_ticket", {"ticket_id": ticket_id}),
                     not_found_detail=f"No ticket {ticket_id}")
    result["runs"] = store.list_runs(ticket_id)
    return result


@app.get("/api/state", tags=["state"])
async def operational_state() -> dict:
    """A dashboard's opening screen: date, cash, open tickets, obligations, proposals."""
    today = await call_tool("get_today", {})
    cash = await call_tool("get_cash_balance", {"account": "checking"})
    tickets = await call_tool("list_tickets", {"status": "open", "limit": 200})
    invoices = await call_tool("list_invoices", {"status": "open", "limit": 200})
    leases = await call_tool("list_leases", {"limit": 200})
    payments = await call_tool("list_payments", {"limit": 200})
    pending = proposals.list_all(proposals.STATUS_PENDING)
    approved = proposals.list_all(proposals.STATUS_APPROVED)
    return {
        "shop_date": today.get("date_today"),
        "cash": cash.get("account"),
        "open_tickets": tickets.get("tickets", []),
        "open_invoices": invoices.get("invoices", []),
        "leases": leases.get("leases", []),
        "payments": payments.get("payments", []),
        "pending_approval_count": len(pending),
        "approved_awaiting_execution_count": len(approved),
    }


@app.get("/api/cash", tags=["state"])
async def cash_balance(account: str = "checking") -> dict:
    """The account balance every proposal competes against."""
    return _unwrap(await call_tool("get_cash_balance", {"account": account}))


@app.get("/api/inventory/{sku}", tags=["state"])
async def inventory(sku: str, size: str = "") -> dict:
    """Stock for a SKU, or one exact (sku, size) pair."""
    return _unwrap(await call_tool("lookup_inventory", {"sku": sku, "size": size}))


# ---------------------------- proposals -----------------------------------

def _public_proposal(p: dict) -> dict:
    """Strip signature material. The dashboard sees who approved, never the proof."""
    view = {k: v for k, v in p.items() if k != "approval"}
    appr = p.get("approval")
    view["approved_by"] = appr["approved_by"] if appr else None
    view["approved_at"] = appr["approved_at"] if appr else None
    return view


@app.get("/api/proposals", tags=["approval"])
async def list_proposals(status_filter: str = Query("", alias="status")) -> dict:
    """Proposals and their status. Readable without authentication; acting on one is not."""
    items = proposals.list_all(status_filter or None)
    return {"proposals": [_public_proposal(p) for p in items], "count": len(items)}


@app.get("/api/proposals/{proposal_id}", tags=["approval"])
async def get_proposal(proposal_id: str) -> dict:
    p = proposals.get(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"No such proposal: {proposal_id}")
    return _public_proposal(p)


# ------------------------- ticket processing ------------------------------

@app.post("/api/tickets/{ticket_id}/process", response_model=TicketRun, tags=["tickets"])
async def process_ticket(ticket_id: int, body: ProcessRequest | None = None,
                         team: CampusCustomsTeam = Depends(get_team)) -> TicketRun:
    """Run the real Boss agent against a ticket.

    The ticket is loaded through MCP and handed to the Boss, which delegates to
    specialists for real. Nothing here decides the outcome; the agents do.

    What this endpoint will *not* do: mark a ticket resolved. A recommendation
    is not a resolution. `stage` reports how far the work got, while
    `ticket_status` reports the database's own view — and those stay distinct
    until a human approves and an action executes.
    """
    body = body or ProcessRequest()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = f"run-{uuid.uuid4().hex[:12]}"

    ticket_result = await call_tool("get_ticket", {"ticket_id": ticket_id})
    if ticket_result.get("ok") is False:
        raise HTTPException(status_code=404, detail=f"No ticket {ticket_id}")
    ticket = ticket_result["ticket"]

    request_text = (
        f"Handle ticket {ticket['id']}.\n"
        f"Type: {ticket['type']}\n"
        f"Requester: {ticket['requester']}\n"
        f"Subject: {ticket['subject']}\n"
        f"Notes: {ticket.get('notes') or '(none)'}\n"
        f"SKU: {ticket.get('sku') or '(none)'}  Size: {ticket.get('size') or '(none)'}  "
        f"Qty: {ticket.get('qty') if ticket.get('qty') is not None else '(none)'}\n"
        f"Linked lease: {ticket.get('lease_id') or '(none)'}  "
        f"Linked invoice: {ticket.get('invoice_id') or '(none)'}\n\n"
        "Investigate using your tools and the relevant specialists, then report what "
        "the shop should do. Prepare proposals where a financial action is warranted, "
        "but do not claim anything has been paid, ordered, or resolved."
    )
    if body.instructions:
        request_text += f"\n\nAdditional operator context: {body.instructions}"

    audit.record("backend.process_ticket", {"ticket_id": ticket_id, "run_id": run_id},
                 "dispatching to Boss agent", "started")

    try:
        outcome: TeamOutcome = await team.run(request_text)
    except Exception as exc:  # noqa: BLE001
        # A failed run must never advance the ticket. Record it and say so.
        finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
        current = (await call_tool("get_ticket", {"ticket_id": ticket_id}))["ticket"]["status"]
        run = TicketRun(
            run_id=run_id, ticket_id=ticket_id, started_at=started, finished_at=finished,
            stage="failed", ticket_status=current, outcome=None,
            error=str(exc), stop_reason=type(exc).__name__,
        )
        store.append(json.loads(run.model_dump_json()))
        audit.record("backend.process_ticket", {"ticket_id": ticket_id, "run_id": run_id},
                     f"run failed: {type(exc).__name__}", "agent_error")
        raise HTTPException(status_code=502, detail={
            "error": "The agent team could not complete this ticket.",
            "stop_reason": type(exc).__name__, "run_id": run_id,
            "ticket_status": current, "message": str(exc),
        }) from exc

    # Stage is derived from what actually happened, not from the Boss's say-so.
    # Actions are gathered from the findings as well as the top level: a
    # specialist can attach a proposal that the Boss fails to echo upward, and
    # the backend must not under-report an action awaiting a human because of
    # that.
    all_actions = list(outcome.proposed_actions)
    seen = {(a.proposal_id, a.description) for a in all_actions}
    for finding in outcome.findings:
        for action in finding.proposed_actions:
            if (action.proposal_id, action.description) not in seen:
                all_actions.append(action)
                seen.add((action.proposal_id, action.description))
    outcome.proposed_actions = all_actions
    if all_actions:
        outcome.needs_human_approval = True
        stage = "awaiting_human_approval"
    elif any(f.needs_human_approval for f in outcome.findings) or outcome.needs_human_approval:
        stage = "awaiting_human_approval"
    else:
        stage = "investigated"

    if body.mark_in_progress:
        await call_tool("update_ticket_status", {
            "ticket_id": ticket_id, "status": "in_progress",
            "note": f"Reviewed by agent team (run {run_id}).",
        })

    ticket_status = (await call_tool("get_ticket", {"ticket_id": ticket_id}))["ticket"]["status"]
    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")

    run = TicketRun(
        run_id=run_id, ticket_id=ticket_id, started_at=started, finished_at=finished,
        stage=stage, ticket_status=ticket_status, outcome=outcome,
    )
    store.append(json.loads(run.model_dump_json()))
    audit.record(
        "backend.process_ticket",
        {"ticket_id": ticket_id, "run_id": run_id,
         "specialists": ",".join(outcome.specialists_consulted)},
        f"stage={stage}; {len(outcome.proposed_actions)} proposed action(s)",
        "completed",
    )
    return run


@app.get("/api/runs", tags=["tickets"])
async def list_runs(ticket_id: int | None = None) -> dict:
    """Past processing runs, for the dashboard to show without re-running agents."""
    runs = store.list_runs(ticket_id)
    return {"runs": runs, "count": len(runs)}


@app.get("/api/runs/{run_id}", tags=["tickets"])
async def get_run(run_id: str) -> dict:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No such run: {run_id}")
    return run


# ------------------------- operator routes --------------------------------
# Everything below requires authentication. Agents have no path here: these are
# HTTP routes, not MCP tools, and the team has no HTTP client.

@app.get("/api/operator/whoami", tags=["operator"])
async def whoami(principal: str = Depends(require_operator)) -> dict:
    """Confirm a token is valid and show the identity approvals will be recorded under."""
    return {"authenticated": True, "principal": principal}


@app.post("/api/operator/proposals/{proposal_id}/approve", tags=["operator"])
async def approve_proposal(proposal_id: str, body: ApprovalRequest,
                           principal: str = Depends(require_operator)) -> dict:
    """Grant human approval for one exact proposal. **Authenticated operators only.**

    `approved_by` is the authenticated principal — not a client-supplied string.
    The amount must match the proposal exactly. Approval records an HMAC
    signature the agents cannot forge (harness §B4); it does not itself move
    money, which still requires a separate execute call.
    """
    try:
        updated = approval.grant(proposal_id, body.approved_amount, principal)
    except approval.ApprovalError as exc:
        audit.record("backend.approve", {"proposal_id": proposal_id, "principal": principal},
                     str(exc), "approval_refused")
        raise HTTPException(status_code=409, detail={"error": str(exc),
                                                     "stop_reason": "approval_refused"}) from exc
    return {"ok": True, "proposal": _public_proposal(updated),
            "next_step": "POST /api/operator/proposals/{id}/execute to carry it out."}


@app.post("/api/operator/proposals/{proposal_id}/reject", tags=["operator"])
async def reject_proposal(proposal_id: str, body: RejectRequest,
                          principal: str = Depends(require_operator)) -> dict:
    """Record a human decision not to proceed. Changes no business data."""
    existing = proposals.get(proposal_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No such proposal: {proposal_id}")
    if existing["status"] == proposals.STATUS_EXECUTED:
        raise HTTPException(status_code=409,
                            detail={"error": f"Proposal {proposal_id} was already executed.",
                                    "stop_reason": "already_executed"})
    updated = proposals.mark(proposal_id, proposals.STATUS_REJECTED, principal,
                             {"reason": body.reason})
    audit.record("backend.reject", {"proposal_id": proposal_id, "principal": principal},
                 f"{proposal_id} rejected", "completed")
    return {"ok": True, "proposal": _public_proposal(updated)}


@app.post("/api/operator/proposals/{proposal_id}/execute", tags=["operator"])
async def execute_proposal(proposal_id: str,
                           principal: str = Depends(require_operator)) -> dict:
    """Carry out an approved proposal. **Authenticated operators only.**

    Delegates to the MCP `execute_payment` / `execute_purchase` tools, which
    re-verify the server-issued approval signature, re-check the balance inside
    the transaction, and refuse a second execution. This route adds
    authentication; it does not weaken any of those guarantees.
    """
    p = proposals.get(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"No such proposal: {proposal_id}")

    tool = "execute_payment" if p["kind"] == "payment" else "execute_purchase"
    result = await call_tool(tool, {"proposal_id": proposal_id})
    if result.get("ok") is False:
        audit.record("backend.execute", {"proposal_id": proposal_id, "principal": principal},
                     result.get("error", ""), result.get("stop_reason", "error"))
        code = 403 if result.get("stop_reason") == "approval_rejected" else 409
        raise HTTPException(status_code=code, detail={"error": result.get("error"),
                                                      "stop_reason": result.get("stop_reason")})
    return {"ok": True, "result": result, "executed_by": principal}


@app.get("/api/audit", tags=["observability"])
async def audit_trail(limit: int = 100, tool: str | None = None) -> dict:
    """Recent audit entries — what the system actually did, newest last.

    Read-only and never written here, so the history cannot be edited through
    the API.
    """
    path = audit.AUDIT_PATH
    if not path.is_file():
        return {"entries": [], "count": 0}
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Audit trail is unreadable.") from None
    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    return {"entries": entries[-max(1, min(limit, 1000)):], "count": len(entries)}
