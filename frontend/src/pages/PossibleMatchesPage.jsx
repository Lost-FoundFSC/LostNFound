import { useEffect, useRef, useState } from 'react'
import './PossibleMatchesPage.css'

const API_URL = 'http://localhost:8000/api/reports/'
const prettyDate = date => date
  ? new Date(`${date}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  : 'Not specified'

function normalizeFormId(formId) {
  if (typeof formId !== 'string' || !/^L#?\d{9}$/i.test(formId.trim())) return null
  return formId.trim().toUpperCase().replace('#', '')
}

async function fetchMatchData(formId, signal) {
  const response = await fetch(`${API_URL}${formId}/matches/`, { signal })
  let data
  try {
    data = await response.json()
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error('The server returned an unreadable response.', { cause: error })
    }
    throw error
  }

  if (response.status === 404) {
    throw new Error('A lost report from this browser session could not be found.')
  }
  if (response.status === 429) {
    throw new Error('Too many match lookups. Please wait a minute and try again.')
  }
  if (!response.ok) {
    throw new Error(data.detail || 'Unable to load possible matches. Please try again.')
  }
  if (!data.lostReport || !Array.isArray(data.matches)) {
    throw new Error('The server returned an unexpected matches response.')
  }
  return data
}

function messageForError(error) {
  return error instanceof TypeError
    ? 'Unable to connect to the server. Check your connection and try again.'
    : error.message || 'Unable to load possible matches. Please try again.'
}

export default function PossibleMatchesPage({ onNavigate, lostReportFormIds = [] }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(() => lostReportFormIds.some(id => normalizeFormId(id)))
  const [errorMessage, setErrorMessage] = useState('')
  const requestController = useRef(null)

  useEffect(() => {
    const formIds = [...new Set(lostReportFormIds.map(normalizeFormId).filter(Boolean))]
    if (!formIds.length) return undefined

    const controller = new AbortController()
    requestController.current = controller
    Promise.allSettled(formIds.map(formId => fetchMatchData(formId, controller.signal)))
      .then(outcomes => {
        if (controller.signal.aborted) return

        const loadedReports = outcomes
          .filter(outcome => outcome.status === 'fulfilled')
          .map(outcome => outcome.value)
        const failedCount = outcomes.length - loadedReports.length
        setReports(loadedReports)

        if (failedCount === outcomes.length) {
          const firstFailure = outcomes.find(outcome => outcome.status === 'rejected')
          setErrorMessage(messageForError(firstFailure.reason))
        } else if (failedCount > 0) {
          setErrorMessage(`Matches for ${failedCount} of your lost reports could not be loaded. Please try again.`)
        }
      })
      .finally(() => {
        if (requestController.current === controller) {
          requestController.current = null
          setLoading(false)
        }
      })

    return () => controller.abort()
  }, [lostReportFormIds])

  return (
    <section className="matches-page page-card" aria-labelledby="matches-title">
      <header className="matches-page-header">
        <div>
          <p className="matches-kicker">LOST &amp; FOUND</p>
          <h1 id="matches-title">Possible Matches</h1>
          <p>Found items that may match your lost-item reports.</p>
        </div>
        <button className="matches-back-button" type="button" onClick={() => onNavigate?.('my-account')}>Back to My Account</button>
      </header>

      <p className="matches-session-notice">
        Showing matches for lost reports saved in this browser session. They are not yet linked to a signed-in account.
      </p>

      {loading && <p className="matches-loading" role="status">Loading possible matches…</p>}
      {errorMessage && <p className="matches-error" role="alert">{errorMessage}</p>}

      {!lostReportFormIds.some(id => normalizeFormId(id)) && (
        <div className="matches-no-reports">
          <p>No lost-item reports are linked to this browser session yet.</p>
          <button type="button" onClick={() => onNavigate?.('forms')}>Submit a lost-item report</button>
        </div>
      )}

      {reports.length > 0 && (
        <div className="matches-results">
          <p className="matches-score-notice">
            Scores compare item name, category, location, and date when available. They are not probabilities
            or proof that an item belongs to you; Campus Security must verify any match.
          </p>
          {reports.map(report => (
            <section className="matches-report-group" key={report.lostReport.formId} aria-labelledby={`lost-report-${report.lostReport.formId.replace('#', '')}`}>
              <header className="matches-lost-item">
                <p className="match-item-label">Possible matches for your lost report</p>
                <h2 id={`lost-report-${report.lostReport.formId.replace('#', '')}`}>{report.lostReport.itemName}</h2>
                <p>{report.lostReport.category} · Report {report.lostReport.formId}</p>
              </header>

              {report.matches.length ? report.matches.map(match => (
                <article className="match-card" key={match.formId}>
                  <header className="match-card-header">
                    <div>
                      <span className="match-reference">Found report {match.formId}</span>
                      <h3>{match.itemName}</h3>
                    </div>
                    <div className="match-score" aria-label={`${match.matchScore}% comparison score`}>
                      <strong>{match.matchScore}%</strong>
                      <span>match score</span>
                    </div>
                  </header>
                  <dl className="match-details">
                    <div><dt>Category</dt><dd>{match.category}</dd></div>
                    <div><dt>Found</dt><dd>{match.campusLocation || 'Location not specified'} · {prettyDate(match.incidentDate)}</dd></div>
                  </dl>
                </article>
              )) : <p className="matches-empty">There are no unlinked found reports for this lost item yet.</p>}
            </section>
          ))}
        </div>
      )}

      <p className="matches-footer">Found-item contact details, descriptions, and photos are kept private. Ask Campus Security to verify a potential match.</p>
    </section>
  )
}
