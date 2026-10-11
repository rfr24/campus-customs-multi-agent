import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from './api/client'
import type {
  AuditEntry, OperationalState, Proposal, Ticket, TicketDetail as Detail, TicketRun,
} from './api/types'
import { ActivityPanel } from './components/ActivityPanel'
import { ApprovalQueue } from './components/ApprovalQueue'
import { Badge } from './components/Badge'
import { CashPanel } from './components/CashPanel'
import { OperatorBar } from './components/OperatorBar'
import { TicketDetail } from './components/TicketDetail'

export function App() {
  const [state, setState] = useState<OperationalState | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [runs, setRuns] = useState<TicketRun[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Session-scoped credential: state only, never persisted to the browser.
  const [token, setToken] = useState<string | null>(null)
  const [principal, setPrincipal] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [s, t, p, r, a] = await Promise.all([
        api.state(), api.tickets(), api.proposals(), api.runs(), api.audit(),
      ])
      setState(s)
      setTickets(t.tickets)
      setProposals(p.proposals)
      setRuns(r.runs)
      setAudit(a.entries)
      setSelectedId((current) => current ?? t.tickets[0]?.id ?? null)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.operatorMessage
          : 'Cannot reach the backend. Is it running on port 8000?',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshDetail = useCallback(async (id: number) => {
    try {
      setDetail(await api.ticket(id))
    } catch {
      setDetail(null)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => { if (selectedId !== null) void refreshDetail(selectedId) },
    [selectedId, refreshDetail])

  // After any action, re-read everything the action could have changed.
  const afterAction = useCallback(() => {
    void refresh()
    if (selectedId !== null) void refreshDetail(selectedId)
  }, [refresh, refreshDetail, selectedId])

  const latestStage = (ticketId: number): string | null => {
    const forTicket = runs
      .filter((r) => r.ticket_id === ticketId)
      .sort((a, b) => b.started_at.localeCompare(a.started_at))
    return forTicket[0]?.stage ?? null
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Campus Customs — Operations</h1>
        {state ? <span className="shop-date">Shop date {state.shop_date}</span> : null}
        <span className="spacer" />
        {state && state.pending_approval_count > 0 ? (
          <Badge
            status="awaiting"
            label={`${state.pending_approval_count} awaiting approval`}
          />
        ) : null}
        <OperatorBar
          token={token}
          principal={principal}
          onSignIn={(t, who) => { setToken(t); setPrincipal(who) }}
          onSignOut={() => { setToken(null); setPrincipal(null) }}
        />
      </header>

      {error ? (
        <div style={{ padding: '16px 24px' }}>
          <p className="error" role="alert">{error}</p>
          <button type="button" className="btn" onClick={() => void refresh()}>Retry</button>
        </div>
      ) : null}

      {loading ? (
        <p className="empty" role="status">Loading operations data…</p>
      ) : (
        <main className="layout">
          <div className="col">
            <section className="card" aria-labelledby="tickets-heading">
              <header>
                <h2 id="tickets-heading">Tickets</h2>
                <span className="count">{tickets.length} total</span>
              </header>
              <div className="body tight">
                {tickets.length === 0 ? (
                  <p className="empty">No tickets.</p>
                ) : (
                  tickets.map((t) => {
                    const stage = latestStage(t.id)
                    return (
                      <button
                        type="button"
                        key={t.id}
                        className="ticket-row"
                        aria-current={selectedId === t.id}
                        onClick={() => setSelectedId(t.id)}
                      >
                        <span className="id">#{t.id}</span>
                        <span className="main">
                          <span className="subject">{t.subject}</span>
                          <span className="meta">
                            {t.type.replace(/_/g, ' ')} · {t.requester}
                            {t.sku ? ` · ${t.sku}${t.size ? `/${t.size}` : ''}` : ''}
                            {t.qty !== null ? ` × ${t.qty}` : ''}
                          </span>
                        </span>
                        <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <Badge status={t.status} />
                          {stage ? <Badge status={stage} /> : null}
                        </span>
                      </button>
                    )
                  })
                )}
              </div>
            </section>

            {detail ? (
              <TicketDetail detail={detail} onProcessed={afterAction} />
            ) : (
              <p className="empty">Select a ticket to see its detail.</p>
            )}
          </div>

          <div className="col">
            {state ? <CashPanel state={state} /> : null}
            <ApprovalQueue proposals={proposals} token={token} onChanged={afterAction} />
            <ActivityPanel runs={runs} audit={audit} />
          </div>
        </main>
      )}
    </div>
  )
}
