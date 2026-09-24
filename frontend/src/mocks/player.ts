// Demo Support dataset. Used only when VITE_MOCK === 'true' (see ./index.ts)
// so the player UI can be polished before the real endpoints exist.
//
// The story is deliberate: strong vision / objectives, weak CS/min and damage,
// so "Fortalezas" and "A mejorar" both say something real.

export interface PlayerOverview {
  puuid: string
  riotid: string
  role: string | null
  champion: string | null
  championPool: string[]
  gamesAnalyzed: number
  wins: number
}

export interface MatchObjectives {
  dragons: number
  barons: number
  turrets: number
}

export interface MockMatch {
  matchId: string
  championName: string
  role: string
  win: boolean
  kills: number
  deaths: number
  assists: number
  kda: number
  cs_per_min: number
  visionScorePerMinute: number
  controlWardsPlaced: number
  wardsPlaced: number
  killParticipation: number
  damagePerMinute: number
  goldPerMinute: number
  goldEarned: number
  durationSeconds: number
  timestamp: string
  csAt10: number
  csAdvantageOnLaneOpponent: number
  turretPlatesTaken: number
  damageToObjectives: number
  teamDamagePercentage: number
  objectives: MatchObjectives
}

export interface ProMetricStats {
  mean: number
  median: number
  p25: number
  p75: number
}

export interface ProBaseline {
  role: string
  source: string
  // Optional: the real baseline doc only carries a season when one was stored.
  season?: number
  games: number
  metrics: Record<string, ProMetricStats>
}

export interface ComparisonRow {
  metric: string
  player: number
  pro: number
  delta: number
  pct: number
}

export interface ComparisonPayload {
  baseline: ProBaseline
  rows: ComparisonRow[]
}

export const mockPlayer: PlayerOverview = {
  puuid: 'demo-support-puuid',
  riotid: 'TR Terminator#1998',
  role: 'Support',
  champion: 'Thresh',
  championPool: ['Thresh', 'Leona', 'Nautilus', 'Rell'],
  gamesAnalyzed: 20,
  wins: 11,
}

// Seed fields that vary per game; kda, goldEarned, timestamp and objectives
// are derived below so the fixture stays internally consistent.
interface MatchSeed {
  id: string
  championName: string
  win: boolean
  kills: number
  deaths: number
  assists: number
  cs_per_min: number
  visionScorePerMinute: number
  controlWardsPlaced: number
  wardsPlaced: number
  killParticipation: number
  damagePerMinute: number
  goldPerMinute: number
  durationSeconds: number
  csAt10: number
  csAdvantageOnLaneOpponent: number
  turretPlatesTaken: number
  damageToObjectives: number
  teamDamagePercentage: number
  dragons: number
  barons: number
  turrets: number
}

// Newest first, mirroring the backend's `_id DESC` ordering. 11 wins / 9 losses.
const MATCH_SEEDS: MatchSeed[] = [
  { id: 'DEMO-020', championName: 'Thresh', win: true, kills: 2, deaths: 4, assists: 24, cs_per_min: 1.1, visionScorePerMinute: 3.4, controlWardsPlaced: 10, wardsPlaced: 28, killParticipation: 0.72, damagePerMinute: 280, goldPerMinute: 300, durationSeconds: 1740, csAt10: 12, csAdvantageOnLaneOpponent: 3, turretPlatesTaken: 2, damageToObjectives: 9000, teamDamagePercentage: 0.18, dragons: 3, barons: 1, turrets: 8 },
  { id: 'DEMO-019', championName: 'Thresh', win: true, kills: 1, deaths: 5, assists: 27, cs_per_min: 1.0, visionScorePerMinute: 3.6, controlWardsPlaced: 11, wardsPlaced: 31, killParticipation: 0.75, damagePerMinute: 260, goldPerMinute: 290, durationSeconds: 1860, csAt10: 11, csAdvantageOnLaneOpponent: 2, turretPlatesTaken: 3, damageToObjectives: 11000, teamDamagePercentage: 0.16, dragons: 4, barons: 1, turrets: 9 },
  { id: 'DEMO-018', championName: 'Leona', win: false, kills: 3, deaths: 8, assists: 15, cs_per_min: 0.9, visionScorePerMinute: 2.8, controlWardsPlaced: 7, wardsPlaced: 22, killParticipation: 0.64, damagePerMinute: 240, goldPerMinute: 250, durationSeconds: 1620, csAt10: 10, csAdvantageOnLaneOpponent: -1, turretPlatesTaken: 0, damageToObjectives: 6000, teamDamagePercentage: 0.15, dragons: 1, barons: 0, turrets: 3 },
  { id: 'DEMO-017', championName: 'Thresh', win: true, kills: 4, deaths: 3, assists: 21, cs_per_min: 1.2, visionScorePerMinute: 3.2, controlWardsPlaced: 9, wardsPlaced: 26, killParticipation: 0.7, damagePerMinute: 300, goldPerMinute: 310, durationSeconds: 1680, csAt10: 13, csAdvantageOnLaneOpponent: 4, turretPlatesTaken: 2, damageToObjectives: 9500, teamDamagePercentage: 0.19, dragons: 3, barons: 1, turrets: 7 },
  { id: 'DEMO-016', championName: 'Nautilus', win: false, kills: 2, deaths: 7, assists: 12, cs_per_min: 0.8, visionScorePerMinute: 2.6, controlWardsPlaced: 6, wardsPlaced: 20, killParticipation: 0.58, damagePerMinute: 210, goldPerMinute: 240, durationSeconds: 1500, csAt10: 9, csAdvantageOnLaneOpponent: -2, turretPlatesTaken: 0, damageToObjectives: 4500, teamDamagePercentage: 0.13, dragons: 1, barons: 0, turrets: 2 },
  { id: 'DEMO-015', championName: 'Thresh', win: true, kills: 1, deaths: 2, assists: 25, cs_per_min: 1.3, visionScorePerMinute: 3.8, controlWardsPlaced: 12, wardsPlaced: 33, killParticipation: 0.78, damagePerMinute: 270, goldPerMinute: 320, durationSeconds: 1920, csAt10: 14, csAdvantageOnLaneOpponent: 5, turretPlatesTaken: 3, damageToObjectives: 12000, teamDamagePercentage: 0.17, dragons: 4, barons: 2, turrets: 10 },
  { id: 'DEMO-014', championName: 'Rell', win: true, kills: 2, deaths: 4, assists: 23, cs_per_min: 1.0, visionScorePerMinute: 3.5, controlWardsPlaced: 10, wardsPlaced: 29, killParticipation: 0.73, damagePerMinute: 290, goldPerMinute: 305, durationSeconds: 1800, csAt10: 12, csAdvantageOnLaneOpponent: 3, turretPlatesTaken: 2, damageToObjectives: 10000, teamDamagePercentage: 0.18, dragons: 3, barons: 1, turrets: 8 },
  { id: 'DEMO-013', championName: 'Thresh', win: false, kills: 0, deaths: 6, assists: 14, cs_per_min: 0.9, visionScorePerMinute: 3.0, controlWardsPlaced: 8, wardsPlaced: 24, killParticipation: 0.6, damagePerMinute: 230, goldPerMinute: 255, durationSeconds: 1560, csAt10: 10, csAdvantageOnLaneOpponent: 0, turretPlatesTaken: 1, damageToObjectives: 5200, teamDamagePercentage: 0.14, dragons: 1, barons: 0, turrets: 3 },
  { id: 'DEMO-012', championName: 'Leona', win: true, kills: 3, deaths: 3, assists: 22, cs_per_min: 1.1, visionScorePerMinute: 3.3, controlWardsPlaced: 9, wardsPlaced: 27, killParticipation: 0.71, damagePerMinute: 275, goldPerMinute: 300, durationSeconds: 1700, csAt10: 12, csAdvantageOnLaneOpponent: 2, turretPlatesTaken: 2, damageToObjectives: 9000, teamDamagePercentage: 0.17, dragons: 3, barons: 1, turrets: 7 },
  { id: 'DEMO-011', championName: 'Thresh', win: false, kills: 1, deaths: 7, assists: 16, cs_per_min: 1.0, visionScorePerMinute: 2.9, controlWardsPlaced: 7, wardsPlaced: 23, killParticipation: 0.62, damagePerMinute: 245, goldPerMinute: 250, durationSeconds: 1600, csAt10: 11, csAdvantageOnLaneOpponent: 1, turretPlatesTaken: 0, damageToObjectives: 5800, teamDamagePercentage: 0.15, dragons: 2, barons: 0, turrets: 4 },
  { id: 'DEMO-010', championName: 'Nautilus', win: false, kills: 2, deaths: 9, assists: 10, cs_per_min: 0.7, visionScorePerMinute: 2.4, controlWardsPlaced: 5, wardsPlaced: 18, killParticipation: 0.52, damagePerMinute: 190, goldPerMinute: 225, durationSeconds: 1440, csAt10: 8, csAdvantageOnLaneOpponent: -3, turretPlatesTaken: 0, damageToObjectives: 4000, teamDamagePercentage: 0.12, dragons: 0, barons: 0, turrets: 2 },
  { id: 'DEMO-009', championName: 'Thresh', win: true, kills: 5, deaths: 4, assists: 20, cs_per_min: 1.2, visionScorePerMinute: 3.4, controlWardsPlaced: 10, wardsPlaced: 30, killParticipation: 0.74, damagePerMinute: 295, goldPerMinute: 315, durationSeconds: 1760, csAt10: 13, csAdvantageOnLaneOpponent: 4, turretPlatesTaken: 3, damageToObjectives: 10500, teamDamagePercentage: 0.18, dragons: 3, barons: 1, turrets: 9 },
  { id: 'DEMO-008', championName: 'Rell', win: true, kills: 2, deaths: 5, assists: 26, cs_per_min: 1.0, visionScorePerMinute: 3.7, controlWardsPlaced: 11, wardsPlaced: 32, killParticipation: 0.76, damagePerMinute: 265, goldPerMinute: 300, durationSeconds: 1880, csAt10: 12, csAdvantageOnLaneOpponent: 3, turretPlatesTaken: 2, damageToObjectives: 11000, teamDamagePercentage: 0.16, dragons: 4, barons: 1, turrets: 9 },
  { id: 'DEMO-007', championName: 'Leona', win: false, kills: 1, deaths: 6, assists: 13, cs_per_min: 0.9, visionScorePerMinute: 2.7, controlWardsPlaced: 6, wardsPlaced: 21, killParticipation: 0.59, damagePerMinute: 220, goldPerMinute: 245, durationSeconds: 1540, csAt10: 10, csAdvantageOnLaneOpponent: -1, turretPlatesTaken: 1, damageToObjectives: 5000, teamDamagePercentage: 0.14, dragons: 1, barons: 0, turrets: 3 },
  { id: 'DEMO-006', championName: 'Thresh', win: true, kills: 3, deaths: 2, assists: 24, cs_per_min: 1.3, visionScorePerMinute: 3.9, controlWardsPlaced: 13, wardsPlaced: 34, killParticipation: 0.79, damagePerMinute: 285, goldPerMinute: 325, durationSeconds: 1940, csAt10: 14, csAdvantageOnLaneOpponent: 6, turretPlatesTaken: 4, damageToObjectives: 12500, teamDamagePercentage: 0.17, dragons: 4, barons: 2, turrets: 11 },
  { id: 'DEMO-005', championName: 'Thresh', win: false, kills: 0, deaths: 5, assists: 15, cs_per_min: 1.1, visionScorePerMinute: 3.1, controlWardsPlaced: 8, wardsPlaced: 25, killParticipation: 0.63, damagePerMinute: 250, goldPerMinute: 260, durationSeconds: 1580, csAt10: 11, csAdvantageOnLaneOpponent: 0, turretPlatesTaken: 1, damageToObjectives: 6000, teamDamagePercentage: 0.15, dragons: 2, barons: 0, turrets: 4 },
  { id: 'DEMO-004', championName: 'Thresh', win: true, kills: 2, deaths: 3, assists: 23, cs_per_min: 1.0, visionScorePerMinute: 3.5, controlWardsPlaced: 10, wardsPlaced: 28, killParticipation: 0.72, damagePerMinute: 280, goldPerMinute: 305, durationSeconds: 1740, csAt10: 12, csAdvantageOnLaneOpponent: 3, turretPlatesTaken: 2, damageToObjectives: 9800, teamDamagePercentage: 0.18, dragons: 3, barons: 1, turrets: 8 },
  { id: 'DEMO-003', championName: 'Leona', win: true, kills: 4, deaths: 4, assists: 21, cs_per_min: 1.1, visionScorePerMinute: 3.3, controlWardsPlaced: 9, wardsPlaced: 27, killParticipation: 0.7, damagePerMinute: 270, goldPerMinute: 300, durationSeconds: 1720, csAt10: 12, csAdvantageOnLaneOpponent: 2, turretPlatesTaken: 2, damageToObjectives: 9200, teamDamagePercentage: 0.17, dragons: 3, barons: 1, turrets: 7 },
  { id: 'DEMO-002', championName: 'Thresh', win: false, kills: 1, deaths: 8, assists: 14, cs_per_min: 0.9, visionScorePerMinute: 2.8, controlWardsPlaced: 7, wardsPlaced: 22, killParticipation: 0.61, damagePerMinute: 235, goldPerMinute: 250, durationSeconds: 1520, csAt10: 10, csAdvantageOnLaneOpponent: -1, turretPlatesTaken: 0, damageToObjectives: 4800, teamDamagePercentage: 0.14, dragons: 1, barons: 0, turrets: 3 },
  { id: 'DEMO-001', championName: 'Thresh', win: false, kills: 0, deaths: 6, assists: 12, cs_per_min: 1.0, visionScorePerMinute: 2.9, controlWardsPlaced: 6, wardsPlaced: 20, killParticipation: 0.57, damagePerMinute: 225, goldPerMinute: 245, durationSeconds: 1500, csAt10: 9, csAdvantageOnLaneOpponent: -2, turretPlatesTaken: 0, damageToObjectives: 4200, teamDamagePercentage: 0.13, dragons: 1, barons: 0, turrets: 2 },
]

const FIRST_MATCH_MS = Date.parse('2025-06-01T20:00:00Z')
const DAY_MS = 86_400_000

export const mockMatches: MockMatch[] = MATCH_SEEDS.map((s, i) => ({
  matchId: s.id,
  championName: s.championName,
  role: 'Support',
  win: s.win,
  kills: s.kills,
  deaths: s.deaths,
  assists: s.assists,
  kda: Number(((s.kills + s.assists) / Math.max(1, s.deaths)).toFixed(2)),
  cs_per_min: s.cs_per_min,
  visionScorePerMinute: s.visionScorePerMinute,
  controlWardsPlaced: s.controlWardsPlaced,
  wardsPlaced: s.wardsPlaced,
  killParticipation: s.killParticipation,
  damagePerMinute: s.damagePerMinute,
  goldPerMinute: s.goldPerMinute,
  goldEarned: Math.round((s.goldPerMinute * s.durationSeconds) / 60),
  durationSeconds: s.durationSeconds,
  timestamp: new Date(FIRST_MATCH_MS - i * DAY_MS).toISOString(),
  csAt10: s.csAt10,
  csAdvantageOnLaneOpponent: s.csAdvantageOnLaneOpponent,
  turretPlatesTaken: s.turretPlatesTaken,
  damageToObjectives: s.damageToObjectives,
  teamDamagePercentage: s.teamDamagePercentage,
  objectives: { dragons: s.dragons, barons: s.barons, turrets: s.turrets },
}))

// Support baseline (Oracle's Elixir 2025). Numbers are plausible aggregates,
// not scraped data — they only need to make the comparison story land.
export const mockProBaseline: ProBaseline = {
  role: 'Support',
  source: "Oracle's Elixir",
  season: 2025,
  games: 4820,
  metrics: {
    cs_per_min: { mean: 1.5, median: 1.4, p25: 1.1, p75: 1.8 },
    visionScorePerMinute: { mean: 2.5, median: 2.4, p25: 1.9, p75: 3.0 },
    controlWardsPlaced: { mean: 5.5, median: 5, p25: 3, p75: 8 },
    wardsPlaced: { mean: 18, median: 17, p25: 13, p75: 22 },
    killParticipation: { mean: 0.62, median: 0.62, p25: 0.54, p75: 0.7 },
    damagePerMinute: { mean: 380, median: 360, p25: 280, p75: 460 },
    goldPerMinute: { mean: 300, median: 295, p25: 260, p75: 335 },
    kda: { mean: 3.0, median: 2.8, p25: 2.1, p75: 3.7 },
    win: { mean: 0.5, median: 0.5, p25: 0.5, p75: 0.5 },
  },
}

type AvgMetricKey =
  | 'cs_per_min'
  | 'visionScorePerMinute'
  | 'controlWardsPlaced'
  | 'wardsPlaced'
  | 'killParticipation'
  | 'damagePerMinute'
  | 'goldPerMinute'
  | 'kda'

const AVG_METRIC_KEYS: AvgMetricKey[] = [
  'cs_per_min',
  'visionScorePerMinute',
  'controlWardsPlaced',
  'wardsPlaced',
  'killParticipation',
  'damagePerMinute',
  'goldPerMinute',
  'kda',
]

// Per-game averages for the metrics the baseline covers; `win` is the winrate.
export function playerMetricAverages(matches: MockMatch[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const key of AVG_METRIC_KEYS) {
    const total = matches.reduce((sum, m) => sum + m[key], 0)
    out[key] = matches.length === 0 ? 0 : total / matches.length
  }
  out['win'] = matches.length === 0 ? 0 : matches.filter((m) => m.win).length / matches.length
  return out
}

// Same shape pro_baseline.comparison_rows produces, derived from the inputs so
// the fixture can never drift from mockMatches / mockProBaseline.
export function buildComparisonRows(
  playerMetrics: Record<string, number>,
  proMetrics: Record<string, ProMetricStats>,
): ComparisonRow[] {
  return Object.keys(proMetrics)
    .filter((metric) => typeof playerMetrics[metric] === 'number')
    .map((metric) => {
      const player = playerMetrics[metric] as number
      const pro = (proMetrics[metric] as ProMetricStats).median
      const delta = player - pro
      const pct = pro === 0 ? 0 : (delta / pro) * 100
      return { metric, player, pro, delta, pct }
    })
    .sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))
}

export const mockPlayerMetrics = playerMetricAverages(mockMatches)
export const mockComparisonRows = buildComparisonRows(
  mockPlayerMetrics,
  mockProBaseline.metrics,
)
