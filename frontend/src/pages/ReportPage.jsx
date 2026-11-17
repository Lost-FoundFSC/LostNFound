import { useRef, useState } from 'react';
import { INITIAL_REPORT, REPORT_CATEGORIES, REPORT_FIELDS } from '../data/reportFields'
import './ReportPage.css'
import { validateReport } from '../utils/reportValidation'

const CAMPUS_LOCATIONS = ['Campus Center', 'Greenley Library', 'Whitman Hall', 'Hale Hall', 'Lupton Hall', 'Nold Hall', 'Other / Unsure']
const API_URL = 'http://localhost:8000/api/reports/'

function Field({ label, children, help, required, error, errorId, helpId }) {
  return <label className={`report-field ${error ? 'report-field--invalid' : ''}`}>
    <span>{label}{required && <span className="report-required" aria-hidden="true"> *</span>}</span>
    {children}
    {help && <small id={helpId}>{help}</small>}
    {error && <span className="report-error" id={errorId} role="alert">{error}</span>}
  </label>
}
function Section({ title, subtitle, children }) {
  return <section className="report-section"><div className="report-section-title"><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><div className="report-section-body">{children}</div></section>
}

/** Page 4: lost/found report form. Submits to the Django backend (POST /api/reports/). */
export default function ReportPage({ onNavigate, onSubmitted }) {
  const formRef = useRef(null)
  const [values, setValues] = useState(INITIAL_REPORT)
  const [touched, setTouched] = useState({})             // fields the user has left after typing
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [serverErrors, setServerErrors] = useState({})   // field errors returned by the backend
  const [formMessage, setFormMessage] = useState('')     // problems not tied to one field
  const [sending, setSending] = useState(false)

  const clientErrors = validateReport(values)
  const errorFor = name => serverErrors[name] || ((submitAttempted || touched[name]) ? clientErrors[name] : undefined)

  function update(name, value) {
    setValues(previous => ({ ...previous, [name]: value }))
    if (serverErrors[name]) setServerErrors(previous => ({ ...previous, [name]: undefined }))
  }

  function leave(name) {
    if (name === 'studentId') update('studentId', values.studentId.trim().toUpperCase())
    if (String(values[name] ?? '').trim()) setTouched(previous => ({ ...previous, [name]: true }))
  }

  const inputProps = (name, helpId) => {
    const error = errorFor(name)
    const describedBy = [helpId, error && `${name}-error`].filter(Boolean).join(' ') || undefined
    return {
      name: REPORT_FIELDS[name],
      value: values[name],
      onChange: event => update(name, event.target.value),
      onBlur: () => leave(name),
      'aria-invalid': error ? true : undefined,
      'aria-describedby': describedBy,
    }
  }
  const fieldProps = name => ({ error: errorFor(name), errorId: `${name}-error` })

  function focusFirstError(errors) {
    const form = formRef.current
    if (!form) return
    const first = Array.from(form.elements).find(element => errors[element.name])
    first?.focus()
  }

  async function submit(event) {
    event.preventDefault()
    setSubmitAttempted(true)
    setFormMessage('')

    const errors = validateReport(values)
    const count = Object.keys(errors).length
    if (count > 0) {
      setFormMessage(`Please fix ${count === 1 ? 'the highlighted field' : `the ${count} highlighted fields`} below.`)
      focusFirstError(errors)
      return
    }

    setSending(true)
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...values, studentId: values.studentId.trim().toUpperCase() }),
      })

      if (response.ok) {
        // The backend replies with the new form ID, e.g. { formId: 'L#591829326', ... }
        const submission = await response.json()
        onSubmitted?.(submission)
        onNavigate?.('report-confirmation')
        return
      }

      if (response.status === 400) {
        // The backend sends { fieldName: ['message'] } using the same field names as the form.
        const body = await response.json().catch(() => ({}))
        const fieldErrors = {}
        const otherMessages = []
        for (const [key, messages] of Object.entries(body)) {
          const message = Array.isArray(messages) ? messages[0] : String(messages)
          if (key in REPORT_FIELDS) fieldErrors[key] = message
          else otherMessages.push(message)
        }
        setServerErrors(fieldErrors)
        setFormMessage(otherMessages[0] || 'Please fix the highlighted fields below.')
        focusFirstError(fieldErrors)
      } else {
        setFormMessage('Something went wrong on the server. Please try again in a moment.')
      }
    } catch (error) {
      console.error('Error submitting report:', error)
      setFormMessage('Unable to connect to the server. Check your connection and try again.')
    } finally {
      setSending(false)
    }
  }

  const liabilityError = errorFor('liabilityAccepted')

  return <div className="report-page">
    <header className="report-header"><div><p className="report-kicker">FSC LOST &amp; FOUND · FRONTEND DEMO</p><h1>Lost and Found Report</h1><p>Choose whether you are reporting a lost item or a found item, then provide as much information as possible. Fields marked <span className="report-required">*</span> are required.</p></div><div className="report-header-side"><span>○ No reports submitted</span><span className="report-user">JD &nbsp; Demo user</span></div></header>
    {formMessage && <div className="report-form-message" role="alert">{formMessage}</div>}
    <form ref={formRef} onSubmit={submit} className="report-grid" noValidate>
      <div className="report-column">
        <Section title="Personal information" subtitle="How can we contact you about this item?">
          <Field label="Name" required {...fieldProps('fullName')}><input {...inputProps('fullName')} placeholder="Enter your full name" maxLength={100} autoComplete="name" required /></Field>
          <Field label="Email address" required {...fieldProps('email')}><input {...inputProps('email')} type="email" placeholder="you@farmingdale.edu" autoComplete="email" maxLength={150} required /></Field>
          <Field label="Student ID (RAM ID)" help="Optional. The letter R followed by exactly 8 digits, like R01234567." helpId="studentId-help" {...fieldProps('studentId')}><input {...inputProps('studentId', 'studentId-help')} placeholder="R01234567" maxLength={12} autoComplete="off" /></Field>
          <Field label="Phone" required help="10-digit phone number." helpId="phone-help" {...fieldProps('phone')}><input {...inputProps('phone', 'phone-help')} type="tel" placeholder="(516) 555-1234" autoComplete="tel" maxLength={25} required /></Field>
          <div className="report-info">🔒 Your contact details and RAM ID are only shared with Campus Security so they can reach you about this item.</div>
        </Section>
        <Section title="Item details" subtitle="Give identifying details that can help match the item.">
          <Field label="Category" required {...fieldProps('category')}><select {...inputProps('category')} required><option value="">Select category</option>{REPORT_CATEGORIES.map(category => <option key={category} value={category}>{category}</option>)}</select></Field>
          <Field label="Item name" required {...fieldProps('itemName')}><input {...inputProps('itemName')} placeholder="e.g. Black umbrella, blue backpack" maxLength={120} required /></Field>
          <Field label="Description" required {...fieldProps('description')}><textarea {...inputProps('description')} rows={5} maxLength={1500} placeholder="Color, brand, distinctive marks, contents, etc." required /></Field>
          <Field label="Estimated value (USD)" {...fieldProps('estimatedValue')}><input {...inputProps('estimatedValue')} type="number" min="0" max="1000000" step="0.01" placeholder="Optional" /></Field>
        </Section>
      </div>
      <div className="report-column">
        <Section title="Report type" subtitle="Are you reporting a lost item or an item you found?">
          <Field label="Report type" required><select {...inputProps('reportType')} required><option value="lost">Lost item</option><option value="found">Found item</option></select></Field>
          <div className="report-choice-hint">{values.reportType === 'lost' ? 'I lost something and would like help finding it.' : 'I found something and want to help return it.'}</div>
        </Section>
        <Section title="Time and location" subtitle="Tell us when and where you last saw the item. If you're not sure, a best guess is fine, or leave it blank.">
          <Field label={values.reportType === 'lost' ? 'Date last seen' : 'Date found'} help="Optional. An estimate is OK." helpId="incidentDate-help" {...fieldProps('incidentDate')}><input {...inputProps('incidentDate', 'incidentDate-help')} type="date" max={new Date().toLocaleDateString('en-CA')} /></Field>
          <Field label="Approximate time" {...fieldProps('incidentTime')}><input {...inputProps('incidentTime')} type="time" /></Field>
          <Field label="Campus location" help="Optional. Pick the closest building, or Other / Unsure." helpId="campusLocation-help" {...fieldProps('campusLocation')}><select {...inputProps('campusLocation', 'campusLocation-help')}><option value="">Select campus location</option>{CAMPUS_LOCATIONS.map(location => <option value={location} key={location}>{location}</option>)}</select></Field>
        </Section>
        <Section title="Approximate location" subtitle="Use the map area as a reference and describe where the item was lost or found.">
          <div className="report-map" aria-label="Campus map placeholder; map integration has not been added"><div className="report-map-mark">⌖</div><strong>Farmingdale State College</strong><span>Campus map preview</span><small>Map integration pending — this is not a verified map or selected location.</small></div>
          <div className="report-location-readout"><strong>Selected area</strong><span>{values.campusLocation || 'Not specified'}</span></div>
          <div className="report-info">ⓘ Add landmarks, building entrances, room numbers, or nearby locations to help identify the area. Do not include sensitive personal information.</div>
          <Field label="Describe the exact location" {...fieldProps('locationDetails')}><textarea {...inputProps('locationDetails')} rows={4} placeholder="e.g. Near the entrance to the library" maxLength={1000} /></Field>
        </Section>
        <Section title="Lost and Found Liability Notice">
          <p className="report-liability">FSC Lost &amp; Found cannot guarantee recovery or return of lost items. Item condition and descriptions cannot be guaranteed. This draft notice requires institutional/legal approval before production use.</p>
          <label className={`report-check ${liabilityError ? 'report-check--invalid' : ''}`}><input type="checkbox" name={REPORT_FIELDS.liabilityAccepted} checked={values.liabilityAccepted} onChange={e => update('liabilityAccepted', e.target.checked)} aria-invalid={liabilityError ? true : undefined} aria-describedby={liabilityError ? 'liabilityAccepted-error' : undefined} required /><span>I acknowledge the notice above.<span className="report-required" aria-hidden="true"> *</span></span></label>
          {liabilityError && <span className="report-error" id="liabilityAccepted-error" role="alert">{liabilityError}</span>}
          <button className="report-submit" type="submit" disabled={sending}>{sending ? 'Submitting…' : <>Submit report <span aria-hidden="true">→</span></>}</button>
          </Section>
      </div>
    </form>
    {onNavigate && <button type="button" className="report-back" onClick={() => onNavigate('my-account')}>← Back to My Account</button>}
  </div>

}
