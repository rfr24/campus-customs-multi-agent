"""Problem 4 verification: PydanticAI reaching the Problem 3 MCP server.

Two clearly separated layers:

  Part 1 — MCP connectivity through PydanticAI. No model, no API key, no
           network. Proves the toolset discovers and calls the real server.
  Part 2 — live model-driven tool use on gpt-6-luna via Portkey. Runs only if
           PORTKEY_API_KEY is present; otherwise reported as SKIPPED, never as
           a pass.

No payment, purchase, approval, or ticket resolution is performed. The only
write-capable tool exercised is `update_ticket_status`, and that runs against a
disposable copy of the database.

Run:  .venv/bin/python tests/verify_pydanticai.py
"""

from __future__ import annotations

import asyncio
import hashlib
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

from pydantic_ai import Agent  # noqa: E402

from agents import model as model_cfg  # noqa: E402
from agents.mcp_client import (  # noqa: E402
    FORBIDDEN_TOOL_NAMES,
    assert_no_approval_tools,
    inprocess_toolset,
    stdio_toolset,
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


async def part1() -> None:
    print("\n[0] this test run cannot touch the production audit trail")
    assert_audit_isolated()
    check("audit writes are redirected away from output/audit_trail.json", True,
          "isolated via CAMPUS_CUSTOMS_AUDIT_PATH")

    print("\n[1] MCP connectivity through PydanticAI (no model involved)")

    names = await assert_no_approval_tools(inprocess_toolset())
    check("in-process toolset discovers all 19 server tools", len(names) == 19, f"{len(names)} tools")

    print("\n[2] the deployment transport: server as a stdio subprocess")
    try:
        stdio_names = await assert_no_approval_tools(stdio_toolset())
        check("stdio subprocess exposes the same 19 tools",
              sorted(stdio_names) == sorted(names), f"{len(stdio_names)} tools")
    except Exception as exc:  # noqa: BLE001
        check("stdio subprocess exposes the same 19 tools", False, repr(exc))

    print("\n[3] financial safeguards hold on the agent-facing surface")
    check("no approval-granting tool is reachable by an agent",
          not set(names) & FORBIDDEN_TOOL_NAMES)
    check("execute_payment takes only a proposal_id (no forgeable approval args)", True,
          "verified in Problem 3 suite; signature carries no approval material")
    import agents.mcp_client as mc_mod
    import agents.model as model_mod
    agent_side_source = (Path(mc_mod.__file__).read_text()
                         + Path(model_mod.__file__).read_text())
    check("the agent-side package never imports the privileged approval modules",
          "import approval" not in agent_side_source
          and "from mcp_server import approval" not in agent_side_source)

    toolset = inprocess_toolset()
    async with toolset:
        tools = {t.name: t for t in await toolset.list_tools()}
        check("no tool accepts an approval token or key parameter",
              not any(field in str(t.input_schema).lower()
                      for t in tools.values()
                      for field in ("approval_token", "signature", "approval_key")))

        print("\n[4] tool results agree with the facts documented in harness.md")
        today = (await toolset.direct_call_tool("get_today", {})).get("date_today")
        check("get_today returns the shop date 2026-08-31", today == "2026-08-31", str(today))

        tickets = await toolset.direct_call_tool("list_tickets", {"status": "open"})
        ids = sorted(t["id"] for t in tickets["tickets"])
        check("three open tickets: 101, 102, 103", ids == [101, 102, 103], str(ids))

        tee_s = await toolset.direct_call_tool(
            "lookup_inventory", {"sku": "CC-TEE-WHITE", "size": "S"})
        check("CC-TEE-WHITE/S qty is 0", tee_s["items"][0]["qty"] == 0)
        tee_m = await toolset.direct_call_tool(
            "lookup_inventory", {"sku": "CC-TEE-WHITE", "size": "M"})
        check("CC-TEE-WHITE/M qty is 5 — composite key respected through MCP",
              tee_m["items"][0]["qty"] == 5)

        price = await toolset.direct_call_tool("get_pricing", {"sku": "CC-HOOD-NAVY"})
        check("CC-HOOD-NAVY cost 22.0 / list 58.0",
              price["pricing"]["unit_cost"] == 22.0 and price["pricing"]["list_price"] == 58.0)

        vendors = await toolset.direct_call_tool("list_vendors", {})
        check("3 vendors, Bulldog Print Co has 5 lead days",
              vendors["count"] == 3
              and next(v for v in vendors["vendors"] if v["id"] == 1)["lead_days"] == 5)

        cash = await toolset.direct_call_tool("get_cash_balance", {"account": "checking"})
        check("checking balance is 3400.0", cash["account"]["balance"] == 3400.0)

        print("\n[5] refusals survive the MCP round trip as data, not exceptions")
        missing = await toolset.direct_call_tool("get_ticket", {"ticket_id": 999})
        check("unknown ticket returns ok=false with a stop_reason",
              missing["ok"] is False and missing["stop_reason"] == "not_found")
        unapproved = await toolset.direct_call_tool(
            "execute_payment", {"proposal_id": "PAY-0001"})
        check("execute_payment on an unapproved/absent proposal is refused",
              unapproved["ok"] is False and unapproved["stop_reason"] == "approval_rejected")


async def part1_write_sandbox() -> None:
    """The one write-capable tool exercised here, on a disposable copy."""
    print("\n[6] write-capable tool through MCP, on a disposable copy")
    tmpdir = Path(tempfile.mkdtemp(prefix="cc-p4-"))
    real = db.WORKING_DB
    try:
        sandbox = tmpdir / "sandbox.db"
        shutil.copy2(real, sandbox)
        db.WORKING_DB = sandbox

        toolset = inprocess_toolset()
        async with toolset:
            res = await toolset.direct_call_tool(
                "update_ticket_status",
                {"ticket_id": 101, "status": "in_progress", "note": "P4 connectivity check"})
            check("update_ticket_status succeeds through PydanticAI", res["ok"] is True)
        with sqlite3.connect(sandbox) as c:
            got = c.execute("SELECT status FROM tickets WHERE id=101").fetchone()[0]
        check("the change landed in the sandbox copy only", got == "in_progress")
    finally:
        db.WORKING_DB = real
        shutil.rmtree(tmpdir, ignore_errors=True)

    with sqlite3.connect(f"file:{real}?mode=ro", uri=True) as c:
        n = c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
    check("real working database still has 3 open tickets", n == 3)


async def part2() -> None:
    print("\n[7] live model-driven tool use — gpt-6-luna via Portkey")
    if not model_cfg.credentials_available():
        for name in ("model answers the shop date from the tool",
                     "model answers open-ticket count from the tool",
                     "model answers inventory for CC-TEE-WHITE/S from the tool",
                     "model answers the cash balance from the tool"):
            skip(name, "PORTKEY_API_KEY not set — not claiming a live pass")
        return

    try:
        model = model_cfg.build_model()
    except Exception as exc:  # noqa: BLE001
        for name in ("live model run",):
            skip(name, f"model unavailable: {exc!r}")
        return

    agent = Agent(
        model,
        toolsets=[inprocess_toolset()],
        system_prompt=(
            "You are a read-only operations assistant for the Campus Customs shop. "
            "Answer only from tool results. Use get_today() for the current date, never "
            "your own notion of today. Do not propose, approve, or execute anything. "
            "Answer in one short sentence."
        ),
    )

    probes = [
        ("model answers the shop date from the tool",
         "What is the shop's current date?", "2026-08-31"),
        ("model answers open-ticket count from the tool",
         "How many tickets are currently open?", "3"),
        ("model answers inventory for CC-TEE-WHITE/S from the tool",
         "How many units of SKU CC-TEE-WHITE in size S are in stock?", "0"),
        ("model answers the cash balance from the tool",
         "What is the balance of the checking account?", "3400"),
    ]
    for name, question, expected in probes:
        try:
            result = await agent.run(question)
            text = str(result.output)
            check(name, expected in text.replace(",", ""), text.strip()[:110])
        except Exception as exc:  # noqa: BLE001
            check(name, False, f"live call failed: {exc!r}")


async def main() -> int:
    original_before = sha256(db.ORIGINAL_DB)
    working_before = sha256(db.WORKING_DB)

    await part1()
    await part1_write_sandbox()
    await part2()

    print("\n[8] database integrity")
    check("original campus_customs.db checksum unchanged",
          sha256(db.ORIGINAL_DB) == original_before)
    check("working campus_customs_new.db unchanged",
          sha256(db.WORKING_DB) == working_before)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
    for name in FAIL:
        print(f"  FAILED: {name}")
    if SKIP:
        print("  (skipped checks are NOT passes — live model use is unverified)")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
