"""The five-agent Campus Customs team.

  Boss ──delegates──► Inventory | Accounting | Facilities | Customer Service

Delegation is real PydanticAI agent-to-agent interaction: each `consult_*` tool
on the Boss runs a *separate* `Agent` with its own model, its own system prompt,
and its own filtered view of the MCP toolset. The Boss never role-plays a
specialist, and specialists never receive the Boss's prompt.

Three structural limits keep delegation bounded:

1. **Specialists have no delegation tools.** The graph is one level deep by
   construction, so recursive loops are impossible rather than merely discouraged.
2. **One consultation per specialist per request**, enforced in code by
   `TeamSession`, not left to the Boss's judgment.
3. **Shared usage limits.** Every nested run bills to the same `RunUsage`, so a
   whole request is capped end to end rather than per agent.

Least privilege: each specialist sees only the MCP tools its role needs, via
`MCPToolset.filtered()`. No agent on any path can reach an approval-granting
capability — none is exposed over MCP at all (harness §B4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import RunUsage, UsageLimits

from agents.mcp_client import inprocess_toolset, stdio_toolset
from agents.model import build_model
from agents.schemas import SpecialistFinding, SpecialistName, TeamOutcome

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

# Tools each specialist may see. Least privilege: Inventory cannot propose a
# payment, Facilities cannot move money, Customer Service reads tickets only.
SPECIALIST_TOOLS: dict[SpecialistName, set[str]] = {
    "inventory": {
        "get_today", "lookup_inventory", "get_pricing", "list_vendors",
        "get_ticket", "list_tickets",
        # Restock purchasing belongs here: propose_purchase takes (sku, size,
        # qty, vendor_id) — exactly the facts Inventory already owns, and it
        # computes cost from pricing.unit_cost so the caller cannot invent a
        # price. Added after a Problem 9 run in which Inventory correctly
        # reported it could not prepare a purchase, because no specialist held
        # this tool. (See harness H8a.)
        "propose_purchase", "list_proposals",
    },
    "accounting": {
        "get_today", "get_cash_balance", "list_invoices", "get_invoice",
        "list_payments", "list_leases", "get_lease", "get_pricing",
        "propose_payment", "list_proposals", "get_ticket",
        # Read-only. Without it, Accounting costed a restock request's full
        # requested quantity instead of the shortfall, because it could not see
        # what was already on hand.
        "lookup_inventory",
    },
    "facilities": {
        "get_today", "list_leases", "get_lease", "list_payments",
        "get_ticket", "list_tickets",
    },
    "customer_service": {
        "get_today", "list_tickets", "get_ticket", "lookup_inventory", "get_pricing",
    },
}

# Caps for one end-to-end team request. Sized for a Boss turn plus four
# specialist consultations with several tool calls each, and generous enough
# that a legitimate request is never truncated.
TEAM_USAGE_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60)
SPECIALIST_RETRIES = 2


def _prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        raise RuntimeError(f"System prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def _toolset_for(role: SpecialistName, *, in_process: bool):
    """The shared MCP toolset, narrowed to one role's tools."""
    base = inprocess_toolset() if in_process else stdio_toolset()
    allowed = SPECIALIST_TOOLS[role]
    return base.filtered(lambda ctx, tool_def: tool_def.name in allowed)


def build_specialist(role: SpecialistName, *, in_process: bool = True) -> Agent:
    """Build one specialist agent on gpt-6-luna with its own filtered toolset."""
    return Agent(
        build_model(),
        name=role,
        system_prompt=_prompt(role),
        output_type=SpecialistFinding,
        toolsets=[_toolset_for(role, in_process=in_process)],
        retries=SPECIALIST_RETRIES,
    )


@dataclass
class TeamSession:
    """Per-request state the Boss's delegation tools run against.

    Holds the specialist agents and the record of who was consulted, so the
    ticket runner and dashboard can see the real delegation path rather than
    taking the Boss's word for it.
    """

    specialists: dict[SpecialistName, Agent]
    consulted: list[SpecialistName] = field(default_factory=list)
    findings: list[SpecialistFinding] = field(default_factory=list)

    async def consult(self, ctx: RunContext[TeamSession], role: SpecialistName,
                      task: str) -> SpecialistFinding:
        """Run one specialist. Refuses a second consultation of the same role."""
        if role in self.consulted:
            raise ValueError(
                f"{role} has already been consulted for this request. Use its existing "
                "finding, or record what is still missing in open_questions."
            )
        self.consulted.append(role)
        # Nested run shares the parent's usage, so limits apply to the whole request.
        result = await self.specialists[role].run(task, usage=ctx.usage)
        finding = result.output
        # Trust the structure, not the label: the agent that ran is the agent recorded.
        finding.agent = role
        self.findings.append(finding)
        return finding


def build_boss(*, in_process: bool = True) -> Agent[TeamSession, TeamOutcome]:
    """Build the Boss with one delegation tool per specialist."""
    boss = Agent(
        build_model(),
        name="boss",
        system_prompt=_prompt("boss"),
        output_type=TeamOutcome,
        deps_type=TeamSession,
        retries=SPECIALIST_RETRIES,
    )

    @boss.tool
    async def consult_inventory(ctx: RunContext[TeamSession], task: str) -> SpecialistFinding:
        """Ask the Inventory agent about stock, shortages, costs, or restock options.

        `task` should be a specific, self-contained question, e.g. "How many
        CC-TEE-WHITE size S are in stock, and when could more arrive?"
        """
        return await ctx.deps.consult(ctx, "inventory", task)

    @boss.tool
    async def consult_accounting(ctx: RunContext[TeamSession], task: str) -> SpecialistFinding:
        """Ask the Accounting agent about cash, invoices, affordability, or to prepare
        a payment proposal for human approval."""
        return await ctx.deps.consult(ctx, "accounting", task)

    @boss.tool
    async def consult_facilities(ctx: RunContext[TeamSession], task: str) -> SpecialistFinding:
        """Ask the Facilities agent about leases, rent obligations, and due dates."""
        return await ctx.deps.consult(ctx, "facilities", task)

    @boss.tool
    async def consult_customer_service(ctx: RunContext[TeamSession],
                                       task: str) -> SpecialistFinding:
        """Ask the Customer Service agent to interpret a customer request or draft a reply."""
        return await ctx.deps.consult(ctx, "customer_service", task)

    return boss


@dataclass
class CampusCustomsTeam:
    """The assembled team. Build once, reuse across requests.

    The later ticket runner and dashboard use `run()` and read `TeamOutcome`.
    """

    boss: Agent
    specialists: dict[SpecialistName, Agent]

    @classmethod
    def build(cls, *, in_process: bool = True) -> CampusCustomsTeam:
        return cls(
            boss=build_boss(in_process=in_process),
            specialists={
                role: build_specialist(role, in_process=in_process)
                for role in SPECIALIST_TOOLS
            },
        )

    async def run(self, request: str, *, usage: RunUsage | None = None) -> TeamOutcome:
        """Handle one operational request end to end.

        The returned TeamOutcome records who was consulted according to the
        session's own ledger, not the Boss's self-report.
        """
        session = TeamSession(specialists=self.specialists)
        result = await self.boss.run(
            request, deps=session, usage=usage, usage_limits=TEAM_USAGE_LIMITS
        )
        outcome = result.output
        outcome.request = request
        outcome.handled_by = "boss"
        outcome.specialists_consulted = list(session.consulted)
        outcome.findings = list(session.findings)
        # Approval need is derived from what actually got proposed, so the Boss
        # cannot under-report it.
        proposed = [a for f in session.findings for a in f.proposed_actions]
        outcome.proposed_actions = proposed or outcome.proposed_actions
        outcome.needs_human_approval = (
            bool(outcome.proposed_actions)
            or any(f.needs_human_approval for f in session.findings)
            or outcome.needs_human_approval
        )
        return outcome
