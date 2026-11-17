/**
 * Validates the date an item was lost or found.
 * Future dates are not allowed.
 */
export function isValidIncidentDate(dateString, today = new Date()) {
  if (!dateString) return false

  const incidentDate = new Date(`${dateString}T00:00:00`)

  if (Number.isNaN(incidentDate.getTime())) {
    return false
  }

  const currentDate = new Date(today)
  currentDate.setHours(0, 0, 0, 0)

  return incidentDate <= currentDate
}

// Same rules as the backend (backend/reports/serializers.py).
const RAM_ID = /^R\d{8}$/i
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Digits only, without a leading US country code 1. */
export function phoneDigits(value) {
  const digits = String(value ?? '').replace(/\D/g, '')
  return digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits
}

export const REPORT_ERRORS = Object.freeze({
  fullName: 'Enter your name.',
  emailRequired: 'Enter your email address.',
  emailFormat: 'Enter a valid email address, like you@farmingdale.edu.',
  studentId: 'A RAM ID is the letter R followed by 8 digits, like R01234567.',
  phoneRequired: 'Enter your phone number.',
  phoneFormat: 'Enter a 10-digit phone number, like (516) 555-1234.',
  category: 'Choose a category.',
  itemName: 'Enter the item name.',
  description: 'Describe the item.',
  estimatedValue: 'Enter a value of 0 or more, or leave it blank.',
  incidentDateRequired: 'Enter the date.',
  incidentDateFuture: 'The date cannot be in the future.',
  campusLocation: 'Choose a campus location.',
  liabilityAccepted: 'You must acknowledge the notice to submit.',
})

/**
 * Checks the whole report form.
 * @returns {Object<string, string>} field name -> error message (empty when valid)
 */
export function validateReport(values, today = new Date()) {
  const errors = {}
  const text = name => String(values[name] ?? '').trim()

  if (!text('fullName')) errors.fullName = REPORT_ERRORS.fullName

  if (!text('email')) errors.email = REPORT_ERRORS.emailRequired
  else if (!EMAIL.test(text('email'))) errors.email = REPORT_ERRORS.emailFormat

  if (text('studentId') && !RAM_ID.test(text('studentId'))) errors.studentId = REPORT_ERRORS.studentId

  if (!text('phone')) errors.phone = REPORT_ERRORS.phoneRequired
  else if (phoneDigits(values.phone).length !== 10) errors.phone = REPORT_ERRORS.phoneFormat

  if (!text('category')) errors.category = REPORT_ERRORS.category
  if (!text('itemName')) errors.itemName = REPORT_ERRORS.itemName
  if (!text('description')) errors.description = REPORT_ERRORS.description

  if (text('estimatedValue')) {
    const value = Number(text('estimatedValue'))
    if (!Number.isFinite(value) || value < 0) errors.estimatedValue = REPORT_ERRORS.estimatedValue
  }

  if (!text('incidentDate')) errors.incidentDate = REPORT_ERRORS.incidentDateRequired
  else if (!isValidIncidentDate(text('incidentDate'), today)) errors.incidentDate = REPORT_ERRORS.incidentDateFuture

  if (!text('campusLocation')) errors.campusLocation = REPORT_ERRORS.campusLocation
  if (!values.liabilityAccepted) errors.liabilityAccepted = REPORT_ERRORS.liabilityAccepted

  return errors
}
