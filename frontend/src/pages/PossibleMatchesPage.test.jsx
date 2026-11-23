/** @vitest-environment jsdom */
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PossibleMatchesPage from './PossibleMatchesPage'

const response = (data, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => data,
})

const report = (formId, itemName, matches = []) => ({
  lostReport: { formId, itemName, category: 'Electronics' },
  matches,
})

describe('PossibleMatchesPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('automatically loads matches for every lost report in the browser session', async () => {
    fetch.mockImplementation(url => url.includes('L123456789')
      ? Promise.resolve(response(report('L#123456789', 'Black AirPods case', [{
        formId: 'F#987654321',
        itemName: 'AirPods case black',
        category: 'Electronics',
        campusLocation: 'Greenley Library',
        incidentDate: '2026-10-19',
        matchScore: 92,
      }])))
      : Promise.resolve(response(report('L#111222333', 'Blue headphones', [{
        formId: 'F#246813579',
        itemName: 'Blue wireless headphones',
        category: 'Electronics',
        campusLocation: 'Student Union',
        incidentDate: '2026-10-20',
        matchScore: 78,
      }]))))

    render(<PossibleMatchesPage lostReportFormIds={['L#123456789', 'L#111222333']} />)

    expect(await screen.findByRole('heading', { name: 'AirPods case black' })).toBeInTheDocument()
    expect(screen.getByLabelText('92% comparison score')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Blue wireless headphones' })).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/reports/L123456789/matches/',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(screen.queryByLabelText('Lost-item form ID')).not.toBeInTheDocument()
  })

  it('shows a loading message while backend requests are pending', async () => {
    let resolveRequest
    fetch.mockReturnValue(new Promise(resolve => { resolveRequest = resolve }))

    render(<PossibleMatchesPage lostReportFormIds={['L#123456789']} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading possible matches')

    await act(async () => {
      resolveRequest(response(report('L#123456789', 'Phone')))
    })
    expect(await screen.findByText('There are no unlinked found reports for this lost item yet.')).toBeInTheDocument()
  })

  it('shows an error when the backend cannot find a session report', async () => {
    fetch.mockResolvedValue(response({ detail: 'Not found.' }, 404))

    render(<PossibleMatchesPage lostReportFormIds={['L#123456789']} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('A lost report from this browser session could not be found.')
  })

  it('offers report submission when no lost reports are linked to the session', () => {
    render(<PossibleMatchesPage />)

    expect(screen.getByText('No lost-item reports are linked to this browser session yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit a lost-item report' })).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
    expect(screen.queryByLabelText('Lost-item form ID')).not.toBeInTheDocument()
  })
})
