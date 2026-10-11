"""Problem 9 follow-up: the purchase-proposal permission fix.

Ticket 103 revealed that `propose_purchase` was in no specialist's allow-list,
so the agent team could not prepare a restock purchase at all. These tests pin
the correction and the limits around it.

Everything that writes runs against a **disposable copy** — temp database, temp
proposals file, temp audit log — selected by environment variable before any
module is imported. The real working database, proposals, and audit trail are
never touched, and no purchase, payment, or approval is performed.

Run:  .venv/bin/python tests/verify_purchase_permissions.py
"""

from __future__ import annotations

import asyncio
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
REAL_PROPOSALS = PROJECT_ROOT / "output" / "proposals.json"
REAL_PREDICTIONS = PROJECT_ROOT / "output" / "predictions.md"
RUN_103 = PROJECT_ROOT / "output" / "run_103.json"

SANDBOX = Path(tempfile.mkdtemp(prefix="cc-p9fix-"))
shutil.copy2(REAL_DB, SANDBOX / "sandbox.db")
os.environ["CAMPUS_CUSTOMS_DB_PATH"] = str(SANDBOX / "sandbox.db")
os.environ["CAMPUS_CUSTOMS_PROPOSALS_PATH"] = str(SANDBOX / "proposals.json")
os.environ["CAMPUS_CUSTOMS_AUDIT_PATH"] = str(SANDBOX / "audit_trail.json")

from pydantic_ai import RunContext  # noqa: E402
from pydantic_ai.usage import RunUsage  # noqa: E402

from agents.mcp_client import FORBIDDEN_TOOL_NAMES, inprocess_toolset  # noqa: E402
from agents.team import SPECIALIST_TOOLS, CampusCustomsTeam  # noqa: E402

PASS, FAIL = [], []
EXECUTE_TOOLS = {"execute_payment", "execute_purchase"}


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def tools_visible_to(agent) -> set[str]:
    names: set[str] = set()
    for toolset in agent.toolsets:
        ctx = RunContext(deps=None, model=agent.model, usage=RunUsage())
        async with toolset:
            names |= set(await toolset.get_tools(ctx))
    return names


async def main() -> int:
    original_before = sha256(REAL_ORIGINAL)
    working_before = sha256(REAL_DB)
    audit_before = json.loads(REAL_AUDIT.read_text())
    proposals_before = json.loads(REAL_PROPOSALS.read_text())
    predictions_before = sha256(REAL_PREDICTIONS)
    run103_before = sha256(RUN_103)

    team = CampusCustomsTeam.build()

    print("\n[1] the defect is fixed: a specialist can now propose a purchase")
    inv = await tools_visible_to(team.specialists["inventory"])
    check("Inventory can reach propose_purchase", "propose_purchase" in inv)
    visible_by_role = {r: await tools_visible_to(a) for r, a in team.specialists.items()}
    check("purchase proposing is reachable by the team at all",
          any("propose_purchase" in v for v in visible_by_role.values()))

    print("\n[2] Inventory keeps the inputs propose_purchase needs")
    for tool in ("lookup_inventory", "get_pricing", "list_vendors", "get_today"):
        check(f"Inventory still has {tool}", tool in inv)

    print("\n[3] Accounting gained read-only inventory, nothing more")
    acct = await tools_visible_to(team.specialists["accounting"])
    check("Accounting can read inventory for shortfall maths", "lookup_inventory" in acct)
    check("Accounting still CANNOT propose a purchase", "propose_purchase" not in acct)
    check("Accounting keeps propose_payment", "propose_payment" in acct)

    print("\n[4] the fix granted no execution or approval authority")
    for role in SPECIALIST_TOOLS:
        visible = await tools_visible_to(team.specialists[role])
        check(f"{role} cannot execute payments or purchases", not visible & EXECUTE_TOOLS)
        check(f"{role} has no approval-granting tool", not visible & FORBIDDEN_TOOL_NAMES)

    print("\n[5] the blast radius is exactly two tools")
    expected = {
        "inventory": {"propose_purchase", "list_proposals"},
        "accounting": {"lookup_inventory"},
        "facilities": set(),
        "customer_service": set(),
    }
    baseline = {
        "inventory": {"get_today", "lookup_inventory", "get_pricing", "list_vendors",
                      "get_ticket", "list_tickets"},
        "accounting": {"get_today", "get_cash_balance", "list_invoices", "get_invoice",
                       "list_payments", "list_leases", "get_lease", "get_pricing",
                       "propose_payment", "list_proposals", "get_ticket"},
        "facilities": {"get_today", "list_leases", "get_lease", "list_payments",
                       "get_ticket", "list_tickets"},
        "customer_service": {"get_today", "list_tickets", "get_ticket", "lookup_inventory",
                             "get_pricing"},
    }
    for role in SPECIALIST_TOOLS:
        added = SPECIALIST_TOOLS[role] - baseline[role]
        removed = baseline[role] - SPECIALIST_TOOLS[role]
        check(f"{role} added exactly {sorted(expected[role]) or 'nothing'}",
              added == expected[role], f"added={sorted(added)}")
        check(f"{role} lost no tool", not removed, f"removed={sorted(removed)}")

    print("\n[6] the tool still refuses what it refused before (disposable copy)")
    toolset = inprocess_toolset()
    async with toolset:
        call = toolset.direct_call_tool

        # Ticket 103's real shortfall, priced by the tool rather than the caller.
        good = await call("propose_purchase", {
            "sku": "CC-HOOD-NAVY", "size": "M", "qty": 12, "vendor_id": 1})
        check("a valid shortfall purchase can be proposed", good["ok"] is True,
              good.get("error", ""))
        check("cost is computed server-side as 12 x 22.00 = 264.00",
              good["proposal"]["amount"] == 264.0, str(good["proposal"].get("amount")))
        check("arrival is shop date + lead_days, not guessed",
              good["expected_arrival"] == "2026-09-05", str(good.get("expected_arrival")))
        check("the proposal is inert and needs a human",
              good["proposal"]["status"] == "pending_human_approval"
              and good["requires_human_approval"] is True)
        check("no approval signature is handed to the agent",
              good["proposal"].get("approval") is None)

        with sqlite3.connect(SANDBOX / "sandbox.db") as c:
            qty = c.execute(
                "SELECT qty FROM inventory WHERE sku='CC-HOOD-NAVY' AND size='M'").fetchone()[0]
            bal = c.execute(
                "SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
            pays = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        check("proposing ordered no stock", qty == 8, f"qty={qty}")
        check("proposing moved no money", bal == 3400.0 and pays == 0)

        # Guards that must survive the permission change.
        bad = await call("propose_purchase", {
            "sku": "CC-HOOD-NAVY", "size": "XXL", "qty": 5, "vendor_id": 1})
        check("an unknown (sku,size) is still refused",
              bad["ok"] is False and bad["stop_reason"] == "not_found")
        bad = await call("propose_purchase", {
            "sku": "CC-HOOD-NAVY", "size": "M", "qty": 0, "vendor_id": 1})
        check("a non-positive qty is still refused", bad["ok"] is False)
        bad = await call("propose_purchase", {
            "sku": "CC-HOOD-NAVY", "size": "M", "qty": 5, "vendor_id": 999})
        check("an unknown vendor is still refused", bad["ok"] is False)
        poor = await call("propose_purchase", {
            "sku": "CC-HOOD-NAVY", "size": "M", "qty": 200, "vendor_id": 1})
        check("a purchase beyond the balance is still refused",
              poor["ok"] is False and poor["stop_reason"] == "insufficient_funds",
              poor.get("error", ""))

        # The approval boundary is unchanged by this fix.
        unapproved = await call("execute_purchase",
                                {"proposal_id": good["proposal"]["proposal_id"]})
        check("an unapproved purchase still cannot execute",
              unapproved["ok"] is False and unapproved["stop_reason"] == "approval_rejected")
        with sqlite3.connect(SANDBOX / "sandbox.db") as c:
            qty = c.execute(
                "SELECT qty FROM inventory WHERE sku='CC-HOOD-NAVY' AND size='M'").fetchone()[0]
        check("the refused execution added no stock", qty == 8)

    print("\n[7] ticket 103's evidence is preserved intact")
    check("output/run_103.json is unchanged", sha256(RUN_103) == run103_before)
    check("output/predictions.md is unchanged", sha256(REAL_PREDICTIONS) == predictions_before)
    check("the real audit trail is unchanged",
          json.loads(REAL_AUDIT.read_text()) == audit_before, f"{len(audit_before)} entries")
    check("the real proposal ledger is unchanged",
          json.loads(REAL_PROPOSALS.read_text()) == proposals_before)
    # The invariant is that THIS TEST changes nothing, not that the ledger holds
    # any particular set of human decisions — those are the operator's and
    # legitimately change over time. What must never be true is that a test
    # advanced a proposal or executed one.
    proposals_after = json.loads(REAL_PROPOSALS.read_text())
    check("no proposal was approved, rejected, or executed by this test",
          proposals_after == proposals_before,
          f"{len(proposals_after)} proposal(s), unchanged")
    check("no proposal in the real ledger is in an executed state",
          not any(p["status"] == "executed" for p in proposals_after),
          ", ".join(f"{p['proposal_id']}={p['status']}" for p in proposals_after))

    print("\n[8] the real databases are untouched")
    check("original campus_customs.db unchanged", sha256(REAL_ORIGINAL) == original_before)
    check("real working database unchanged", sha256(REAL_DB) == working_before)
    with sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True) as c:
        n_open = c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
        hood = c.execute(
            "SELECT qty FROM inventory WHERE sku='CC-HOOD-NAVY' AND size='M'").fetchone()[0]
        pays = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    check("all three tickets still open", n_open == 3)
    check("real CC-HOOD-NAVY/M still 8", hood == 8)
    check("no payments in the real database", pays == 0)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)
