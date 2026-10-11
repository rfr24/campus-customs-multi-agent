"""Targeted verification for the Problem 3 MCP server.

Read checks run against the real working copy. Every write check runs against a
*disposable* copy of the database and a disposable proposals file, so the real
working database is never mutated by the test suite. The original
data/campus_customs.db is checksummed before and after.

Run:  .venv/bin/python tests/verify_mcp.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._isolation import assert_audit_isolated, isolate_audit

# Must run before any mcp_server import: the audit module resolves its path at
# import time, so a later redirect would be too late.
isolate_audit()

from fastmcp import Client  # noqa: E402

from mcp_server import approval, db, proposals  # noqa: E402
from mcp_server.server import mcp  # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def call(client: Client, tool: str, **kwargs) -> dict:
    result = await client.call_tool(tool, kwargs)
    return result.data


async def main() -> int:
    original_before = sha256(db.ORIGINAL_DB)
    working_before = sha256(db.WORKING_DB)

    print("\n[0] this test run cannot touch the production audit trail")
    assert_audit_isolated()
    check("audit writes are redirected away from output/audit_trail.json", True,
          "isolated via CAMPUS_CUSTOMS_AUDIT_PATH")

    print("\n[1] server starts and tools are discoverable")
    async with Client(mcp) as client:
        tools = sorted(t.name for t in await client.list_tools())
        check("server responds to list_tools", len(tools) > 0, f"{len(tools)} tools")
        for expected in ("get_today", "get_ticket", "lookup_inventory", "get_cash_balance",
                         "propose_payment", "execute_payment", "propose_purchase",
                         "execute_purchase"):
            check(f"tool exposed: {expected}", expected in tools)

        print("\n[2] shop clock comes from the desk table")
        today = await call(client, "get_today")
        check("get_today == 2026-08-31", today.get("date_today") == "2026-08-31",
              str(today.get("date_today")))

        print("\n[3] read tools return accurate data for tickets 101-103")
        t101 = await call(client, "get_ticket", ticket_id=101)
        check("101 is a customer_order for CC-TEE-WHITE/S",
              t101["ticket"]["type"] == "customer_order"
              and t101["ticket"]["sku"] == "CC-TEE-WHITE"
              and t101["ticket"]["size"] == "S")
        check("101 joins invoice 501 for 840.0",
              t101["invoice"] and t101["invoice"]["id"] == 501
              and t101["invoice"]["amount"] == 840.0)

        t102 = await call(client, "get_ticket", ticket_id=102)
        check("102 is a rent_notice on lease 1",
              t102["ticket"]["type"] == "rent_notice" and t102["ticket"]["lease_id"] == 1)
        check("102 lease rent is 2400.0 due 2026-09-02",
              t102["lease"]["monthly_rent"] == 2400.0
              and t102["lease"]["next_due"] == "2026-09-02")

        t103 = await call(client, "get_ticket", ticket_id=103)
        check("103 is a price_override for 20x CC-HOOD-NAVY/M",
              t103["ticket"]["type"] == "price_override"
              and t103["ticket"]["qty"] == 20 and t103["ticket"]["size"] == "M")

        open_tickets = await call(client, "list_tickets", status="open")
        check("three open tickets listed", open_tickets["count"] == 3,
              f"count={open_tickets['count']}")

        print("\n[4] inventory respects the composite (sku, size) key")
        tee_s = await call(client, "lookup_inventory", sku="CC-TEE-WHITE", size="S")
        check("CC-TEE-WHITE/S qty is 0", tee_s["items"][0]["qty"] == 0)
        tee_m = await call(client, "lookup_inventory", sku="CC-TEE-WHITE", size="M")
        check("CC-TEE-WHITE/M qty is 5 (same sku, different size)", tee_m["items"][0]["qty"] == 5)
        hood_m = await call(client, "lookup_inventory", sku="CC-HOOD-NAVY", size="M")
        check("CC-HOOD-NAVY/M qty is 8, short of the 20 on ticket 103",
              hood_m["items"][0]["qty"] == 8)
        all_tee = await call(client, "lookup_inventory", sku="CC-TEE-WHITE")
        check("size-less lookup returns all 4 sizes", all_tee["count"] == 4)
        bad_size = await call(client, "lookup_inventory", sku="CC-TEE-WHITE", size="XXL")
        check("unknown size is refused, not silently matched",
              bad_size["ok"] is False and bad_size["stop_reason"] == "not_found")
        lower = await call(client, "lookup_inventory", sku="cc-tee-white", size="s")
        check("sku/size are normalised before the query", lower["ok"] is True)

        print("\n[5] cash balance reads correctly")
        cash = await call(client, "get_cash_balance", account="checking")
        check("checking balance is 3400.0", cash["account"]["balance"] == 3400.0)
        missing = await call(client, "get_cash_balance", account="savings")
        check("unknown account is refused", missing["ok"] is False)

        print("\n[6] overdue / due-date maths uses the shop date")
        inv501 = await call(client, "get_invoice", invoice_id=501)
        check("invoice 501 is overdue by 3 days",
              inv501["invoice"]["overdue"] is True and inv501["invoice"]["days_to_due"] == -3,
              f"days_to_due={inv501['invoice']['days_to_due']}")
        lease1 = await call(client, "get_lease", lease_id=1)
        check("lease 1 is due in 2 days", lease1["lease"]["days_to_due"] == 2)

        print("\n[7] SQL injection attempt is parameterised away")
        inj = await call(client, "lookup_inventory", sku="CC-TEE-WHITE'; DROP TABLE inventory;--")
        check("injection string is treated as data", inj["ok"] is False
              and inj["stop_reason"] == "not_found")

    # ---- write-path checks on a disposable copy -------------------------
    print("\n[8] write and approval safeguards (disposable copy)")
    tmpdir = Path(tempfile.mkdtemp(prefix="cc-mcp-verify-"))
    try:
        sandbox_db = tmpdir / "sandbox.db"
        shutil.copy2(db.WORKING_DB, sandbox_db)
        db.WORKING_DB = sandbox_db
        proposals.PROPOSALS_PATH = tmpdir / "proposals.json"

        async with Client(mcp) as client:
            # proposing changes nothing
            prop = await call(client, "propose_payment", kind="rent", ref_id=1)
            check("propose_payment returns a pending proposal",
                  prop["ok"] and prop["proposal"]["status"] == "pending_human_approval")
            check("proposed amount is taken from the lease, not the caller",
                  prop["proposal"]["amount"] == 2400.0)
            check("no approval material is handed to the agent",
                  "approval_token" not in prop["proposal"]
                  and prop["proposal"].get("approval") is None)
            with sqlite3.connect(sandbox_db) as c:
                moved = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
                n_pay = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
            check("proposing moved no money", moved == 3400.0 and n_pay == 0)

            pid = prop["proposal"]["proposal_id"]

            print("\n[8a] an agent cannot manufacture approval")
            # The MCP surface must expose no way to grant approval.
            tool_names = {t.name for t in await client.list_tools()}
            check("no approval-granting tool is exposed over MCP",
                  not {"grant_approval", "approve_proposal", "approve"} & tool_names)

            # Direct execution of an unapproved proposal.
            direct = await call(client, "execute_payment", proposal_id=pid)
            check("executing an unapproved proposal is refused",
                  direct["ok"] is False and direct["stop_reason"] == "approval_rejected",
                  direct.get("error", ""))

            # The old gap: recomputing sha256 over public proposal fields.
            p_rec = proposals.get(pid)
            forged_hash = hashlib.sha256(
                f"{pid}|{p_rec['kind']}|{p_rec['target']}|{p_rec['amount']:.2f}|"
                f"{p_rec['account']}".encode()
            ).hexdigest()[:32]
            proposals.attach_approval(pid, {
                "approved_by": "Totally A Human",
                "approved_at": "2026-08-31T00:00:00+00:00",
                "nonce": "deadbeef",
                "signature": forged_hash,
            })
            forged = await call(client, "execute_payment", proposal_id=pid)
            check("approval forged from a public-field hash is refused",
                  forged["ok"] is False and forged["stop_reason"] == "approval_rejected",
                  forged.get("error", ""))

            # A fabricated approved_by with no valid signature at all.
            proposals.attach_approval(pid, {
                "approved_by": "Rachel Rosenberg",
                "approved_at": "2026-08-31T00:00:00+00:00",
                "nonce": "0" * 16,
                "signature": "f" * 64,
            })
            fabricated = await call(client, "execute_payment", proposal_id=pid)
            check("fabricated approved_by without a real signature is refused",
                  fabricated["ok"] is False and fabricated["stop_reason"] == "approval_rejected")

            # Status flipped straight to approved by editing the ledger.
            items = json.loads(proposals.PROPOSALS_PATH.read_text())
            for it in items:
                if it["proposal_id"] == pid:
                    it["approval"] = None
                    it["status"] = "approved"
            proposals.PROPOSALS_PATH.write_text(json.dumps(items))
            flipped = await call(client, "execute_payment", proposal_id=pid)
            check("hand-edited 'approved' status without a signature is refused",
                  flipped["ok"] is False and flipped["stop_reason"] == "approval_rejected")

            # A signature validly issued for a *different* proposal.
            other = await call(client, "propose_purchase", sku="CC-HOOD-NAVY", size="M",
                               qty=2, vendor_id=1)
            other_id = other["proposal"]["proposal_id"]
            approval.grant(other_id, other["proposal"]["amount"], "Rachel (test approver)")
            stolen = proposals.get(other_id)["approval"]
            proposals.attach_approval(pid, stolen)
            replayed = await call(client, "execute_payment", proposal_id=pid)
            check("an approval issued for another proposal cannot be transplanted",
                  replayed["ok"] is False and replayed["stop_reason"] == "approval_rejected")

            with sqlite3.connect(sandbox_db) as c:
                still = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
                n = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
            check("no forgery attempt moved money", still == 3400.0 and n == 0)

            print("\n[8b] a genuine, privileged approval works end to end")
            # Reset the proposal the forgery tests tampered with.
            items = json.loads(proposals.PROPOSALS_PATH.read_text())
            for it in items:
                if it["proposal_id"] == pid:
                    it["approval"] = None
                    it["status"] = "pending_human_approval"
            proposals.PROPOSALS_PATH.write_text(json.dumps(items))

            wrong_amt = False
            try:
                approval.grant(pid, 1.00, "Rachel (test approver)")
            except approval.ApprovalError:
                wrong_amt = True
            check("granting with an amount that differs from the proposal is refused", wrong_amt)

            no_name = False
            try:
                approval.grant(pid, 2400.0, "   ")
            except approval.ApprovalError:
                no_name = True
            check("granting without an authenticated identity is refused", no_name)

            granted = approval.grant(pid, 2400.0, "Rachel (test approver)")
            check("privileged grant marks the proposal approved",
                  granted["status"] == "approved" and granted["approval"]["signature"])
            check("list_proposals never discloses the signature",
                  all("approval" not in p for p in
                      (await call(client, "list_proposals"))["proposals"]))

            good = await call(client, "execute_payment", proposal_id=pid)
            check("correctly approved payment executes", good["ok"] is True, good.get("error", ""))
            check("balance drawn down atomically to 1000.0", good["balance_after"] == 1000.0)
            with sqlite3.connect(sandbox_db) as c:
                row = c.execute("SELECT kind, ref_id, amount, approved_by FROM payments").fetchall()
                due = c.execute("SELECT next_due FROM leases WHERE id=1").fetchone()[0]
            check("payment row records the approver from the signed approval, not the caller",
                  len(row) == 1 and row[0][3] == "Rachel (test approver)")
            check("lease rolled to the next month", due == "2026-10-02", due)

            # replay protection
            replay = await call(client, "execute_payment", proposal_id=pid)
            check("re-running an executed proposal is refused",
                  replay["ok"] is False and replay["stop_reason"] == "approval_rejected")
            with sqlite3.connect(sandbox_db) as c:
                n = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
            check("replay created no second payment", n == 1)

            regrant = False
            try:
                approval.grant(pid, 2400.0, "Rachel (test approver)")
            except approval.ApprovalError:
                regrant = True
            check("an executed proposal cannot be re-approved", regrant)

            # duplicate-payment guard at proposal time
            dup = await call(client, "propose_payment", kind="rent", ref_id=1)
            check("re-proposing an already-paid obligation is refused",
                  dup["ok"] is False and dup["stop_reason"] == "duplicate_payment")

            # insufficient funds
            poor = await call(client, "propose_purchase", sku="CC-HOOD-NAVY", size="M",
                              qty=100, vendor_id=1)
            check("purchase beyond the balance is refused (2200 > 1000)",
                  poor["ok"] is False and poor["stop_reason"] == "insufficient_funds",
                  poor.get("error", ""))

            # a fundable purchase, through the full approval path
            pur = await call(client, "propose_purchase", sku="CC-HOOD-NAVY", size="M",
                             qty=12, vendor_id=1)
            check("purchase cost computed from unit_cost (12 x 22 = 264)",
                  pur["ok"] and pur["proposal"]["amount"] == 264.0)
            check("expected arrival uses shop date + lead_days (5)",
                  pur["expected_arrival"] == "2026-09-05", str(pur.get("expected_arrival")))
            pur_id = pur["proposal"]["proposal_id"]
            check("unapproved purchase will not execute",
                  (await call(client, "execute_purchase", proposal_id=pur_id))["ok"] is False)
            approval.grant(pur_id, 264.0, "Rachel (test approver)")
            done = await call(client, "execute_purchase", proposal_id=pur_id)
            check("approved purchase raises stock and pays together",
                  done["ok"] and done["qty_after"] == 20 and done["balance_after"] == 736.0,
                  done.get("error", ""))

            # cross-kind misuse: a purchase approval spent as a payment
            pur2 = await call(client, "propose_purchase", sku="CC-HOOD-NAVY", size="L",
                              qty=1, vendor_id=1)
            approval.grant(pur2["proposal"]["proposal_id"], pur2["proposal"]["amount"],
                           "Rachel (test approver)")
            cross = await call(client, "execute_payment",
                               proposal_id=pur2["proposal"]["proposal_id"])
            check("a purchase approval cannot be spent as a payment", cross["ok"] is False)

            # the secret key is never exposed through a tool result
            dump = json.dumps(await call(client, "list_proposals"))
            check("approval key material never appears in tool output",
                  approval._load_key().hex() not in dump and "signature" not in dump)

            # validation
            bad_inv = await call(client, "propose_purchase", sku="CC-TEE-WHITE", size="XXL",
                                 qty=5, vendor_id=1)
            check("purchase for a non-existent (sku,size) is refused", bad_inv["ok"] is False)
            bad_qty = await call(client, "propose_purchase", sku="CC-TEE-WHITE", size="S",
                                 qty=0, vendor_id=1)
            check("non-positive qty is refused", bad_qty["ok"] is False)
            bad_vendor = await call(client, "propose_purchase", sku="CC-TEE-WHITE", size="S",
                                    qty=5, vendor_id=999)
            check("unknown vendor is refused", bad_vendor["ok"] is False)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        db.WORKING_DB = db.DATA_DIR / "campus_customs_new.db"
        proposals.PROPOSALS_PATH = Path(__file__).resolve().parent.parent / "output" / "proposals.json"

    print("\n[9] database integrity")
    check("original campus_customs.db checksum unchanged",
          sha256(db.ORIGINAL_DB) == original_before)
    check("working campus_customs_new.db unchanged by the test run",
          sha256(db.WORKING_DB) == working_before)
    check("tickets 101-103 are still open in the working copy",
          sqlite3.connect(f"file:{db.WORKING_DB}?mode=ro", uri=True)
          .execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0] == 3)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    for name in FAIL:
        print(f"  FAILED: {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
