import { useState } from 'react'
import { ApiError, api } from '../api/client'
import type { Proposal } from '../api/types'
import { Badge } from './Badge'
import { Money } from './Money'

interface Props {
  proposals: Proposal[]
  token: string | null
  onChanged: () => void
}

type Pending = { id: string; action: 'approve' | 'reject' | 'execute' } | null

/**
 * The human approval queue.
 *
 * Two rules shape this component:
 *  1. Nothing consequential happens on a single click. Approve, reject, and
 *     execute each open an explicit confirmation showing the exact target and
 *     amount, because the amount is what the approval is cryptographically
 *     bound to on the server.
 *  2. The UI never claims a payment happened. Success text is written only
 *     from what the backend returned after it executed.
 */
export function ApprovalQueue({ proposals, token, onChanged }: Props) {
  const [pending, setPending] = useState<Pending>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const actionable = proposals.filter(
    (p) => p.status === 'pending_human_approval' || p.status === 'approved',
  )

  async function run(proposal: Proposal, action: 'approve' | 'reject' | 'execute') {
    if (!token) return
    setBusy(proposal.proposal_id)
    setError(null)
    setDone(null)
    try {
      if (action === 'approve') {
        await api.approve(token, proposal.proposal_id, proposal.amount)
        setDone(`${proposal.proposal_id} approved. It will not move money until you execute it.`)
      } else if (action === 'reject') {
        await api.reject(token, proposal.proposal_id, 'Rejected by operator from dashboard')
        setDone(`${proposal.proposal_id} rejected. Nothing was paid.`)
      } else {
        // Report only what the backend confirms.
        const result = await api.execute(token, proposal.proposal_id)
        const after = (result.result as { balance_after?: number }).balance_after
        setDone(
          after === undefined
            ? `${proposal.proposal_id} executed.`
            : `${proposal.proposal_id} executed. Checking balance is now ` +
              `${after.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}.`,
        )
      }
      setPending(null)
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.operatorMessage : 'The action failed.')
      setPending(null)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="card" aria-labelledby="approval-heading">
      <header>
        <h2 id="approval-heading">Approval queue</h2>
        <span className="count">{actionable.length} awaiting you</span>
      </header>
      <div className="body">
        {error ? <p className="error" role="alert">{error}</p> : null}
        {done ? <p className="notice" role="status">{done}</p> : null}

        {!token ? (
          <p className="notice">
            Sign in with your operator token to approve, reject, or execute proposals.
            Viewing is open; acting is not.
          </p>
        ) : null}

        {actionable.length === 0 ? (
          <p className="empty">
            No proposals awaiting a decision. Agents can prepare proposals, but only you can
            authorize them.
          </p>
        ) : (
          actionable.map((p) => {
            const isPending = pending?.id === p.proposal_id
            const working = busy === p.proposal_id
            return (
              <article className="proposal" key={p.proposal_id}>
                <div className="head">
                  <span className="mono">{p.proposal_id}</span>
                  <Badge status={p.status} />
                  <span className="amount" style={{ marginLeft: 'auto' }}>
                    <Money value={p.amount} />
                  </span>
                </div>

                <dl>
                  <dt>Type</dt><dd>{p.kind}</dd>
                  <dt>Target</dt><dd className="mono">{p.target}</dd>
                  <dt>Account</dt><dd>{p.account}</dd>
                  {p.approved_by ? (<><dt>Approved by</dt><dd>{p.approved_by}</dd></>) : null}
                </dl>

                {isPending ? (
                  <div className="confirm" role="alertdialog" aria-label="Confirm action">
                    <p>
                      Confirm you want to <strong>{pending.action}</strong>{' '}
                      <span className="mono">{p.proposal_id}</span>
                      {pending.action !== 'reject' ? (
                        <> for <strong><Money value={p.amount} /></strong> from {p.account}</>
                      ) : null}
                      .
                      {pending.action === 'execute'
                        ? ' This moves money and cannot be undone.'
                        : pending.action === 'approve'
                          ? ' This authorizes the action; it does not pay yet.'
                          : ''}
                    </p>
                    <div className="btn-row">
                      <button
                        type="button"
                        className={`btn ${pending.action}`}
                        onClick={() => run(p, pending.action)}
                        disabled={working}
                      >
                        {working ? <span className="spinner" /> : null}
                        Yes, {pending.action}
                      </button>
                      <button type="button" className="btn" onClick={() => setPending(null)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="btn-row">
                    {p.status === 'pending_human_approval' ? (
                      <button
                        type="button"
                        className="btn approve"
                        disabled={!token || working}
                        onClick={() => setPending({ id: p.proposal_id, action: 'approve' })}
                      >
                        Approve
                      </button>
                    ) : null}
                    {p.status === 'approved' ? (
                      <button
                        type="button"
                        className="btn execute"
                        disabled={!token || working}
                        onClick={() => setPending({ id: p.proposal_id, action: 'execute' })}
                      >
                        Execute payment
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="btn reject"
                      disabled={!token || working || p.status === 'approved'}
                      onClick={() => setPending({ id: p.proposal_id, action: 'reject' })}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </article>
            )
          })
        )}
      </div>
    </section>
  )
}
