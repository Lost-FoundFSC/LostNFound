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
  incidentDateFuture: 'The date cannot be in the future.',
  liabilityAccepted: 'You must acknowledge the notice to submit.',
})

/**
 * Contact details are required on lost reports (Campus Security has to reach
 * the owner) and optional on found reports (the finder has handed the item in).
 */
export function contactRequired(reportType) {
  return reportType !== 'found'
}

/**
 * Checks the whole report form.
 * @returns {Object<string, string>} field name -> error message (empty when valid)
 */
export function validateReport(values, today = new Date()) {
  const errors = {}
  const text = name => String(values[name] ?? '').trim()
  const required = contactRequired(values.reportType)

  // Contact fields: required for lost reports; if filled in, always checked.
  if (required && !text('fullName')) errors.fullName = REPORT_ERRORS.fullName

  if (!text('email')) { if (required) errors.email = REPORT_ERRORS.emailRequired }
  else if (!EMAIL.test(text('email'))) errors.email = REPORT_ERRORS.emailFormat

  if (text('studentId') && !RAM_ID.test(text('studentId'))) errors.studentId = REPORT_ERRORS.studentId

  if (!text('phone')) { if (required) errors.phone = REPORT_ERRORS.phoneRequired }
  else if (phoneDigits(values.phone).length !== 10) errors.phone = REPORT_ERRORS.phoneFormat

  if (!text('category')) errors.category = REPORT_ERRORS.category
  if (!text('itemName')) errors.itemName = REPORT_ERRORS.itemName
  if (!text('description')) errors.description = REPORT_ERRORS.description

  if (text('estimatedValue')) {
    const value = Number(text('estimatedValue'))
    if (!Number.isFinite(value) || value < 0) errors.estimatedValue = REPORT_ERRORS.estimatedValue
  }

  // Date and campus location are optional (a best guess is fine),
  // but a date that is filled in cannot be in the future.
  if (text('incidentDate') && !isValidIncidentDate(text('incidentDate'), today)) {
    errors.incidentDate = REPORT_ERRORS.incidentDateFuture
  }
  if (!values.liabilityAccepted) errors.liabilityAccepted = REPORT_ERRORS.liabilityAccepted

  return errors
}

// Photo rules, same as the backend (backend/reports/images.py).
export const MAX_PHOTOS = 5
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024
export const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp']

/**
 * Splits newly picked files into ones that can be added and error messages
 * for the ones that cannot.
 * @returns {{ accepted: File[], errors: string[] }}
 */
export function checkPhotos(newFiles, currentCount = 0) {
  const accepted = []
  const errors = []
  for (const file of newFiles) {
    if (!PHOTO_TYPES.includes(file.type)) {
      errors.push(`${file.name}: only JPEG, PNG, or WebP photos can be uploaded.`)
    } else if (file.size > MAX_PHOTO_BYTES) {
      errors.push(`${file.name}: photo is larger than 5 MB.`)
    } else if (currentCount + accepted.length >= MAX_PHOTOS) {
      errors.push(`You can add up to ${MAX_PHOTOS} photos.`)
      break
    } else {
      accepted.push(file)
    }
  }
  return { accepted, errors }
}
