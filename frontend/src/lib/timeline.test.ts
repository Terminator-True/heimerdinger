import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

// MOCK_ENABLED is read lazily by playerData.ts; a getter over a mutable flag
// lets this file exercise both mock and real modes without real fetches.
const flags = vi.hoisted(() => ({ mock: false }))

vi.mock('../mocks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../mocks')>()
  return {
    ...actual,
    get MOCK_ENABLED() {
      return flags.mock
    },
  }
})

import { buildMockTimeline } from '../mocks'
import { valueAtMinute } from './timeline'
import { useMatchTimeline } from './playerData'

// --- fetch stubbing (mirrors src/lib/playerData.test.ts conventions) --------

function stubRoutes(routes: ReadonlyArray<readonly [string, unknown]>): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (url: string) => {
    const hit = routes.find(([fragment]) => url.includes(fragment))
    if (!hit) {
      return { ok: false, status: 404, json: async () => ({ detail: 'not found' }) }
    }
    return { ok: true, status: 200, json: async () => hit[1] }
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => {
  flags.mock = false
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const TIMELINE_OK = {
  matchId: 'm1',
  puuid: 'p1',
  frameIntervalMs: 60000,
  series: [
    { minute: 10, gold: 4500, cs: 50, xp: 1000, level: 1 },
    { minute: 11, gold: 5000, cs: 55, xp: 1100, level: 2 },
  ],
  opponent: { puuid: 'opp', championName: 'Zed' },
  opponentSeries: [
    { minute: 10, gold: 3500, cs: 40, xp: 900, level: 1 },
    { minute: 11, gold: 3900, cs: 44, xp: 980, level: 2 },
  ],
  diff: [
    { minute: 10, goldDiff: 1000, csDiff: 10 },
    { minute: 11, goldDiff: 1100, csDiff: 11 },
  ],
  milestones: {
    goldAt10: 4500,
    csAt10: 50,
    goldDiffAt10: 1000,
    goldAt15: null,
    csAt15: null,
    goldDiffAt15: null,
    goldAt20: null,
    csAt20: null,
    goldDiffAt20: null,
  },
}

describe('useMatchTimeline (real mode)', () => {
  it('fetches /timeline and parses the series, opponent and milestones', async () => {
    const fetchMock = stubRoutes([['/timeline', TIMELINE_OK]])
    const { result } = renderHook(() => useMatchTimeline('p1', 'm1'))

    await waitFor(() => expect(result.current.state.phase).toBe('success'))
    if (result.current.state.phase === 'success') {
      expect(result.current.state.data.series[0]?.cs).toBe(50)
      expect(result.current.state.data.opponent?.championName).toBe('Zed')
      expect(result.current.state.data.milestones.goldAt10).toBe(4500)
      expect(result.current.state.data.milestones.goldAt15).toBeNull()
    }
    expect(fetchMock.mock.calls[0]?.[0]).toContain('/players/p1/matches/m1/timeline')
  })

  it('maps a 404 timeline to empty', async () => {
    stubRoutes([])
    const { result } = renderHook(() => useMatchTimeline('p1', 'm1'))

    await waitFor(() => expect(result.current.state.phase).toBe('empty'))
  })

  it('fires zero fetches when the matchId is empty', async () => {
    const fetchMock = stubRoutes([])
    renderHook(() => useMatchTimeline('p1', ''))

    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled())
  })
})

describe('useMatchTimeline (mock mode)', () => {
  it('builds a deterministic timeline without touching fetch', () => {
    flags.mock = true
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useMatchTimeline('puuid-1', 'DEMO-020'))

    expect(result.current.state.phase).toBe('success')
    if (result.current.state.phase === 'success') {
      expect(result.current.state.data).toEqual(buildMockTimeline('DEMO-020'))
      expect(result.current.state.data.series.length).toBeGreaterThan(0)
      expect(result.current.state.data.opponent?.championName).toBeTruthy()
    }
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('buildMockTimeline', () => {
  it('is deterministic per matchId and monotonic in gold/cs/xp', () => {
    const a = buildMockTimeline('DEMO-020')
    const b = buildMockTimeline('DEMO-020')
    expect(a).toEqual(b)

    for (let i = 1; i < a.series.length; i++) {
      const prev = a.series[i - 1]!
      const next = a.series[i]!
      expect(next.gold).toBeGreaterThanOrEqual(prev.gold)
      expect(next.cs).toBeGreaterThanOrEqual(prev.cs)
      expect(next.xp).toBeGreaterThanOrEqual(prev.xp)
    }
  })

  it('derives milestones with the same rule as the backend', () => {
    const t = buildMockTimeline('DEMO-020')
    expect(t.milestones.goldAt10).toBe(valueAtMinute(t.series, 10, 'gold'))
    expect(t.milestones.csAt15).toBe(valueAtMinute(t.series, 15, 'cs'))
    expect(t.milestones.goldDiffAt20).toBe(valueAtMinute(t.diff, 20, 'goldDiff'))
  })
})

describe('valueAtMinute', () => {
  const series = [
    { minute: 9, gold: 900 },
    { minute: 10, gold: 1000 },
    { minute: 12, gold: 1200 },
  ]

  it('returns the last point at or before the target', () => {
    expect(valueAtMinute(series, 10, 'gold')).toBe(1000)
    expect(valueAtMinute(series, 11, 'gold')).toBe(1000)
  })

  it('returns null when the game ended before the minute', () => {
    expect(valueAtMinute(series, 15, 'gold')).toBeNull()
  })

  it('returns null on an empty series', () => {
    expect(valueAtMinute([], 10, 'gold')).toBeNull()
  })
})
