import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  metricPositionPct,
  useComparison,
  useMatchList,
  type MatchRow,
  type ProBaseline,
  type ProMetricStats,
} from '../lib/playerData'
import {
  METRICS_BY_PHASE,
  METRIC_LABELS,
  PHASE_LABELS,
  PHASE_ORDER,
  formatMetric,
  type MetricPhase,
} from '../lib/metrics'
import { PanelSkeleton } from '../components/PanelSkeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { MatchCard } from '../components/player/MatchCard'
import { PlayerTabs } from '../components/player/PlayerTabs'

const HISTORY_ERROR_COPY = 'No se pudieron cargar las partidas.'
const NO_MATCHES_COPY = 'Sin partidas todavía.'
const NO_FILTER_MATCHES_COPY = 'No hay partidas que coincidan con los filtros.'
const EMPTY_BREAKDOWN_COPY = 'Seleccioná una partida para ver el desglose.'

type ResultFilter = 'all' | 'win' | 'loss'

const RESULT_FILTERS: ReadonlyArray<{ value: ResultFilter; label: string }> = [
  { value: 'all', label: 'Todas' },
  { value: 'win', label: 'Victorias' },
  { value: 'loss', label: 'Derrotas' },
]

const OBJECTIVE_KEYS = ['dragons', 'barons', 'turrets'] as const
type ObjectiveKey = (typeof OBJECTIVE_KEYS)[number]

function isObjectiveKey(key: string): key is ObjectiveKey {
  return (OBJECTIVE_KEYS as readonly string[]).includes(key)
}

// The three objective counts live under a nested object; every other metric is
// a flat MatchRow field. Missing/invalid → null (rendered without a bar/delta).
function metricValue(match: MatchRow, key: string): number | null {
  const raw: unknown = isObjectiveKey(key)
    ? match.objectives[key]
    : (match as unknown as Record<string, unknown>)[key]
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null
}

function signedPct(pct: number): string {
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
}

function deltaTone(pct: number): string {
  if (Math.abs(pct) < 0.5) return 'text-slate-400'
  return pct > 0 ? 'text-blue-400' : 'text-red-400'
}

function ValueBar({ pos, label }: { pos: number; label: string }) {
  return (
    <div
      role="img"
      aria-label={label}
      className="relative h-2 min-w-16 rounded bg-slate-800"
    >
      <span
        className="absolute top-0 h-2 w-1 -translate-x-1/2 rounded bg-amber-500"
        style={{ left: `${pos}%` }}
      />
    </div>
  )
}

// One metric row: label | your value | position bar | signed delta vs pro.
// When no pro stats exist the value stands alone (no invented baseline).
function MetricRow({
  metric,
  value,
  stats,
}: {
  metric: string
  value: number
  stats: ProMetricStats | undefined
}) {
  const label = METRIC_LABELS[metric] ?? metric
  const pct =
    stats && stats.median !== 0 ? ((value - stats.median) / stats.median) * 100 : null
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,4rem)_3.5rem] items-center gap-3 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="text-right font-medium text-slate-100">
        {formatMetric(metric, value)}
      </span>
      {stats ? (
        <ValueBar
          pos={metricPositionPct(value, stats)}
          label={`${label}: ${formatMetric(metric, value)}`}
        />
      ) : (
        <span />
      )}
      {pct === null ? (
        <span />
      ) : (
        <span className={`text-right font-medium ${deltaTone(pct)}`}>
          {signedPct(pct)}
        </span>
      )}
    </li>
  )
}

function PhaseSection({
  phase,
  match,
  baseline,
}: {
  phase: MetricPhase
  match: MatchRow
  baseline: ProBaseline | null
}) {
  return (
    <section
      aria-label={PHASE_LABELS[phase]}
      className="rounded border border-slate-800 bg-slate-900 p-4"
    >
      <h3 className="text-sm font-semibold text-slate-100">{PHASE_LABELS[phase]}</h3>
      <ul className="mt-3 flex flex-col gap-3">
        {METRICS_BY_PHASE[phase].map((metric) => {
          const value = metricValue(match, metric)
          if (value === null) return null
          return (
            <MetricRow
              key={metric}
              metric={metric}
              value={value}
              stats={baseline?.metrics[metric]}
            />
          )
        })}
      </ul>
    </section>
  )
}

function PhaseBreakdown({ match, baseline }: { match: MatchRow; baseline: ProBaseline | null }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-100">
          Desglose por fase · {match.matchId}
        </h2>
        <span className="text-sm text-slate-400">{match.championName}</span>
      </div>
      {PHASE_ORDER.map((phase) => (
        <PhaseSection key={phase} phase={phase} match={match} baseline={baseline} />
      ))}
    </div>
  )
}

export function PlayerMatchesView() {
  const { puuid = '' } = useParams()
  const matches = useMatchList(puuid)
  const comparison = useComparison(puuid)
  const [champion, setChampion] = useState('all')
  const [result, setResult] = useState<ResultFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  if (!puuid) return null

  const baseline =
    comparison.state.phase === 'success' ? comparison.state.data.baseline : null
  const all = matches.state.phase === 'success' ? matches.state.data : []
  const champions = [...new Set(all.map((m) => m.championName))]
  const visible = all.filter(
    (m) =>
      (champion === 'all' || m.championName === champion) &&
      (result === 'all' ||
        (result === 'win' ? m.win === true : m.win === false)),
  )
  const selected = selectedId ? (all.find((m) => m.matchId === selectedId) ?? null) : null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Partidas</h1>
      <PlayerTabs puuid={puuid} />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-4">
          {matches.state.phase === 'success' && (
            <div className="flex flex-wrap items-end gap-4 rounded border border-slate-800 bg-slate-900 p-4">
              <label className="flex items-center gap-2 text-sm text-slate-400">
                Campeón
                <select
                  aria-label="Campeón"
                  value={champion}
                  onChange={(e) => setChampion(e.target.value)}
                  className="rounded border border-slate-800 bg-slate-950 px-2 py-1 text-sm text-slate-100"
                >
                  <option value="all">Todos</option>
                  {champions.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>

              <div role="group" aria-label="Resultado" className="flex gap-1">
                {RESULT_FILTERS.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={result === value}
                    onClick={() => setResult(value)}
                    className={`rounded border px-3 py-1 text-sm ${
                      result === value
                        ? 'border-amber-500 text-amber-500'
                        : 'border-slate-800 text-slate-400 hover:text-slate-100'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {matches.state.phase === 'loading' && <PanelSkeleton />}
          {matches.state.phase === 'error' && (
            <ErrorState message={HISTORY_ERROR_COPY} onRetry={matches.retry} />
          )}
          {matches.state.phase === 'empty' && <EmptyState message={NO_MATCHES_COPY} />}
          {matches.state.phase === 'success' &&
            (visible.length === 0 ? (
              <EmptyState message={NO_FILTER_MATCHES_COPY} />
            ) : (
              <div className="flex flex-col gap-3">
                {visible.map((row) => (
                  <MatchCard
                    key={row.matchId}
                    row={row}
                    onViewDetails={(matchId) => setSelectedId(matchId)}
                  />
                ))}
              </div>
            ))}
        </div>

        <div className="min-w-0">
          {selected ? (
            <PhaseBreakdown match={selected} baseline={baseline} />
          ) : (
            <EmptyState message={EMPTY_BREAKDOWN_COPY} />
          )}
        </div>
      </div>
    </main>
  )
}
