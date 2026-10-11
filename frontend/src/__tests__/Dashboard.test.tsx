import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { api } from '../api/client'
import { state, pendingProposal, ticketDetail } from './fixtures'

function stubApi() {
  vi.spyOn(api, 'state').mockResolvedValue(state)
  vi.spyOn(api, 'tickets').mockResolvedValue({ tickets: [ticketDetail.ticket], count: 1 })
  vi.spyOn(api, 'proposals').mockResolvedValue({ proposals: [pendingProposal], count: 1 })
  vi.spyOn(api, 'runs').mockResolvedValue({ runs: ticketDetail.runs, count: 1 })
  vi.spyOn(api, 'audit').mockResolvedValue({
    entries: [{ time: '2026-08-31T10:00:00+00:00', tool: 'get_today', args: {}, result: 'today=2026-08-31', stop_reason: 'completed' }],
    count: 1,
  })
  vi.spyOn(api, 'ticket').mockResolvedValue(ticketDetail)
}

describe('Dashboard', () => {
  beforeEach(() => { vi.restoreAllMocks(); stubApi() })

  it('loads real ticket and cash data from the API', async () => {
    render(<App />)
    expect(await screen.findByText('Bulldog tee')).toBeInTheDocument()
    expect(screen.getByText('$3,400.00')).toBeInTheDocument()
    expect(screen.getByText(/shop date 2026-08-31/i)).toBeInTheDocument()
  })

  it('shows obligations and what would remain if all were paid', async () => {
    render(<App />)
    await screen.findByText('Bulldog tee')
    const cash = screen.getByRole('region', { name: /cash/i })
    // Both appear twice: once as a total, once as the line item.
    expect(within(cash).getAllByText('$840.00').length).toBeGreaterThan(0)
    // Appears twice: the rent-due total and the lease line itself.
    expect(within(cash).getAllByText('$2,400.00').length).toBeGreaterThan(0)
    // 3400 - 840 - 2400 = 160
    expect(within(cash).getByText('$160.00')).toBeInTheDocument()
  })

  it('displays agent findings and which specialists were consulted', async () => {
    render(<App />)
    expect(await screen.findByText(/out of stock/i)).toBeInTheDocument()
    expect(screen.getByText(/CC-TEE-WHITE\/S qty = 0/)).toBeInTheDocument()
    expect(screen.getByText('inventory')).toBeInTheDocument()
    expect(screen.getByText(/which obligation should be paid first/i)).toBeInTheDocument()
  })

  it('labels a proposing run as awaiting approval, not resolved', async () => {
    render(<App />)
    // The detail pane loads on its own request; wait for it rather than for
    // the ticket row alone.
    const dbStatus = await screen.findByText(/ticket status in database:/i)
    expect(screen.getAllByText(/awaiting your approval/i).length).toBeGreaterThan(0)
    expect(screen.queryByText(/resolved/i)).not.toBeInTheDocument()
    // The database's own view is shown alongside.
    expect(dbStatus).toHaveTextContent('open')
  })

  it('marks proposed actions as not yet done', async () => {
    render(<App />)
    expect(await screen.findByText(/proposed — not yet done/i)).toBeInTheDocument()
    expect(screen.getByText(/pay invoice 501/i)).toBeInTheDocument()
    expect(screen.getByText(/nothing has been paid or ordered/i)).toBeInTheDocument()
  })

  it('calls the processing endpoint only when the operator clicks', async () => {
    const process = vi.spyOn(api, 'processTicket').mockResolvedValue(ticketDetail.runs[0])
    render(<App />)
    const button = await screen.findByRole('button', { name: /process ticket/i })
    expect(process).not.toHaveBeenCalled()

    await userEvent.click(button)
    expect(process).toHaveBeenCalledWith(101)
  })

  it('refreshes data after processing', async () => {
    vi.spyOn(api, 'processTicket').mockResolvedValue(ticketDetail.runs[0])
    render(<App />)
    const button = await screen.findByRole('button', { name: /process ticket/i })
    const before = (api.state as unknown as { mock: { calls: unknown[] } }).mock.calls.length
    await userEvent.click(button)
    await waitFor(() => {
      const after = (api.state as unknown as { mock: { calls: unknown[] } }).mock.calls.length
      expect(after).toBeGreaterThan(before)
    })
  })

  it('reports a backend failure without claiming the ticket advanced', async () => {
    const { ApiError } = await import('../api/client')
    vi.spyOn(api, 'processTicket').mockRejectedValue(
      new ApiError('The agent team could not complete this ticket.', 502, 'ModelAPIError'),
    )
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /process ticket/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not finish/i)
  })

  it('shows a reachable error when the backend is down', async () => {
    vi.spyOn(api, 'state').mockRejectedValue(new Error('network'))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot reach the backend/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('requires sign-in before approval controls become usable', async () => {
    render(<App />)
    await screen.findByText('Bulldog tee')
    expect(screen.getByRole('button', { name: /^approve$/i })).toBeDisabled()
  })

  it('keeps the operator token out of browser storage', async () => {
    vi.spyOn(api, 'whoami').mockResolvedValue({ authenticated: true, principal: 'operator (local)' })
    render(<App />)
    await screen.findByText('Bulldog tee')

    await userEvent.type(screen.getByLabelText(/operator token/i), 'secret-token-value')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/signed in as/i)).toBeInTheDocument()

    expect(window.localStorage.length).toBe(0)
    expect(window.sessionStorage.length).toBe(0)
    expect(document.cookie).not.toContain('secret-token-value')
    expect(screen.getByRole('button', { name: /^approve$/i })).toBeEnabled()
  })
})
