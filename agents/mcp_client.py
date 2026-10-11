"""Shared MCP connection for the Campus Customs agent team.

One place that knows how to reach the Problem 3 MCP server, so the five agents
(Boss, Inventory, Accounting, Facilities, Customer Service) built in later
problems all attach the *same* toolset rather than each opening its own
connection or — worse — its own database handle.

Two transports, same server:

* `stdio_toolset()`  — launches `python -m mcp_server.server` as a subprocess.
  This is the deployment shape: the agent process and the server process are
  separate, so the agent reaches the shop only through MCP.
* `inprocess_toolset()` — attaches to the `FastMCP` object directly, no
  subprocess. Fast and deterministic; used by the test suite.

Both expose exactly the 19 tools defined in `mcp_server/server.py`. There is no
approval-granting tool on either path: `approval.grant()` and the operator CLI
are deliberately outside the MCP surface (see harness §B4).
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_ai.mcp import MCPToolset, StdioTransport

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Capabilities an agent must never be able to call. Asserted at connection time
# rather than trusted, so a future change to server.py that accidentally
# exposes approval fails loudly here.
FORBIDDEN_TOOL_NAMES = {"grant_approval", "approve_proposal", "approve", "grant"}


def stdio_toolset(**kwargs) -> MCPToolset:
    """Connect to the MCP server as a subprocess over stdio."""
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(PROJECT_ROOT),
    )
    return MCPToolset(transport, id="campus-customs", **kwargs)


def inprocess_toolset(**kwargs) -> MCPToolset:
    """Attach to the FastMCP server object in this process (tests)."""
    from mcp_server.server import mcp

    return MCPToolset(mcp, id="campus-customs", **kwargs)


async def assert_no_approval_tools(toolset: MCPToolset) -> list[str]:
    """Fail loudly if the agent-facing toolset ever gains approval authority.

    Returns the discovered tool names so a caller can log or assert on them.
    """
    async with toolset:
        names = [t.name for t in await toolset.list_tools()]
    leaked = sorted(set(names) & FORBIDDEN_TOOL_NAMES)
    if leaked:
        raise RuntimeError(
            f"MCP toolset exposes approval capability to agents: {', '.join(leaked)}. "
            "Approval must stay on the privileged side of the trust boundary."
        )
    return names
