// The single swap seam between mock fixtures and real endpoints. Views only
// import from here; when the real endpoints land, only this file changes.
//
// MOCK_ENABLED=true  -> synthetic success states from src/mocks/player.ts
// MOCK_ENABLED=false -> /report + /comparison + /matches, normalized below
import { getMatchTimeline, getPlayerComparison, getPlayerMatches, getPlayerReport } from './api'
import { useApiQuery, type QueryState } from '../hooks/useApiQuery'
import type { MatchTimeline } from './timeline'
import {
  MOCK_ENABLED,
  buildMockTimeline,
  mockComparisonRows,
  mockMatches,
  mockPlayer,
  mockProBaseline,
  type ComparisonPayload,
  type ComparisonRow,
  type MatchObjectives,
  type PlayerOverview,
  type ProBaseline,
  type ProMetricStats,
} from '../mocks'

export type {
  ComparisonPayload,
  ComparisonRow,
  MatchObjectives,
  PlayerOverview,
  ProBaseline,
  ProMetricStats,
} from '../mocks'

// QueryState plus the retry callback ErrorState needs (design §hook pattern).
export interface PlayerQuery<T> {
  state: QueryState<T>
  retry: () => void
}

const MATCH_HISTORY_LIMIT = 20

type ReportData = Awaited<ReturnType<typeof getPlayerReport>>
type ApiComparison = Awaited<ReturnType<typeof getPlayerComparison>>
type ApiMatchRow = Awaited<ReturnType<typeof getPlayerMatches>>[number] & {
  win?: boolean | null
}

// --- Match normalization ---------------------------------------------------
//
// Real rows keep the rich stats in `parsed_metrics` under challenge names
// (`ch_visionScorePerMinute`, …) beside the parser fields; mock rows carry the
// canonical names at the top level. `normalizeMatchRow` collapses both into one
// shape so the views never branch on the source and never see a `ch_` prefix.

export interface MatchRow {
  matchId: string
  championName: string
  role: string
  // Real rows can have an unknown win flag (null); mock rows always know it.
  win: boolean | null
  timestamp: number | null
  // Raw payload kept for MatchCard's alias-tolerant reads.
  parsed_metrics: Record<string, unknown>
  objectives?: MatchObjectives
  // Canonical metrics — present only when the source row actually carries them.
  kills?: number
  deaths?: number
  assists?: number
  kda?: number
  cs_per_min?: number
  csAt10?: number
  csAdvantageOnLaneOpponent?: number
  goldPerMinute?: number
  goldEarned?: number
  visionScorePerMinute?: number
  controlWardsPlaced?: number
  wardsPlaced?: number
  wardsKilled?: number
  visionScore?: number
  killParticipation?: number
  damagePerMinute?: number
  teamDamagePercentage?: number
  damageDealtToChampions?: number
  damageToObjectives?: number
  turretPlatesTaken?: number
  durationSeconds?: number
  // Team objective counts, lifted out of the mock's nested `objectives` object
  // or read from the flat rich keys the API returns.
  dragons?: number
  barons?: number
  turrets?: number
}

export interface RawMatchInput {
  matchId: string
  championName?: string | null
  role?: string | null
  timestamp?: number | null
  win?: boolean | null
  parsed_metrics?: Record<string, unknown> | null
  objectives?: MatchObjectives | null
}

// Canonical metric -> candidate source keys, most preferred first. Top-level
// raw fields win over `parsed_metrics` (mock rows are flat, real rows are not).
export const MATCH_METRIC_ALIASES: Record<string, readonly string[]> = {
  kills: ['kills'],
  deaths: ['deaths'],
  assists: ['assists'],
  kda: ['kda'],
  cs_per_min: ['cs_per_min', 'csPerMinute', 'csPerMin', 'cspm'],
  // The rich challenge counts lane minions in the first 10 min; it is the
  // closest live substitute for the parser-era `csAt10`.
  csAt10: ['csAt10', 'cs_at_10', 'ch_laneMinionsFirst10Minutes', 'laneMinionsFirst10Minutes'],
  csAdvantageOnLaneOpponent: ['csAdvantageOnLaneOpponent', 'ch_maxCsAdvantageOnLaneOpponent'],
  goldPerMinute: ['goldPerMinute', 'ch_goldPerMinute', 'gold_per_minute', 'gpm'],
  goldEarned: ['goldEarned', 'gold_earned'],
  visionScorePerMinute: [
    'visionScorePerMinute',
    'ch_visionScorePerMinute',
    'vision_score_per_minute',
    'vspm',
  ],
  visionScore: ['visionScore'],
  controlWardsPlaced: ['controlWardsPlaced', 'ch_controlWardsPlaced', 'control_wards_placed'],
  wardsPlaced: ['wardsPlaced', 'wards_placed'],
  wardsKilled: ['wardsKilled', 'wards_killed'],
  killParticipation: ['killParticipation', 'ch_killParticipation', 'kill_participation'],
  damagePerMinute: ['damagePerMinute', 'ch_damagePerMinute', 'damage_per_minute', 'dpm'],
  teamDamagePercentage: ['teamDamagePercentage', 'ch_teamDamagePercentage'],
  damageDealtToChampions: ['damageDealtToChampions', 'totalDamageDealtToChampions'],
  damageToObjectives: ['damageToObjectives', 'damageDealtToObjectives'],
  turretPlatesTaken: ['turretPlatesTaken', 'ch_turretPlatesTaken'],
  durationSeconds: ['durationSeconds', 'gameDuration', 'gameDurationSeconds', 'game_duration', 'duration'],
  // Team objective counts. Prefer the team totals (a support rarely lands the
  // last hit on a dragon) and fall back to the participant-level kills.
  dragons: ['dragons', 'team_dragonKills', 'dragonKills'],
  barons: ['barons', 'team_baronKills', 'baronKills'],
  turrets: ['turrets', 'team_towerKills', 'turretKills'],
}

export function normalizeMatchRow(raw: RawMatchInput): MatchRow {
  const src = raw as unknown as Record<string, unknown>
  const pm = raw.parsed_metrics ?? {}
  const out: Record<string, unknown> = {
    matchId: raw.matchId,
    championName: raw.championName ?? '',
    role: raw.role ?? '',
    win:
      typeof raw.win === 'boolean'
        ? raw.win
        : typeof pm['win'] === 'boolean'
          ? pm['win']
          : null,
    timestamp: typeof raw.timestamp === 'number' ? raw.timestamp : null,
    parsed_metrics: pm,
  }
  if (raw.objectives) out['objectives'] = raw.objectives
  // Mock fixtures nest the objective counts under `objectives`; the API returns
  // them as flat rich keys. Accept both so views only read canonical fields.
  const nested = (raw.objectives ?? {}) as Record<string, unknown>
  for (const [canonical, candidates] of Object.entries(MATCH_METRIC_ALIASES)) {
    for (const key of candidates) {
      const v = src[key] ?? pm[key] ?? nested[key]
      if (typeof v === 'number' && Number.isFinite(v)) {
        out[canonical] = v
        break
      }
    }
  }
  return out as unknown as MatchRow
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

// Wins are not a raw metric: the backend reports a `win` rate. Prefer the
// comparison row (rate) scaled by games; fall back to an explicit `wins` count.
function resolveWins(
  metrics: Record<string, unknown>,
  games: number,
  rows: ComparisonRow[],
): number {
  const explicit = numMetric(metrics, ['wins'])
  if (explicit > 0) return Math.round(explicit)
  const winRow = rows.find((r) => r.metric === 'win')
  const rate = winRow ? winRow.player : numMetric(metrics, ['win'])
  if (rate > 0 && games > 0) return Math.round(rate * games)
  return 0
}

function mapOverview(
  puuid: string,
  state: QueryState<ReportData>,
  comparison: QueryState<ComparisonPayload>,
): QueryState<PlayerOverview> {
  if (state.phase !== 'success') return state
  const d = state.data
  if (!isFullReport(d)) return { phase: 'empty' }
  const rows = comparison.phase === 'success' ? comparison.data.rows : []
  return {
    phase: 'success',
    data: {
      puuid,
      riotid: d.player,
      role: d.role,
      champion: d.champion,
      championPool: [],
      gamesAnalyzed: d.games_analyzed,
      wins: resolveWins(d.metrics, d.games_analyzed, rows),
    },
  }
}

function mapMatchList(state: QueryState<ApiMatchRow[]>): QueryState<MatchRow[]> {
  if (state.phase !== 'success') return state
  // Mapping bypasses useApiQuery's isEmptyPayload, so re-apply it here.
  if (state.data.length === 0) return { phase: 'empty' }
  return { phase: 'success', data: state.data.map((row) => normalizeMatchRow(row)) }
}

// Real comparison rows already carry the baseline percentiles; fold them back
// into a ProBaseline.metrics map so the existing score/percentile helpers and
// the phase breakdown keep their `baseline.metrics[metric]` contract. Metrics
// missing quartiles are left out rather than fabricated.
function mapComparison(state: QueryState<ApiComparison>): QueryState<ComparisonPayload> {
  if (state.phase !== 'success') return state
  const { baseline, rows } = state.data
  // No baseline imported yet: explicit empty, never invented bars.
  if (baseline === null) return { phase: 'empty' }

  const metrics: Record<string, ProMetricStats> = {}
  const mapped: ComparisonRow[] = rows.map((r) => {
    if (typeof r.p25 === 'number' && typeof r.median === 'number' && typeof r.p75 === 'number') {
      metrics[r.metric] = { mean: r.pro, median: r.median, p25: r.p25, p75: r.p75 }
    }
    return {
      metric: r.metric,
      player: r.player,
      pro: r.pro,
      delta: r.delta,
      pct: r.pct ?? 0,
    }
  })

  const proBaseline: ProBaseline = {
    role: baseline.role ?? '',
    source: baseline.source ?? '',
    games: baseline.games ?? 0,
    metrics,
  }
  if (typeof baseline.season === 'number') proBaseline.season = baseline.season

  return { phase: 'success', data: { baseline: proBaseline, rows: mapped } }
}

const MOCK_MATCH_ROWS: MatchRow[] = mockMatches.map((m) =>
  normalizeMatchRow({
    ...m,
    timestamp: Date.parse(m.timestamp),
    // Keep the parser keys MatchCard reads for its stat row.
    parsed_metrics: {
      win: m.win,
      kda: m.kda,
      cs_per_min: m.cs_per_min,
      goldEarned: m.goldEarned,
      gameDuration: m.durationSeconds,
    },
  }),
)

export function usePlayerOverview(puuid: string): PlayerQuery<PlayerOverview> {
  // enabled=false in mock mode keeps the real fetchers from ever firing.
  const enabled = puuid !== '' && !MOCK_ENABLED
  const report = useApiQuery(() => getPlayerReport(puuid), [puuid], { enabled })
  // Composition: the report has identity/games; the comparison supplies the
  // win rate the header needs. Comparison failure never sinks the header.
  const comparison = useApiQuery(() => getPlayerComparison(puuid), [puuid], { enabled })
  if (MOCK_ENABLED && puuid !== '') {
    return { state: { phase: 'success', data: mockPlayer }, retry: report.retry }
  }
  return {
    state: mapOverview(puuid, report.state, mapComparison(comparison.state)),
    retry: report.retry,
  }
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
  const enabled = puuid !== '' && !MOCK_ENABLED
  const { state, retry } = useApiQuery(() => getPlayerComparison(puuid), [puuid], { enabled })
  if (MOCK_ENABLED && puuid !== '') {
    return {
      state: {
        phase: 'success',
        data: { baseline: mockProBaseline, rows: mockComparisonRows },
      },
      retry,
    }
  }
  return { state: mapComparison(state), retry }
}

// Per-minute curves for one match. Gated on a non-empty matchId so the panel
// stays inert until a row is selected; a 404 (timeline not captured) maps to
// `empty` through useApiQuery, never an error.
export function useMatchTimeline(puuid: string, matchId: string): PlayerQuery<MatchTimeline> {
  const enabled = puuid !== '' && matchId !== '' && !MOCK_ENABLED
  const { state, retry } = useApiQuery(
    () => getMatchTimeline(puuid, matchId),
    [puuid, matchId],
    { enabled },
  )
  if (MOCK_ENABLED && puuid !== '' && matchId !== '') {
    return { state: { phase: 'success', data: buildMockTimeline(matchId) }, retry }
  }
  return { state, retry }
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
