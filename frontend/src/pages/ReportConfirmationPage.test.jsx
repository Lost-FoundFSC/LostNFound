/** @vitest-environment jsdom */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ReportConfirmationPage from './ReportConfirmationPage'

describe('ReportConfirmationPage', () => {
  it('shows the real form ID returned by the backend', () => {
    render(<ReportConfirmationPage submission={{ formId: 'L#591829326', reportType: 'lost', status: 'reported' }} />)
    expect(screen.getByTestId('confirmation-form-id')).toHaveTextContent('L#591829326')
    expect(screen.getByRole('heading', { name: 'Report submitted' })).toBeInTheDocument()
    expect(screen.getByText(/lost item report was received/i)).toBeInTheDocument()
    expect(screen.queryByText('LF-2026-001847')).not.toBeInTheDocument()
    expect(screen.queryByText('SAMPLE')).not.toBeInTheDocument()
  })

  it('says found item for found reports', () => {
    render(<ReportConfirmationPage submission={{ formId: 'F#923356063', reportType: 'found' }} />)
    expect(screen.getByText(/found item report was received/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'View potential matches' })).not.toBeInTheDocument()
  })

  it('lets a lost-item reporter open their potential matches', () => {
    const onViewMatches = vi.fn()
    render(<ReportConfirmationPage
      submission={{ formId: 'L#591829326', reportType: 'lost' }}
      onViewMatches={onViewMatches}
    />)
    fireEvent.click(screen.getByRole('button', { name: 'View potential matches' }))
    expect(onViewMatches).toHaveBeenCalledWith('L#591829326')
  })

  it('mentions attached photos', () => {
    render(<ReportConfirmationPage submission={{ formId: 'F#923356063', reportType: 'found', imageCount: 2 }} />)
    expect(screen.getByText(/found item report with 2 photos was received/i)).toBeInTheDocument()
  })

  it('falls back to the labeled sample preview without a submission', () => {
    render(<ReportConfirmationPage />)
    expect(screen.getByText('LF-2026-001847')).toBeInTheDocument()
    expect(screen.getByText('SAMPLE')).toBeInTheDocument()
    expect(screen.queryByTestId('confirmation-form-id')).not.toBeInTheDocument()
  })
})
