import { describe, expect, it } from 'vitest'
import { deriveWin, fmtDuration } from './MatchCard'

describe('deriveWin', () => {
  it('returns true when top-level win is true', () => {
    expect(deriveWin({ matchId: 'M1', win: true, parsed_metrics: {} })).toBe(true)
  })

  it('returns false when top-level win is false', () => {
    expect(deriveWin({ matchId: 'M1', win: false, parsed_metrics: {} })).toBe(false)
  })

  it('falls back to parsed_metrics.win when top-level win is undefined', () => {
    expect(
      deriveWin({ matchId: 'M1', parsed_metrics: { win: true } }),
    ).toBe(true)
    expect(
      deriveWin({ matchId: 'M1', parsed_metrics: { win: false } }),
    ).toBe(false)
  })

  it('top-level win takes precedence over parsed_metrics.win', () => {
    expect(
      deriveWin({ matchId: 'M1', win: true, parsed_metrics: { win: false } }),
    ).toBe(true)
  })

  it('returns null when win is absent everywhere', () => {
    expect(deriveWin({ matchId: 'M1', parsed_metrics: {} })).toBeNull()
    // @ts-expect-error -- runtime rows come from passthrough parsing
    expect(deriveWin({ matchId: 'M1' })).toBeNull()
  })
})

describe('fmtDuration', () => {
  it('formats seconds as m:ss', () => {
    expect(fmtDuration(1800)).toBe('30:00')
    expect(fmtDuration(75)).toBe('1:15')
  })

  it('rounds sub-second noise without wrapping past 59', () => {
    expect(fmtDuration(1799.6)).toBe('30:00')
  })

  it('returns em-dash for missing/invalid durations', () => {
    expect(fmtDuration(undefined)).toBe('—')
    expect(fmtDuration(null)).toBe('—')
    expect(fmtDuration(-5)).toBe('—')
  })
})
