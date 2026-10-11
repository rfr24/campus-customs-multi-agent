# Campus Customs — Technical Harness

Living document for Homework 5. Problem 2 establishes the **database** section only.
Later problems will add MCP tools, agents, API routes, safety rules, and the dashboard.

---

## 1. Database files

| File | Role |
| --- | --- |
| `data/campus_customs.db` | **Untouched original.** Extracted from the assignment ZIP, set to read-only (`chmod 444`). Never written to. |
| `data/campus_customs_new.db` | **Working copy.** Byte-identical copy of the original. All future operational changes go here. |

Verified identical at creation time (SHA-256):

```
23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a  data/campus_customs.db
23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a  data/campus_customs_new.db
```

Neither database was modified during Problem 2; all inspection used `file:...?mode=ro` URIs.

---

## 2. Operational rules found in the data

- **The shop's "today" is `desk.date_today` = `2026-08-31`.** Always read the current date from this table, never from the system clock. Every due-date, overdue, and lead-time calculation must be anchored here.
- **One cash account exists:** `checking`, balance `3400.00` as of `2026-08-31`. It is the only funding source, so spending decisions compete against a single finite balance.
- **`payments` is currently empty** — no money has moved yet. It is the append-only audit trail for anything the agents pay.
- **Inventory is keyed by (sku, size)**, so stock must always be checked per size, not per SKU.
- **Foreign keys are declared but SQLite does not enforce them unless `PRAGMA foreign_keys = ON`** is set per connection. Future write tools should set it.
- Several logical relationships are *not* declared as foreign keys (`inventory.sku` ↔ `pricing.sku`, `tickets.sku`/`tickets.size` ↔ `inventory`), so they must be validated in application code.

---

## 3. Tables and fields

### `desk`
`date_today TEXT NOT NULL`, `notes TEXT` — no primary key, single row.

**Why it matters:** the authoritative clock for the whole agent team. Every agent that reasons about "due", "overdue", "in N days", or vendor lead times must start here.

### `tickets`
`id INTEGER PK`, `type TEXT NOT NULL`, `requester TEXT NOT NULL`, `subject TEXT NOT NULL`, `sku TEXT`, `size TEXT`, `qty INTEGER`, `lease_id INTEGER → leases.id`, `invoice_id INTEGER → invoices.id`, `status TEXT NOT NULL`, `notes TEXT`, `created_at TEXT NOT NULL`.

**Why it matters:** the work queue. `type` is what the Boss agent routes on (`customer_order`, `rent_notice`, `price_override`), and the nullable `sku`/`size`/`qty`/`lease_id`/`invoice_id` columns tell each specialist agent which other table to open.

### `inventory`
`sku TEXT NOT NULL`, `name TEXT NOT NULL`, `size TEXT NOT NULL`, `qty INTEGER NOT NULL`, `location TEXT NOT NULL`, **PK (sku, size)**.

**Why it matters:** the Inventory agent's source of truth for whether an order can be filled. A SKU can be in stock in one size and out in another.

### `pricing`
`sku TEXT PK`, `unit_cost REAL NOT NULL`, `list_price REAL NOT NULL`.

**Why it matters:** one row per SKU (not per size). `unit_cost` is the margin floor any discount request must be checked against; `list_price` is the starting point for quotes.

### `vendors`
`id INTEGER PK`, `name TEXT NOT NULL`, `specialty TEXT NOT NULL`, `lead_days INTEGER NOT NULL`.

**Why it matters:** restock options. `lead_days` added to `desk.date_today` gives the earliest realistic fulfillment date, which drives what the Customer Service agent can promise.

### `leases`
`id INTEGER PK`, `space_name TEXT NOT NULL`, `landlord TEXT NOT NULL`, `monthly_rent REAL NOT NULL`, `next_due TEXT NOT NULL`, `notes TEXT`.

**Why it matters:** the Facilities agent's record for rent obligations. `next_due` vs `desk.date_today` determines urgency; `monthly_rent` is the amount Accounting would have to release.

### `cash_accounts`
`name TEXT PK`, `balance REAL NOT NULL`, `date TEXT NOT NULL`.

**Why it matters:** the Accounting agent's solvency check. Every proposed payment must be tested against this balance before approval.

### `payments`
`id INTEGER PK`, `kind TEXT NOT NULL`, `ref_id INTEGER`, `amount REAL NOT NULL`, `account TEXT NOT NULL`, `paid_at TEXT NOT NULL`, `approved_by TEXT NOT NULL`.

**Why it matters:** the audit log. `kind` + `ref_id` form a loose polymorphic pointer (e.g. an invoice id or lease id), and `approved_by` is where agent accountability is recorded. Currently empty.

### `invoices`
`id INTEGER PK`, `vendor_id INTEGER NOT NULL → vendors.id`, `amount REAL NOT NULL`, `due_date TEXT NOT NULL`, `status TEXT NOT NULL`, `description TEXT`.

**Why it matters:** money owed to vendors. Accounting reconciles these against `cash_accounts` and records settlement in `payments`.

---

## 4. Relationships

Declared foreign keys:

- `tickets.lease_id` → `leases.id`
- `tickets.invoice_id` → `invoices.id`
- `invoices.vendor_id` → `vendors.id`

Logical (undeclared, must be validated in code):

- `inventory.sku` ↔ `pricing.sku` (every stocked SKU has exactly one pricing row)
- `tickets.sku` + `tickets.size` ↔ `inventory (sku, size)`
- `payments.account` ↔ `cash_accounts.name`
- `payments.ref_id` ↔ `invoices.id` or `leases.id`, disambiguated by `payments.kind`
- `leases.landlord` ↔ `tickets.requester` for rent notices (string match, not a key)

Shape:

```
desk (clock)
tickets ──► leases ──► (rent payment) ──┐
        └─► invoices ──► vendors        ├──► payments ──► cash_accounts
        └─► inventory ◄──► pricing  ────┘
```

---

## 5. Open tickets 101–103

### Ticket 101 — `customer_order`, Tauhid Zaman, "Bulldog tee"
Wants 1 × `CC-TEE-WHITE`, size **S**. Created 2026-08-31T09:15-04:00. Links to `invoice_id = 501`.

- **Tables involved:** `inventory` (CC-TEE-WHITE / S), `pricing` (CC-TEE-WHITE), `invoices` (501), `vendors` (1), `cash_accounts`, `payments`, `desk`.
- **Likely agents:** Boss (route) → Inventory (stock check) → Accounting (invoice 501) → Customer Service (reply / ETA).
- **Facts in the data:** `inventory` shows **qty 0** for CC-TEE-WHITE size S (other sizes M/L/XL have stock). Invoice **501** is a `840.00` rush reprint of exactly "CC-TEE-WHITE S" from vendor 1 (Bulldog Print Co, `lead_days = 5`), `status = open`, `due_date = 2026-08-28` — which is **3 days before the shop's today**, i.e. already past due.
- **Dependencies/constraints:** the order cannot be filled from stock today; it depends on the reprint, which is tied to an overdue unpaid invoice, which competes with rent for the single `checking` balance of 3400.00. (Resolution deferred.)

### Ticket 102 — `rent_notice`, Elm City Properties, "Rent due"
Links to `lease_id = 1`. Note: "Email: shop rent due in 2 days." Created 2026-08-31T11:05-04:00.

- **Tables involved:** `leases` (1), `cash_accounts`, `payments`, `desk`.
- **Likely agents:** Boss → Facilities (lease verification) → Accounting (funds + payment record).
- **Facts in the data:** lease 1 is the Chapel Street shop, landlord **Elm City Properties** (matches the requester), `monthly_rent = 2400.00`, `next_due = 2026-09-02`. Against `desk.date_today = 2026-08-31`, that is exactly **2 days out**, consistent with the email's claim.
- **Dependencies/constraints:** 2400.00 rent + 840.00 invoice = 3240.00 against a 3400.00 balance — both are payable but the margin is thin, so ordering matters. The request arrived by email and names a payee, so it should be checked against the lease record rather than trusted on its face.

### Ticket 103 — `price_override`, Yale AI Club, "Bulk hoodie discount"
Wants 20 × `CC-HOOD-NAVY`, size **M**, at a bulk discount. Created 2026-08-31T16:55-04:00.

- **Tables involved:** `inventory` (CC-HOOD-NAVY, all sizes), `pricing` (CC-HOOD-NAVY), `vendors` (1, apparel reprint), `desk`.
- **Likely agents:** Boss → Inventory (stock) → Accounting (margin / discount authority) → Customer Service (quote).
- **Facts in the data:** `inventory` has CC-HOOD-NAVY M at **qty 8** — short of the 20 requested (S 4, L 14, XL 6; total across all sizes 32). `pricing` gives `unit_cost = 22.00`, `list_price = 58.00`, so list revenue on 20 units is 1160.00 against a 440.00 cost.
- **Dependencies/constraints:** the quantity cannot be met from size-M stock today; any top-up runs through vendor 1 at 5 lead days (earliest ~2026-09-05). Any discount must stay above `unit_cost`, and no discount-approval threshold is stored in the database — that rule is not in the data and must not be invented. (Resolution deferred.)

---

## 6. Cross-ticket constraint to carry into Problem 3

All three tickets land on the same day (2026-08-31) and ultimately draw on one `checking` balance of **3400.00**. Known committed amounts: rent 2400.00 (due 2026-09-02) and invoice 501 for 840.00 (already overdue). Sequencing and approval authority will matter once agents can write.

---

---

# Part B — Shared MCP server (Problem 3)

> **Assumption flagged:** the HW5 assignment text is not present in this project folder, so no
> official tool names or approval thresholds were available. Tool names below are derived from
> the Problem 2 schema and the project's HW4 conventions. **No business policy (discount floor,
> approval limit, payment priority) has been invented** — the server enforces only arithmetic and
> integrity facts. If the handout specifies exact names or thresholds, they are a rename away.

## B1. Architecture and connection

Package `mcp_server/`:

| File | Responsibility |
| --- | --- |
| `mcp_server/server.py` | The FastMCP server and all 19 tools |
| `mcp_server/db.py` | Connection management, read-only vs. transactional write, result caps |
| `mcp_server/proposals.py` | Proposal ledger and lifecycle state |
| `mcp_server/approval.py` | **Privileged** approval granting + HMAC signing — not an MCP tool |
| `mcp_server/approve.py` | Operator CLI for the human approval step — not an MCP tool |
| `mcp_server/audit.py` | Append-only audit trail |

Built on **FastMCP 4.1**. All five agents (Boss, Inventory, Accounting, Facilities, Customer
Service) connect to this one server; no agent opens SQLite directly, so the safety rules and the
audit trail apply uniformly no matter which agent acts.

Start the server over stdio (the transport the agents will use):

```bash
.venv/bin/python -m mcp_server.server
```

Equivalent via the CLI, and the in-process client used by tests:

```bash
.venv/bin/fastmcp run mcp_server/server.py
```

```python
from fastmcp import Client
from mcp_server.server import mcp
async with Client(mcp) as client:      # in-memory, no subprocess
    await client.call_tool("get_today", {})
```

Every tool returns a dict with `ok: true` plus its payload, or `ok: false` with `error` and a
machine-readable `stop_reason` (`invalid_input`, `not_found`, `insufficient_funds`,
`duplicate_payment`, `approval_rejected`, `already_settled`, `wrong_proposal_kind`,
`database_error`). Tools do not raise into the agent; a refusal is data the agent can reason about.

## B2. Tools

### Read-only (mode=ro connection — cannot write even by mistake)

| Tool | Inputs → Outputs | Tables | Why it exists |
| --- | --- | --- | --- |
| `get_today()` | → `date_today`, `notes` | `desk` | The shop's authoritative clock. Every due/overdue/lead-time calculation starts here, never the host clock. |
| `list_tickets(status="open", limit=50)` | → `tickets[]`, `count` | `tickets` | The work queue the Boss agent routes on. `status=""` returns all. |
| `get_ticket(ticket_id)` | → `ticket`, `lease`, `invoice` | `tickets`, `leases`, `invoices` | One call gives a specialist agent the ticket plus whatever it is linked to. |
| `lookup_inventory(sku, size="")` | → `items[]`, `total_qty`, `in_stock` | `inventory` | Stock check honouring the **(sku, size)** key. Omit `size` for all sizes. |
| `get_pricing(sku)` | → `unit_cost`, `list_price`, `margin_per_unit` | `pricing` | Margin floor for discount reasoning. Per SKU, not per size. |
| `list_vendors(specialty="", limit=50)` | → `vendors[]` | `vendors` | Restock options and `lead_days`. |
| `list_invoices(status="", limit=50)` | → `invoices[]` with `vendor_name`, `days_to_due` | `invoices`, `vendors`, `desk` | Obligations ranked by due date; negative `days_to_due` = overdue. |
| `get_invoice(invoice_id)` | → `invoice` with `overdue`, `already_paid` | `invoices`, `vendors`, `desk`, `payments` | Accounting's single-invoice view, including whether it was already settled. |
| `list_leases(limit=50)` | → `leases[]` with `days_to_due` | `leases`, `desk` | Facilities' rent calendar. |
| `get_lease(lease_id)` | → `lease`, prior rent `payments` | `leases`, `desk`, `payments` | Lets Facilities check an emailed rent demand against the actual lease rather than trusting the email. |
| `get_cash_balance(account="checking")` | → `account` row | `cash_accounts` | Solvency check before any approval. |
| `list_payments(limit=50)` | → `payments[]`, `total` | `payments` | The money audit trail. |
| `list_proposals(status="")` | → `proposals[]` | *(no DB — `output/proposals.json`)* | What is awaiting a human. Shows `approved_by`/`approved_at`; signature material is stripped. |

### Proposal tools (write only to `output/proposals.json` — no business data changes)

| Tool | Behaviour | Tables read |
| --- | --- | --- |
| `propose_payment(kind, ref_id, account="checking", memo="")` | `kind` is `"invoice"` or `"rent"`. **Amount is read from the invoice/lease record, never from the caller**, so an agent cannot propose an amount the records do not support. Refuses an already-paid obligation, a non-open invoice, and an unfundable amount. Returns `proposal_id`; the proposal is inert until approved. | `invoices`, `leases`, `cash_accounts`, `payments` |
| `propose_purchase(sku, size, qty, vendor_id, memo="", account="checking")` | Cost = `pricing.unit_cost * qty`, computed server-side. Validates the `(sku, size)` pair exists, the vendor exists, `qty > 0`, and the cost is fundable. Returns the expected arrival as `get_today() + vendor.lead_days`. | `inventory`, `pricing`, `vendors`, `cash_accounts`, `desk` |
| `reject_proposal(proposal_id, decided_by, reason="")` | Records a human "no". Touches no business data. | — |

Re-proposing an identical target while one is still pending returns the **existing** proposal
(`reused: true`) instead of creating a second one.

### Write-capable (foreign keys ON, single atomic transaction)

| Tool | Writes | Guard |
| --- | --- | --- |
| `execute_payment(proposal_id)` | `payments` (insert), `cash_accounts.balance`, and either `invoices.status='paid'` or `leases.next_due += 1 month` | Requires a persisted, server-signed human approval; re-validated balance and duplicate check *inside* the transaction |
| `execute_purchase(proposal_id)` | `payments` (insert), `cash_accounts.balance`, `inventory.qty` for the exact (sku, size) | Same, plus the inventory row must still exist |
| `update_ticket_status(ticket_id, status, note="")` | `tickets.status`, `tickets.notes` | Status restricted to `open / in_progress / resolved / closed / blocked`. Workflow bookkeeping only — moves no money and no stock. |

## B3. Database safety

- Every application read and write targets **`data/campus_customs_new.db`**. The original
  `data/campus_customs.db` is never opened for writing anywhere in the code; it is also `chmod 444`
  on disk.
- Read tools connect through a `file:…?mode=ro` URI, so a bug in a read tool physically cannot write.
- Write tools set `PRAGMA foreign_keys = ON` and run inside `BEGIN IMMEDIATE` … `COMMIT`, with
  `ROLLBACK` on any exception.
- **All SQL is parameterised.** No value is ever string-formatted into a statement; SKU and size are
  normalised (trim + uppercase) before binding. Verified with an injection-shaped input.
- Identifiers are validated before use: ticket, invoice, lease, vendor, and account ids must resolve,
  and `(sku, size)` must exist in `inventory` — an unknown size reports the stocked sizes rather than
  silently matching nothing.
- **Result caps:** every list tool clamps `limit` to `1..200` (`MAX_ROWS = 200`, default 50).

## B4. Human approval and cash safeguards

> **Revised after a Problem 3 follow-up review.** The first version bound approval to
> `sha256(public proposal fields)` and accepted any non-empty `approved_by` string. Both are
> reproducible by the agent that created the proposal, so an agent could have signed its own
> approval. That scheme is gone.

The boundary is **propose → a human grants approval out of band → execute**.

### The trust boundary

| Surface | Reachable by | Can authorize? |
| --- | --- | --- |
| MCP tools (`mcp_server/server.py`) | the five agents | **No.** No tool grants approval. |
| `mcp_server/approval.grant()` | privileged in-process callers only | Yes |
| `python -m mcp_server.approve` (operator CLI) | whoever has a shell on the server | Yes |
| *future* authenticated FastAPI route | the logged-in human operator | Yes |

Nothing in `approval.py` or `approve.py` is registered with `@mcp.tool`, so the capability is
absent from the agent's surface rather than merely guarded within it.

### How authorization is proved

`approval.grant()` records an **HMAC-SHA256** signature over
`proposal_id | kind | target | amount | account | approved_by | approved_at | nonce`, keyed with a
server-side secret in **`.secrets/approval_key`** (32 random bytes, mode `0600`, created on first
use, git-ignored). The key is never returned by any tool and never written to the audit log, so an
agent that knows every public field of a proposal still cannot produce a valid signature.

`execute_payment(proposal_id)` and `execute_purchase(proposal_id)` now take **the proposal id and
nothing else**. There is no argument through which a caller can assert authority: the tools read
persisted state, require `status == "approved"`, and verify the signature with
`hmac.compare_digest`. `payments.approved_by` is written from the *signed* approval record, never
from a caller-supplied string.

Proposal lifecycle: `pending_human_approval → approved → executed`, or `→ rejected`.
`list_proposals` returns `approved_by` and `approved_at` so an agent can see that a human acted,
but strips the signature material.

### Requirement for the future dashboard route

`grant()` authenticates nothing — it trusts its caller. The FastAPI route that exposes it **must**
authenticate the human operator (session or signed token tied to a real account) and pass that
verified identity as `approved_by`. It must not be exposed unauthenticated, and must not be
re-exported through the MCP server. Agents call the route's *read* side at most; approval authority
stays on the human side of the boundary.

### Cash and duplicate protection (unchanged)

1. **Cash:** the balance is checked at proposal time *and* re-checked inside the execution
   transaction. A payment that would make the balance negative is refused with
   `insufficient_funds`. Money and the thing it settles (invoice status / lease date / stock qty)
   move in one transaction, so they cannot diverge.
2. **Amount integrity:** the amount is read from the invoice or lease record, never from the
   caller, and `grant()` refuses an approval whose amount differs from the proposal.
3. **Single use:** an executed proposal is marked `executed`; a second execute is refused, and it
   cannot be re-approved.
4. **Duplicates:** `payments` is checked for an existing `(kind, ref_id)` at both proposal and
   execution time.

**Deferred to later problems:** the authenticated FastAPI route and the dashboard's approve/reject
control. The CLI above is the human interface until then.

## B5. Auditability

Every tool call appends one entry to **`output/audit_trail.json`**, matching the project's existing
HW4 format:

```json
{ "time": "...Z", "tool": "propose_payment", "args": { "kind": "rent", "ref_id": 1 },
  "result": "proposal PAY-0001 for rent:1 amount=2400.00 awaiting human approval",
  "stop_reason": "completed" }
```

Successes and refusals are both recorded; `stop_reason` carries the refusal reason. The file is
append-only: existing entries are read, the new one added, the array rewritten. Argument values are
truncated to 120 chars, collections are summarised as counts, and any key named like a secret
(`api_key`, `password`, `token`, `secret`, `authorization`) is written as `<redacted>`. Model
reasoning, prompts, and chain-of-thought are never logged. Audit failures are swallowed so logging
can never take the server down.

**Concurrency and data loss (Problem 5 follow-up).**

*What happened.* The first implementation did a bare read-modify-write with no locking. During
Problem 5, concurrent agent traffic plus the stdio subprocess caused a reader to catch a partially
written file, fall back to an empty array, and overwrite the history. **62 genuine audit records
from Problems 3–4 were lost. They were not reconstructed, and no replacements were fabricated** —
the log now contains 81 genuine entries, all of them real calls.

*The safeguard.* The read-modify-write is guarded by an exclusive `fcntl.flock` and committed with
an atomic `os.replace`, so a reader never sees a half-written array and two writers never interleave.

Three details make the lock correct rather than merely present:

- **The lock is on a stable sibling file, `audit_trail.json.lock`, never on the JSON itself.**
  `os.replace` swaps the JSON's inode on every write, so a lock held on *that* file would be a lock
  on an unlinked inode — a second writer could hold the old inode while a third locked the new one
  and both would proceed. The lock file is never replaced; verified by comparing inodes across
  writes.
- The lock file is opened `"a"`, so acquiring the lock never truncates anything, even transiently.
- The temp file is **per-process** (`audit_trail.json.<pid>.tmp`), so two writers cannot collide on
  it even if one somehow proceeded without the lock.

*Corruption is preserved, not discarded.* An unparseable log is moved aside as
`audit_trail.corrupt-<timestamp>.json` with its bytes kept verbatim, and the fresh log opens with an
`audit.salvage` entry naming the preserved file — so a truncated history can never be mistaken for a
quiet one. An empty file is treated as an empty log, not as corruption.

*Verified* by `tests/verify_audit_integrity.py` — **19 checks, all passing**: 8 processes × 60
appends with zero lost updates, lock-inode stability across atomic replaces, corrupt-file
preservation, and confirmation that the real 81-entry log is intact. All stress testing runs against
a throwaway file selected with `CAMPUS_CUSTOMS_AUDIT_PATH`; the real log is never written by the
suite.

## B6. Verification (Problem 3)

`.venv/bin/python tests/verify_mcp.py` — **63 checks, all passing**. Read checks run against the real
working copy; **every write check runs against a disposable temp copy** of the database with a temp
proposals file, so the real working database is never mutated by the suite. Both database checksums
are compared before and after.

Read-path coverage: tool discovery; shop clock; tickets 101–103 and their joins; `(sku, size)`
composite-key behaviour; cash balance; overdue arithmetic anchored to the shop date; injection input.

Approval-forgery coverage (added by the follow-up):

- no approval-granting tool is exposed over MCP at all;
- executing an unapproved proposal is refused;
- an approval forged by recomputing SHA-256 over public proposal fields — the original gap — is refused;
- a fabricated `approved_by` with no valid signature is refused;
- a hand-edited `"approved"` status with no signature is refused;
- a signature validly issued for a *different* proposal cannot be transplanted;
- no forgery attempt moved money;
- `grant()` refuses a mismatched amount or a blank identity;
- an executed proposal cannot be re-approved or re-executed;
- key material never appears in tool output.

Plus the unchanged guards: insufficient funds, duplicate payment, cross-kind misuse, and invalid
sku/size/qty/vendor.

## B7. Still to come (after Problem 3)

The five agents, the FastAPI backend and its approval route, and the React dashboard. Tickets
101–103 remain **open and unresolved** — Problem 3 built the capability, not the resolution.

---

# Part C — PydanticAI ↔ MCP connection (Problem 4)

## C1. Architecture

Problem 4 adds no tools and no database code. It connects **PydanticAI 2.55** to the existing
Problem 3 server and verifies the 19 tools are usable through the agent framework.

| File | Responsibility |
| --- | --- |
| `agents/mcp_client.py` | The one reusable MCP connection the five agents will share |
| `agents/model.py` | The one place a model is built — `gpt-6-luna` via Portkey |

PydanticAI 2.55 exposes MCP through **`MCPToolset`** (built on the FastMCP client), not the older
`MCPServerStdio` class. Two transports, same server:

```python
from agents.mcp_client import stdio_toolset, inprocess_toolset

stdio_toolset()      # launches `python -m mcp_server.server` as a subprocess — deployment shape
inprocess_toolset()  # attaches to the FastMCP object directly — fast, deterministic, for tests
```

Both discover the identical 19 tools. Attaching them to an agent is one argument, so every agent in
Problem 5 shares this connection rather than opening its own:

```python
from pydantic_ai import Agent
from agents.mcp_client import stdio_toolset
from agents.model import build_model

agent = Agent(build_model(), toolsets=[stdio_toolset()], system_prompt=...)
```

## C2. Model configuration

`gpt-6-luna` through Portkey (`https://api.portkey.ai/v1`), with `PORTKEY_API_KEY` read from the
environment or a local `.env` — never hard-coded, printed, or logged. `build_model()` **refuses any
model name other than `gpt-6-luna`**, so no agent can silently substitute another.

**One transport decision worth recording:** on `/v1/chat/completions`, `gpt-6-luna` rejects function
tools with
`"Function tools with reasoning_effort are not supported for gpt-6-luna-global ... use /v1/responses
or set reasoning_effort to 'none'"`. Since every agent in this project is tool-driven, the model is
built with **`OpenAIResponsesModel`** (the Responses API) rather than disabling the model's
reasoning. Same model, same gateway — different endpoint.

**Timeouts (raised during Problem 5).** One Boss request fans out to several specialists, each
making multiple tool calls on a reasoning model, so a single HTTP call can legitimately run for
minutes. The SDK default is far too tight and surfaced as `ModelAPIError('Request timed out.')`
mid-delegation. The client is built with `timeout=600s, max_retries=2`.

## C3. Financial safeguards across the boundary

Problem 4 performed **no payment, purchase, approval, or ticket resolution**. Verified at the agent
boundary rather than assumed:

- the agent-facing toolset exposes **no approval-granting tool** — `assert_no_approval_tools()`
  raises at connection time if that ever changes, so a future edit to `server.py` fails loudly here;
- **no tool schema accepts** an `approval_token`, `signature`, or `approval_key` parameter;
- `agents/` never imports `mcp_server.approval`, so the signing key is unreachable from the agent
  side of the process;
- `execute_payment` on an unapproved proposal is refused through MCP exactly as it is directly.

The only write-capable tool exercised was `update_ticket_status`, against a **disposable copy**.

## C4. Verification (Problem 4)

`.venv/bin/python tests/verify_pydanticai.py` — **24 checks, all passing**, with connectivity and
live model use reported separately so one cannot be mistaken for the other.

**Part 1 — MCP connectivity (no model, no network):** 19 tools discovered over both transports;
approval capability absent; `get_today` = `2026-08-31`; open tickets `[101, 102, 103]`;
`CC-TEE-WHITE` S=0 vs M=5 (composite key intact across the MCP round trip); `CC-HOOD-NAVY`
22.0/58.0; 3 vendors with Bulldog Print Co at 5 lead days; checking 3400.0 — each matching the
Part A facts. Refusals arrive as `ok:false` data rather than exceptions.

**Part 2 — live model-driven tool use on `gpt-6-luna`:** the agent answered four questions by
calling tools, and the answers match the database: the shop date, 3 open tickets, 0 units of
CC-TEE-WHITE/S, and a $3,400.00 checking balance. Had credentials been absent these would have been
reported **SKIPPED, never as passes**.

Problem 3's suite still passes unchanged (63/63), and both database checksums are untouched.

## C5. Still to come (after Problem 4)

The five agents and their routing, the FastAPI backend with the authenticated approval route, and
the React dashboard.

---

# Part D — The five-agent team (Problem 5)

## D1. Architecture

```
                         Boss (coordinator)
                               │
      ┌────────────┬───────────┼────────────┬──────────────────┐
  Inventory    Accounting   Facilities   Customer Service
      └────────────┴───────────┴────────────┴──────────────────┘
                   all four share the one MCP server (Part B)
```

| File | Responsibility |
| --- | --- |
| `agents/team.py` | The five agents, delegation tools, and the per-request session |
| `agents/schemas.py` | `TeamOutcome` / `SpecialistFinding` — the contract the dashboard reads |
| `agents/prompts/*.md` | One focused system prompt per agent |

Problem 5 adds **no MCP tools and no database code**. Every agent reaches the shop through the
Problem 4 `MCPToolset`, and both transports still work: `CampusCustomsTeam.build(in_process=False)`
runs the server as a stdio subprocess, `in_process=True` (default) attaches directly.

```python
from agents.team import CampusCustomsTeam

team = CampusCustomsTeam.build()
outcome = await team.run("A student is asking about CC-TEE-WHITE in size S …")
```

## D2. The agents

| Agent | Owns | Cannot |
| --- | --- | --- |
| **Boss** | Routing, delegation, synthesis, cross-ticket dependencies | Do specialist work; approve anything |
| **Inventory** | Stock by `(sku, size)`, shortages, costs, vendor lead times | Judge affordability; propose payments |
| **Accounting** | Cash, invoices, feasibility, **preparing payment proposals** | Approve or execute; decide payment priority |
| **Facilities** | Leases, rent, due dates, verifying rent demands against the record | Move money — must route to Accounting |
| **Customer Service** | Interpreting requests, drafting replies | Touch money; promise an unapproved action |

Each prompt states the role, its tools, its limits, and who it hands off to. Three rules recur in
all of them: use `get_today()` rather than any notion of "now"; report only what a tool returned;
and never invent business policy — discount floors, approval thresholds, and payment priority go to
a human via `unresolved` / `open_questions`.

## D3. Delegation

Delegation is **genuine agent-to-agent interaction**: each `consult_*` tool on the Boss runs a
separate `Agent` with its own model instance, system prompt, and toolset. The Boss never role-plays
a specialist.

Three limits are enforced **in code, not by prompt wording**:

1. **No recursion by construction** — specialists have zero delegation tools, so the graph is one
   level deep and a loop cannot form.
2. **One consultation per specialist per request** — `TeamSession.consult()` raises on a repeat.
3. **Shared usage limits** — nested runs pass the parent's `ctx.usage`, so
   `UsageLimits(request_limit=40, tool_calls_limit=60)` caps a whole request end to end rather than
   per agent.

`specialists_consulted` and `findings` are written from the **session's own ledger**, and each
finding's `agent` field is overwritten with the agent that actually ran — so the dashboard sees the
real delegation path rather than the Boss's self-report.

## D4. Least privilege

Each specialist sees only the MCP tools its role needs, via `MCPToolset.filtered()`:

| Agent | Tools visible |
| --- | --- |
| Inventory | 8 — stock, pricing, vendors, tickets, date, **`propose_purchase`**, `list_proposals` |
| Accounting | 12 — cash, invoices, payments, leases, stock *(read-only)*, **`propose_payment`**, date |
| Facilities | 6 — leases, payments, tickets, date |
| Customer Service | 5 — tickets, stock, pricing, date |

> Inventory's `propose_purchase` and Accounting's `lookup_inventory` were added after Problem 9
> ticket 103 exposed that no specialist could prepare a purchase. See §H8a.

**No agent on any path sees `execute_payment`, `execute_purchase`, or any approval-granting tool.**
Accounting can *prepare* a proposal; nothing in the team can authorize one. `agents/` never imports
`mcp_server.approval` and never reads the signing key — verified by the test suite rather than
assumed.

## D5. Structured outputs

`TeamOutcome` answers exactly what the later ticket runner and dashboard need: `handled_by`,
`specialists_consulted`, `findings[]`, `summary`, `dependencies`, `proposed_actions[]`,
`needs_human_approval`, `open_questions`. Each `SpecialistFinding` carries `agent`, `summary`,
`facts[]` (verified, tool-sourced), `constraints[]`, `proposed_actions[]`, `needs_human_approval`,
and `unresolved[]`.

The models encode the distinction that matters: a **fact** is something a tool returned; a
**`ProposedAction`** has not happened and carries `requires_human_approval=True`.
`needs_human_approval` is **derived from what was actually proposed**, so the Boss cannot
under-report it.

## D6. Verification (Problem 5)

`.venv/bin/python tests/verify_team.py` — **73 checks, all passing**, with structure and live
delegation reported separately. Structure: five distinct agents, all on `gpt-6-luna` via `OpenAIResponsesModel`; each
specialist's visible tool set exactly matches its declared allow-list; no agent can execute or
approve; the Boss has exactly four delegation tools and specialists have none; a repeat consultation
raises; structured-output fields present; and **no ticket id (101/102/103) appears in team code or
prompts** — outcomes are not hard-coded.

Live: the Boss delegated to Inventory for a stock question and the finding was grounded in real
data (0 on hand, vendor lead time); a multi-domain rent-and-invoice request drew in both Accounting
and Facilities, each consulted exactly once, with the Boss synthesising across them. Nothing was executed, no proposal was approved, the balance is still
3400.0, and tickets 101–103 remain open.

## D7. Still to come (after Problem 5)

The ticket runner, the FastAPI backend with the authenticated approval route, and the React
dashboard.

---

# Part E — Ticket preparation and predictions (Problem 6)

## E1. Ticket preparation procedure

**No preparation step was needed and none was taken.** Tickets 101–103 have been `open` and
unresolved since Problem 2; nothing in Problems 3–5 resolved them, and the working database was
never mutated outside disposable copies. Preparation therefore consisted of *verification only*,
performed with read-only MCP tools through the Problem 4 connection:

`get_today`, `list_tickets`, `get_ticket`, `lookup_inventory`, `get_pricing`, `get_invoice`,
`get_lease`, `get_cash_balance`, `list_payments`, `list_proposals`.

The working database was **not** reset, reseeded, or modified.

## E2. Baseline state (verified 2026-08-31 shop date)

| Fact | Value |
| --- | --- |
| Open tickets | 101, 102, 103 |
| `CC-TEE-WHITE` / S | 0 |
| `CC-HOOD-NAVY` / M | 8 |
| Invoice 501 | 840.00, 3 days overdue, `open` |
| Lease 1 | 2400.00, due 2026-09-02 (2 days out) |
| Checking | 3400.00 |
| Payments / proposals | 0 / 0 |

Identical to the Part A figures — the baseline has not drifted across five problems.

## E3. How predictions were recorded before execution

`output/predictions.md` was written **before any agent was run against the tickets**, and says so at
the top. For each ticket it records the starting situation, the expected participants and delegation
sequence, what should be investigated, expected recommendations, whether human approval is required,
and the conflicts and risks.

Predictions are written to be **falsifiable rather than flattering**. Each ticket ends in a checklist
of concrete observable outcomes — specific values (`0`, `2026-09-05`, `264.00`, `3240 vs 3400`) and
specific absences (no invented discount threshold). Two predicted *failures* are recorded on purpose:
that the agents may invent a discount rule on ticket 103, and that they may miss the three-way cash
interaction in which paying rent and invoice 501 leaves only 160.00 — not enough for a 264.00
restock.

## E4. How actuals will be compared

The document ends with a clearly separated **"Actual results — to be filled in after Problem 7"**
section: one table per ticket plus a cross-ticket table, each row pairing a prediction with blank
`Actual` and `Match?` cells. **Those fields are intentionally blank** and must not be completed until
the agents have genuinely run.

Comparison will draw on three independent sources, so the agents' self-report is not taken at face
value: the structured `TeamOutcome` (`specialists_consulted` and `findings` come from the session
ledger, not the Boss's claim — Part D3), `output/audit_trail.json` for the tool calls actually made,
and a direct read of the database to confirm nothing moved.

## E5. Scope

Problem 6 created a document and verified a baseline. No ticket was run, simulated, or resolved; no
payment, purchase, or approval occurred; no agent was invoked.

---

# Part F — Ticket-processing backend (Problem 7)

## F1. Architecture

```
HTTP  →  FastAPI (backend/)  →  PydanticAI team  →  MCP server  →  SQLite
```

The backend owns **no business logic and opens no database handle**. Every read goes through an MCP
tool and every decision goes through the real Boss, so no rule is duplicated and none can drift.
(Verified: `sqlite3.connect` does not appear in `backend/main.py`.)

| File | Responsibility |
| --- | --- |
| `backend/main.py` | The FastAPI app and all 16 routes |
| `backend/auth.py` | Operator bearer authentication for the privileged routes |
| `backend/store.py` | Append-only persistence of ticket runs |

Run it:

```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`.

## F2. Routes

**Open — read state and run the team.** Safe because nothing on this path can move money or stock.

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Liveness plus the shop's authoritative date |
| `GET /api/tickets?status=` | The ticket queue |
| `GET /api/tickets/{id}` | One ticket with its linked lease/invoice **and its run history** |
| `GET /api/state` | Dashboard opening screen: date, cash, tickets, invoices, leases, pending counts |
| `GET /api/cash` | The balance every proposal competes against |
| `GET /api/inventory/{sku}?size=` | Stock, honouring the `(sku, size)` key |
| `GET /api/proposals?status=` | Proposals and their status (signatures stripped) |
| `GET /api/proposals/{id}` | One proposal |
| `POST /api/tickets/{id}/process` | **Run the real Boss agent against a ticket** |
| `GET /api/runs?ticket_id=` | Past runs, so the dashboard need not re-pay for agents |
| `GET /api/runs/{run_id}` | One run |
| `GET /api/audit?limit=&tool=` | The audit trail, read-only |

**Operator — authenticated, privileged.**

| Route | Purpose |
| --- | --- |
| `GET /api/operator/whoami` | Verify a token; show the identity approvals record under |
| `POST /api/operator/proposals/{id}/approve` | Grant human approval for one exact proposal |
| `POST /api/operator/proposals/{id}/reject` | Record a decision not to proceed |
| `POST /api/operator/proposals/{id}/execute` | Carry out an approved proposal |

Tool refusals become real HTTP statuses rather than `200 {ok: false}` — 404 not found, 409 conflict
(insufficient funds, duplicate, already settled), 403 approval rejected, 502 agent failure.

## F3. How a ticket reaches the Boss

`POST /api/tickets/{id}/process` loads the ticket **through MCP**, renders its real fields into a
request, and hands it to `CampusCustomsTeam.run()`. The Boss then delegates to specialists exactly
as in Part D — genuine agent-to-agent calls, genuine tool calls. Nothing here decides an outcome,
and **no ticket-specific behaviour is hard-coded**.

The returned `TicketRun` keeps three things apart that are easy to conflate:

- **`stage`** — how far the work got: `investigated`, `awaiting_human_approval`, or `failed`.
  There is deliberately **no `resolved` stage**: a recommendation is not a resolution.
- **`ticket_status`** — the database's own view, read back after the run.
- **`outcome`** — the structured `TeamOutcome` from Part D5, reused rather than re-invented.

`stage` is derived from what actually happened, not from the Boss's self-report. Proposed actions
are gathered from the **findings as well as the top level**, so a specialist's proposal that the
Boss fails to echo upward still marks the run as awaiting a human. (That gap was a real bug caught
by the test suite.)

A run leaves the database untouched by default. `mark_in_progress: true` is opt-in.

## F4. Authentication and the approval boundary

Problem 3 required that whatever exposes `approval.grant()` **must authenticate the human
operator**. This is that authentication: a bearer token generated once into `.secrets/operator_token`
(mode 0600, git-ignored), compared in constant time, never returned by any route and never logged.

Two properties matter more than the mechanism:

1. **`approved_by` is the authenticated principal, never a request field.** The `ApprovalRequest`
   model has no `approved_by` at all — verified against the generated OpenAPI schema. A client
   cannot name itself, which is the same lesson as the Problem 3 follow-up.
2. **Agents have no path to these routes.** They are HTTP endpoints, not MCP tools, and the team has
   no HTTP client. The boundary is structural, not a guard that could be argued past.

Approval records the HMAC signature from Part B4 and **moves no money**; execution is a separate
call that re-verifies the signature, re-checks the balance inside the transaction, and refuses a
second run. The backend adds authentication on top of those guarantees and weakens none of them.

## F5. Persistence and observability

Every run is appended to `output/ticket_runs.json` using the same lock-guarded, atomically-committed
pattern as the audit trail (§B5) — runs cost real model calls, so they must not be lost or
overwritten. Failed runs are recorded too, not hidden.

The API distinguishes ticket status, agents consulted, findings, pending proposals, human approvals,
executed transactions, and errors with stop reasons. `GET /api/audit` is **read-only**: history
cannot be edited through the API, and the backend never rewrites prior entries.

## F6. Verification (Problem 7)

`.venv/bin/python tests/verify_backend.py` — **68 checks, all passing**; with `--live`, **70/70**. Every mutating test runs against a **disposable sandbox**: temp database, temp proposals, temp
runs file, temp audit log, temp operator token, all selected by environment variable before the app
is imported.

Covered: app startup and OpenAPI; read endpoints matching the database; the default team dependency
building the real `CampusCustomsTeam`; structured results surfaced intact; a recommendation **not**
resolving a ticket; a failed run returning 502 with the ticket untouched and the failure still
recorded; unauthenticated and bad-token approval/execution rejected; no client-supplied
`approved_by` in the schema; unapproved execution refused; approval bound to exact proposal and
amount; execution exactly once with a second attempt refused; an approved-but-unaffordable payment
still refused by the transactional balance check; and audit/proposal views never exposing signature
material.

The `--live` run confirmed the real team end to end through HTTP: processing ticket 101 drew in
**Inventory, Accounting, and Customer Service**, returned `stage = awaiting_human_approval`, and left
the ticket open — a real delegation, through the real API, resolving nothing.

Confirmed untouched by the suite: both database checksums, the real audit trail, `output/predictions.md`,
and tickets 101–103 still open with zero payments.

## F7. Limitations and deferred work (Problem 7)

- **Single-operator authentication.** One shared bearer token is appropriate for a local
  single-operator assignment. Multiple operators would need per-user accounts and sessions; the
  principal is already threaded through `grant()`, so that change is localised to `backend/auth.py`.
- **No TLS.** The token is bearer-only and assumes a local, trusted network.

---

# Part G — Operations dashboard (Problem 8)

## G1. Structure

Vite + React 19 + TypeScript, matching the project's existing frontend conventions.

```
frontend/src/
  App.tsx                     layout, data loading, refresh orchestration
  api/client.ts               the only place that talks to FastAPI
  api/types.ts                mirrors the backend's Pydantic models
  components/
    TicketDetail.tsx          ticket record, findings, run history, Process control
    ApprovalQueue.tsx         approve / reject / execute, with confirmation
    CashPanel.tsx             balance and competing obligations
    ActivityPanel.tsx         recent runs and audit events
    OperatorBar.tsx           token sign-in
    Badge.tsx, Money.tsx      status pills and currency formatting

A ticket row's title and metadata are separate block elements: as inline spans they rendered as one
run-on line ("Bulk hoodie discountprice override"). Below 560px the row wraps so the subject keeps
its own line instead of being squeezed by the id and status badges.
```

Six sections: **Tickets**, **Ticket detail**, **Agent activity** (inside the detail),
**Approval queue**, **Cash**, **Recent activity**. Nothing about tickets 101–103 is hard-coded; the
dashboard renders whatever the API returns.

## G2. Connection to FastAPI

`api/client.ts` is a thin wrapper around `fetch` — **no business rules are duplicated**. Vite proxies
`/api` to the backend, so the browser stays on one origin and **no API base URL or credential is
baked into the bundle**. Override the target with `BACKEND_URL` if port 8000 is taken.

`ApiError` carries the backend's own `status` and `stop_reason` and turns them into operator
language: `insufficient_funds` → "Not enough cash to cover this", 401 → "Operator token missing or
invalid", 502 → "The agent team could not finish".

After processing, approving, rejecting, or executing, the dashboard re-reads state, tickets,
proposals, runs, audit, and the open ticket's detail.

## G3. Ticket and approval workflows

The UI distinguishes six states rather than collapsing them: ticket **open**; run
**investigated — no action proposed**; run **awaiting your approval**; proposal **approved**
(awaiting execution); proposal **executed**; ticket **resolved**. The run's stage and the database's
own `ticket_status` are shown side by side, and `stageLabel()` has **no "resolved" case**, because a
recommendation is not a resolution. Proposed actions are labelled *"Proposed — not yet done"* with
the note that nothing has been paid or ordered.

Approve, Reject, and Execute are visually distinct and **none fires on a single click**. Each opens
a confirmation naming the exact proposal, target, and amount — the amount matters because it is what
the approval is cryptographically bound to server-side. Execute warns that it moves money and
cannot be undone; Approve states that it does *not* pay yet. Success text for execution is written
from the backend's returned `balance_after`, so **the dashboard never claims a payment completed
before the backend confirms it**.

## G4. Authentication

The operator token is entered manually and held in **React state only** — never localStorage,
sessionStorage, a cookie, or a build variable. Closing the tab ends the session. It is sent per
request as `Authorization: Bearer`. Viewing is open; every mutating control is disabled until
sign-in. The HMAC signing key and Portkey credentials never reach the frontend at all.

## G5. Running it

```bash
# terminal 1 — backend
.venv/bin/uvicorn backend.main:app --port 8000

# terminal 2 — dashboard
npm --prefix frontend install
npm --prefix frontend run dev            # http://localhost:5173
```

If another project is already on port 8000:
`BACKEND_URL=http://localhost:8077 npm --prefix frontend run dev`, with the backend on `--port 8077`.

Print the operator token (never commit it):
`cat .secrets/operator_token`

## G6. Verification (Problem 8)

`npm --prefix frontend test` — **28 tests passing**, in four groups:

- **ApprovalQueue (10)** — exact target/amount shown before any decision; controls disabled when
  signed out; **a first click confirms rather than approves**; cancel acts on nothing; Execute
  appears only after approval; the "cannot be undone" and "does not pay yet" warnings; no success
  claimed until the backend confirms; insufficient-funds and 401 surfaced in operator language.
- **Dashboard (11)** — real ticket and cash data; obligations and remaining-if-all-paid arithmetic;
  findings and consulted specialists; a proposing run labelled awaiting approval and **never
  resolved**; processing called only on an explicit click; refresh after processing; a 502 reported
  without claiming the ticket advanced; backend-down error with Retry; **the token absent from
  localStorage, sessionStorage, and cookies after sign-in**.
- **Live integration (3)** — the real dashboard against a **running backend, no mocks**: real ticket
  subjects, `$3,400.00` cash, the `$160.00` remaining figure, shop date 2026-08-31, all three
  tickets open and unprocessed, approval controls inert while signed out.
- **TicketRow (4)** — regression guard for the ticket-list formatting fix: subject and metadata are
  separate sibling elements, the subject carries none of the metadata, and the stylesheet keeps both
  `display: block` with a 560px wrapping breakpoint.

Also verified: `npm run build` succeeds (tsc + vite); the built bundle contains **no operator token,
no approval key, no Portkey credential, and no `VITE_*` variable**; unauthenticated and bad-token
approval attempts return 401 through the proxy.

## G7. Limitations (Problem 8)

- **The in-app browser preview could not launch here** (a sandbox permission error reading
  `node_modules`), so the dashboard was verified by rendering it against the live backend in jsdom
  rather than by screenshot. The server itself runs fine.
- HW4's backend occupies port 8000 on this machine, hence the `BACKEND_URL` override.
- Single shared operator token, no TLS — carried over from Part F.
- The dashboard polls nothing; it refreshes after actions. Live updates would need SSE or polling.

---

# Part H — Ticket execution and evaluation (Problem 9)

## H1. Procedure

Tickets are processed **one at a time**, each reviewed by a human before the next is started. No
batch run.

For each ticket:

1. **Baseline capture** — checksums of both databases and `output/predictions.md`, ticket statuses,
   cash, payments, proposals, and the audit/run counts, all read-only.
2. **Process** — `POST /api/tickets/{id}/process` against the running backend, so the real Boss
   delegates to the real specialists on `gpt-6-luna`. No fixtures, no stubs.
3. **Verify independently** — the agents' self-report is never the evidence. Specialists consulted
   come from the session ledger (Part D3); tool calls from `output/audit_trail.json`; database
   effects from a direct `mode=ro` query.
4. **Stop at the approval boundary** — if a consequential action is proposed, the run halts there.
   The operator token is not used on the human's behalf.
5. **Record** — `output/results.md`, plus the raw outcome archived as `output/run_<id>.json`.

The working database is never reset or reseeded between tickets.

## H2. Baseline (before any processing)

Shop date **2026-08-31**. All three tickets `open`; checking **$3,400.00**; **0** payments; **0**
proposals; invoice 501 `open` and 3 days overdue; `CC-TEE-WHITE`/S = 0; `CC-HOOD-NAVY`/M = 8.
**347** audit entries, **0** ticket runs. Both databases `23686a90…1f360a`.

## H3. Ticket 101 — processed

Run `run-e96c3efe8944`, 23.7 s, stage **`awaiting_human_approval`**. Boss consulted
**Customer Service, Inventory, and Accounting**; 21 new audit entries, no refusals.

One proposal was created — **PAY-0001, $840.00 for invoice 501, `pending_human_approval`** — and
**nothing was approved or executed**. Verified afterwards: ticket 101 still `open`, balance still
$3,400.00, payments still 0, invoice 501 still `open`, original database unchanged.

All eight predicted checklist items matched. The predicted failure mode — assuming that paying
invoice 501 releases the reprint — **did not occur**; the agents refuted that inference explicitly
twice. Accounting also surfaced the $3,240-vs-$3,400 cross-ticket constraint on ticket 101, earlier
than predicted.

Full detail, including the prediction-vs-observed table, is in `output/results.md`.

## H4. Ticket 101 — human review

The operator reviewed the run and chose to **hold PAY-0001 pending further information**. It was
not approved, rejected, or executed. The system has no `hold` status and **none was invented**: the
proposal stays at its genuine `pending_human_approval`, with the decision recorded as a review note
in `output/results.md`.

## H5. Ticket 102 — processed

Run `run-2e2f1a85be87`, 17.0 s, stage **`awaiting_human_approval`**. Boss consulted
**Facilities and Accounting** — two of four, correctly leaving Inventory and Customer Service out of
a rent question. 16 new audit entries (368 → 384), no refusals.

Facilities verified the emailed demand **against lease 1** rather than trusting it: landlord,
$2,400.00 rent, and `next_due` 2026-09-02 all matched, with `days_to_due 2` measured from the shop
date. It then stopped at its own boundary — it has no `propose_payment` tool (Part D4) — and handed
funding to Accounting, which checked `list_payments` first, then prepared **PAY-0002, $2,400.00,
`pending_human_approval`**.

**Nothing was approved or executed.** Verified afterwards: ticket 102 still `open`, balance still
$3,400.00, payments still 0, lease `next_due` unmoved, original database unchanged.

All seven predicted checklist items matched. The predicted risk — accepting the emailed rent demand
at face value — did not occur.

## H6. Ticket 102 — human review

The operator chose to **hold PAY-0002** pending review of ticket 103 and the combined financial
picture. Not approved, rejected, or executed; status left at the genuine `pending_human_approval`.
The PAY-0001 hold stands.

## H7. Ticket 103 — processed

Run `run-86743a41ccc8`, 23.1 s, stage **`awaiting_human_approval`**. Boss consulted **Inventory,
Customer Service, and Accounting**. 19 new audit entries (385 → 404), no refusals.

Both Problem 6 predicted failures **did not occur**. No discount policy was invented — a scan of the
outcome for percentage or discount-rate language returns nothing. And the three-way cash
interaction, predicted to be missed, was computed exactly: "adding the $264 replenishment would
exceed available cash by $104. A human must decide priorities; no obligation is presumed deferred."

**No formal proposal was created.** The recommendation carries `proposal_id: null` and says so.

### Design gap surfaced by this run

`propose_purchase` is in **no specialist's allow-list** (Part D4). The MCP server implements it and
the operator route can execute it, but no agent can reach it; Accounting also lacks
`lookup_inventory`. Both agents reported the limitation accurately instead of fabricating a
proposal.

This is recorded rather than patched: ticket 103's run is the evidence for Problem 9, and changing
the configuration now would invalidate it. The fix — adding `propose_purchase` to Inventory or
Accounting and re-running — is a decision for the operator.

## H8a. Defect and correction — purchase-proposal permissions

**The defect.** Ticket 103 was the first ticket needing a purchase, and it revealed that
`propose_purchase` was in **no specialist's allow-list**. The MCP server implemented it and the
operator route could execute it, but the agent team could not reach it. Accounting also lacked
`lookup_inventory`, so it costed the full 20 units ($440) instead of the 12-unit shortfall ($264).
Both agents reported the limitation accurately rather than fabricating a proposal.

**Order of operations.** The fix was applied **after** ticket 103 completed, so the run remains
valid evidence. `output/run_103.json`, the audit trail, the proposal ledger, and
`output/predictions.md` are byte-identical to their state at run time, checked by checksum in the
test suite.

**The change** — `agents/team.py` allow-lists only; no tool, prompt, or server code touched:

- **Inventory** gained `propose_purchase` and `list_proposals`. Purchasing belongs here: the tool
  takes `(sku, size, qty, vendor_id)` — the facts Inventory already owns — and computes cost from
  `pricing.unit_cost`, so a caller cannot invent a price.
- **Accounting** gained `lookup_inventory`, read-only, for accurate shortfall arithmetic.

**Not granted:** no `execute_payment`, no `execute_purchase`, no approval capability anywhere — all
still absent from the MCP surface entirely (§B4). Accounting was deliberately *not* given
`propose_purchase`; purchasing stays with Inventory and Accounting does the cash analysis.

**Verified** by `tests/verify_purchase_permissions.py` — **48 checks, all passing** on a disposable
database and proposals file: the fix works (12 units propose at exactly $264.00, arrival
2026-09-05); every prior guard still refuses (unknown `(sku, size)`, non-positive qty, unknown
vendor, insufficient funds); an unapproved purchase still cannot execute; the change added exactly
two tools and removed none; and ticket 103's evidence plus both real databases are untouched.

## H8b. Ticket 103 — post-fix rerun

The operator authorised a single controlled rerun. Run `run-4d06881ddba5`, 18.4 s, stage
`awaiting_human_approval`. **This is a second, separate run**; the original `run-86743a41ccc8` is
preserved unchanged as evidence of the defect (`output/run_103.json`, `6bbc9105…588225b`, verified
identical afterwards). The rerun is archived separately as `output/run_103_postfix.json`.

**Both fixes worked, and the audit trail shows exactly why.** The rerun made 23 tool calls against
the original's 19, and the difference is precisely the two added tools: `propose_purchase` ×1 (never
called before) and `lookup_inventory` ×2 instead of ×1.

- **Inventory created `PUR-0001`** — 12 × `CC-HOOD-NAVY`/M from Bulldog Print Co, **$264.00**,
  expected arrival 2026-09-05, `pending_human_approval`, no approval signature.
- **Accounting used the 8 units on hand**, costing the 12-unit shortfall at $264.00 rather than the
  original run's full-quantity $440.00. The read-only grant produced exactly the intended
  correction.

No duplicate proposals (three distinct targets), no invented discount policy (a scan for
percentage/discount language returns nothing), no asserted vendor quote, and the cross-ticket
shortfall was computed again: all three commitments exceed the balance by $104.

Nothing was approved or executed. Ticket 103 still `open`, balance still $3,400.00, stock still 8.

**Tickets 101 and 102 were not re-run.**

## H8. Combined result

All three tickets processed, **all three still open**. Three formal proposals: PAY-0002 $2,400.00
**approved but not executed**, PAY-0001 $840.00 and PUR-0001 $264.00 both **held** at
`pending_human_approval`. Balance still $3,400.00, zero payments, no ticket resolved.

The three obligations total **$3,504.00 against $3,400.00** — the shop can fund any two, not all
three. Full detail and the prediction comparison are in `output/results.md`.

## H8c. Final human decisions

The operator issued explicit decisions on all three proposals, applied through the existing Part F4
authenticated workflow. No new approval state was added, no authorization rule changed, no agent
re-run.

| Proposal | Decision | Resulting status |
| --- | --- | --- |
| PAY-0002 $2,400.00 rent | **approve only, do not execute** | **`approved`** |
| PAY-0001 $840.00 invoice 501 | hold | `pending_human_approval` |
| PUR-0001 $264.00 restock | hold | `pending_human_approval` |

Holds are recorded as human review notes in `output/results.md`, not as proposal states — the
system has no `hold` status and none was invented.

**Approval is not execution, and the state proves it.** PAY-0002 carries a server-signed
authorization that the payment *may* proceed; `cash_accounts`, `payments`, `invoices`, and `leases`
are untouched. Checking is still $3,400.00 with zero payments. Execution would need a separate call
to `/api/operator/proposals/PAY-0002/execute`, which was not made.

Authentication used the existing operator token; `whoami` returned the configured principal
`operator (local)`. No identity was invented and no signature forged. The approval signature
verifies against the server key and **fails** against a tampered amount, confirming it is bound to
$2,400.00 specifically.

Audit: 523 → 527 entries, all prior events retained; the new ones are backend startup, a
`get_today`, the genuine `approval.grant`, and shutdown.

### Audit isolation — defect and fix

**The defect.** `mcp_server.audit` resolves `AUDIT_PATH` **once at import time** from
`CAMPUS_CUSTOMS_AUDIT_PATH`, falling back to `output/audit_trail.json`. A suite that exercised real
MCP tools without setting that variable *before* importing `mcp_server` appended to the production
log, even with its database redirected to a disposable copy. Eight `execute_*` entries marked
`completed` reached the real trail this way.

**Measured, not assumed.** Each suite was checksummed before and after a run:

| Suite | Before the fix |
| --- | --- |
| `verify_mcp.py` | polluted, **+41** entries (set no env vars at all) |
| `verify_pydanticai.py` | polluted, **+14** |
| `verify_team.py` | polluted, **+13** |
| `verify_purchase_permissions.py` | already clean |
| `verify_backend.py` | already clean |

This corrected an earlier assumption: `verify_purchase_permissions.py` was never a polluter, and the
two agent suites had not previously been identified as ones.

**The fix.** `tests/_isolation.py` provides `isolate_audit()` — creates a temp dir, points
`CAMPUS_CUSTOMS_AUDIT_PATH` into it, and registers an `atexit` cleanup **scoped to that directory**,
so cleanup cannot reach the real trail. `assert_audit_isolated()` raises if `mcp_server.audit`
resolved to the production log, guarding the ordering mistake that caused the problem. The three
affected suites call it before any `mcp_server` import and assert isolation as their first check.

`CAMPUS_CUSTOMS_DB_PATH` was deliberately left alone: those suites read the real working database on
purpose to assert documented facts. Only the audit *write* path moved.

**Regression check.** `tests/verify_audit_isolation.py` is empirical — it checksums the production
audit file, runs each suite as a subprocess, and compares, so a regression is caught however it is
written. **8/8 passing with `--all`: every suite now leaves `output/audit_trail.json` byte-identical.**

**Historical entries were not touched.** Nothing was deleted, rewritten, or fabricated. The existing
test-origin entries remain exactly as recorded; their content identifies them (proposal ids and
balances that never existed in the real ledger), and `SELECT * FROM payments` returns zero rows.

## H9. Integrity

`output/predictions.md` is byte-identical to its pre-run state (`c953ab18…296c98`) and its
actual-results fields remain blank — `output/results.md` is a separate document, so the Problem 6
predictions stay exactly as written. No audit entry was fabricated; every new entry is a genuine
tool call from a run. Ticket 101's evidence (`output/run_101.json`, its results section, and
PAY-0001's state) is preserved unchanged across ticket 102's run.

---

# Part I — Reflection (Problem 10)

`output/reflection.md` — a first-person reflection written after all three tickets were processed
and the human decisions recorded. It follows the Problem 10 points documented in `AI_prompts.md`:
agent performance across the three tickets, predictions versus actual behaviour, the strongest
coordination example, the purchasing-permission defect and its corrected rerun, the audit-isolation
problem, the recommend/approve/execute distinction, and the remaining limitations.

Length is ~1,350 words. An editorial target of 900–1,100 was suggested, but the final revision was
explicitly not to be shortened to meet it; there is no mandatory word count.

Three corrections were made in the final pass: the $22 figure is described as a **recorded unit
cost, not a pricing floor or policy** (the shop has no rule about what a sale may go below); the
conclusion says the system **does not resolve every ticket on its own** rather than that it cannot
resolve tickets, noting it can carry one through to execution once a person authorizes it; and the
opening frames the goal as coordination, factual verification, and appropriate human oversight
rather than removing the need to check numbers.

**Problem 10 is complete.**

Every figure and quotation was checked against the archived evidence rather than written from
memory: the arithmetic ($3,504 vs $3,400, the $104 shortfall, $264 = 12 × $22, $440 = 20 × $22)
recomputed, and each quoted sentence confirmed verbatim in `run_101.json`, `run_103.json`, or
`run_103_postfix.json`. The reflection states that PAY-0002 was **approved only** and that the
balance remains $3,400 with zero payments, consistent with the verified state.

No proposal, prediction, run archive, or audit record was changed by Problem 10.
