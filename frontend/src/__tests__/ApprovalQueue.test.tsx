import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApprovalQueue } from '../components/ApprovalQueue'
import { api } from '../api/client'
import { approvedProposal, pendingProposal } from './fixtures'

describe('ApprovalQueue', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('shows the exact target and amount before any decision', () => {
    render(<ApprovalQueue proposals={[pendingProposal]} token="t" onChanged={() => {}} />)
    expect(screen.getByText('PAY-0001')).toBeInTheDocument()
    expect(screen.getByText('rent:1')).toBeInTheDocument()
    expect(screen.getByText('$2,400.00')).toBeInTheDocument()
  })

  it('disables actions until an operator signs in', () => {
    render(<ApprovalQueue proposals={[pendingProposal]} token={null} onChanged={() => {}} />)
    expect(screen.getByRole('button', { name: /approve/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /reject/i })).toBeDisabled()
    expect(screen.getByText(/viewing is open; acting is not/i)).toBeInTheDocument()
  })

  it('does NOT approve on the first click — it asks for confirmation', async () => {
    const approve = vi.spyOn(api, 'approve').mockResolvedValue({ ok: true, proposal: approvedProposal })
    render(<ApprovalQueue proposals={[pendingProposal]} token="t" onChanged={() => {}} />)

    await userEvent.click(screen.getByRole('button', { name: /^approve$/i }))
    expect(approve).not.toHaveBeenCalled()
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /yes, approve/i }))
    expect(approve).toHaveBeenCalledWith('t', 'PAY-0001', 2400)
  })

  it('lets the operator cancel a confirmation without acting', async () => {
    const approve = vi.spyOn(api, 'approve')
    render(<ApprovalQueue proposals={[pendingProposal]} token="t" onChanged={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /^approve$/i }))
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(approve).not.toHaveBeenCalled()
  })

  it('offers Execute only once a proposal is approved, and never before', async () => {
    const { rerender } = render(
      <ApprovalQueue proposals={[pendingProposal]} token="t" onChanged={() => {}} />,
    )
    expect(screen.queryByRole('button', { name: /execute/i })).not.toBeInTheDocument()

    rerender(<ApprovalQueue proposals={[approvedProposal]} token="t" onChanged={() => {}} />)
    expect(screen.getByRole('button', { name: /execute/i })).toBeInTheDocument()
  })

  it('warns that execution moves money and cannot be undone', async () => {
    render(<ApprovalQueue proposals={[approvedProposal]} token="t" onChanged={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /execute payment/i }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent(/moves money and cannot be undone/i)
  })

  it('states that approval alone does not pay', async () => {
    render(<ApprovalQueue proposals={[pendingProposal]} token="t" onChanged={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /^approve$/i }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent(/does not pay yet/i)
  })

  it('never claims a payment completed until the backend confirms it', async () => {
    vi.spyOn(api, 'execute').mockResolvedValue({
      ok: true, result: { balance_after: 1000 }, executed_by: 'operator (local)',
    })
    render(<ApprovalQueue proposals={[approvedProposal]} token="t" onChanged={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /execute payment/i }))
    // Nothing is claimed while the confirmation is still open.
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /yes, execute/i }))
    expect(await screen.findByRole('status')).toHaveTextContent(/executed.*\$1,000\.00/i)
  })

  it('surfaces an insufficient-funds refusal in operator language', async () => {
    const { ApiError } = await import('../api/client')
    vi.spyOn(api, 'execute').mockRejectedValue(
      new ApiError('checking holds 100.00, payment needs 2400.00', 409, 'insufficient_funds'),
    )
    render(<ApprovalQueue proposals={[approvedProposal]} token="t" onChanged={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /execute payment/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, execute/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/not enough cash/i)
  })

  it('surfaces an unauthorized error safely', async () => {
    const { ApiError } = await import('../api/client')
    vi.spyOn(api, 'approve').mockRejectedValue(new ApiError('Invalid operator token.', 401))
    render(<ApprovalQueue proposals={[pendingProposal]} token="bad" onChanged={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /^approve$/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, approve/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/token missing or invalid/i)
  })
})
