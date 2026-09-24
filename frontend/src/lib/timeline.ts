// Per-minute timeline contract shared by the API schema output, the mock
// generator and the Partidas "Curvas" panel. Mirrors the backend
// modules/data/timeline.py::build_player_timeline payload field-for-field.

export interface TimelinePoint {
  minute: number
  gold: number
  cs: number
  xp: number
  level: number
}

export interface TimelineOpponent {
  puuid: string | null
  championName: string | null
}

export interface TimelineDiffPoint {
  minute: number
  goldDiff: number
  csDiff: number
}

export interface TimelineMilestones {
  goldAt10: number | null
  csAt10: number | null
  goldDiffAt10: number | null
  goldAt15: number | null
  csAt15: number | null
  goldDiffAt15: number | null
  goldAt20: number | null
  csAt20: number | null
  goldDiffAt20: number | null
}

export interface MatchTimeline {
  matchId: string
  puuid: string
  frameIntervalMs: number
  series: TimelinePoint[]
  // Empty/None when no lane opponent could be identified.
  opponent: TimelineOpponent | null
  opponentSeries: TimelinePoint[]
  diff: TimelineDiffPoint[]
  milestones: TimelineMilestones
}

// The @10/@15/@20 minutes the backend reports milestones for.
export const MILESTONE_MINUTES = [10, 15, 20] as const

// The fields a curve can plot.
export type TimelineMetric = 'gold' | 'cs' | 'xp' | 'level'

export const TIMELINE_METRIC_LABELS: Record<TimelineMetric, string> = {
  gold: 'Oro',
  cs: 'CS',
  xp: 'XP',
  level: 'Nivel',
}

// Value at the last point at/before `target`; null when the series never
// reached the minute. Mirrors timeline.py::_milestone_value so the view and
// the mock milestones derive identical numbers — a short game renders "—",
// never a fabricated value.
export function valueAtMinute<T extends { minute: number }>(
  series: readonly T[],
  target: number,
  key: keyof T,
): number | null {
  if (series.length === 0) return null
  let maxMinute = -Infinity
  for (const point of series) {
    if (point.minute > maxMinute) maxMinute = point.minute
  }
  if (maxMinute < target) return null

  let best: T | undefined
  for (const point of series) {
    if (point.minute > target) continue
    if (!best || point.minute > best.minute) best = point
  }
  if (!best) return null
  const value = best[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
