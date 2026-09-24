import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'
import {
  metricPositionPct,
  useComparison,
  useMatchList,
  useMatchTimeline,
  type MatchRow,
  type ProBaseline,
  type ProMetricStats,
} from '../lib/playerData'
import {
  MILESTONE_MINUTES,
  TIMELINE_METRIC_LABELS,
  valueAtMinute,
  type TimelineMetric,
} from '../lib/timeline'
import {
  METRICS_BY_PHASE,
  METRIC_LABELS,
  PHASE_LABELS,
  PHASE_ORDER,
  formatMetric,
  type MetricPhase,
} from '../lib/metrics'
import { errorCopy } from '../lib/errorCopy'
import { PanelSkeleton } from '../components/PanelSkeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { MatchCard } from '../components/player/MatchCard'
import { PlayerTabs } from '../components/player/PlayerTabs'

const HISTORY_ERROR_COPY = 'No se pudieron cargar las partidas.'
const NO_MATCHES_COPY = 'Sin partidas todavía.'
const NO_FILTER_MATCHES_COPY = 'No hay partidas que coincidan con los filtros.'
const EMPTY_BREAKDOWN_COPY = 'Seleccioná una partida para ver el desglose.'
const TIMELINE_EMPTY_COPY =
  'Las curvas de esta partida todavía no fueron capturadas. Ejecutá scripts/backfill_timelines.py para generarlas.'

const TIMELINE_METRICS: readonly TimelineMetric[] = ['gold', 'cs', 'xp', 'level']

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

// Objective counts are canonical flat MatchRow fields (the normalizer lifts
// them out of the mock's nested `objectives` object), with the nested object
// kept as a fallback. Missing/invalid → null (rendered without a bar/delta) —
// never fabricated.
function metricValue(match: MatchRow, key: string): number | null {
  const flat = (match as unknown as Record<string, unknown>)[key]
  const raw: unknown =
    typeof flat === 'number' && Number.isFinite(flat)
      ? flat
      : isObjectiveKey(key)
        ? match.objectives?.[key]
        : undefined
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

// --- Curvas: per-minute player vs lane-opponent curves ---------------------

function milestoneCell(value: number | null): string {
  return value === null ? '—' : String(value)
}

function diffCell(value: number | null): string {
  if (value === null) return '—'
  return `${value >= 0 ? '+' : ''}${value}`
}

function diffTone(value: number | null): string {
  if (value === null || value === 0) return 'text-slate-400'
  return value > 0 ? 'text-blue-400' : 'text-red-400'
}

function TimelinePanel({ puuid, matchId }: { puuid: string; matchId: string }) {
  const { state, retry } = useMatchTimeline(puuid, matchId)
  const [metric, setMetric] = useState<TimelineMetric>('gold')

  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') {
    return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  }
  if (state.phase === 'empty' || state.data.series.length === 0) {
    return (
      <section
        aria-label="Curvas"
        className="rounded border border-slate-800 bg-slate-900 p-4"
      >
        <h3 className="text-sm font-semibold text-slate-100">Curvas</h3>
        <p className="mt-3 text-sm text-slate-400">{TIMELINE_EMPTY_COPY}</p>
      </section>
    )
  }

  const data = state.data
  const label = TIMELINE_METRIC_LABELS[metric]
  const opponentByMinute = new Map(data.opponentSeries.map((p) => [p.minute, p]))
  const chartData = data.series.map((p) => ({
    minute: p.minute,
    player: p[metric],
    opponent: opponentByMinute.get(p.minute)?.[metric] ?? null,
  }))

  return (
    <section
      aria-label="Curvas"
      className="rounded border border-slate-800 bg-slate-900 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-100">Curvas</h3>
        <div role="group" aria-label="Métrica" className="flex gap-1">
          {TIMELINE_METRICS.map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={metric === m}
              onClick={() => setMetric(m)}
              className={`rounded border px-2 py-1 text-xs ${
                metric === m
                  ? 'border-amber-500 text-amber-500'
                  : 'border-slate-800 text-slate-400 hover:text-slate-100'
              }`}
            >
              {TIMELINE_METRIC_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      {/* ponytail: fixed chart size, no ResponsiveContainer — it needs
          ResizeObserver, which jsdom lacks (chart never renders in tests). */}
      <div
        role="img"
        aria-label={`Curva de ${label} por minuto`}
        className="mt-4 overflow-x-auto"
      >
        <LineChart width={800} height={256} data={chartData}>
          <XAxis dataKey="minute" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="player"
            name="Vos"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={false}
          />
          {data.opponent && (
            <Line
              type="monotone"
              dataKey="opponent"
              name={data.opponent.championName ?? 'Rival'}
              stroke="#60a5fa"
              strokeWidth={2}
              dot={false}
            />
          )}
        </LineChart>
      </div>

      <table className="mt-4 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400">
            <th className="py-2 pr-2 font-medium">Min</th>
            <th className="py-2 pr-2 text-right font-medium">{label}</th>
            <th className="py-2 text-right font-medium">Dif. oro</th>
          </tr>
        </thead>
        <tbody>
          {MILESTONE_MINUTES.map((minute) => {
            const value = valueAtMinute(data.series, minute, metric)
            const goldDiff = valueAtMinute(data.diff, minute, 'goldDiff')
            return (
              <tr key={minute} className="border-b border-slate-800/60">
                <th scope="row" className="py-2 pr-2 font-medium text-slate-400">
                  @{minute}
                </th>
                <td className="py-2 pr-2 text-right text-slate-100">
                  {milestoneCell(value)}
                </td>
                <td className={`py-2 text-right font-medium ${diffTone(goldDiff)}`}>
                  {diffCell(goldDiff)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
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
            <div className="flex flex-col gap-4">
              <PhaseBreakdown match={selected} baseline={baseline} />
              <TimelinePanel puuid={puuid} matchId={selected.matchId} />
            </div>
          ) : (
            <EmptyState message={EMPTY_BREAKDOWN_COPY} />
          )}
        </div>
      </div>
    </main>
  )
}
