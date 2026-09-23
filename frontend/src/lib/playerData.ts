// The single swap seam between mock fixtures and real endpoints. Views only
// import from here; when the real endpoints land, only this file changes.
//
// MOCK_ENABLED=true  -> synthetic success states from src/mocks/player.ts
// MOCK_ENABLED=false -> the real useApiQuery-backed calls that exist today
import { getPlayerMatches, getPlayerReport } from './api'
import { useApiQuery, type QueryState } from '../hooks/useApiQuery'
import {
  MOCK_ENABLED,
  mockComparisonRows,
  mockMatches,
  mockPlayer,
  mockProBaseline,
  type ComparisonPayload,
  type ComparisonRow,
  type MockMatch,
  type PlayerOverview,
  type ProBaseline,
  type ProMetricStats,
} from '../mocks'

export type {
  ComparisonPayload,
  ComparisonRow,
  MockMatch,
  PlayerOverview,
  ProBaseline,
  ProMetricStats,
} from '../mocks'

// MatchCard needs `parsed_metrics`; the trend chart needs the flat metrics.
// Real rows carry parsed_metrics; mock rows get them synthesized below.
export type MatchRow = Omit<MockMatch, 'timestamp' | 'win'> & {
  timestamp: number | null
  // Real rows can have an unknown win flag (null); mock rows always know it.
  win: boolean | null
  parsed_metrics: Record<string, unknown>
}

// QueryState plus the retry callback ErrorState needs (design §hook pattern).
export interface PlayerQuery<T> {
  state: QueryState<T>
  retry: () => void
}

const noop = () => {}
const MATCH_HISTORY_LIMIT = 20

type ReportData = Awaited<ReturnType<typeof getPlayerReport>>
type ApiMatchRow = Awaited<ReturnType<typeof getPlayerMatches>>[number] & {
  win?: boolean | null
}

function isFullReport(d: ReportData): d is Extract<ReportData, { games_analyzed: number }> {
  return 'games_analyzed' in d
}

function numMetric(metrics: Record<string, unknown>, keys: string[]): number {
  for (const key of keys) {
    const v = metrics[key]
    if (typeof v === 'number' && Number.isFinite(v)) return v
  }
  return 0
}

function mapOverview(puuid: string, state: QueryState<ReportData>): QueryState<PlayerOverview> {
  if (state.phase !== 'success') return state
  const d = state.data
  if (!isFullReport(d)) return { phase: 'empty' }
  return {
    phase: 'success',
    data: {
      puuid,
      riotid: d.player,
      role: d.role,
      champion: d.champion,
      championPool: [],
      gamesAnalyzed: d.games_analyzed,
      wins: Math.round(numMetric(d.metrics, ['wins', 'win'])),
    },
  }
}

function toMatchRow(row: ApiMatchRow): MatchRow {
  const m = row.parsed_metrics
  const win =
    typeof row.win === 'boolean'
      ? row.win
      : typeof m['win'] === 'boolean'
        ? m['win']
        : null
  return {
    matchId: row.matchId,
    championName: row.championName,
    role: row.role,
    win,
    timestamp: row.timestamp,
    parsed_metrics: m,
    kills: numMetric(m, ['kills']),
    deaths: numMetric(m, ['deaths']),
    assists: numMetric(m, ['assists']),
    kda: numMetric(m, ['kda']),
    cs_per_min: numMetric(m, ['cs_per_min', 'csPerMin']),
    visionScorePerMinute: numMetric(m, ['visionScorePerMinute', 'vision_score_per_minute']),
    controlWardsPlaced: numMetric(m, ['controlWardsPlaced', 'control_wards_placed']),
    wardsPlaced: numMetric(m, ['wardsPlaced', 'wards_placed']),
    killParticipation: numMetric(m, ['killParticipation', 'kill_participation']),
    damagePerMinute: numMetric(m, ['damagePerMinute', 'damage_per_minute']),
    goldPerMinute: numMetric(m, ['goldPerMinute', 'gold_per_minute', 'gpm']),
    goldEarned: numMetric(m, ['goldEarned', 'gold_earned']),
    durationSeconds: numMetric(m, ['gameDuration', 'game_duration', 'duration']),
    csAt10: numMetric(m, ['csAt10', 'cs_at_10']),
    csAdvantageOnLaneOpponent: numMetric(m, ['csAdvantageOnLaneOpponent']),
    turretPlatesTaken: numMetric(m, ['turretPlatesTaken']),
    damageToObjectives: numMetric(m, ['damageToObjectives']),
    teamDamagePercentage: numMetric(m, ['teamDamagePercentage']),
    objectives: {
      dragons: numMetric(m, ['dragons']),
      barons: numMetric(m, ['barons']),
      turrets: numMetric(m, ['turrets']),
    },
  }
}

function mapMatchList(state: QueryState<ApiMatchRow[]>): QueryState<MatchRow[]> {
  if (state.phase !== 'success') return state
  // Mapping bypasses useApiQuery's isEmptyPayload, so re-apply it here.
  if (state.data.length === 0) return { phase: 'empty' }
  return { phase: 'success', data: state.data.map(toMatchRow) }
}

const MOCK_MATCH_ROWS: MatchRow[] = mockMatches.map((m) => ({
  ...m,
  timestamp: Date.parse(m.timestamp),
  parsed_metrics: {
    win: m.win,
    kda: m.kda,
    cs_per_min: m.cs_per_min,
    goldEarned: m.goldEarned,
    gameDuration: m.durationSeconds,
  },
}))

export function usePlayerOverview(puuid: string): PlayerQuery<PlayerOverview> {
  // enabled=false in mock mode keeps the real fetcher from ever firing.
  const enabled = puuid !== '' && !MOCK_ENABLED
  const { state, retry } = useApiQuery(() => getPlayerReport(puuid), [puuid], { enabled })
  if (MOCK_ENABLED && puuid !== '') {
    return { state: { phase: 'success', data: mockPlayer }, retry }
  }
  return { state: mapOverview(puuid, state), retry }
}

export function useMatchList(puuid: string): PlayerQuery<MatchRow[]> {
  const enabled = puuid !== '' && !MOCK_ENABLED
  const { state, retry } = useApiQuery(
    async () => (await getPlayerMatches(puuid, MATCH_HISTORY_LIMIT)) as ApiMatchRow[],
    [puuid],
    { enabled },
  )
  if (MOCK_ENABLED && puuid !== '') {
    return { state: { phase: 'success', data: MOCK_MATCH_ROWS }, retry }
  }
  return { state: mapMatchList(state), retry }
}

export function useComparison(puuid: string): PlayerQuery<ComparisonPayload> {
  // ponytail: the comparison endpoint does not exist yet — real mode degrades
  // to empty. `puuid` stays in the signature so callers don't change when the
  // real request lands here.
  void puuid
  if (MOCK_ENABLED) {
    return {
      state: {
        phase: 'success',
        data: { baseline: mockProBaseline, rows: mockComparisonRows },
      },
      retry: noop,
    }
  }
  return { state: { phase: 'empty' }, retry: noop }
}

// --- Score helpers (0-100 position of the player vs the pro distribution) ---

// Key Support metrics shown in the percentile card and used for the score.
export const SCORE_METRICS = [
  'visionScorePerMinute',
  'controlWardsPlaced',
  'cs_per_min',
  'killParticipation',
  'damagePerMinute',
  'kda',
] as const

export type ScoreMetric = (typeof SCORE_METRICS)[number]

function lerp(value: number, lo: number, hi: number, loScore: number, hiScore: number): number {
  if (hi === lo) return (loScore + hiScore) / 2
  return loScore + ((value - lo) / (hi - lo)) * (hiScore - loScore)
}

// Map a value onto 0-100 using the pro quartiles as anchors.
export function metricPercentileScore(value: number, s: ProMetricStats): number {
  if (value <= s.p25) return s.p25 === 0 ? 0 : Math.max(0, (value / s.p25) * 25)
  if (value <= s.median) return lerp(value, s.p25, s.median, 25, 50)
  if (value <= s.p75) return lerp(value, s.median, s.p75, 50, 75)
  const span = s.p75 - s.median
  if (span <= 0) return 100
  return Math.min(100, 75 + ((value - s.p75) / span) * 25)
}

// Position between p25 (0%) and p75 (100%), clamped — drives the percentile bar.
export function metricPositionPct(value: number, s: ProMetricStats): number {
  const span = s.p75 - s.p25
  if (span <= 0) return 50
  return Math.min(100, Math.max(0, ((value - s.p25) / span) * 100))
}

export function overallScore(rows: ComparisonRow[], baseline: ProBaseline): number {
  const scores: number[] = []
  for (const metric of SCORE_METRICS) {
    const row = rows.find((r) => r.metric === metric)
    const stats = baseline.metrics[metric]
    if (!row || !stats) continue
    scores.push(metricPercentileScore(row.player, stats))
  }
  if (scores.length === 0) return 0
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
}

export function averagePct(rows: ComparisonRow[]): number {
  if (rows.length === 0) return 0
  return rows.reduce((a, r) => a + r.pct, 0) / rows.length
}
