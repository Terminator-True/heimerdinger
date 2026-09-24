import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  metricPositionPct,
  useComparison,
  type ComparisonPayload,
  type ComparisonRow,
  type ProMetricStats,
} from '../lib/playerData'
import { errorCopy } from '../lib/errorCopy'
import {
  METRIC_LABELS,
  METRIC_PHASES,
  PHASE_LABELS,
  PHASE_ORDER,
  formatMetric,
  type MetricPhase,
} from '../lib/metrics'
import { PanelSkeleton } from '../components/PanelSkeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { PlayerTabs } from '../components/player/PlayerTabs'

const COMPARISON_EMPTY = 'Comparativa no disponible todavía.'

type PhaseFilter = 'all' | MetricPhase
type SortDir = 'asc' | 'desc'

function chipClass(active: boolean): string {
  return `rounded border px-3 py-1 text-sm ${
    active
      ? 'border-amber-500 text-amber-500'
      : 'border-slate-800 text-slate-400 hover:text-slate-100'
  }`
}

function signedPct(pct: number): string {
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
}

// Deterministic thousands separator: es-ES sets minimumGroupingDigits=2, so
// 4820 would render ungrouped. The baseline label expects 4.820.
function formatThousands(n: number): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

function PercentileBar({
  value,
  stats,
  label,
}: {
  value: number
  stats: ProMetricStats
  label: string
}) {
  return (
    <div
      role="img"
      aria-label={label}
      className="relative h-2 w-24 rounded bg-slate-800"
    >
      <span
        className="absolute top-0 h-2 w-1 -translate-x-1/2 rounded bg-amber-500"
        style={{ left: `${metricPositionPct(value, stats)}%` }}
      />
    </div>
  )
}

function CompareTable({
  payload,
  phase,
  onPhase,
  negOnly,
  onToggleNegOnly,
  sortDir,
  onToggleSort,
}: {
  payload: ComparisonPayload
  phase: PhaseFilter
  onPhase: (phase: PhaseFilter) => void
  negOnly: boolean
  onToggleNegOnly: () => void
  sortDir: SortDir
  onToggleSort: () => void
}) {
  const { baseline, rows } = payload

  const filtered = rows.filter(
    (r) =>
      (phase === 'all' || METRIC_PHASES[r.metric] === phase) &&
      (!negOnly || r.pct < 0),
  )
  const sorted: ComparisonRow[] = [...filtered].sort((a, b) =>
    sortDir === 'desc'
      ? Math.abs(b.pct) - Math.abs(a.pct)
      : Math.abs(a.pct) - Math.abs(b.pct),
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Fase" className="flex flex-wrap gap-1">
          <button
            type="button"
            aria-pressed={phase === 'all'}
            onClick={() => onPhase('all')}
            className={chipClass(phase === 'all')}
          >
            Todas
          </button>
          {PHASE_ORDER.map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={phase === p}
              onClick={() => onPhase(p)}
              className={chipClass(phase === p)}
            >
              {PHASE_LABELS[p]}
            </button>
          ))}
        </div>
        <button
          type="button"
          aria-pressed={negOnly}
          onClick={onToggleNegOnly}
          className={chipClass(negOnly)}
        >
          Solo brechas negativas
        </button>
      </div>

      <div className="overflow-x-auto rounded border border-slate-800 bg-slate-900 p-6">
        <table className="w-full text-left text-sm">
          <caption className="mb-3 text-left text-sm text-slate-400">
            Baseline: {baseline.source} — {baseline.role}
            {baseline.season !== undefined ? `, ${baseline.season}` : ''} ·{' '}
            {formatThousands(baseline.games)} partidas
          </caption>
          <thead>
            <tr className="border-b border-slate-800 text-slate-400">
              <th scope="col" className="py-2 pr-2 font-medium">
                Métrica
              </th>
              <th scope="col" className="py-2 pr-2 text-right font-medium">
                Tú
              </th>
              <th scope="col" className="py-2 pr-2 text-right font-medium">
                Mediana pro
              </th>
              <th scope="col" className="py-2 pr-2 text-right font-medium">
                p25
              </th>
              <th scope="col" className="py-2 pr-2 text-right font-medium">
                p75
              </th>
              <th
                scope="col"
                aria-sort={sortDir === 'desc' ? 'descending' : 'ascending'}
                className="py-2 pr-2 text-right font-medium"
              >
                <button
                  type="button"
                  onClick={onToggleSort}
                  className="hover:text-slate-100"
                >
                  Delta{' '}
                  <span aria-hidden="true">{sortDir === 'desc' ? '▼' : '▲'}</span>
                </button>
              </th>
              <th scope="col" className="py-2 font-medium">
                Percentil
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td colSpan={7} className="py-3 text-slate-400">
                  Sin métricas para este filtro.
                </td>
              </tr>
            )}
            {sorted.map((r) => {
              const stats = baseline.metrics[r.metric]
              const label = METRIC_LABELS[r.metric] ?? r.metric
              const positive = r.pct >= 0
              return (
                <tr
                  key={r.metric}
                  className={positive ? 'bg-blue-400/5' : 'bg-red-400/5'}
                >
                  <th scope="row" className="py-2 pr-2 font-medium text-slate-100">
                    {label}
                  </th>
                  <td className="py-2 pr-2 text-right">
                    {formatMetric(r.metric, r.player)}
                  </td>
                  <td className="py-2 pr-2 text-right text-slate-300">
                    {formatMetric(r.metric, r.pro)}
                  </td>
                  <td className="py-2 pr-2 text-right text-slate-300">
                    {stats ? formatMetric(r.metric, stats.p25) : '—'}
                  </td>
                  <td className="py-2 pr-2 text-right text-slate-300">
                    {stats ? formatMetric(r.metric, stats.p75) : '—'}
                  </td>
                  <td
                    className={`py-2 pr-2 text-right font-medium ${
                      positive ? 'text-blue-400' : 'text-red-400'
                    }`}
                  >
                    {signedPct(r.pct)}
                  </td>
                  <td className="py-2">
                    {stats && (
                      <PercentileBar
                        value={r.player}
                        stats={stats}
                        label={`${label}: ${formatMetric(r.metric, r.player)}`}
                      />
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function PlayerCompareView() {
  const { puuid = '' } = useParams()
  const { state, retry } = useComparison(puuid)
  const [phase, setPhase] = useState<PhaseFilter>('all')
  const [negOnly, setNegOnly] = useState(false)
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  if (!puuid) return null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Comparativa</h1>
      <PlayerTabs puuid={puuid} />

      {state.phase === 'loading' && <PanelSkeleton />}
      {state.phase === 'error' && (
        <ErrorState message={errorCopy(state.error)} onRetry={retry} />
      )}
      {state.phase === 'empty' && <EmptyState message={COMPARISON_EMPTY} />}
      {state.phase === 'success' && (
        <CompareTable
          payload={state.data}
          phase={phase}
          onPhase={setPhase}
          negOnly={negOnly}
          onToggleNegOnly={() => setNegOnly((v) => !v)}
          sortDir={sortDir}
          onToggleSort={() => setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))}
        />
      )}
    </main>
  )
}
