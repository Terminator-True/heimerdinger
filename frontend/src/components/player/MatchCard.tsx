// Match history row card + pure derivations shared by the dashboard.
import { fmtValue } from '../../lib/format'

export interface MatchRow {
  matchId: string
  championName?: string
  role?: string
  timestamp?: number | null
  // Schema passthrough extra: boolean when present, null = unknown.
  win?: boolean | null
  parsed_metrics: Record<string, unknown>
}

// Win flag lives top-level on newer rows and inside parsed_metrics on older
// ones; absent in both → null (neutral border, never guessed).
export function deriveWin(row: MatchRow): boolean | null {
  if (typeof row.win === 'boolean') return row.win
  if (typeof row.parsed_metrics?.win === 'boolean') {
    return row.parsed_metrics.win
  }
  return null
}

// Durations arrive as seconds; format m:ss. Invalid/missing → em-dash.
export function fmtDuration(seconds: unknown): string {
  const n = typeof seconds === 'number' ? seconds : Number(seconds)
  if (!Number.isFinite(n) || n <= 0) return '—'
  let m = Math.floor(n / 60)
  let s = Math.round(n % 60)
  if (s === 60) {
    m += 1
    s = 0
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

// First present metric among alias keys — parsed_metrics keys vary by
// backend parse version.
function pickMetric(metrics: Record<string, unknown>, keys: string[]): unknown {
  for (const k of keys) {
    const v = metrics[k]
    if (v !== undefined && v !== null) return v
  }
  return undefined
}

interface StatProps {
  label: string
  value: string
}

function Stat({ label, value }: StatProps) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="text-sm font-medium text-slate-100">{value}</dd>
    </div>
  )
}

interface MatchCardProps {
  row: MatchRow
  onViewDetails: (matchId: string) => void
}

export function MatchCard({ row, onViewDetails }: MatchCardProps) {
  const win = deriveWin(row)
  const borderClass =
    win === true
      ? 'border-blue-400'
      : win === false
        ? 'border-red-400'
        : 'border-slate-800'
  const m = row.parsed_metrics ?? {}

  return (
    <article
      aria-label={row.matchId}
      className={`rounded border ${borderClass} bg-slate-900 p-4`}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">
          {row.championName ?? '—'}
        </h3>
        {row.role && <span className="text-xs text-slate-400">{row.role}</span>}
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
        <Stat label="KDA" value={fmtValue(pickMetric(m, ['kda']))} />
        <Stat label="CS/min" value={fmtValue(pickMetric(m, ['cs_per_min', 'csPerMin']))} />
        <Stat label="Oro" value={fmtValue(pickMetric(m, ['goldEarned', 'gold_earned']))} />
        <Stat
          label="Duración"
          value={fmtDuration(pickMetric(m, ['gameDuration', 'game_duration', 'duration']))}
        />
      </dl>
      <button
        type="button"
        onClick={() => onViewDetails(row.matchId)}
        className="mt-3 rounded border border-slate-800 px-3 py-1 text-xs text-amber-500 hover:bg-slate-800"
      >
        Ver detalles
      </button>
    </article>
  )
}
