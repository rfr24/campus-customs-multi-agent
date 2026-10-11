# Campus Customs — Multi-Agent Operations

Yale AI Foundations, Homework 5.

A five-agent operations system for a campus apparel shop. A Boss agent coordinates four specialists
— Inventory, Accounting, Facilities, and Customer Service — over a shared MCP server, behind a
FastAPI backend and a React operations dashboard.

**Status: the three sample tickets (101, 102, 103) were processed and remain open and unresolved.**
The agents investigated them and prepared proposals; two of those are still awaiting a human
decision and one is approved but deliberately not executed. See
[`output/results.md`](output/results.md) for the full record and
[`output/reflection.md`](output/reflection.md) for what I took away from it.

---

## Architecture

```
React dashboard  →  FastAPI backend  →  PydanticAI team  →  MCP server  →  SQLite
                                        (Boss + 4 specialists)
```

| Directory | Contents |
| --- | --- |
| `mcp_server/` | FastMCP server, 19 operational tools, approval boundary, audit trail |
| `agents/` | The five agents, their prompts, structured outputs, model wiring |
| `backend/` | FastAPI app, operator authentication, run persistence |
| `frontend/` | Vite + React + TypeScript dashboard |
| `tests/` | Python verification suites |
| `output/` | Harness, predictions, results, reflection, run archives, audit trail |
| `data/` | Both SQLite databases |

**Every agent runs `gpt-6-luna` through Portkey.** No other model is used; `agents/model.py` refuses
to build one.

### The databases

- `data/campus_customs.db` — the assignment's **untouched original**, read-only.
- `data/campus_customs_new.db` — the **working copy**. All operations target this file.

Both are currently byte-identical, because no transaction has been executed.

---

## Setup

Requires Python 3.12+ and Node 20+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend install
```

### Environment configuration

Copy the example and add your own Portkey key:

```bash
cp .env.example .env
```

```
PORTKEY_API_KEY=your_portkey_api_key_here
```

The key is read from the environment or a local `.env` and is **never** hard-coded, logged, or sent
to the frontend. `.env` and `.secrets/` are git-ignored.

### Local credentials, and what that means for a fresh clone

Two further secrets live in `.secrets/`. **Neither is in this repository**, and neither needs to be
created by hand — each is generated automatically, with owner-only permissions (`0600`), the first
time something asks for it:

| File | Generated when | Purpose |
| --- | --- | --- |
| `.secrets/approval_key` | the first approval is signed or verified | 32 random bytes; the HMAC key behind every human approval |
| `.secrets/operator_token` | the first request hits an operator route (or `whoami`) | bearer token for the authenticated operator routes |

Print your operator token with `cat .secrets/operator_token`. Don't commit either file; `.gitignore`
already excludes the whole directory.

**Historical approval signatures will not verify on your machine.** This matters for reading the
committed evidence, so it's worth being explicit about.

`output/proposals.json` is committed as part of the Problem 9 record, and it contains `PAY-0002`
with status `approved` and the HMAC signature produced when I approved it. That signature was made
with *my* local `.secrets/approval_key`, which is deliberately **not** published. When you clone this
repository and run anything that touches approvals, a **different** key is generated — so the stored
signature will not verify against it. I checked this rather than assuming: on a simulated fresh
clone, `approval.verify()` on the committed `PAY-0002` returns `False`.

The practical consequence is that **`PAY-0002` reads as `approved` in the ledger but cannot be
executed on a fresh clone** — `execute_payment` refuses it with "carries no valid server-issued
approval signature." That is the system failing closed, which is the behaviour I want: an approval
is only meaningful on the server that issued it, and a signature copied between machines confers no
authority. To exercise the flow yourself, approve a proposal with your own key through
`/api/operator/proposals/{id}/approve`.

Publishing the signature itself is safe. It is an HMAC output, not the key, and cannot be reversed
to recover the key or used to forge an approval for anything else.

---

## Running it

**Backend** (port 8000; use another port if that one is taken):

```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

API docs at `http://localhost:8000/docs`.

**Dashboard:**

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. If the backend is on a different port:

```bash
BACKEND_URL=http://localhost:8077 npm --prefix frontend run dev
```

**The MCP server on its own** (the agents launch it themselves; this is for inspection):

```bash
.venv/bin/python -m mcp_server.server
```

**Tests:**

```bash
.venv/bin/python tests/verify_mcp.py                   # MCP server and safety rules
.venv/bin/python tests/verify_pydanticai.py            # PydanticAI ↔ MCP connection
.venv/bin/python tests/verify_team.py                  # the five-agent team
.venv/bin/python tests/verify_backend.py               # FastAPI backend
.venv/bin/python tests/verify_purchase_permissions.py  # specialist tool permissions
.venv/bin/python tests/verify_audit_integrity.py       # audit concurrency
.venv/bin/python tests/verify_audit_isolation.py       # tests don't touch the real audit log
npm --prefix frontend test                             # dashboard
```

Every test that mutates data runs against a disposable copy. The real working database and audit
trail are never written by the suites.

---

## How the agents work

The **Boss** reads a ticket and decides which specialists it needs, then delegates. Delegation is
real agent-to-agent interaction: each `consult_*` tool runs a separate `Agent` with its own model,
prompt, and toolset. The Boss never role-plays a specialist.

| Agent | Owns | Cannot |
| --- | --- | --- |
| **Boss** | Routing, synthesis, cross-ticket dependencies | Do specialist work; approve anything |
| **Inventory** | Stock by `(sku, size)`, shortages, vendor lead times, restock proposals | Judge affordability; propose payments |
| **Accounting** | Cash, invoices, feasibility, payment proposals | Approve or execute; set payment priority |
| **Facilities** | Leases, rent, verifying demands against the record | Move money — routes to Accounting |
| **Customer Service** | Interpreting requests, drafting replies | Touch money; promise an unapproved action |

Three limits are enforced in code, not by prompt wording: specialists have **no delegation tools**
(so recursion is impossible by construction), each may be consulted **once per request**, and nested
runs share a usage budget that caps the whole request.

Each specialist sees only the MCP tools its role needs. **No agent on any path can see
`execute_payment`, `execute_purchase`, or any approval-granting tool.**

Agents are instructed to use the shop's own date (`get_today()`, currently 2026-08-31) rather than
the system clock, to report only what tools returned, and never to invent business policy — discount
thresholds, approval limits, and payment priority all go to a human.

---

## The human approval workflow

This is the heart of the design, and it separates three things that are easy to conflate:

**1. Recommend.** An agent prepares a proposal. It is inert — it moves no money and no stock, and
lives outside the business database. Agents may do this and nothing more.

**2. Approve.** A human authorizes one specific proposal through an authenticated route:

```bash
curl -X POST http://localhost:8000/api/operator/proposals/PAY-0002/approve \
  -H "Authorization: Bearer $(cat .secrets/operator_token)" \
  -H 'Content-Type: application/json' \
  -d '{"approved_amount": 2400.0}'
```

Approval records an **HMAC-SHA256 signature** over the exact proposal, amount, and account, keyed
with a server-side secret the agents cannot read. Change the amount and the signature no longer
verifies. Note what the request does *not* contain: an `approved_by` field. The approver's identity
comes from the authenticated session, so a caller cannot name itself.

**Approving moves no money.**

**3. Execute.** A separate, separately authenticated call carries the action out. It re-verifies the
signature, re-checks the balance inside the transaction, refuses a second execution, and writes the
payment and the thing it settles atomically.

Agents have no path to steps 2 or 3 — those are HTTP routes, not MCP tools, and the team has no HTTP
client. The boundary is structural, not a guard that could be argued past.

The dashboard surfaces all three states, requires an explicit confirmation naming the exact amount
before any consequential action, and never reports a payment as complete until the backend confirms
execution.

An operator CLI is also available:

```bash
.venv/bin/python -m mcp_server.approve --list
```

---

## Current ticket state

| Ticket | Type | Status | Proposal |
| --- | --- | --- | --- |
| 101 | Customer order, out of stock | **open** | `PAY-0001` $840.00 — held |
| 102 | Rent notice | **open** | `PAY-0002` $2,400.00 — **approved, not executed** |
| 103 | Bulk discount request | **open** | `PUR-0001` $264.00 — held |

Checking balance **$3,400.00**, zero payments executed.

The three obligations total **$3,504.00** against $3,400.00 — the shop can fund any two, not all
three. The agents identified this themselves and declined to choose, correctly: no payment-priority
rule exists in the data. Three questions remain open for a human — the unconfirmed vendor price and
delivery date, the absent discount policy, and which obligation to defer.

**No ticket has been resolved**, and none can be until an approved action is executed and verified.

---

## Documentation

| File | Contents |
| --- | --- |
| [`output/harness.md`](output/harness.md) | Full technical record: schema, tools, agents, routes, safety rules, every defect found |
| [`output/predictions.md`](output/predictions.md) | Predictions written **before** any ticket ran, unmodified since |
| [`output/results.md`](output/results.md) | What the agents actually did, measured against those predictions |
| [`output/reflection.md`](output/reflection.md) | My reflection on the assignment |
| [`AI_prompts.md`](AI_prompts.md) | Every prompt I gave the AI assistant, verbatim, with follow-ups |
| `output/run_*.json` | Archived agent runs, including the pre- and post-fix ticket 103 runs |
| `output/audit_trail.json` | Append-only log of every tool call |

Two defects found during the work are documented rather than quietly patched: a permission gap that
left `propose_purchase` unreachable by every agent, and test suites that wrote to the production
audit trail. Both are described in the harness alongside their fixes, and the original ticket 103
run is preserved as evidence of the first.
