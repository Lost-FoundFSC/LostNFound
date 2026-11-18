/** @vitest-environment jsdom */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
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

const photo = (name = 'iphone.jpg', type = 'image/jpeg', size = 1000) => {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
};
const photoInput = () => document.getElementById('report-photos-input');
const addPhotos = (...files) => fireEvent.change(photoInput(), { target: { files } });

describe('ReportPage', () => {
  beforeEach(() => {
    let count = 0;
    URL.createObjectURL = vi.fn(() => `blob:preview-${++count}`);
    URL.revokeObjectURL = vi.fn();
  });
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

  it('makes contact details optional on found reports', () => {
    render(<ReportPage />);
    set(/^Report type/, 'found');
    for (const label of [/^Name/, /^Email address/, /^Phone/]) {
      expect(field(label)).not.toBeRequired();
      expect(field(label).closest('label')).not.toHaveTextContent('*');
    }
    expect(screen.getByText(/Optional for found items/)).toBeInTheDocument();
  });

  it('submits a found report without contact details', async () => {
    const fetchMock = mockFetch(201, { formId: 'F#923356063', reportType: 'found' });
    const onNavigate = vi.fn();
    render(<ReportPage onNavigate={onNavigate} />);
    set(/^Report type/, 'found');
    set(/^Category/, 'Electronics');
    set(/^Item name/, 'Black game controller');
    set(/^Description/, 'Wavy line design');
    fireEvent.click(field(/I acknowledge the notice above/));
    fireEvent.click(submitButton());
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('report-confirmation'));
    const sent = fetchMock.mock.calls[0][1].body;
    expect(sent.get('reportType')).toBe('found');
    expect(sent.get('fullName')).toBe('');
  });

  it('still requires contact details on lost reports', () => {
    render(<ReportPage />);
    set(/^Report type/, 'found');
    set(/^Report type/, 'lost');
    fireEvent.click(submitButton());
    expect(screen.getByText('Enter your name.')).toBeInTheDocument();
    expect(field(/^Phone/)).toBeRequired();
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
    const sent = fetchMock.mock.calls[0][1].body;
    expect(sent.get('incidentDate')).toBe('');
    expect(sent.get('campusLocation')).toBe('');
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
    const sent = fetchMock.mock.calls[0][1].body;
    expect(sent).toBeInstanceOf(FormData);
    expect(sent.get('studentId')).toBe('R12345678');
    expect(sent.get('phone')).toBe('5165512685');
    expect(sent.get('liabilityAccepted')).toBe('true');
    expect(sent.getAll('images')).toHaveLength(0);
  });

  it('has an upload photos button', () => {
    render(<ReportPage />);
    expect(screen.getByText('Upload photos')).toBeInTheDocument();
    expect(photoInput()).toHaveAttribute('type', 'file');
    expect(photoInput()).toHaveAttribute('multiple');
    expect(screen.getByText('0 of 5 added')).toBeInTheDocument();
  });

  it('shows previews and lets photos be removed', () => {
    render(<ReportPage />);
    addPhotos(photo('front.jpg'), photo('back.png', 'image/png'));
    expect(screen.getAllByRole('img', { name: /Selected photo/ })).toHaveLength(2);
    expect(screen.getByText('2 of 5 added')).toBeInTheDocument();
    expect(screen.getByText('Add more photos')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Remove photo 1: front.jpg/ }));
    expect(screen.getAllByRole('img', { name: /Selected photo/ })).toHaveLength(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview-1');
  });

  it('rejects the wrong file type and photos over 5 MB', () => {
    render(<ReportPage />);
    addPhotos(photo('doc.pdf', 'application/pdf'), photo('huge.jpg', 'image/jpeg', 6 * 1024 * 1024), photo('ok.jpg'));
    expect(screen.getByText(/doc.pdf: only JPEG, PNG, or WebP/)).toBeInTheDocument();
    expect(screen.getByText(/huge.jpg: photo is larger than 5 MB/)).toBeInTheDocument();
    expect(screen.getByText('1 of 5 added')).toBeInTheDocument();
  });

  it('allows at most 5 photos', () => {
    render(<ReportPage />);
    addPhotos(...Array.from({ length: 6 }, (_, i) => photo(`p${i}.jpg`)));
    expect(screen.getByText('5 of 5 added')).toBeInTheDocument();
    expect(screen.getByText(/You can add up to 5 photos/)).toBeInTheDocument();
    expect(photoInput()).toBeDisabled();
  });

  it('sends the photos with the report', async () => {
    const fetchMock = mockFetch(201, { formId: 'F#923356063', reportType: 'found', imageCount: 2 });
    const onSubmitted = vi.fn();
    render(<ReportPage onNavigate={vi.fn()} onSubmitted={onSubmitted} />);
    fillValidForm();
    addPhotos(photo('front.jpg'), photo('back.jpg'));
    fireEvent.click(submitButton());
    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    const images = fetchMock.mock.calls[0][1].body.getAll('images');
    expect(images.map(file => file.name)).toEqual(['front.jpg', 'back.jpg']);
    expect(fetchMock.mock.calls[0][1].headers).toBeUndefined();
  });

  it('shows photo errors from the backend', async () => {
    mockFetch(400, { images: ['front.jpg: file is not a valid image.'] });
    render(<ReportPage />);
    fillValidForm();
    addPhotos(photo('front.jpg'));
    fireEvent.click(submitButton());
    expect(await screen.findByText('front.jpg: file is not a valid image.')).toBeInTheDocument();
  });
});
