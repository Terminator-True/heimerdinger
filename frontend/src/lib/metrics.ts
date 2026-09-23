// Single source of truth for metric display metadata shared by the Partidas
// phase breakdown and the Comparativa table. Phase keys are the stable
// identifiers; labels are the Spanish copy shown in the UI.

export type MetricPhase = 'laning' | 'economy' | 'vision' | 'combat' | 'objectives'

// Display order of the five phases, used by both views for grouping/chips.
export const PHASE_ORDER: readonly MetricPhase[] = [
  'laning',
  'economy',
  'vision',
  'combat',
  'objectives',
]

export const PHASE_LABELS: Record<MetricPhase, string> = {
  laning: 'Laning',
  economy: 'Economía',
  vision: 'Visión',
  combat: 'Combate',
  objectives: 'Objetivos',
}

// Metrics owned by each phase, in display order.
export const METRICS_BY_PHASE: Record<MetricPhase, readonly string[]> = {
  laning: ['cs_per_min', 'csAt10', 'csAdvantageOnLaneOpponent'],
  economy: ['goldPerMinute', 'goldEarned'],
  vision: ['visionScorePerMinute', 'controlWardsPlaced', 'wardsPlaced'],
  combat: ['killParticipation', 'damagePerMinute', 'teamDamagePercentage', 'kda'],
  // dragons/barons/turrets come from the nested `objectives` object, not a
  // top-level field, but they are grouped here so chips/labels stay uniform.
  objectives: ['turretPlatesTaken', 'damageToObjectives', 'dragons', 'barons', 'turrets'],
}

// Reverse index: metric key -> phase. Derived so it can never drift from
// METRICS_BY_PHASE.
export const METRIC_PHASES: Record<string, MetricPhase> = Object.fromEntries(
  PHASE_ORDER.flatMap((phase) =>
    METRICS_BY_PHASE[phase].map((metric) => [metric, phase] as const),
  ),
)

export const METRIC_LABELS: Record<string, string> = {
  cs_per_min: 'CS/min',
  csAt10: 'CS a 10 min',
  csAdvantageOnLaneOpponent: 'Ventaja CS en línea',
  goldPerMinute: 'Oro/min',
  goldEarned: 'Oro ganado',
  visionScorePerMinute: 'Visión/min',
  controlWardsPlaced: 'Control wards',
  wardsPlaced: 'Wards',
  killParticipation: 'KP',
  damagePerMinute: 'Daño/min',
  teamDamagePercentage: '% daño del equipo',
  kda: 'KDA',
  turretPlatesTaken: 'Placas de torre',
  damageToObjectives: 'Daño a objetivos',
  dragons: 'Dragones',
  barons: 'Barones',
  turrets: 'Torres',
  win: 'Winrate',
}

const PCT_METRICS = new Set(['killParticipation', 'teamDamagePercentage', 'win'])
const PER_MINUTE_METRICS = new Set([
  'cs_per_min',
  'visionScorePerMinute',
  'goldPerMinute',
  'damagePerMinute',
])

// Value formatting by metric shape: rates show one decimal, ratios render as
// percentages, everything else (counts, gold) rounds to an integer.
export function formatMetric(key: string, value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (PCT_METRICS.has(key)) return `${Math.round(value * 100)}%`
  if (PER_MINUTE_METRICS.has(key)) return value.toFixed(1)
  return String(Math.round(value))
}
