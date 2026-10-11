import { useState } from 'react'
import { ApiError, api } from '../api/client'
import type { TicketDetail as Detail, TicketRun } from '../api/types'
import { Badge, stageLabel } from './Badge'
import { Money } from './Money'

interface Props {
  detail: Detail
  onProcessed: () => void
}

/** Full ticket view: the record, its linked obligations, and what the agents found. */
export function TicketDetail({ detail, onProcessed }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { ticket, lease, invoice, runs } = detail

  // Newest run first; the dashboard shows the latest but keeps the history.
  const ordered = [...runs].sort((a, b) => b.started_at.localeCompare(a.started_at))
  const latest: TicketRun | undefined = ordered[0]

  async function process() {
    setBusy(true)
    setError(null)
    try {
      await api.processTicket(ticket.id)
      onProcessed()
    } catch (err) {
      setError(err instanceof ApiError ? err.operatorMessage : 'Processing failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card" aria-labelledby="detail-heading">
      <header>
        <h2 id="detail-heading">Ticket {ticket.id}</h2>
        <Badge status={ticket.status} />
        <span className="count">{ticket.type.replace(/_/g, ' ')}</span>
      </header>

      <div className="body">
        <h3 style={{ margin: '0 0 4px', fontSize: 17 }}>{ticket.subject}</h3>
        <p className="small muted" style={{ marginTop: 0 }}>
          From {ticket.requester} · opened {new Date(ticket.created_at).toLocaleString()}
        </p>
        {ticket.notes ? <p style={{ whiteSpace: 'pre-wrap' }}>{ticket.notes}</p> : null}

        <dl className="proposal" style={{ background: 'transparent', border: 0, padding: 0 }}>
          {ticket.sku ? (
            <>
              <dt>Item</dt>
              <dd className="mono">{ticket.sku}{ticket.size ? ` / ${ticket.size}` : ''}
                {ticket.qty !== null ? ` × ${ticket.qty}` : ''}</dd>
            </>
          ) : null}
          {invoice ? (
            <>
              <dt>Invoice</dt>
              <dd>
                #{invoice.id} <Money value={invoice.amount} /> due {invoice.due_date}{' '}
                {invoice.overdue ? <Badge status="overdue" label="overdue" /> : null}
              </dd>
            </>
          ) : null}
          {lease ? (
            <>
              <dt>Lease</dt>
              <dd>
                {lease.space_name} — <Money value={lease.monthly_rent} /> due {lease.next_due}
                {lease.days_to_due !== undefined ? ` (in ${lease.days_to_due} days)` : ''}
              </dd>
            </>
          ) : null}
        </dl>

        <div className="btn-row" style={{ marginTop: 14 }}>
          <button type="button" className="btn primary" onClick={process} disabled={busy}>
            {busy ? <span className="spinner" /> : null}
            {busy ? 'Agents working…' : 'Process ticket'}
          </button>
          {busy ? (
            <span className="small muted" role="status">
              The Boss is delegating to specialists. This takes a minute.
            </span>
          ) : null}
        </div>

        {error ? <p className="error" role="alert" style={{ marginTop: 12 }}>{error}</p> : null}

        {latest ? (
          <div style={{ marginTop: 20 }}>
            <div className="stat">
              <span className="label">Latest run</span>
              <span className="value">
                <Badge status={latest.stage} label={stageLabel(latest.stage)} />
              </span>
            </div>
            <p className="small muted" style={{ marginTop: 6 }}>
              {latest.run_id} · finished {new Date(latest.finished_at).toLocaleString()} ·
              ticket status in database: <strong>{latest.ticket_status}</strong>
            </p>

            {latest.error ? (
              <p className="error" role="alert">
                {latest.error} <span className="mono">({latest.stop_reason})</span>
              </p>
            ) : null}

            {latest.outcome ? (
              <>
                <p style={{ marginTop: 12 }}>{latest.outcome.summary}</p>

                {latest.outcome.dependencies.length > 0 ? (
                  <>
                    <p className="list-label small">Dependencies</p>
                    <ul className="small muted">
                      {latest.outcome.dependencies.map((d) => <li key={d}>{d}</li>)}
                    </ul>
                  </>
                ) : null}

                {latest.outcome.proposed_actions.length > 0 ? (
                  <div className="finding" style={{ borderColor: 'var(--awaiting)' }}>
                    <h4 style={{ color: 'var(--awaiting)' }}>Proposed — not yet done</h4>
                    <p className="small muted">
                      Prepared for you. Nothing has been paid or ordered; approve in the
                      queue to authorize.
                    </p>
                    <ul>
                      {latest.outcome.proposed_actions.map((a, i) => (
                        <li key={i}>
                          {a.description}
                          {a.amount !== null ? <> — <Money value={a.amount} /></> : null}
                          {a.proposal_id ? <span className="mono"> ({a.proposal_id})</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <p className="list-label small" style={{ marginTop: 14 }}>
                  Specialists consulted ({latest.outcome.specialists_consulted.length})
                </p>
                {latest.outcome.findings.length === 0 ? (
                  <p className="empty">No specialist findings recorded for this run.</p>
                ) : (
                  latest.outcome.findings.map((f) => (
                    <div className="finding" key={f.agent}>
                      <h4>{f.agent.replace(/_/g, ' ')}</h4>
                      <p>{f.summary}</p>
                      {f.facts.length > 0 ? (
                        <>
                          <p className="list-label">Verified facts</p>
                          <ul>{f.facts.map((x, i) => <li key={i}>{x}</li>)}</ul>
                        </>
                      ) : null}
                      {f.constraints.length > 0 ? (
                        <>
                          <p className="list-label">Constraints</p>
                          <ul>{f.constraints.map((x, i) => <li key={i}>{x}</li>)}</ul>
                        </>
                      ) : null}
                      {f.proposed_actions.length > 0 ? (
                        <>
                          <p className="list-label">Proposed — not yet done</p>
                          <ul>
                            {f.proposed_actions.map((a, i) => (
                              <li key={i}>
                                {a.description}
                                {a.amount !== null ? <> — <Money value={a.amount} /></> : null}
                                {a.proposal_id ? <span className="mono"> ({a.proposal_id})</span> : null}
                              </li>
                            ))}
                          </ul>
                        </>
                      ) : null}
                      {f.unresolved.length > 0 ? (
                        <>
                          <p className="list-label">Needs a human decision</p>
                          <ul>{f.unresolved.map((x, i) => <li key={i}>{x}</li>)}</ul>
                        </>
                      ) : null}
                    </div>
                  ))
                )}

                {latest.outcome.open_questions.length > 0 ? (
                  <>
                    <p className="list-label small" style={{ marginTop: 14 }}>Open questions for you</p>
                    <ul className="small muted">
                      {latest.outcome.open_questions.map((q, i) => <li key={i}>{q}</li>)}
                    </ul>
                  </>
                ) : null}
              </>
            ) : null}

            {ordered.length > 1 ? (
              <details style={{ marginTop: 16 }}>
                <summary className="small muted" style={{ cursor: 'pointer' }}>
                  Processing history ({ordered.length} runs)
                </summary>
                <ul className="small muted" style={{ paddingLeft: 18 }}>
                  {ordered.slice(1).map((r) => (
                    <li key={r.run_id}>
                      {new Date(r.started_at).toLocaleString()} — {stageLabel(r.stage)}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        ) : (
          <p className="empty" style={{ marginTop: 16 }}>
            This ticket has not been processed yet. Use <strong>Process ticket</strong> to have the
            agent team investigate it.
          </p>
        )}
      </div>
    </section>
  )
}
