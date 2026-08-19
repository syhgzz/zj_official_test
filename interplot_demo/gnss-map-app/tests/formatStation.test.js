import { describe, expect, test } from 'vitest'

import { escapeHtml, formatTimestamp } from '../src/ui/formatStation.js'

describe('escapeHtml', () => {
  test('escapes all characters that can break station detail markup', () => {
    expect(escapeHtml(`<img src="x" onerror='run'>&`)).toBe(
      '&lt;img src=&quot;x&quot; onerror=&#39;run&#39;&gt;&amp;',
    )
  })

  test('turns nullish values into an empty safe string', () => {
    expect(escapeHtml(null)).toBe('')
    expect(escapeHtml(undefined)).toBe('')
  })
})

describe('formatTimestamp', () => {
  test('returns a placeholder for invalid timestamps', () => {
    expect(formatTimestamp(null)).toBe('--')
    expect(formatTimestamp('')).toBe('--')
    expect(formatTimestamp('not-a-date')).toBe('--')
  })

  test('formats a numeric millisecond timestamp as a readable local date', () => {
    const result = formatTimestamp(1_787_124_405_649)

    expect(result).not.toBe('--')
    expect(result).not.toContain('Invalid')
    expect(result).toMatch(/\d{4}/)
  })
})
