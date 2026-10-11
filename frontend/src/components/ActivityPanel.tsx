import type { AuditEntry, TicketRun } from '../api/types'
import { stageLabel } from './Badge'

/** Recent operational activity: what the system actually did, newest first. */
export function ActivityPanel({ runs, audit }: { runs: TicketRun[]; audit: AuditEntry[] }) {
  const recentRuns = [...runs].sort((a, b) => b.started_at.localeCompare(a.started_at)).slice(0, 5)
  const recentAudit = [...audit].reverse().slice(0, 40)

  return (
    <section className="card" aria-labelledby="activity-heading">
      <header>
        <h2 id="activity-heading">Recent activity</h2>
        <span className="count">{audit.length} audit events</span>
      </header>

      {recentRuns.length > 0 ? (
        <div className="body" style={{ paddingBottom: 8 }}>
          <p className="list-label small" style={{ margin: '0 0 6px', color: 'var(--text-faint)' }}>
            Agent runs
          </p>
          {recentRuns.map((r) => (
            <div className="stat" key={r.run_id}>
              <span className="label">
                Ticket {r.ticket_id} — {stageLabel(r.stage)}
              </span>
              <span className="value small">{new Date(r.finished_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      ) : null}

      {recentAudit.length === 0 ? (
        <p className="empty">No audit events yet.</p>
      ) : (
        <ul className="audit">
          {recentAudit.map((e, i) => (
            <li key={`${e.time}-${i}`}>
              <time dateTime={e.time}>{new Date(e.time).toLocaleTimeString()}</time>
              <span className="tool">{e.tool}</span>
              <span className="result" title={e.result}>{e.result}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
