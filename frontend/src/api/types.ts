// Shapes returned by the FastAPI backend. These mirror the Pydantic models in
// `agents/schemas.py` and `backend/main.py` — they do not add rules of their own.

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
}

export interface Invoice {
  id: number
  vendor_id: number
  vendor_name?: string
  amount: number
  due_date: string
  status: string
  description: string | null
  days_to_due?: number
  overdue?: boolean
}

export interface Lease {
  id: number
  space_name: string
  landlord: string
  monthly_rent: number
  next_due: string
  days_to_due?: number
  notes: string | null
}

export interface ProposedAction {
  proposal_id: string | null
  description: string
  amount: number | null
  requires_human_approval: boolean
}

export interface SpecialistFinding {
  agent: string
  summary: string
  facts: string[]
  constraints: string[]
  proposed_actions: ProposedAction[]
  needs_human_approval: boolean
  unresolved: string[]
}

export interface TeamOutcome {
  request: string
  handled_by: string
  specialists_consulted: string[]
  findings: SpecialistFinding[]
  summary: string
  dependencies: string[]
  proposed_actions: ProposedAction[]
  needs_human_approval: boolean
  open_questions: string[]
}

/** How far a processing run got. Note there is no "resolved" stage: a
 *  recommendation is not a resolution. */
export type RunStage = 'investigated' | 'awaiting_human_approval' | 'failed'

export interface TicketRun {
  run_id: string
  ticket_id: number
  started_at: string
  finished_at: string
  stage: RunStage
  ticket_status: string
  outcome: TeamOutcome | null
  error: string | null
  stop_reason: string | null
}

export type ProposalStatus =
  | 'pending_human_approval'
  | 'approved'
  | 'executed'
  | 'rejected'

export interface Proposal {
  proposal_id: string
  kind: 'payment' | 'purchase'
  target: string
  amount: number
  account: string
  detail: Record<string, unknown>
  status: ProposalStatus
  created_at: string
  decided_at: string | null
  decided_by: string | null
  approved_by: string | null
  approved_at: string | null
  outcome?: Record<string, unknown>
}

export interface CashAccount {
  name: string
  balance: number
  date: string
}

export interface OperationalState {
  shop_date: string
  cash: CashAccount
  open_tickets: Ticket[]
  open_invoices: Invoice[]
  leases: Lease[]
  payments: Payment[]
  pending_approval_count: number
  approved_awaiting_execution_count: number
}

export interface Payment {
  id: number
  kind: string
  ref_id: number | null
  amount: number
  account: string
  paid_at: string
  approved_by: string
}

export interface AuditEntry {
  time: string
  tool: string
  args: Record<string, unknown>
  result: string
  stop_reason: string
}

export interface TicketDetail {
  ok: boolean
  ticket: Ticket
  lease: Lease | null
  invoice: Invoice | null
  runs: TicketRun[]
}
