import type { OperationalState } from '../api/types'
import { Badge } from './Badge'
import { Money } from './Money'

/**
 * Cash and obligations.
 *
 * The shop has a single account, so the headline number only means something
 * next to what is already owed. The "if all paid" line is arithmetic over
 * backend data, not a recommendation — deciding what to pay is the operator's
 * call, and no policy is implied here.
 */
export function CashPanel({ state }: { state: OperationalState }) {
  const invoiceTotal = state.open_invoices.reduce((sum, i) => sum + i.amount, 0)
  const rentTotal = state.leases.reduce((sum, l) => sum + l.monthly_rent, 0)
  const committed = invoiceTotal + rentTotal
  const remaining = state.cash.balance - committed

  return (
    <section className="card" aria-labelledby="cash-heading">
      <header>
        <h2 id="cash-heading">Cash</h2>
        <span className="count">as of {state.cash.date}</span>
      </header>
      <div className="body">
        <div className="stat">
          <span className="label">{state.cash.name}</span>
          <span className="value big"><Money value={state.cash.balance} /></span>
        </div>
        <div className="stat">
          <span className="label">Open invoices ({state.open_invoices.length})</span>
          <span className="value"><Money value={invoiceTotal} /></span>
        </div>
        <div className="stat">
          <span className="label">Rent due ({state.leases.length})</span>
          <span className="value"><Money value={rentTotal} /></span>
        </div>
        <div className="stat">
          <span className="label">Remaining if all paid</span>
          <span className={`value ${remaining < 0 ? 'danger' : ''}`}>
            <Money value={remaining} />
          </span>
        </div>

        {state.open_invoices.length > 0 ? (
          <>
            <p className="list-label small" style={{ marginTop: 14, color: 'var(--text-faint)' }}>
              Obligations
            </p>
            {state.open_invoices.map((i) => (
              <div className="stat" key={i.id}>
                <span className="label">
                  #{i.id} {i.vendor_name ?? ''}{' '}
                  {i.overdue ? <Badge status="overdue" label="overdue" /> : null}
                </span>
                <span className="value"><Money value={i.amount} /></span>
              </div>
            ))}
            {state.leases.map((l) => (
              <div className="stat" key={l.id}>
                <span className="label">
                  {l.space_name} · due {l.next_due}
                  {l.days_to_due !== undefined ? ` (${l.days_to_due}d)` : ''}
                </span>
                <span className="value"><Money value={l.monthly_rent} /></span>
              </div>
            ))}
          </>
        ) : null}

        {state.payments.length > 0 ? (
          <>
            <p className="list-label small" style={{ marginTop: 14, color: 'var(--text-faint)' }}>
              Completed payments
            </p>
            {state.payments.map((p) => (
              <div className="stat" key={p.id}>
                <span className="label">{p.kind} #{p.ref_id} · {p.paid_at} · {p.approved_by}</span>
                <span className="value"><Money value={p.amount} /></span>
              </div>
            ))}
          </>
        ) : (
          <p className="small muted" style={{ marginTop: 12 }}>
            No payments have been made.
          </p>
        )}
      </div>
    </section>
  )
}
