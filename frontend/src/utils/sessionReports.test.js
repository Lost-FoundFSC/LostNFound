import { afterEach, describe, expect, it, vi } from 'vitest'
import { addLostReportId, LOST_REPORT_IDS_KEY, readLostReportIds } from './sessionReports'

function createStorage(initialValue = null) {
  let value = initialValue
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((key, nextValue) => { value = nextValue }),
  }
}

describe('lost report session storage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reads and validates saved lost report IDs', () => {
    const storage = createStorage(JSON.stringify(['L#123456789', 'bad-id', 'L#123456789', 'l987654321']))

    expect(readLostReportIds(storage)).toEqual(['L#123456789', 'l987654321'])
  })

  it('adds a submitted lost report ID once and persists it in the session', () => {
    const storage = createStorage()

    const first = addLostReportId([], 'L#123456789', storage)
    const second = addLostReportId(first, 'L#123456789', storage)

    expect(second).toEqual(['L#123456789'])
    expect(storage.setItem).toHaveBeenLastCalledWith(LOST_REPORT_IDS_KEY, '["L#123456789"]')
  })

  it('does not save a found report ID as a lost report', () => {
    const storage = createStorage()

    expect(addLostReportId([], 'F#123456789', storage)).toEqual([])
    expect(storage.setItem).not.toHaveBeenCalled()
  })
})
