import { useState } from 'react'
import { ApiError, api } from '../api/client'

interface Props {
  token: string | null
  principal: string | null
  onSignIn: (token: string, principal: string) => void
  onSignOut: () => void
}

/**
 * Operator sign-in.
 *
 * The token lives in React state only — never localStorage, sessionStorage, a
 * cookie, or a build variable. Closing the tab ends the session, which is the
 * behaviour we want for an approval credential.
 */
export function OperatorBar({ token, principal, onSignIn, onSignOut }: Props) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (token && principal) {
    return (
      <div className="btn-row" style={{ alignItems: 'center' }}>
        <span className="small muted">
          Signed in as <strong>{principal}</strong>
        </span>
        <button type="button" className="btn small" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    )
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const who = await api.whoami(value)
      onSignIn(value, who.principal)
      setValue('')
    } catch (err) {
      setError(err instanceof ApiError ? err.operatorMessage : 'Sign-in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="btn-row" style={{ alignItems: 'center' }}>
      <label htmlFor="operator-token" className="sr-only">Operator token</label>
      <input
        id="operator-token"
        type="password"
        placeholder="Operator token"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoComplete="off"
        style={{ width: 200 }}
      />
      <button type="submit" className="btn" disabled={!value || busy}>
        {busy ? <span className="spinner" /> : null}
        Sign in
      </button>
      {error ? <span className="small" style={{ color: 'var(--danger)' }} role="alert">{error}</span> : null}
    </form>
  )
}
