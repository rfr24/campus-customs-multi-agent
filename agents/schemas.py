"""Structured outputs for the Campus Customs agent team.

These are the contract the later ticket runner and dashboard read. Every field
exists to answer one of the questions those consumers need to ask: who handled
this, who was consulted, what was found, does it need a human, and was anything
actually proposed.

A deliberate distinction runs through these models: a **finding** is a verified
fact read from a tool, while a **proposed action** is something that has not
happened and will not happen until a human approves it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SpecialistName = Literal["inventory", "accounting", "facilities", "customer_service"]


class ProposedAction(BaseModel):
    """An action prepared for a human, not an action taken."""

    proposal_id: str | None = Field(
        None, description="The id returned by propose_payment/propose_purchase, if one was created."
    )
    description: str = Field(description="What is being proposed, in one line.")
    amount: float | None = Field(None, description="Cost in dollars, if the action costs money.")
    requires_human_approval: bool = Field(
        True, description="Always true for anything touching money or stock."
    )


class SpecialistFinding(BaseModel):
    """What one specialist established about one task."""

    agent: SpecialistName
    summary: str = Field(description="The answer, in two or three sentences.")
    facts: list[str] = Field(
        default_factory=list,
        description="Verified facts read from MCP tools, each citing the concrete value.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Blockers or limits found in the data, e.g. a shortage or a cash ceiling.",
    )
    proposed_actions: list[ProposedAction] = Field(
        default_factory=list, description="Actions prepared for human approval. May be empty."
    )
    needs_human_approval: bool = Field(
        False, description="True if resolving this requires a human to approve something."
    )
    unresolved: list[str] = Field(
        default_factory=list,
        description="Questions the data cannot answer — policy calls a human must make.",
    )


class TeamOutcome(BaseModel):
    """The Boss's synthesis of a request handled by the team."""

    request: str = Field(description="The request as received.")
    handled_by: str = Field("boss", description="The coordinating agent.")
    specialists_consulted: list[SpecialistName] = Field(
        default_factory=list, description="Which specialists the Boss actually delegated to."
    )
    findings: list[SpecialistFinding] = Field(
        default_factory=list, description="Each specialist's structured finding."
    )
    summary: str = Field(description="The Boss's synthesis across specialists.")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Cross-ticket couplings that matter, especially shared cash and stock.",
    )
    proposed_actions: list[ProposedAction] = Field(
        default_factory=list, description="Everything prepared for a human, across specialists."
    )
    needs_human_approval: bool = Field(
        False, description="True if any proposed action awaits approval."
    )
    open_questions: list[str] = Field(
        default_factory=list, description="Policy decisions the data does not settle."
    )
