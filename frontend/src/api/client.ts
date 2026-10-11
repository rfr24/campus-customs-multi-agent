// Minimal API client. It knows how to call the backend and how to report
// failures — nothing else. All business rules stay on the server.

import type {
  AuditEntry, CashAccount, OperationalState, Proposal, Ticket, TicketDetail, TicketRun,
} from './types'

/** An API failure carrying the backend's own status and stop_reason. */
export class ApiError extends Error {
  readonly status: number
  readonly stopReason?: string

  constructor(message: string, status: number, stopReason?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.stopReason = stopReason
  }

  /** A sentence an operator can act on, rather than a raw status code. */
  get operatorMessage(): string {
    switch (this.stopReason) {
      case 'insufficient_funds':
        return `Not enough cash to cover this. ${this.message}`
      case 'duplicate_payment':
        return `This obligation was already paid. ${this.message}`
      case 'approval_rejected':
        return `Refused by the approval boundary. ${this.message}`
      case 'already_executed':
        return 'This proposal has already been carried out.'
      default:
        break
    }
    if (this.status === 401) return 'Operator token missing or invalid. Sign in again.'
    if (this.status === 502) return `The agent team could not finish. ${this.message}`
    return this.message
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  // The token is passed per-call from in-memory state; it is never stored here.
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(path, { ...init, headers })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    let stopReason: string | undefined
    try {
      const body = await response.json()
      const detail = body?.detail
      if (typeof detail === 'string') {
        message = detail
      } else if (detail && typeof detail === 'object') {
        message = detail.error ?? detail.message ?? message
        stopReason = detail.stop_reason
      }
    } catch {
      // Keep the status-based message when the body is not JSON.
    }
    throw new ApiError(message, response.status, stopReason)
  }

  return response.json() as Promise<T>
}

export const api = {
  state: () => request<OperationalState>('/api/state'),
  cash: () => request<{ account: CashAccount }>('/api/cash'),

  tickets: (status = '') =>
    request<{ tickets: Ticket[]; count: number }>(
      `/api/tickets${status ? `?status=${encodeURIComponent(status)}` : ''}`,
    ),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),

  processTicket: (id: number) =>
    request<TicketRun>(`/api/tickets/${id}/process`, {
      method: 'POST',
      body: JSON.stringify({ mark_in_progress: false }),
    }),

  runs: (ticketId?: number) =>
    request<{ runs: TicketRun[]; count: number }>(
      `/api/runs${ticketId ? `?ticket_id=${ticketId}` : ''}`,
    ),

  proposals: (status = '') =>
    request<{ proposals: Proposal[]; count: number }>(
      `/api/proposals${status ? `?status=${encodeURIComponent(status)}` : ''}`,
    ),

  audit: (limit = 60) => request<{ entries: AuditEntry[]; count: number }>(`/api/audit?limit=${limit}`),

  // --- operator routes: every one requires a token ---
  whoami: (token: string) =>
    request<{ authenticated: boolean; principal: string }>('/api/operator/whoami', {}, token),

  approve: (token: string, proposalId: string, approvedAmount: number) =>
    request<{ ok: boolean; proposal: Proposal }>(
      `/api/operator/proposals/${proposalId}/approve`,
      { method: 'POST', body: JSON.stringify({ approved_amount: approvedAmount }) },
      token,
    ),

  reject: (token: string, proposalId: string, reason: string) =>
    request<{ ok: boolean; proposal: Proposal }>(
      `/api/operator/proposals/${proposalId}/reject`,
      { method: 'POST', body: JSON.stringify({ reason }) },
      token,
    ),

  execute: (token: string, proposalId: string) =>
    request<{ ok: boolean; result: Record<string, unknown>; executed_by: string }>(
      `/api/operator/proposals/${proposalId}/execute`,
      { method: 'POST' },
      token,
    ),
}
