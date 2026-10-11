"""Problem 5 verification: the five-agent team.

Two layers, reported separately:

  Part 1 — structure. No model calls. Proves the five agents exist, each sees
           only its own MCP tools, none can reach approval, and delegation is
           bounded by code rather than by prompt wording.
  Part 2 — live delegation on gpt-6-luna via Portkey. Skipped, never passed,
           if credentials are unavailable.

No payment, purchase, approval, or ticket resolution is performed, and tickets
101-103 are not hard-coded anywhere. The live request used here is a read-only
inventory question.

Run:  .venv/bin/python tests/verify_team.py
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._isolation import assert_audit_isolated, isolate_audit

# Must run before any mcp_server import: the audit module resolves its path at
# import time, so a later redirect would be too late.
isolate_audit()

from pydantic_ai import RunContext  # noqa: E402
from pydantic_ai.usage import RunUsage  # noqa: E402

from agents import model as model_cfg  # noqa: E402
from agents.mcp_client import FORBIDDEN_TOOL_NAMES  # noqa: E402
from agents.schemas import SpecialistFinding, TeamOutcome  # noqa: E402
from agents.team import (  # noqa: E402
    SPECIALIST_TOOLS,
    TEAM_USAGE_LIMITS,
    CampusCustomsTeam,
    TeamSession,
)
from mcp_server import db  # noqa: E402

PASS, FAIL, SKIP = [], [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def skip(name: str, why: str) -> None:
    SKIP.append(name)
    print(f"  SKIP  {name}  — {why}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def tools_visible_to(agent) -> set[str]:
    """The tool names an agent would actually be offered at run time."""
    names: set[str] = set()
    for toolset in agent.toolsets:
        ctx = RunContext(deps=None, model=agent.model, usage=RunUsage())
        async with toolset:
            tools = await toolset.get_tools(ctx)
        names |= set(tools)
    return names


async def part1(team: CampusCustomsTeam) -> None:
    print("\n[0] this test run cannot touch the production audit trail")
    assert_audit_isolated()
    check("audit writes are redirected away from output/audit_trail.json", True,
          "isolated via CAMPUS_CUSTOMS_AUDIT_PATH")

    print("\n[1] the five agents exist and are distinct")
    check("four specialists plus a boss", len(team.specialists) == 4 and team.boss is not None)
    for role in ("inventory", "accounting", "facilities", "customer_service"):
        check(f"{role} agent built", role in team.specialists)
    check("each agent is its own Agent instance, not the Boss reused",
          len({id(a) for a in [team.boss, *team.specialists.values()]}) == 5)
    check("every agent is named for the dashboard to attribute work",
          all(a.name for a in team.specialists.values()) and team.boss.name == "boss")

    print("\n[2] every agent runs gpt-6-luna through Portkey's Responses API")
    for name, agent in [("boss", team.boss), *team.specialists.items()]:
        model = agent.model
        check(f"{name} uses gpt-6-luna",
              model.model_name == "gpt-6-luna" and type(model).__name__ == "OpenAIResponsesModel",
              type(model).__name__)

    print("\n[3] least privilege: each specialist sees only its own MCP tools")
    for role, allowed in SPECIALIST_TOOLS.items():
        visible = await tools_visible_to(team.specialists[role])
        check(f"{role} sees exactly its {len(allowed)} declared tools",
              visible == allowed, f"{len(visible)} visible")

    inv = await tools_visible_to(team.specialists["inventory"])
    check("Inventory cannot propose a payment", "propose_payment" not in inv)
    fac = await tools_visible_to(team.specialists["facilities"])
    check("Facilities cannot propose a payment (must route through Accounting)",
          "propose_payment" not in fac)
    cs = await tools_visible_to(team.specialists["customer_service"])
    check("Customer Service cannot touch money", not {"propose_payment", "get_cash_balance"} & cs)
    acct = await tools_visible_to(team.specialists["accounting"])
    check("Accounting CAN prepare a payment proposal", "propose_payment" in acct)

    print("\n[4] the approval boundary survives into the agent team")
    for role in SPECIALIST_TOOLS:
        visible = await tools_visible_to(team.specialists[role])
        check(f"{role} has no approval-granting tool", not visible & FORBIDDEN_TOOL_NAMES)
        check(f"{role} cannot execute payments or purchases",
              not {"execute_payment", "execute_purchase"} & visible)
    team_source = (Path("agents/team.py").read_text() + Path("agents/schemas.py").read_text())

    # Parse rather than grep: a docstring that *mentions* approval.grant() is
    # documentation, not a privilege. Only real imports and calls count.
    import ast

    def privileged_references(path: Path) -> list[str]:
        tree = ast.parse(path.read_text())
        hits: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and "approval" in (node.module or ""):
                hits.append(f"{path.name}: from {node.module} import ...")
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in {"approval", "approve"}:
                        hits.append(f"{path.name}: from {node.module} import {alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "approval" in alias.name or alias.name.endswith(".approve"):
                        hits.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.Attribute) and node.attr == "grant":
                hits.append(f"{path.name}: .grant() call")
        return hits

    all_hits = [h for f in Path("agents").rglob("*.py") for h in privileged_references(f)]
    check("no agent module imports or calls the privileged approval code",
          not all_hits, "; ".join(all_hits) or "clean (AST-verified)")
    check("no agent module reads the signing key",
          not any("approval_key" in f.read_text() for f in Path("agents").rglob("*.py")))

    print("\n[5] delegation is bounded by code, not by prompt wording")
    boss_tools = {t for t in team.boss._function_toolset.tools}
    check("Boss has exactly four delegation tools",
          boss_tools == {"consult_inventory", "consult_accounting",
                         "consult_facilities", "consult_customer_service"},
          str(sorted(boss_tools)))
    for role, agent in team.specialists.items():
        check(f"{role} has no delegation tool — recursion is impossible by construction",
              not agent._function_toolset.tools)

    session = TeamSession(specialists=team.specialists)
    ctx = RunContext(deps=session, model=team.boss.model, usage=RunUsage())
    session.consulted.append("inventory")
    repeated = False
    try:
        await session.consult(ctx, "inventory", "ask again")
    except ValueError:
        repeated = True
    check("a specialist cannot be consulted twice in one request", repeated)
    check("usage limits cap the whole request",
          TEAM_USAGE_LIMITS.request_limit == 40 and TEAM_USAGE_LIMITS.tool_calls_limit == 60)

    print("\n[6] structured outputs carry what the dashboard needs")
    for field in ("specialists_consulted", "findings", "summary", "dependencies",
                  "proposed_actions", "needs_human_approval", "open_questions", "handled_by"):
        check(f"TeamOutcome exposes {field}", field in TeamOutcome.model_fields)
    for field in ("agent", "summary", "facts", "constraints", "proposed_actions",
                  "needs_human_approval", "unresolved"):
        check(f"SpecialistFinding exposes {field}", field in SpecialistFinding.model_fields)
    check("Boss output is the structured TeamOutcome", team.boss.output_type is TeamOutcome)
    check("specialist output is the structured SpecialistFinding",
          all(a.output_type is SpecialistFinding for a in team.specialists.values()))

    print("\n[7] no ticket outcomes are hard-coded")
    joined = team_source + "".join(
        p.read_text() for p in Path("agents/prompts").glob("*.md"))
    check("no ticket id appears in team code or prompts",
          not any(t in joined for t in ("101", "102", "103")))


async def part2(team: CampusCustomsTeam) -> None:
    print("\n[8] live delegation on gpt-6-luna via Portkey")
    if not model_cfg.credentials_available():
        for name in ("Boss delegates to a real specialist agent",
                     "specialist findings are grounded in tool results",
                     "no action is taken without approval"):
            skip(name, "PORTKEY_API_KEY not set — not claiming a live pass")
        return

    request = (
        "A student is asking about SKU CC-TEE-WHITE in size S. Find out whether we can "
        "fill that order today, and if not, what the restock path would be. Do not pay "
        "for or order anything."
    )
    try:
        outcome = await team.run(request)
    except Exception as exc:  # noqa: BLE001
        check("Boss delegates to a real specialist agent", False, f"live run failed: {exc!r}")
        return

    check("Boss returned a structured TeamOutcome", isinstance(outcome, TeamOutcome))
    check("Boss actually delegated to at least one specialist",
          len(outcome.specialists_consulted) >= 1, str(outcome.specialists_consulted))
    check("Inventory was consulted for a stock question",
          "inventory" in outcome.specialists_consulted, str(outcome.specialists_consulted))
    check("delegation was recorded by the session, not self-reported",
          len(outcome.findings) == len(outcome.specialists_consulted))
    check("each finding is attributed to the agent that actually ran",
          all(f.agent in outcome.specialists_consulted for f in outcome.findings))

    inv = next((f for f in outcome.findings if f.agent == "inventory"), None)
    if inv is None:
        check("Inventory finding is grounded in tool results", False, "no inventory finding")
    else:
        blob = " ".join([inv.summary, *inv.facts, *inv.constraints]).lower()
        check("Inventory reports the real shortage (0 in stock, from the database)",
              "0" in blob or "zero" in blob or "out of stock" in blob,
              inv.summary[:110])
        check("Inventory names a real vendor lead time or arrival date",
              any(s in blob for s in ("2026-09", "5 day", "lead")), inv.summary[:110])

    print("\n[8b] collaboration across specialists on a multi-domain request")
    multi = (
        "Rent is coming due on the shop lease and we also have an unpaid vendor invoice. "
        "Tell me where we stand financially and what the lease actually says. "
        "Prepare nothing for payment yet."
    )
    try:
        outcome2 = await team.run(multi)
    except Exception as exc:  # noqa: BLE001
        check("Boss consults multiple specialists when a request spans domains", False, repr(exc))
        return
    check("Boss consults multiple specialists when a request spans domains",
          len(outcome2.specialists_consulted) >= 2, str(outcome2.specialists_consulted))
    check("both Accounting and Facilities contributed",
          {"accounting", "facilities"} <= set(outcome2.specialists_consulted),
          str(outcome2.specialists_consulted))
    check("the Boss synthesised a summary across them", len(outcome2.summary) > 40)
    check("no specialist was consulted twice",
          len(outcome2.specialists_consulted) == len(set(outcome2.specialists_consulted)))

    print("\n[9] nothing was executed and no approval was granted")
    from mcp_server import proposals
    executed = [p for p in proposals.list_all() if p["status"] == "executed"]
    approved = [p for p in proposals.list_all() if p["status"] == "approved"]
    check("no proposal was executed by the team", not executed)
    check("no proposal was approved by the team", not approved)
    with __import__("sqlite3").connect(f"file:{db.WORKING_DB}?mode=ro", uri=True) as c:
        n_pay = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        n_open = c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    check("no payments were recorded", n_pay == 0)
    check("checking balance still 3400.0", bal == 3400.0)
    check("tickets 101-103 still open and unresolved", n_open == 3)


async def main() -> int:
    original_before = sha256(db.ORIGINAL_DB)
    working_before = sha256(db.WORKING_DB)

    team = CampusCustomsTeam.build()
    await part1(team)
    await part2(team)

    print("\n[10] database integrity")
    check("original campus_customs.db checksum unchanged",
          sha256(db.ORIGINAL_DB) == original_before)
    check("working campus_customs_new.db unchanged",
          sha256(db.WORKING_DB) == working_before)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
    for name in FAIL:
        print(f"  FAILED: {name}")
    if SKIP:
        print("  (skipped checks are NOT passes — live delegation is unverified)")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
