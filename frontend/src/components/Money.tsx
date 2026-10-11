export function Money({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="muted">—</span>
  return (
    <span className="money">
      {value.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}
    </span>
  )
}
