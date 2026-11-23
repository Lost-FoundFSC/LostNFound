export const LOST_REPORT_IDS_KEY = 'fsc-lost-report-form-ids'

const isLostReportId = value => typeof value === 'string' && /^L#?\d{9}$/i.test(value)

export function readLostReportIds(storage = window.sessionStorage) {
  try {
    const stored = storage.getItem(LOST_REPORT_IDS_KEY)
    if (!stored) return []

    const reportIds = JSON.parse(stored)
    if (!Array.isArray(reportIds)) {
      throw new TypeError('Expected a list of lost report form IDs.')
    }
    return [...new Set(reportIds.filter(isLostReportId))]
  } catch (error) {
    console.error('Unable to read lost report IDs for this browser session:', error)
    return []
  }
}

export function addLostReportId(currentIds, formId, storage = window.sessionStorage) {
  if (!isLostReportId(formId)) return currentIds

  const reportIds = [...new Set([...currentIds, formId])]
  try {
    storage.setItem(LOST_REPORT_IDS_KEY, JSON.stringify(reportIds))
  } catch (error) {
    console.error('Unable to save lost report IDs for this browser session:', error)
  }
  return reportIds
}
