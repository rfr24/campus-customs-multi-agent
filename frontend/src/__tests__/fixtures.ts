// Isolated frontend fixtures. These exist only so component behaviour can be
// tested without a live backend or model calls; the running dashboard always
// uses real API data.

import type { OperationalState, Proposal, TicketDetail } from '../api/types'

export const state: OperationalState = {
  shop_date: '2026-08-31',
  cash: { name: 'checking', balance: 3400, date: '2026-08-31' },
  open_tickets: [],
  open_invoices: [{
    id: 501, vendor_id: 1, vendor_name: 'Bulldog Print Co', amount: 840,
    due_date: '2026-08-28', status: 'open', description: 'Rush reprint',
    days_to_due: -3, overdue: true,
  }],
  leases: [{
    id: 1, space_name: 'Chapel Street shop', landlord: 'Elm City Properties',
    monthly_rent: 2400, next_due: '2026-09-02', days_to_due: 2, notes: null,
  }],
  payments: [],
  pending_approval_count: 1,
  approved_awaiting_execution_count: 0,
}

export const pendingProposal: Proposal = {
  proposal_id: 'PAY-0001', kind: 'payment', target: 'rent:1', amount: 2400,
  account: 'checking', detail: {}, status: 'pending_human_approval',
  created_at: '2026-08-31T10:00:00+00:00', decided_at: null, decided_by: null,
  approved_by: null, approved_at: null,
}

export const approvedProposal: Proposal = {
  ...pendingProposal, status: 'approved',
  approved_by: 'operator (local)', approved_at: '2026-08-31T10:05:00+00:00',
}

export const ticketDetail: TicketDetail = {
  ok: true,
  ticket: {
    id: 101, type: 'customer_order', requester: 'Tauhid Zaman', subject: 'Bulldog tee',
    sku: 'CC-TEE-WHITE', size: 'S', qty: 1, lease_id: null, invoice_id: 501,
    status: 'open', notes: 'Needs a tee in size S.', created_at: '2026-08-31T09:15:00-04:00',
  },
  lease: null,
  invoice: {
    id: 501, vendor_id: 1, amount: 840, due_date: '2026-08-28', status: 'open',
    description: 'Rush reprint', overdue: true,
  },
  runs: [{
    run_id: 'run-abc123', ticket_id: 101,
    started_at: '2026-08-31T10:00:00+00:00', finished_at: '2026-08-31T10:01:00+00:00',
    stage: 'awaiting_human_approval', ticket_status: 'open',
    error: null, stop_reason: null,
    outcome: {
      request: 'Handle ticket 101', handled_by: 'boss',
      specialists_consulted: ['inventory', 'accounting'],
      findings: [{
        agent: 'inventory',
        summary: 'CC-TEE-WHITE size S is out of stock.',
        facts: ['CC-TEE-WHITE/S qty = 0'],
        constraints: ['Earliest restock 2026-09-05'],
        proposed_actions: [],
        needs_human_approval: false,
        unresolved: [],
      }],
      summary: 'Cannot fill from stock today.',
      dependencies: ['Rent and invoice 501 compete for one balance'],
      proposed_actions: [{
        proposal_id: 'PAY-0001', description: 'Pay invoice 501',
        amount: 840, requires_human_approval: true,
      }],
      needs_human_approval: true,
      open_questions: ['Which obligation should be paid first?'],
    },
  }],
}
