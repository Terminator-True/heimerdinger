import { describe, expect, it } from 'vitest'
import {
  buildComparisonRows,
  mockComparisonRows,
  mockMatches,
  mockPlayer,
  mockPlayerMetrics,
  mockProBaseline,
} from './player'

describe('mock player fixture', () => {
  it('has 20 matches and the promised win count', () => {
    expect(mockMatches).toHaveLength(20)
    expect(mockMatches.filter((m) => m.win)).toHaveLength(mockPlayer.wins)
  })
})

describe('mock comparison rows', () => {
  it('is sorted by absolute pct descending', () => {
    const pcts = mockComparisonRows.map((r) => Math.abs(r.pct))
    const sorted = [...pcts].sort((a, b) => b - a)
    expect(pcts).toEqual(sorted)
  })

  it('every row metric exists in the pro baseline', () => {
    for (const row of mockComparisonRows) {
      expect(mockProBaseline.metrics[row.metric]).toBeDefined()
    }
  })

  it('is derived from the fixture inputs, never a hand-written duplicate', () => {
    const recomputed = buildComparisonRows(mockPlayerMetrics, mockProBaseline.metrics)
    expect(mockComparisonRows).toEqual(recomputed)
  })
})
