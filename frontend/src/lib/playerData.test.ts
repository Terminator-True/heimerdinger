import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import {
  MATCH_METRIC_ALIASES,
  normalizeMatchRow,
  useComparison,
  useMatchList,
  usePlayerOverview,
  type MatchRow,
  type RawMatchInput,
} from './playerData'
import { mockMatches, type MockMatch } from '../mocks'

// --- fetch stubbing (mirrors src/lib/api.test.ts conventions) --------------

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

afterEach(() => {
  vi.unstubAllGlobals()
})

// --- normalization ---------------------------------------------------------

// Real backend row: rich stats live in parsed_metrics behind `ch_` names.
const REAL_ROW: RawMatchInput & { player_puuid: string } = {
  player_puuid: 'p1',
  matchId: 'M-1',
  championName: 'Thresh',
  role: 'Support',
  timestamp: 1_700_000_000_000,
  parsed_metrics: {
    cs_per_min: 1.1,
    kda: 2.5,
    win: true,
    goldEarned: 9000,
    gameDuration: 1700,
    ch_visionScorePerMinute: 3.4,
    ch_controlWardsPlaced: 10,
    ch_killParticipation: 0.72,
    ch_damagePerMinute: 280,
    ch_goldPerMinute: 300,
    ch_teamDamagePercentage: 0.18,
    ch_maxCsAdvantageOnLaneOpponent: 3,
    ch_turretPlatesTaken: 2,
    ch_laneMinionsFirst10Minutes: 12,
    totalDamageDealtToChampions: 12000,
    damageDealtToObjectives: 9000,
    wardsPlaced: 28,
    wardsKilled: 4,
    visionScore: 60,
  },
}

const CANONICAL_ONLY = [
  'matchId',
  'championName',
  'role',
  'win',
  'timestamp',
  'parsed_metrics',
  'objectives',
]

function canonicalKeys(row: MatchRow): string[] {
  return Object.keys(row)
    .filter((k) => !CANONICAL_ONLY.includes(k))
    .sort()
}

describe('normalizeMatchRow', () => {
  it('lifts ch_*/total* rich metrics to canonical keys', () => {
    const row = normalizeMatchRow(REAL_ROW)

    expect(row.visionScorePerMinute).toBe(3.4)
    expect(row.controlWardsPlaced).toBe(10)
    expect(row.killParticipation).toBe(0.72)
    expect(row.damagePerMinute).toBe(280)
    expect(row.goldPerMinute).toBe(300)
    expect(row.teamDamagePercentage).toBe(0.18)
    expect(row.csAdvantageOnLaneOpponent).toBe(3)
    expect(row.turretPlatesTaken).toBe(2)
    expect(row.csAt10).toBe(12)
    expect(row.damageDealtToChampions).toBe(12000)
    expect(row.damageToObjectives).toBe(9000)
    expect(row.cs_per_min).toBe(1.1)
    expect(row.durationSeconds).toBe(1700)
    expect(row.win).toBe(true)
  })

  it('never exposes a ch_ prefix on the normalized row', () => {
    const row = normalizeMatchRow(REAL_ROW)
    expect(Object.keys(row).some((k) => k.startsWith('ch_'))).toBe(false)
    // Raw payload is preserved untouched for MatchCard's alias reads.
    expect(row.parsed_metrics['ch_visionScorePerMinute']).toBe(3.4)
  })

  it('leaves a missing metric absent instead of coercing it to 0', () => {
    const row = normalizeMatchRow({ matchId: 'M-2', parsed_metrics: {} })

    expect(row.visionScorePerMinute).toBeUndefined()
    expect('cs_per_min' in row).toBe(false)
    expect(row.win).toBeNull()
    expect(row.timestamp).toBeNull()
  })

  it('lifts objective counts from the flat rich keys and from nested objectives', () => {
    // Real API rows: team totals arrive as flat rich keys.
    const fromTeam = normalizeMatchRow({
      matchId: 'M-3',
      parsed_metrics: { team_dragonKills: 3, team_baronKills: 1, team_towerKills: 7 },
    })
    expect(fromTeam.dragons).toBe(3)
    expect(fromTeam.barons).toBe(1)
    expect(fromTeam.turrets).toBe(7)

    // Mock-shaped rows nest them; a real 0 count must survive, not vanish.
    const fromNested = normalizeMatchRow({
      matchId: 'M-4',
      parsed_metrics: {},
      objectives: { dragons: 2, barons: 0, turrets: 5 },
    })
    expect(fromNested.dragons).toBe(2)
    expect(fromNested.barons).toBe(0)
    expect(fromNested.turrets).toBe(5)
  })

  it('documents every canonical key through an alias list', () => {
    for (const candidates of Object.values(MATCH_METRIC_ALIASES)) {
      expect(candidates.length).toBeGreaterThan(0)
    }
  })
})

// A mock-shaped raw carries the canonical names at the top level; the same
// numbers arriving through the real `ch_`/total* names must normalize equal.
function asRealRow(m: MockMatch): RawMatchInput {
  return {
    matchId: m.matchId,
    championName: m.championName,
    role: m.role,
    timestamp: Date.parse(m.timestamp),
    parsed_metrics: {
      cs_per_min: m.cs_per_min,
      kda: m.kda,
      win: m.win,
      goldEarned: m.goldEarned,
      gameDuration: m.durationSeconds,
      ch_visionScorePerMinute: m.visionScorePerMinute,
      ch_controlWardsPlaced: m.controlWardsPlaced,
      ch_killParticipation: m.killParticipation,
      ch_damagePerMinute: m.damagePerMinute,
      ch_goldPerMinute: m.goldPerMinute,
      ch_teamDamagePercentage: m.teamDamagePercentage,
      ch_maxCsAdvantageOnLaneOpponent: m.csAdvantageOnLaneOpponent,
      ch_turretPlatesTaken: m.turretPlatesTaken,
      ch_laneMinionsFirst10Minutes: m.csAt10,
      damageDealtToObjectives: m.damageToObjectives,
      wardsPlaced: m.wardsPlaced,
    },
  }
}

const SHARED_METRICS: readonly (keyof MatchRow)[] = [
  'kda',
  'cs_per_min',
  'csAt10',
  'csAdvantageOnLaneOpponent',
  'goldPerMinute',
  'goldEarned',
  'visionScorePerMinute',
  'controlWardsPlaced',
  'wardsPlaced',
  'killParticipation',
  'damagePerMinute',
  'teamDamagePercentage',
  'damageToObjectives',
  'turretPlatesTaken',
  'durationSeconds',
]

describe('normalization source agreement', () => {
  it('mock and real rows agree on canonical keys and values', () => {
    const mock = mockMatches[0] as MockMatch
    const mockRow = normalizeMatchRow({ ...mock, timestamp: Date.parse(mock.timestamp) })
    const realRow = normalizeMatchRow(asRealRow(mock))

    for (const key of SHARED_METRICS) {
      expect(realRow[key]).toBe(mockRow[key])
    }
    // The real-shaped row produces exactly the shared canonical set — no ch_
    // prefix, no invented extras.
    expect(new Set(canonicalKeys(realRow))).toEqual(new Set(SHARED_METRICS))
    expect(canonicalKeys(mockRow).every((k) => !k.startsWith('ch_'))).toBe(true)
  })
})

// --- real-mode hooks (fetch stubbed) ---------------------------------------

const COMPARISON_OK = {
  player: 'p1',
  role: 'Support',
  games_analyzed: 20,
  baseline: { role: 'Support', source: "Oracle's Elixir", games: 4820, season: 2025 },
  rows: [
    {
      metric: 'visionScorePerMinute',
      player: 3.4,
      pro: 2.5,
      delta: 0.9,
      pct: 36,
      p25: 1.9,
      median: 2.4,
      p75: 3.0,
      n: 120,
    },
    {
      metric: 'kda',
      player: 2.5,
      pro: 2.8,
      delta: -0.3,
      pct: -10.7,
      p25: 2.1,
      median: 2.8,
      p75: 3.7,
      n: 200,
    },
  ],
}

const REPORT_OK = {
  player: 'Faker#KR1',
  role: 'Mid',
  champion: 'Ahri',
  games_analyzed: 20,
  metrics: { win: 0.55, kda: 3.4 },
  pro_reference: null,
  deltas: {},
}

describe('useMatchList (real mode)', () => {
  it('fetches /matches and normalizes ch_* rows to canonical keys', async () => {
    const fetchMock = stubRoutes([['/players/p1/matches', [REAL_ROW]]])
    const { result } = renderHook(() => useMatchList('p1'))

    await waitFor(() => expect(result.current.state.phase).toBe('success'))
    if (result.current.state.phase === 'success') {
      const row = result.current.state.data[0]!
      expect(row.visionScorePerMinute).toBe(3.4)
      expect(row.damageDealtToChampions).toBe(12000)
      expect(row.parsed_metrics['ch_visionScorePerMinute']).toBe(3.4)
      expect(Object.keys(row).some((k) => k.startsWith('ch_'))).toBe(false)
    }
    expect(fetchMock.mock.calls[0]?.[0]).toContain('/players/p1/matches?limit=20')
  })
})

describe('useComparison (real mode)', () => {
  it('maps rows and folds the per-row percentiles into baseline.metrics', async () => {
    stubRoutes([['/players/p1/comparison', COMPARISON_OK]])
    const { result } = renderHook(() => useComparison('p1'))

    await waitFor(() => expect(result.current.state.phase).toBe('success'))
    if (result.current.state.phase === 'success') {
      expect(result.current.state.data.rows[0]).toEqual({
        metric: 'visionScorePerMinute',
        player: 3.4,
        pro: 2.5,
        delta: 0.9,
        pct: 36,
      })
      expect(result.current.state.data.baseline.metrics['visionScorePerMinute']).toEqual({
        mean: 2.5,
        median: 2.4,
        p25: 1.9,
        p75: 3.0,
      })
      expect(result.current.state.data.baseline.season).toBe(2025)
    }
  })

  it('maps a null baseline to empty — never fabricated bars', async () => {
    stubRoutes([
      ['/players/p1/comparison', { player: 'p1', role: 'Support', games_analyzed: 5, baseline: null, rows: [] }],
    ])
    const { result } = renderHook(() => useComparison('p1'))

    await waitFor(() => expect(result.current.state.phase).toBe('empty'))
  })

  it('maps a 404 comparison to empty', async () => {
    stubRoutes([])
    const { result } = renderHook(() => useComparison('p1'))

    await waitFor(() => expect(result.current.state.phase).toBe('empty'))
  })
})

describe('usePlayerOverview (real mode)', () => {
  it('composes /report identity with the /comparison win rate', async () => {
    const winComparison = {
      ...COMPARISON_OK,
      rows: [
        {
          metric: 'win',
          player: 0.55,
          pro: 0.5,
          delta: 0.05,
          pct: 10,
          p25: 0.45,
          median: 0.5,
          p75: 0.55,
          n: 100,
        },
      ],
    }
    const fetchMock = stubRoutes([
      ['/players/p1/report', REPORT_OK],
      ['/players/p1/comparison', winComparison],
    ])

    const { result } = renderHook(() => usePlayerOverview('p1'))
    await waitFor(() => expect(result.current.state.phase).toBe('success'))
    if (result.current.state.phase === 'success') {
      expect(result.current.state.data.riotid).toBe('Faker#KR1')
      expect(result.current.state.data.gamesAnalyzed).toBe(20)
      expect(result.current.state.data.wins).toBe(11) // round(0.55 * 20)
    }
    const urls = fetchMock.mock.calls.map((c) => c[0])
    expect(urls.some((u) => String(u).includes('/report'))).toBe(true)
    expect(urls.some((u) => String(u).includes('/comparison'))).toBe(true)
  })
})
