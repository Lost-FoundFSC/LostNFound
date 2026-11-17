/** @vitest-environment jsdom */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import ReportPage from './ReportPage';

const submitButton = () => screen.getByRole('button', { name: /Submit report/i });
const field = label => screen.getByLabelText(label);
const set = (label, value) => fireEvent.change(field(label), { target: { value } });

function fillValidForm() {
  set(/^Name/, 'Matthew Quintanilla');
  set(/^Email address/, 'quinma1@farmingdale.edu');
  set(/^Student ID/, 'R12345678');
  set(/^Phone/, '5165512685');
  set(/^Category/, 'Electronics');
  set(/^Item name/, 'iPhone 15 Pro');
  set(/^Description/, 'Silver edges');
  set(/^Date last seen/, '2026-10-11');
  set(/^Campus location/, 'Hale Hall');
  fireEvent.click(field(/I acknowledge the notice above/));
}

function mockFetch(status, body) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: status < 300, status, json: async () => body });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('ReportPage', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders the report form and submit button', () => {
    render(<ReportPage />);
    expect(submitButton()).toBeInTheDocument();
  });

  it('marks name, email, and phone as required', () => {
    render(<ReportPage />);
    for (const label of [/^Name/, /^Email address/, /^Phone/]) {
      expect(field(label)).toBeRequired();
      expect(field(label).closest('label')).toHaveTextContent('*');
    }
    expect(field(/^Student ID/)).not.toBeRequired();
  });

  it('does not require the date or campus location', () => {
    render(<ReportPage />);
    expect(field(/^Date last seen/)).not.toBeRequired();
    expect(field(/^Campus location/)).not.toBeRequired();
    expect(field(/^Date last seen/).closest('label')).not.toHaveTextContent('*');
    expect(screen.getByText('Optional. An estimate is OK.')).toBeInTheDocument();
  });

  it('submits without a date or campus location', async () => {
    const fetchMock = mockFetch(201, { formId: 'L#591829326', reportType: 'lost' });
    const onNavigate = vi.fn();
    render(<ReportPage onNavigate={onNavigate} />);
    fillValidForm();
    set(/^Date last seen/, '');
    set(/^Campus location/, '');
    fireEvent.click(submitButton());
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('report-confirmation'));
    const sent = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sent.incidentDate).toBe('');
    expect(sent.campusLocation).toBe('');
  });

  it('explains the RAM ID format', () => {
    render(<ReportPage />);
    expect(screen.getByText(/R followed by exactly 8 digits/i)).toBeInTheDocument();
  });

  it('shows an error under each missing required field and does not submit', () => {
    const fetchMock = mockFetch(201, {});
    render(<ReportPage />);
    fireEvent.click(submitButton());

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText('Enter your name.')).toBeInTheDocument();
    expect(screen.getByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your phone number.')).toBeInTheDocument();
    expect(screen.getByText('You must acknowledge the notice to submit.')).toBeInTheDocument();
    expect(field(/^Name/)).toHaveAttribute('aria-invalid', 'true');
    expect(field(/^Name/)).toHaveFocus();
    expect(screen.getByText(/Please fix the \d+ highlighted fields/)).toBeInTheDocument();
  });

  it('shows the RAM ID error as soon as the user leaves the field', () => {
    render(<ReportPage />);
    set(/^Student ID/, 'R123456789');
    fireEvent.blur(field(/^Student ID/));
    expect(screen.getByText(/A RAM ID is the letter R followed by 8 digits/)).toBeInTheDocument();
    expect(field(/^Student ID/)).toHaveAttribute('aria-invalid', 'true');
  });

  it('clears an error once the field is fixed', () => {
    render(<ReportPage />);
    fireEvent.click(submitButton());
    expect(screen.getByText('Enter your name.')).toBeInTheDocument();
    set(/^Name/, 'Matthew Quintanilla');
    expect(screen.queryByText('Enter your name.')).not.toBeInTheDocument();
  });

  it('shows backend errors under the matching field', async () => {
    mockFetch(400, { phone: ['Enter a 10-digit phone number, like (516) 555-1234.'] });
    render(<ReportPage />);
    fillValidForm();
    fireEvent.click(submitButton());
    expect(await screen.findByText('Enter a 10-digit phone number, like (516) 555-1234.')).toBeInTheDocument();
    expect(field(/^Phone/)).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows a message when the server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<ReportPage />);
    fillValidForm();
    fireEvent.click(submitButton());
    expect(await screen.findByText(/Unable to connect to the server/)).toBeInTheDocument();
  });

  it('passes the backend form ID to the confirmation page', async () => {
    const fetchMock = mockFetch(201, { formId: 'L#591829326', reportType: 'lost', status: 'reported', imageCount: 0 });
    const onSubmitted = vi.fn();
    const onNavigate = vi.fn();
    render(<ReportPage onNavigate={onNavigate} onSubmitted={onSubmitted} />);
    fillValidForm();
    fireEvent.click(submitButton());

    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('report-confirmation'));
    expect(onSubmitted).toHaveBeenCalledWith(expect.objectContaining({ formId: 'L#591829326' }));
    const sent = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sent.studentId).toBe('R12345678');
    expect(sent.phone).toBe('5165512685');
  });
});
