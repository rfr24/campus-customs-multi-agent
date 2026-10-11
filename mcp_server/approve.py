"""Operator CLI for the human approval step. PRIVILEGED — not an MCP tool.

This is the human side of the trust boundary until the authenticated dashboard
route exists. Whoever can run this command is, by definition, the operator:
it is reachable from a shell on the server, never from an agent.

    .venv/bin/python -m mcp_server.approve --list
    .venv/bin/python -m mcp_server.approve --approve PAY-0001 --amount 2400.00 --by "Rachel"
    .venv/bin/python -m mcp_server.approve --reject  PAY-0001 --by "Rachel" --reason "defer"
"""

from __future__ import annotations

import argparse
import sys

from mcp_server import approval, proposals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mcp_server.approve", description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="show proposals")
    group.add_argument("--approve", metavar="PROPOSAL_ID")
    group.add_argument("--reject", metavar="PROPOSAL_ID")
    ap.add_argument("--amount", type=float, help="must match the proposed amount exactly")
    ap.add_argument("--by", help="name of the human approving")
    ap.add_argument("--reason", default="")
    args = ap.parse_args(argv)

    if args.list:
        items = proposals.list_all()
        if not items:
            print("No proposals.")
            return 0
        for p in items:
            who = p["approval"]["approved_by"] if p.get("approval") else "-"
            print(f"{p['proposal_id']:<10} {p['status']:<22} {p['amount']:>10.2f}  "
                  f"{p['target']:<34} approved_by={who}")
        return 0

    if not args.by:
        ap.error("--by is required: record which human is deciding")

    if args.approve:
        if args.amount is None:
            ap.error("--amount is required when approving, and must match the proposal")
        try:
            updated = approval.grant(args.approve, args.amount, args.by)
        except approval.ApprovalError as exc:
            print(f"Refused: {exc}", file=sys.stderr)
            return 1
        print(f"Approved {updated['proposal_id']} for {updated['amount']:.2f} by {args.by}.")
        print("Run the matching execute_payment / execute_purchase tool to carry it out.")
        return 0

    try:
        updated = proposals.mark(args.reject, proposals.STATUS_REJECTED, args.by,
                                 {"reason": args.reason})
    except proposals.ApprovalError as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1
    print(f"Rejected {updated['proposal_id']} by {args.by}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
