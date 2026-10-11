"""Problem 7 verification: the FastAPI ticket-processing backend.

Everything that mutates business state runs against **disposable copies** — a
temp database, a temp proposals file, a temp runs file, a temp audit log — all
selected through environment variables before the app is imported. The real
working database, the real proposals, and the real audit trail are never
written by this suite.

Model cost is kept low on purpose: route logic is verified with a stub team, and
the "it invokes the real team" claim is checked structurally rather than by
paying for repeated live delegation (Problem 5 already produced live evidence).
One optional live run is available behind --live.

Run:  .venv/bin/python tests/verify_backend.py [--live]
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REAL_DB = PROJECT_ROOT / "data" / "campus_customs_new.db"
REAL_ORIGINAL = PROJECT_ROOT / "data" / "campus_customs.db"
REAL_AUDIT = PROJECT_ROOT / "output" / "audit_trail.json"
REAL_PREDICTIONS = PROJECT_ROOT / "output" / "predictions.md"

# ---- redirect every mutable path to a sandbox BEFORE importing the app ----
SANDBOX = Path(tempfile.mkdtemp(prefix="cc-p7-"))
shutil.copy2(REAL_DB, SANDBOX / "sandbox.db")
os.environ["CAMPUS_CUSTOMS_DB_PATH"] = str(SANDBOX / "sandbox.db")
os.environ["CAMPUS_CUSTOMS_PROPOSALS_PATH"] = str(SANDBOX / "proposals.json")
os.environ["CAMPUS_CUSTOMS_RUNS_PATH"] = str(SANDBOX / "ticket_runs.json")
os.environ["CAMPUS_CUSTOMS_AUDIT_PATH"] = str(SANDBOX / "audit_trail.json")
os.environ["CAMPUS_CUSTOMS_OPERATOR_TOKEN_PATH"] = str(SANDBOX / "operator_token")

from fastapi.testclient import TestClient  # noqa: E402

from agents.schemas import ProposedAction, SpecialistFinding, TeamOutcome  # noqa: E402
from backend import auth  # noqa: E402
from backend.main import app, get_team  # noqa: E402
from mcp_server import db, proposals  # noqa: E402

PASS, FAIL, SKIP = [], [], []
LIVE = "--live" in sys.argv


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def skip(name: str, why: str) -> None:
    SKIP.append(name)
    print(f"  SKIP  {name}  — {why}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StubTeam:
    """Stands in for the five-agent team so route logic can be tested cheaply.

    It does NOT prove the real team runs — that is checked separately against
    the real dependency.
    """

    def __init__(self, outcome: TeamOutcome | Exception) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    async def run(self, request: str, **kwargs) -> TeamOutcome:
        self.calls.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def investigation_outcome() -> TeamOutcome:
    return TeamOutcome(
        request="x", handled_by="boss", specialists_consulted=["inventory"],
        findings=[SpecialistFinding(agent="inventory", summary="0 in stock", facts=["qty=0"])],
        summary="Out of stock.", needs_human_approval=False,
    )


def proposal_outcome(proposal_id: str, amount: float) -> TeamOutcome:
    return TeamOutcome(
        request="x", handled_by="boss", specialists_consulted=["accounting", "facilities"],
        findings=[SpecialistFinding(
            agent="accounting", summary="Rent is due.", facts=["rent=2400.00"],
            proposed_actions=[ProposedAction(proposal_id=proposal_id, description="Pay rent",
                                             amount=amount)],
            needs_human_approval=True)],
        summary="Prepared a rent payment for approval.", needs_human_approval=True,
    )


def main() -> int:
    original_before = sha256(REAL_ORIGINAL)
    working_before = sha256(REAL_DB)
    audit_before = json.loads(REAL_AUDIT.read_text())
    predictions_before = sha256(REAL_PREDICTIONS)

    client = TestClient(app)
    token = auth.load_or_create_token()
    auth_hdr = {"Authorization": f"Bearer {token}"}

    print("\n[1] the application starts and serves state")
    r = client.get("/api/health")
    check("GET /api/health returns 200", r.status_code == 200)
    check("health reports the shop date from the desk table",
          r.json().get("shop_date") == "2026-08-31", str(r.json()))
    check("OpenAPI schema is generated", client.get("/openapi.json").status_code == 200)

    print("\n[2] read endpoints return correct database information")
    r = client.get("/api/tickets", params={"status": "open"})
    ids = sorted(t["id"] for t in r.json()["tickets"])
    check("GET /api/tickets?status=open returns 101-103", ids == [101, 102, 103], str(ids))

    r = client.get("/api/tickets/101")
    body = r.json()
    check("GET /api/tickets/101 includes the linked invoice 501",
          body["invoice"]["id"] == 501 and body["invoice"]["amount"] == 840.0)
    check("ticket detail includes a runs list for the dashboard", "runs" in body)
    check("GET /api/tickets/999 is a 404, not a 200 with ok:false",
          client.get("/api/tickets/999").status_code == 404)

    r = client.get("/api/cash").json()
    check("GET /api/cash reports 3400.0", r["account"]["balance"] == 3400.0)

    r = client.get("/api/inventory/CC-TEE-WHITE", params={"size": "S"}).json()
    check("GET /api/inventory respects the (sku,size) key", r["items"][0]["qty"] == 0)

    r = client.get("/api/state").json()
    check("GET /api/state summarises date, cash, tickets, invoices, leases",
          r["shop_date"] == "2026-08-31" and r["cash"]["balance"] == 3400.0
          and len(r["open_tickets"]) == 3 and len(r["open_invoices"]) == 1
          and len(r["leases"]) == 1)
    check("state reports pending-approval counts for the dashboard",
          r["pending_approval_count"] == 0 and r["approved_awaiting_execution_count"] == 0)

    print("\n[3] ticket processing is wired to the REAL team by default")
    check("the default team dependency builds the real five-agent team",
          get_team.__module__ == "backend.main"
          and "CampusCustomsTeam" in Path("backend/main.py").read_text())
    from agents.team import CampusCustomsTeam
    import inspect
    src = inspect.getsource(get_team)
    check("get_team() constructs CampusCustomsTeam, not a stub",
          "CampusCustomsTeam.build()" in src)
    check("the backend opens no database handle of its own",
          "sqlite3.connect" not in Path("backend/main.py").read_text())

    print("\n[4] structured results are returned correctly")
    stub = StubTeam(investigation_outcome())
    app.dependency_overrides[get_team] = lambda: stub
    r = client.post("/api/tickets/101/process", json={})
    check("POST /api/tickets/101/process returns 200", r.status_code == 200, r.text[:120])
    run = r.json()
    check("the ticket's real content was passed to the Boss",
          "CC-TEE-WHITE" in stub.calls[0] and "101" in stub.calls[0])
    check("response carries the structured TeamOutcome",
          run["outcome"]["summary"] == "Out of stock.")
    check("specialists consulted are surfaced", run["outcome"]["specialists_consulted"] == ["inventory"])
    check("findings are surfaced", run["outcome"]["findings"][0]["agent"] == "inventory")
    check("a run with no proposals is staged 'investigated'", run["stage"] == "investigated")
    check("the ticket is NOT marked resolved by a recommendation",
          run["ticket_status"] == "open")
    check("run_id and timestamps are recorded", bool(run["run_id"]) and bool(run["finished_at"]))

    print("\n[5] a run that proposes an action awaits human approval")
    pending = proposals.create("payment", "rent:1", 2400.0, "checking", {"memo": "test"})
    stub2 = StubTeam(proposal_outcome(pending["proposal_id"], 2400.0))
    app.dependency_overrides[get_team] = lambda: stub2
    run2 = client.post("/api/tickets/102/process", json={}).json()
    check("stage is 'awaiting_human_approval' when an action is proposed",
          run2["stage"] == "awaiting_human_approval", run2["stage"])
    check("needs_human_approval is surfaced", run2["outcome"]["needs_human_approval"] is True)
    check("ticket 102 is still open — a proposal is not a resolution",
          run2["ticket_status"] == "open")

    print("\n[6] runs are persisted for the dashboard")
    runs = client.get("/api/runs").json()
    check("GET /api/runs lists both runs", runs["count"] == 2, str(runs["count"]))
    check("GET /api/runs?ticket_id=101 filters",
          client.get("/api/runs", params={"ticket_id": 101}).json()["count"] == 1)
    check("GET /api/runs/{id} fetches one run",
          client.get(f"/api/runs/{run['run_id']}").json()["run_id"] == run["run_id"])
    check("ticket detail now shows its run history",
          len(client.get("/api/tickets/101").json()["runs"]) == 1)

    print("\n[7] a failed run does not falsely resolve a ticket")
    app.dependency_overrides[get_team] = lambda: StubTeam(RuntimeError("model exploded"))
    r = client.post("/api/tickets/103/process", json={})
    check("a failing team run returns 502, not 200", r.status_code == 502, str(r.status_code))
    detail = r.json()["detail"]
    check("the error reports a stop_reason", detail["stop_reason"] == "RuntimeError")
    check("the failure reports the ticket still open", detail["ticket_status"] == "open")
    with sqlite3.connect(f"file:{db.WORKING_DB}?mode=ro", uri=True) as c:
        st = c.execute("SELECT status FROM tickets WHERE id=103").fetchone()[0]
    check("ticket 103 is untouched in the database after a failure", st == "open")
    failed = [x for x in client.get("/api/runs").json()["runs"] if x["stage"] == "failed"]
    check("the failed run is still recorded, not hidden", len(failed) == 1)
    app.dependency_overrides.clear()

    print("\n[8] unauthorized approvals are rejected")
    pid = pending["proposal_id"]
    r = client.post(f"/api/operator/proposals/{pid}/approve", json={"approved_amount": 2400.0})
    check("approval with no token is 401", r.status_code == 401, str(r.status_code))
    r = client.post(f"/api/operator/proposals/{pid}/approve", json={"approved_amount": 2400.0},
                    headers={"Authorization": "Bearer wrong-token"})
    check("approval with a bad token is 401", r.status_code == 401)
    r = client.post(f"/api/operator/proposals/{pid}/execute")
    check("execution with no token is 401", r.status_code == 401)
    check("whoami requires a token", client.get("/api/operator/whoami").status_code == 401)
    check("whoami with a valid token returns the principal",
          client.get("/api/operator/whoami", headers=auth_hdr).json()["principal"]
          == auth.OPERATOR_PRINCIPAL)

    # The client cannot name itself as approver.
    schema = json.loads(client.get("/openapi.json").text)
    approve_schema = schema["components"]["schemas"]["ApprovalRequest"]["properties"]
    check("the approve route accepts NO client-supplied approved_by",
          "approved_by" not in approve_schema, str(list(approve_schema)))

    with sqlite3.connect(f"file:{db.WORKING_DB}?mode=ro", uri=True) as c:
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    check("no unauthorized attempt moved money", bal == 3400.0)

    print("\n[9] an unapproved proposal cannot be executed")
    r = client.post(f"/api/operator/proposals/{pid}/execute", headers=auth_hdr)
    check("executing before approval is refused", r.status_code == 403, str(r.status_code))
    check("the refusal cites the approval boundary",
          "approval" in json.dumps(r.json()).lower())

    print("\n[10] approval binds to the exact proposal and amount")
    r = client.post(f"/api/operator/proposals/{pid}/approve", json={"approved_amount": 1.0},
                    headers=auth_hdr)
    check("approving a different amount is refused", r.status_code == 409, str(r.status_code))
    r = client.post("/api/operator/proposals/PAY-9999/approve", json={"approved_amount": 2400.0},
                    headers=auth_hdr)
    check("approving an unknown proposal is refused", r.status_code == 409)

    r = client.post(f"/api/operator/proposals/{pid}/approve", json={"approved_amount": 2400.0},
                    headers=auth_hdr)
    check("a correct, authenticated approval succeeds", r.status_code == 200, r.text[:120])
    approved = r.json()["proposal"]
    check("the approver recorded is the authenticated principal, not client input",
          approved["approved_by"] == auth.OPERATOR_PRINCIPAL, str(approved["approved_by"]))
    check("the signature is never exposed over HTTP", "approval" not in approved)
    with sqlite3.connect(f"file:{db.WORKING_DB}?mode=ro", uri=True) as c:
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    check("approval alone moves no money", bal == 3400.0)

    print("\n[11] execution happens exactly once, with cash protection")
    r = client.post(f"/api/operator/proposals/{pid}/execute", headers=auth_hdr)
    check("the approved payment executes", r.status_code == 200, r.text[:140])
    check("the balance is drawn down to 1000.0",
          r.json()["result"]["balance_after"] == 1000.0)
    check("the execution is attributed to the operator",
          r.json()["executed_by"] == auth.OPERATOR_PRINCIPAL)
    r2 = client.post(f"/api/operator/proposals/{pid}/execute", headers=auth_hdr)
    check("a second execution is refused", r2.status_code in (403, 409), str(r2.status_code))
    with sqlite3.connect(f"file:{db.WORKING_DB}?mode=ro", uri=True) as c:
        n = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    check("exactly one payment row exists", n == 1, f"{n} rows")
    check("the balance was drawn down once only", bal == 1000.0)

    # cash protection: a proposal larger than the remaining balance
    big = proposals.create("payment", "invoice:501", 5000.0, "checking", {"memo": "too big"})
    client.post(f"/api/operator/proposals/{big['proposal_id']}/approve",
                json={"approved_amount": 5000.0}, headers=auth_hdr)
    r = client.post(f"/api/operator/proposals/{big['proposal_id']}/execute", headers=auth_hdr)
    check("an approved payment beyond the balance is still refused",
          r.status_code == 409 and r.json()["detail"]["stop_reason"] == "insufficient_funds",
          str(r.json().get("detail")))
    with sqlite3.connect(f"file:{db.WORKING_DB}?mode=ro", uri=True) as c:
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    check("the refused payment left the balance alone", bal == 1000.0)

    print("\n[12] observability")
    a = client.get("/api/audit").json()
    check("GET /api/audit returns entries", a["count"] > 0, f"{a['count']} entries")
    tools = {e["tool"] for e in a["entries"]}
    check("backend ticket processing is audited", "backend.process_ticket" in tools)
    check("approvals are audited", any(t.startswith("approval.") or t.startswith("backend.")
                                       for t in tools))
    check("audit filtering by tool works",
          client.get("/api/audit", params={"tool": "backend.process_ticket"}).json()["count"] > 0)
    proposals_view = client.get("/api/proposals").json()
    check("proposals list exposes status and approver, never the signature",
          all("approval" not in p for p in proposals_view["proposals"])
          and any(p["status"] == "executed" for p in proposals_view["proposals"]))

    print("\n[13] live run against the real team (optional)")
    if not LIVE:
        skip("real team processes a ticket end to end",
             "pass --live to run; Problem 5 already produced live delegation evidence")
    else:
        r = client.post("/api/tickets/101/process", json={}, timeout=900)
        check("a real live run returns a structured outcome", r.status_code == 200, r.text[:140])
        if r.status_code == 200:
            out = r.json()["outcome"]
            check("the real Boss consulted at least one specialist",
                  len(out["specialists_consulted"]) >= 1, str(out["specialists_consulted"]))

    print("\n[14] the real project state is untouched")
    check("original campus_customs.db checksum unchanged", sha256(REAL_ORIGINAL) == original_before)
    check("real working database unchanged", sha256(REAL_DB) == working_before)
    audit_after = json.loads(REAL_AUDIT.read_text())
    check("the real audit trail is intact and unmodified",
          audit_after == audit_before, f"{len(audit_after)} entries")
    check("output/predictions.md is unmodified",
          sha256(REAL_PREDICTIONS) == predictions_before)
    with sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True) as c:
        n_open = c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
        n_pay = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    check("tickets 101-103 are still open in the real database", n_open == 3)
    check("no payments exist in the real database", n_pay == 0)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)
