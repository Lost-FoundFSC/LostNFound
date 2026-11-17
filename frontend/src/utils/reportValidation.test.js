
import { describe, it, expect } from 'vitest'
import { isValidIncidentDate } from './reportValidation'

describe('Lost and Found Report Date Validation', () => {
  const today = new Date(2026, 10, 8)

  it('accepts a past incident date', () => {
    expect(isValidIncidentDate('2026-11-01', today)).toBe(true)
  })

  it('accepts the current date', () => {
    expect(isValidIncidentDate('2026-11-08', today)).toBe(true)
  })

  it('rejects a future incident date', () => {
    expect(isValidIncidentDate('2026-11-09', today)).toBe(false)
  })

  it('rejects an empty incident date', () => {
    expect(isValidIncidentDate('', today)).toBe(false)
  })

  it('rejects an invalid incident date', () => {
    expect(isValidIncidentDate('not-a-date', today)).toBe(false)
  })
})

import { validateReport, phoneDigits, REPORT_ERRORS } from './reportValidation'

describe('validateReport', () => {
  const today = new Date(2026, 10, 17)
  const valid = {
    reportType: 'lost', fullName: 'Matthew Quintanilla', email: 'quinma1@farmingdale.edu',
    studentId: 'R12345678', phone: '5165512685', category: 'Electronics', itemName: 'iPhone',
    description: 'Silver edges', estimatedValue: '1000', incidentDate: '2026-10-11', incidentTime: '',
    campusLocation: 'Hale Hall', locationDetails: '', liabilityAccepted: true,
  }

  it('accepts a complete report', () => {
    expect(validateReport(valid, today)).toEqual({})
  })

  it('requires name, email, and phone', () => {
    const errors = validateReport({ ...valid, fullName: ' ', email: '', phone: '' }, today)
    expect(errors.fullName).toBe(REPORT_ERRORS.fullName)
    expect(errors.email).toBe(REPORT_ERRORS.emailRequired)
    expect(errors.phone).toBe(REPORT_ERRORS.phoneRequired)
  })

  it('rejects a RAM ID with the wrong number of digits', () => {
    expect(validateReport({ ...valid, studentId: 'R123456789' }, today).studentId).toBe(REPORT_ERRORS.studentId)
    expect(validateReport({ ...valid, studentId: 'R1234567' }, today).studentId).toBe(REPORT_ERRORS.studentId)
    expect(validateReport({ ...valid, studentId: '12345678' }, today).studentId).toBe(REPORT_ERRORS.studentId)
  })

  it('allows a blank or lowercase RAM ID', () => {
    expect(validateReport({ ...valid, studentId: '' }, today).studentId).toBeUndefined()
    expect(validateReport({ ...valid, studentId: 'r12345678' }, today).studentId).toBeUndefined()
  })

  it('checks email and phone format', () => {
    expect(validateReport({ ...valid, email: 'quinma1' }, today).email).toBe(REPORT_ERRORS.emailFormat)
    expect(validateReport({ ...valid, phone: '555-1234' }, today).phone).toBe(REPORT_ERRORS.phoneFormat)
    expect(validateReport({ ...valid, phone: '+1 (516) 551-2685' }, today).phone).toBeUndefined()
  })

  it('requires item details and the notice', () => {
    const errors = validateReport({ ...valid, category: '', itemName: '', description: '', liabilityAccepted: false }, today)
    expect(Object.keys(errors).sort()).toEqual(['category', 'description', 'itemName', 'liabilityAccepted'])
  })

  it('allows the date and campus location to be left blank', () => {
    expect(validateReport({ ...valid, incidentDate: '', campusLocation: '' }, today)).toEqual({})
  })

  it('rejects future dates and negative values', () => {
    expect(validateReport({ ...valid, incidentDate: '2026-11-18' }, today).incidentDate).toBe(REPORT_ERRORS.incidentDateFuture)
    expect(validateReport({ ...valid, estimatedValue: '-5' }, today).estimatedValue).toBe(REPORT_ERRORS.estimatedValue)
  })

  it('strips formatting and a leading 1 from phone numbers', () => {
    expect(phoneDigits('+1 (516) 551-2685')).toBe('5165512685')
  })
})
