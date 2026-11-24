
import { useEffect, useMemo, useState } from 'react'
import './SearchPage.css'

const API_URL = 'http://localhost:8000/api/reports/search/'

export default function SearchPage() {
  const [reports, setReports] = useState([])
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    async function loadReports() {
      try {
        const response = await fetch(API_URL, {
          signal: controller.signal
        })

        if (!response.ok) {
          throw new Error('Unable to load reports.')
        }

        const data = await response.json()

        if (!Array.isArray(data.results)) {
          throw new Error('Invalid report data.')
        }

        setReports(data.results)
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError('Reports could not be loaded. Please try again.')
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    loadReports()

    return () => controller.abort()
  }, [])

  const filteredReports = useMemo(() => {
    const search = query.trim().toLowerCase()

    return reports.filter(report => {
      const matchesType =
        filter === 'all' || report.reportType === filter

      const searchableText = [
        report.itemName,
        report.category,
        report.campusLocation
      ].join(' ').toLowerCase()

      return matchesType && searchableText.includes(search)
    })
  }, [reports, query, filter])

  return (
    <div className="search-page">
      <header className="search-header">
        <h1>Search Lost & Found</h1>
        <p>Browse items reported lost or found on campus.</p>
      </header>

      <section className="search-controls">
        <input
          type="search"
          aria-label="Search reports"
          placeholder="Search items, categories, or locations..."
          value={query}
          onChange={event => setQuery(event.target.value)}
        />

        <div className="search-filters" aria-label="Filter reports">
          {['all', 'lost', 'found'].map(type => (
            <button
              key={type}
              type="button"
              className={filter === type ? 'active' : ''}
              aria-pressed={filter === type}
              onClick={() => setFilter(type)}
            >
              {type === 'all'
                ? 'All Items'
                : type === 'lost' ? 'Lost' : 'Found'}
            </button>
          ))}
        </div>
      </section>

      {loading && <p role="status">Loading reports...</p>}
      {error && <p role="alert">{error}</p>}

      {!loading && !error && (
        <>
          <p className="search-count">
            Showing {filteredReports.length} reports
          </p>

          <div className="search-results">
            {filteredReports.map(report => (
              <article className="search-card" key={report.formId}>
                <span className={`search-status ${report.reportType}`}>
                  {report.reportType === 'lost' ? 'Lost' : 'Found'}
                </span>

                <h2>{report.itemName}</h2>

                <p><strong>Category:</strong> {report.category}</p>
                <p><strong>Location:</strong> {report.campusLocation}</p>
                <p><strong>Date:</strong> {report.incidentDate}</p>
                <p className="search-report-id">
                  Report ID: {report.formId}
                </p>
              </article>
            ))}
          </div>

          {filteredReports.length === 0 && (
            <p>No reports match your search.</p>
          )}
        </>
      )}
    </div>
  )
}
