/** A status pill. Labels are spelled out so the colour is never the only signal. */
export function Badge({ status, label }: { status: string; label?: string }) {
  const text = label ?? status.replace(/_/g, ' ')
  return (
    <span className={`badge ${status}`}>
      <span className="dot" aria-hidden="true" />
      {text}
    </span>
  )
}

/** Plain-language explanation of where a ticket stands.
 *  Deliberately explicit that a recommendation is not a resolution. */
export function stageLabel(stage: string): string {
  switch (stage) {
    case 'investigated': return 'investigated — no action proposed'
    case 'awaiting_human_approval': return 'awaiting your approval'
    case 'failed': return 'run failed'
    default: return stage.replace(/_/g, ' ')
  }
}
