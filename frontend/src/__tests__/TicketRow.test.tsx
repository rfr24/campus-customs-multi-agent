/**
 * Regression guard for the ticket-list formatting.
 *
 * The subject and metadata are both <span>, so with default inline display
 * they rendered as one unbroken string — "Bulk hoodie discountprice override".
 * jsdom does not apply the stylesheet, so these tests assert the structural
 * facts the fix depends on: the two are separate elements with the classes the
 * CSS targets, and the accessible text keeps them apart.
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { App } from '../App'
import { api } from '../api/client'
import { state, ticketDetail } from './fixtures'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// jsdom's import.meta.url is not a file: URL, so resolve from the project root.
const css = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf-8')

const hoodie = {
  ...ticketDetail.ticket,
  id: 103, subject: 'Bulk hoodie discount', type: 'price_override',
  requester: 'Yale AI Club', sku: 'CC-HOOD-NAVY', size: 'M', qty: 20, invoice_id: null,
}

describe('ticket row formatting', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'state').mockResolvedValue(state)
    vi.spyOn(api, 'tickets').mockResolvedValue({ tickets: [hoodie], count: 1 })
    vi.spyOn(api, 'proposals').mockResolvedValue({ proposals: [], count: 0 })
    vi.spyOn(api, 'runs').mockResolvedValue({ runs: [], count: 0 })
    vi.spyOn(api, 'audit').mockResolvedValue({ entries: [], count: 0 })
    vi.spyOn(api, 'ticket').mockResolvedValue({ ...ticketDetail, ticket: hoodie, invoice: null })
  })

  it('keeps the subject and the metadata in separate elements', async () => {
    render(<App />)
    const row = (await screen.findByText('Bulk hoodie discount')).closest('button')!
    const subject = within(row).getByText('Bulk hoodie discount')
    const meta = row.querySelector('.meta')!

    expect(subject).toHaveClass('subject')
    expect(meta).not.toBe(subject)
    expect(subject.textContent).toBe('Bulk hoodie discount')
    expect(meta.textContent).toContain('price override')
  })

  it('puts the metadata in its own sibling element, not inside the subject', async () => {
    render(<App />)
    const row = (await screen.findByText('Bulk hoodie discount')).closest('button')!
    const subject = row.querySelector('.subject')!
    const meta = row.querySelector('.meta')!

    // The symptom was one visual line; structurally the fix is that the
    // subject contains none of the metadata and the two are siblings.
    expect(subject.textContent).not.toMatch(/price override/i)
    expect(subject.parentElement).toBe(meta.parentElement)
    expect(subject.nextElementSibling).toBe(meta)
  })

  it('styles both parts as block so they occupy separate lines', () => {
    // jsdom ignores the stylesheet, so assert the rule itself is present.
    expect(css).toMatch(/\.ticket-row \.subject \{[^}]*display:\s*block/)
    expect(css).toMatch(/\.ticket-row \.meta \{[^}]*display:\s*block/)
  })

  it('wraps the row on narrow screens instead of crushing the subject', () => {
    expect(css).toMatch(/@media \(max-width: 560px\)/)
    expect(css).toMatch(/\.ticket-row \{ flex-wrap: wrap/)
    expect(css).toMatch(/overflow-wrap:\s*anywhere/)
  })
})
