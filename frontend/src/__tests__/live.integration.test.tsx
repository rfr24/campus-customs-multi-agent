/**
 * Integration test against a RUNNING backend — no mocks, no fixtures.
 *
 * Opt-in: set LIVE_API to the backend's base URL, e.g.
 *   LIVE_API=http://localhost:8077 npx vitest run --config vitest.config.ts live
 *
 * It renders the real dashboard against real API responses, so it catches the
 * class of bug that mocked tests cannot: a field the backend actually returns
 * under a different name or shape. It performs no mutation — no processing,
 * no approval, no execution.
 */
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { App } from '../App'

const BASE = process.env.LIVE_API
const maybe = BASE ? describe : describe.skip

maybe('live dashboard against the real backend', () => {
  beforeAll(() => {
    // jsdom has no origin for relative URLs; point them at the live server.
    const original = globalThis.fetch
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' && input.startsWith('/') ? `${BASE}${input}` : input
      return original(url as RequestInfo, init)
    }) as typeof fetch
  })

  // Unmount before the environment tears down, so in-flight fetches settle quietly.
  afterEach(async () => {
    cleanup()
    await new Promise((resolve) => setTimeout(resolve, 50))
  })

  it('renders real tickets, cash, and obligations from the API', async () => {
    render(<App />)

    // Real ticket subjects, straight from the working database.
    expect(await screen.findByText('Bulldog tee', {}, { timeout: 8000 })).toBeInTheDocument()
    expect(screen.getByText('Rent due')).toBeInTheDocument()
    expect(screen.getByText('Bulk hoodie discount')).toBeInTheDocument()

    // Real financial state.
    const cash = screen.getByRole('region', { name: /cash/i })
    expect(within(cash).getByText('$3,400.00')).toBeInTheDocument()
    expect(within(cash).getAllByText('$840.00').length).toBeGreaterThan(0)
    expect(within(cash).getAllByText('$2,400.00').length).toBeGreaterThan(0)
    // 3400 - 840 - 2400 = 160 remaining if both were paid.
    expect(within(cash).getByText('$160.00')).toBeInTheDocument()

    // The shop's authoritative date, not the host clock.
    expect(screen.getByText(/shop date 2026-08-31/i)).toBeInTheDocument()
  })

  it('shows the tickets as open and unprocessed, claiming no resolution', async () => {
    render(<App />)
    await screen.findByText('Bulldog tee', {}, { timeout: 8000 })
    expect(screen.getAllByText('open').length).toBeGreaterThanOrEqual(3)
    expect(screen.queryByText(/resolved/i)).not.toBeInTheDocument()
    expect(await screen.findByText(/has not been processed yet/i)).toBeInTheDocument()
  })

  it('keeps approval controls inert until an operator signs in', async () => {
    render(<App />)
    await screen.findByText('Bulldog tee', {}, { timeout: 8000 })
    expect(screen.getByLabelText(/operator token/i)).toBeInTheDocument()
    expect(screen.getByText(/viewing is open; acting is not/i)).toBeInTheDocument()
  })
})
