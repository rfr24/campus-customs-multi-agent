"""Campus Customs shared MCP server.

One FastMCP server that all five agents (Boss, Inventory, Accounting,
Facilities, Customer Service) use for shop operations. No agent opens SQLite
directly: every read and every write goes through a tool here, so the safety
rules and the audit trail apply uniformly.

Run it:
    .venv/bin/python -m mcp_server.server            # stdio (agent transport)
    .venv/bin/fastmcp run mcp_server/server.py       # equivalent via the CLI

Safety model
  * All application data access targets data/campus_customs_new.db.
    data/campus_customs.db is the untouched original and is never written.
  * Read tools use a mode=ro connection; write tools use foreign-key
    enforcement inside a single atomic transaction.
  * Money and stock only move through an approved proposal. See proposals.py.
  * Every tool call is appended to output/audit_trail.json.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastmcp import FastMCP

from mcp_server import audit, proposals
from mcp_server.db import (
    DatabaseError,
    clamp_limit,
    read_conn,
    rows_to_dicts,
    shop_today,
    write_conn,
)

mcp = FastMCP(
    name="campus-customs",
    instructions=(
        "Shared operations server for the Campus Customs shop. Use get_today() for "
        "the shop's current date — never the host clock. Inventory is keyed by "
        "(sku, size). Money and stock change only through propose_*, then a human "
        "approving that proposal out of band, then execute_*. Agents cannot approve "
        "their own proposals; there is no tool here that grants approval."
    ),
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _ok(tool: str, args: dict[str, Any], summary: str, payload: dict) -> dict:
    audit.record(tool, args, summary, "completed")
    return {"ok": True, **payload}


def _fail(tool: str, args: dict[str, Any], reason: str, stop_reason: str) -> dict:
    audit.record(tool, args, reason, stop_reason)
    return {"ok": False, "error": reason, "stop_reason": stop_reason}


def _norm_sku(sku: str) -> str:
    return str(sku or "").strip().upper()


def _norm_size(size: str) -> str:
    return str(size or "").strip().upper()


# --------------------------------------------------------------------------
# read tools — shop clock and work queue
# --------------------------------------------------------------------------

@mcp.tool
def get_today() -> dict:
    """Return the shop's authoritative current date from the desk table.

    Every due-date, overdue, and lead-time calculation must start here rather
    than from the computer's clock.
    Reads: desk.
    """
    args: dict[str, Any] = {}
    try:
        with read_conn() as conn:
            today = shop_today(conn)
            row = conn.execute("SELECT notes FROM desk LIMIT 1").fetchone()
        return _ok("get_today", args, f"today={today}", {"date_today": today, "notes": row["notes"] if row else None})
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("get_today", args, str(exc), "database_error")


@mcp.tool
def list_tickets(status: str = "open", limit: int = 50) -> dict:
    """List shop tickets, newest first, optionally filtered by status.

    The Boss agent routes on `type`. Pass status="" for every ticket.
    Reads: tickets.
    """
    args = {"status": status, "limit": limit}
    capped = clamp_limit(limit)
    try:
        with read_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tickets WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, capped),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tickets ORDER BY created_at DESC LIMIT ?", (capped,)
                ).fetchall()
        tickets = rows_to_dicts(rows)
        return _ok("list_tickets", args, f"{len(tickets)} ticket(s)", {"tickets": tickets, "count": len(tickets)})
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("list_tickets", args, str(exc), "database_error")


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Return one ticket by id, with its linked lease and invoice if it has any.

    Reads: tickets, leases, invoices.
    """
    args = {"ticket_id": ticket_id}
    try:
        with read_conn() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None:
                return _fail("get_ticket", args, f"No ticket {ticket_id}", "not_found")
            ticket = dict(row)
            lease = invoice = None
            if ticket["lease_id"] is not None:
                r = conn.execute("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone()
                lease = dict(r) if r else None
            if ticket["invoice_id"] is not None:
                r = conn.execute("SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)).fetchone()
                invoice = dict(r) if r else None
        return _ok(
            "get_ticket", args, f"ticket {ticket_id} type={ticket['type']} status={ticket['status']}",
            {"ticket": ticket, "lease": lease, "invoice": invoice},
        )
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("get_ticket", args, str(exc), "database_error")


# --------------------------------------------------------------------------
# read tools — inventory and pricing
# --------------------------------------------------------------------------

@mcp.tool
def lookup_inventory(sku: str, size: str = "") -> dict:
    """Look up stock for a SKU, or for one exact (sku, size) pair.

    Inventory's primary key is (sku, size): a SKU can be in stock in one size
    and out in another, so a size-less answer is never enough to promise an
    order. Omit `size` to see every size for the SKU.
    Reads: inventory.
    """
    args = {"sku": sku, "size": size}
    sku_n, size_n = _norm_sku(sku), _norm_size(size)
    if not sku_n:
        return _fail("lookup_inventory", args, "sku is required", "invalid_input")
    try:
        with read_conn() as conn:
            if size_n:
                rows = conn.execute(
                    "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku_n, size_n)
                ).fetchall()
                if not rows:
                    known = conn.execute(
                        "SELECT size FROM inventory WHERE sku = ? ORDER BY size", (sku_n,)
                    ).fetchall()
                    if not known:
                        return _fail("lookup_inventory", args, f"Unknown sku {sku_n}", "not_found")
                    sizes = [r["size"] for r in known]
                    return _fail(
                        "lookup_inventory", args,
                        f"{sku_n} has no size {size_n}; stocked sizes: {', '.join(sizes)}",
                        "not_found",
                    )
            else:
                rows = conn.execute(
                    "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku_n,)
                ).fetchall()
                if not rows:
                    return _fail("lookup_inventory", args, f"Unknown sku {sku_n}", "not_found")
        items = rows_to_dicts(rows)
        total = sum(i["qty"] for i in items)
        summary = "; ".join(f"{i['size']}={i['qty']}" for i in items)
        return _ok(
            "lookup_inventory", args, f"{sku_n} {summary}",
            {"sku": sku_n, "items": items, "total_qty": total,
             "in_stock": total > 0, "count": len(items)},
        )
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("lookup_inventory", args, str(exc), "database_error")


@mcp.tool
def get_pricing(sku: str) -> dict:
    """Return unit cost and list price for a SKU.

    Pricing is per SKU, not per size. `unit_cost` is the floor any discount
    must stay above; the server does not itself hold a discount policy.
    Reads: pricing.
    """
    args = {"sku": sku}
    sku_n = _norm_sku(sku)
    try:
        with read_conn() as conn:
            row = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku_n,)).fetchone()
        if row is None:
            return _fail("get_pricing", args, f"No pricing for sku {sku_n}", "not_found")
        p = dict(row)
        p["margin_per_unit"] = round(p["list_price"] - p["unit_cost"], 2)
        return _ok("get_pricing", args, f"{sku_n} cost={p['unit_cost']} list={p['list_price']}", {"pricing": p})
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("get_pricing", args, str(exc), "database_error")


@mcp.tool
def list_vendors(specialty: str = "", limit: int = 50) -> dict:
    """List vendors and their lead times.

    `lead_days` added to get_today() gives the earliest realistic restock date.
    Reads: vendors.
    """
    args = {"specialty": specialty, "limit": limit}
    capped = clamp_limit(limit)
    try:
        with read_conn() as conn:
            if specialty:
                rows = conn.execute(
                    "SELECT * FROM vendors WHERE specialty LIKE ? ORDER BY id LIMIT ?",
                    (f"%{specialty}%", capped),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM vendors ORDER BY id LIMIT ?", (capped,)).fetchall()
        vendors = rows_to_dicts(rows)
        return _ok("list_vendors", args, f"{len(vendors)} vendor(s)", {"vendors": vendors, "count": len(vendors)})
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("list_vendors", args, str(exc), "database_error")


# --------------------------------------------------------------------------
# read tools — money
# --------------------------------------------------------------------------

@mcp.tool
def list_invoices(status: str = "", limit: int = 50) -> dict:
    """List vendor invoices with their vendor name and days-to-due.

    days_to_due is measured against the shop's date, so a negative value is
    an overdue invoice.
    Reads: invoices, vendors, desk.
    """
    args = {"status": status, "limit": limit}
    capped = clamp_limit(limit)
    try:
        with read_conn() as conn:
            today = shop_today(conn)
            sql = (
                "SELECT i.*, v.name AS vendor_name, v.lead_days, "
                "CAST(julianday(i.due_date) - julianday(?) AS INTEGER) AS days_to_due "
                "FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
            )
            if status:
                rows = conn.execute(
                    sql + "WHERE i.status = ? ORDER BY i.due_date LIMIT ?", (today, status, capped)
                ).fetchall()
            else:
                rows = conn.execute(sql + "ORDER BY i.due_date LIMIT ?", (today, capped)).fetchall()
        invoices = rows_to_dicts(rows)
        return _ok(
            "list_invoices", args, f"{len(invoices)} invoice(s) as of {today}",
            {"invoices": invoices, "count": len(invoices), "as_of": today},
        )
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("list_invoices", args, str(exc), "database_error")


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Return one invoice with its vendor and whether it is overdue today.

    Reads: invoices, vendors, desk, payments.
    """
    args = {"invoice_id": invoice_id}
    try:
        with read_conn() as conn:
            today = shop_today(conn)
            row = conn.execute(
                "SELECT i.*, v.name AS vendor_name, v.lead_days, "
                "CAST(julianday(i.due_date) - julianday(?) AS INTEGER) AS days_to_due "
                "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (today, invoice_id),
            ).fetchone()
            if row is None:
                return _fail("get_invoice", args, f"No invoice {invoice_id}", "not_found")
            invoice = dict(row)
            paid = conn.execute(
                "SELECT * FROM payments WHERE kind = 'invoice' AND ref_id = ?", (invoice_id,)
            ).fetchall()
        invoice["overdue"] = invoice["days_to_due"] < 0
        invoice["already_paid"] = len(paid) > 0
        return _ok(
            "get_invoice", args,
            f"invoice {invoice_id} {invoice['amount']} status={invoice['status']} overdue={invoice['overdue']}",
            {"invoice": invoice, "payments": rows_to_dicts(paid), "as_of": today},
        )
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("get_invoice", args, str(exc), "database_error")


@mcp.tool
def list_leases(limit: int = 50) -> dict:
    """List leases with rent, next due date, and days until due.

    Reads: leases, desk.
    """
    args = {"limit": limit}
    capped = clamp_limit(limit)
    try:
        with read_conn() as conn:
            today = shop_today(conn)
            rows = conn.execute(
                "SELECT *, CAST(julianday(next_due) - julianday(?) AS INTEGER) AS days_to_due "
                "FROM leases ORDER BY next_due LIMIT ?",
                (today, capped),
            ).fetchall()
        leases = rows_to_dicts(rows)
        return _ok("list_leases", args, f"{len(leases)} lease(s) as of {today}",
                   {"leases": leases, "count": len(leases), "as_of": today})
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("list_leases", args, str(exc), "database_error")


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Return one lease, its days-to-due, and whether rent was already paid.

    Lets the Facilities agent check an emailed rent demand against the actual
    lease record instead of trusting the email.
    Reads: leases, desk, payments.
    """
    args = {"lease_id": lease_id}
    try:
        with read_conn() as conn:
            today = shop_today(conn)
            row = conn.execute(
                "SELECT *, CAST(julianday(next_due) - julianday(?) AS INTEGER) AS days_to_due "
                "FROM leases WHERE id = ?",
                (today, lease_id),
            ).fetchone()
            if row is None:
                return _fail("get_lease", args, f"No lease {lease_id}", "not_found")
            lease = dict(row)
            paid = conn.execute(
                "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ?", (lease_id,)
            ).fetchall()
        return _ok(
            "get_lease", args,
            f"lease {lease_id} rent={lease['monthly_rent']} due={lease['next_due']} in {lease['days_to_due']}d",
            {"lease": lease, "payments": rows_to_dicts(paid), "as_of": today},
        )
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("get_lease", args, str(exc), "database_error")


@mcp.tool
def get_cash_balance(account: str = "checking") -> dict:
    """Return the balance of a cash account.

    The shop has a single account, so every proposal competes against this one
    number. Accounting must check it before approving anything.
    Reads: cash_accounts.
    """
    args = {"account": account}
    name = str(account or "").strip()
    try:
        with read_conn() as conn:
            row = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (name,)).fetchone()
        if row is None:
            return _fail("get_cash_balance", args, f"No cash account named {name!r}", "not_found")
        acct = dict(row)
        return _ok("get_cash_balance", args, f"{name} balance={acct['balance']}", {"account": acct})
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("get_cash_balance", args, str(exc), "database_error")


@mcp.tool
def list_payments(limit: int = 50) -> dict:
    """List recorded payments, newest first. This is the money audit trail.

    Reads: payments.
    """
    args = {"limit": limit}
    capped = clamp_limit(limit)
    try:
        with read_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM payments ORDER BY paid_at DESC, id DESC LIMIT ?", (capped,)
            ).fetchall()
        payments = rows_to_dicts(rows)
        total = round(sum(p["amount"] for p in payments), 2)
        return _ok("list_payments", args, f"{len(payments)} payment(s) totalling {total}",
                   {"payments": payments, "count": len(payments), "total": total})
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("list_payments", args, str(exc), "database_error")


# --------------------------------------------------------------------------
# proposal tools — prepare an action, change nothing
# --------------------------------------------------------------------------

@mcp.tool
def propose_payment(kind: str, ref_id: int, account: str = "checking", memo: str = "") -> dict:
    """Prepare a payment for human approval. Moves no money.

    `kind` is "invoice" or "rent". The amount is taken from the invoice or
    lease record itself, never from the caller, so an agent cannot propose an
    amount the records do not support. The proposal is checked for an existing
    payment and for sufficient funds before it is written.

    Returns a proposal_id. The proposal stays inert until a human approves it
    through the privileged approval surface; only then will execute_payment act.
    Reads: invoices, leases, cash_accounts, payments. Writes: output/proposals.json only.
    """
    args = {"kind": kind, "ref_id": ref_id, "account": account, "memo": memo}
    kind_n = str(kind or "").strip().lower()
    account_n = str(account or "").strip()
    if kind_n not in {"invoice", "rent"}:
        return _fail("propose_payment", args, "kind must be 'invoice' or 'rent'", "invalid_input")
    try:
        with read_conn() as conn:
            acct = conn.execute(
                "SELECT * FROM cash_accounts WHERE name = ?", (account_n,)
            ).fetchone()
            if acct is None:
                return _fail("propose_payment", args, f"No cash account named {account_n!r}", "not_found")

            if kind_n == "invoice":
                row = conn.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
                if row is None:
                    return _fail("propose_payment", args, f"No invoice {ref_id}", "not_found")
                if row["status"] != "open":
                    return _fail("propose_payment", args,
                                 f"Invoice {ref_id} has status {row['status']!r}, not open", "already_settled")
                amount = float(row["amount"])
                target = f"invoice:{ref_id}"
                detail = {"vendor_id": row["vendor_id"], "due_date": row["due_date"],
                          "description": row["description"], "memo": memo}
            else:
                row = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
                if row is None:
                    return _fail("propose_payment", args, f"No lease {ref_id}", "not_found")
                amount = float(row["monthly_rent"])
                target = f"rent:{ref_id}"
                detail = {"landlord": row["landlord"], "space_name": row["space_name"],
                          "next_due": row["next_due"], "memo": memo}

            dup = conn.execute(
                "SELECT id, paid_at FROM payments WHERE kind = ? AND ref_id = ?", (kind_n, ref_id)
            ).fetchone()
            if dup is not None:
                return _fail("propose_payment", args,
                             f"{kind_n} {ref_id} was already paid (payment {dup['id']} on {dup['paid_at']})",
                             "duplicate_payment")

            balance = float(acct["balance"])

        # A proposal that cannot be funded is refused at proposal time, not only
        # at execution time, so no one is asked to approve an impossible payment.
        if amount > balance:
            return _fail("propose_payment", args,
                         f"Insufficient funds: {account_n} holds {balance:.2f}, payment needs {amount:.2f}",
                         "insufficient_funds")

        pending = [p for p in proposals.list_all(proposals.STATUS_PENDING)
                   if p["target"] == target]
        if pending:
            existing = pending[0]
            return _ok("propose_payment", args,
                       f"reused pending proposal {existing['proposal_id']} for {target}",
                       {"proposal": existing, "reused": True,
                        "note": "A pending proposal for this target already exists; not duplicating it."})

        proposal = proposals.create("payment", target, amount, account_n, detail)
        return _ok(
            "propose_payment", args,
            f"proposal {proposal['proposal_id']} for {target} amount={amount:.2f} awaiting human approval",
            {"proposal": proposal, "balance_before": balance,
             "balance_if_approved": round(balance - amount, 2),
             "requires_human_approval": True},
        )
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("propose_payment", args, str(exc), "database_error")


@mcp.tool
def propose_purchase(sku: str, size: str, qty: int, vendor_id: int, memo: str = "",
                     account: str = "checking") -> dict:
    """Prepare a restock purchase for human approval. Orders nothing, pays nothing.

    Cost is computed as pricing.unit_cost * qty, so the caller cannot invent a
    price. The (sku, size) pair must already exist in inventory. The expected
    arrival date is the shop's date plus the vendor's lead_days.
    Reads: inventory, pricing, vendors, cash_accounts, desk. Writes: output/proposals.json only.
    """
    args = {"sku": sku, "size": size, "qty": qty, "vendor_id": vendor_id,
            "account": account, "memo": memo}
    sku_n, size_n = _norm_sku(sku), _norm_size(size)
    account_n = str(account or "").strip()
    try:
        qty_n = int(qty)
    except (TypeError, ValueError):
        return _fail("propose_purchase", args, "qty must be a whole number", "invalid_input")
    if qty_n <= 0:
        return _fail("propose_purchase", args, "qty must be greater than zero", "invalid_input")

    try:
        with read_conn() as conn:
            today = shop_today(conn)
            inv = conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku_n, size_n)
            ).fetchone()
            if inv is None:
                return _fail("propose_purchase", args,
                             f"No inventory row for ({sku_n}, {size_n})", "not_found")
            price = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku_n,)).fetchone()
            if price is None:
                return _fail("propose_purchase", args, f"No pricing for sku {sku_n}", "not_found")
            vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
            if vendor is None:
                return _fail("propose_purchase", args, f"No vendor {vendor_id}", "not_found")
            acct = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account_n,)).fetchone()
            if acct is None:
                return _fail("propose_purchase", args, f"No cash account named {account_n!r}", "not_found")

            amount = round(float(price["unit_cost"]) * qty_n, 2)
            balance = float(acct["balance"])
            eta = conn.execute(
                "SELECT date(?, ?) AS eta", (today, f"+{int(vendor['lead_days'])} days")
            ).fetchone()["eta"]

        if amount > balance:
            return _fail("propose_purchase", args,
                         f"Insufficient funds: {account_n} holds {balance:.2f}, purchase needs {amount:.2f}",
                         "insufficient_funds")

        target = f"purchase:{sku_n}:{size_n}:{qty_n}:{vendor_id}"
        pending = [p for p in proposals.list_all(proposals.STATUS_PENDING) if p["target"] == target]
        if pending:
            existing = pending[0]
            return _ok("propose_purchase", args,
                       f"reused pending proposal {existing['proposal_id']} for {target}",
                       {"proposal": existing, "reused": True,
                        "note": "A pending proposal for this purchase already exists; not duplicating it."})

        detail = {"sku": sku_n, "size": size_n, "qty": qty_n, "vendor_id": vendor_id,
                  "vendor_name": vendor["name"], "lead_days": vendor["lead_days"],
                  "unit_cost": price["unit_cost"], "expected_arrival": eta,
                  "qty_on_hand_now": inv["qty"], "memo": memo}
        proposal = proposals.create("purchase", target, amount, account_n, detail)
        return _ok(
            "propose_purchase", args,
            f"proposal {proposal['proposal_id']} {qty_n}x{sku_n}/{size_n} cost={amount:.2f} eta={eta}",
            {"proposal": proposal, "balance_before": balance,
             "balance_if_approved": round(balance - amount, 2),
             "expected_arrival": eta, "requires_human_approval": True},
        )
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("propose_purchase", args, str(exc), "database_error")


@mcp.tool
def list_proposals(status: str = "") -> dict:
    """List proposals, optionally filtered by status.

    Statuses: pending_human_approval, executed, rejected.
    Reads: output/proposals.json. No database access.
    """
    args = {"status": status}
    items = proposals.list_all(status or None)
    # Never expose approval signature material to an agent. Show only who
    # approved and when, so an agent can see that a human has acted.
    safe = []
    for p in items:
        view = {k: v for k, v in p.items() if k != "approval"}
        appr = p.get("approval")
        view["approved_by"] = appr["approved_by"] if appr else None
        view["approved_at"] = appr["approved_at"] if appr else None
        safe.append(view)
    return _ok("list_proposals", args, f"{len(safe)} proposal(s)", {"proposals": safe, "count": len(safe)})


@mcp.tool
def reject_proposal(proposal_id: str, decided_by: str, reason: str = "") -> dict:
    """Record a human decision not to proceed. Changes no business data."""
    args = {"proposal_id": proposal_id, "decided_by": decided_by, "reason": reason}
    if not str(decided_by or "").strip():
        return _fail("reject_proposal", args, "decided_by must name the human deciding", "invalid_input")
    try:
        existing = proposals.get(proposal_id)
        if existing is None:
            return _fail("reject_proposal", args, f"No such proposal: {proposal_id}", "not_found")
        if existing["status"] == proposals.STATUS_EXECUTED:
            return _fail("reject_proposal", args,
                         f"Proposal {proposal_id} was already executed", "already_executed")
        if existing["status"] == proposals.STATUS_APPROVED:
            return _fail("reject_proposal", args,
                         f"Proposal {proposal_id} carries a human approval; only the "
                         "privileged approval surface may withdraw it", "approval_required")
        updated = proposals.mark(proposal_id, proposals.STATUS_REJECTED, decided_by,
                                 {"reason": reason})
        return _ok("reject_proposal", args, f"{proposal_id} rejected by {decided_by}",
                   {"proposal": updated})
    except proposals.ApprovalError as exc:
        return _fail("reject_proposal", args, str(exc), "approval_error")


# --------------------------------------------------------------------------
# execution tools — require a human approval that matches the proposal
# --------------------------------------------------------------------------

@mcp.tool
def execute_payment(proposal_id: str) -> dict:
    """Execute a payment a human has already approved. The only tool that moves money.

    Takes the proposal id and nothing else. Authorization is read from persisted
    state signed with the server's secret key, so this tool cannot be talked
    into acting on an unapproved proposal: passing a name, a hash, or any other
    argument does not create authority. A human grants approval out of band
    (operator CLI today, authenticated dashboard route later).

    The balance check runs again inside the transaction, so a payment can never
    drive the account negative. Executing a proposal twice is refused.

    Writes (atomically): payments (insert), cash_accounts (balance),
    invoices.status or leases.next_due. Reads: invoices, leases, cash_accounts, desk.
    """
    args = {"proposal_id": proposal_id}
    try:
        proposal = proposals.verify_for_execution(proposal_id)
    except proposals.ApprovalError as exc:
        return _fail("execute_payment", args, str(exc), "approval_rejected")
    approved_by = proposal["approval"]["approved_by"]

    if proposal["kind"] != "payment":
        return _fail("execute_payment", args,
                     f"Proposal {proposal_id} is a {proposal['kind']}, not a payment",
                     "wrong_proposal_kind")

    kind_n, ref_id = proposal["target"].split(":", 1)[0], int(proposal["target"].split(":", 1)[1])
    amount, account_n = proposal["amount"], proposal["account"]

    try:
        with write_conn() as conn:
            today = shop_today(conn)

            dup = conn.execute(
                "SELECT id FROM payments WHERE kind = ? AND ref_id = ?", (kind_n, ref_id)
            ).fetchone()
            if dup is not None:
                raise _Abort(f"{kind_n} {ref_id} was already paid (payment {dup['id']})",
                             "duplicate_payment")

            acct = conn.execute(
                "SELECT balance FROM cash_accounts WHERE name = ?", (account_n,)
            ).fetchone()
            if acct is None:
                raise _Abort(f"No cash account named {account_n!r}", "not_found")
            balance = float(acct["balance"])
            if amount > balance:
                raise _Abort(
                    f"Insufficient funds: {account_n} holds {balance:.2f}, payment needs {amount:.2f}",
                    "insufficient_funds",
                )

            new_balance = round(balance - amount, 2)
            conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind_n, ref_id, amount, account_n, today, approved_by),
            )
            payment_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            conn.execute(
                "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                (new_balance, today, account_n),
            )
            if kind_n == "invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
                settled = f"invoice {ref_id} marked paid"
            else:
                conn.execute(
                    "UPDATE leases SET next_due = date(next_due, '+1 month') WHERE id = ?",
                    (ref_id,),
                )
                settled = f"lease {ref_id} rolled to next month"
    except _Abort as exc:
        return _fail("execute_payment", args, exc.reason, exc.stop_reason)
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("execute_payment", args, str(exc), "database_error")

    proposals.mark(proposal_id, proposals.STATUS_EXECUTED, approved_by,
                   {"payment_id": payment_id, "balance_after": new_balance})
    return _ok(
        "execute_payment", args,
        f"paid {amount:.2f} for {kind_n} {ref_id}; {settled}; {account_n} now {new_balance:.2f}",
        {"payment_id": payment_id, "kind": kind_n, "ref_id": ref_id, "amount": amount,
         "account": account_n, "balance_after": new_balance, "paid_at": today,
         "approved_by": approved_by, "settled": settled},
    )


@mcp.tool
def execute_purchase(proposal_id: str) -> dict:
    """Execute a restock purchase a human has already approved. The only tool that adds stock.

    Takes the proposal id and nothing else; authorization comes from persisted,
    server-signed approval state exactly as in execute_payment.

    Pays the vendor from the account and raises inventory.qty for the exact
    (sku, size) in one transaction, so stock and cash can never disagree.

    Writes (atomically): payments (insert), cash_accounts (balance),
    inventory.qty. Reads: inventory, cash_accounts, desk.
    """
    args = {"proposal_id": proposal_id}
    try:
        proposal = proposals.verify_for_execution(proposal_id)
    except proposals.ApprovalError as exc:
        return _fail("execute_purchase", args, str(exc), "approval_rejected")
    approved_by = proposal["approval"]["approved_by"]

    if proposal["kind"] != "purchase":
        return _fail("execute_purchase", args,
                     f"Proposal {proposal_id} is a {proposal['kind']}, not a purchase",
                     "wrong_proposal_kind")

    d = proposal["detail"]
    sku_n, size_n, qty_n = d["sku"], d["size"], int(d["qty"])
    amount, account_n = proposal["amount"], proposal["account"]

    try:
        with write_conn() as conn:
            today = shop_today(conn)
            inv = conn.execute(
                "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku_n, size_n)
            ).fetchone()
            if inv is None:
                raise _Abort(f"No inventory row for ({sku_n}, {size_n})", "not_found")

            acct = conn.execute(
                "SELECT balance FROM cash_accounts WHERE name = ?", (account_n,)
            ).fetchone()
            if acct is None:
                raise _Abort(f"No cash account named {account_n!r}", "not_found")
            balance = float(acct["balance"])
            if amount > balance:
                raise _Abort(
                    f"Insufficient funds: {account_n} holds {balance:.2f}, purchase needs {amount:.2f}",
                    "insufficient_funds",
                )

            new_balance = round(balance - amount, 2)
            new_qty = int(inv["qty"]) + qty_n
            conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                "VALUES ('purchase', ?, ?, ?, ?, ?)",
                (d["vendor_id"], amount, account_n, today, approved_by),
            )
            payment_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            conn.execute(
                "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                (new_balance, today, account_n),
            )
            conn.execute(
                "UPDATE inventory SET qty = ? WHERE sku = ? AND size = ?",
                (new_qty, sku_n, size_n),
            )
    except _Abort as exc:
        return _fail("execute_purchase", args, exc.reason, exc.stop_reason)
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("execute_purchase", args, str(exc), "database_error")

    proposals.mark(proposal_id, proposals.STATUS_EXECUTED, approved_by,
                   {"payment_id": payment_id, "balance_after": new_balance, "qty_after": new_qty})
    return _ok(
        "execute_purchase", args,
        f"bought {qty_n}x{sku_n}/{size_n} for {amount:.2f}; qty now {new_qty}; {account_n} now {new_balance:.2f}",
        {"payment_id": payment_id, "sku": sku_n, "size": size_n, "qty_added": qty_n,
         "qty_after": new_qty, "amount": amount, "account": account_n,
         "balance_after": new_balance, "expected_arrival": d.get("expected_arrival"),
         "approved_by": approved_by},
    )


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, note: str = "") -> dict:
    """Set a ticket's status and optionally append a note.

    Workflow bookkeeping only: this tool moves no money and no stock.
    Writes: tickets. Reads: tickets.
    """
    args = {"ticket_id": ticket_id, "status": status, "note": note}
    allowed = {"open", "in_progress", "resolved", "closed", "blocked"}
    status_n = str(status or "").strip().lower()
    if status_n not in allowed:
        return _fail("update_ticket_status", args,
                     f"status must be one of: {', '.join(sorted(allowed))}", "invalid_input")
    try:
        with write_conn() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise _Abort(f"No ticket {ticket_id}", "not_found")
            notes = row["notes"] or ""
            if note:
                notes = f"{notes}\n[{status_n}] {note}".strip()
            conn.execute(
                "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
                (status_n, notes, ticket_id),
            )
    except _Abort as exc:
        return _fail("update_ticket_status", args, exc.reason, exc.stop_reason)
    except (DatabaseError, sqlite3.Error) as exc:
        return _fail("update_ticket_status", args, str(exc), "database_error")
    return _ok("update_ticket_status", args, f"ticket {ticket_id} -> {status_n}",
               {"ticket_id": ticket_id, "status": status_n})


class _Abort(Exception):
    """Abort a write transaction with a clean reason; triggers ROLLBACK."""

    def __init__(self, reason: str, stop_reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.stop_reason = stop_reason


if __name__ == "__main__":
    mcp.run()
