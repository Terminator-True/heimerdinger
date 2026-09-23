import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'
import {
  averagePct,
  metricPositionPct,
  overallScore,
  SCORE_METRICS,
  useComparison,
  useMatchList,
  usePlayerOverview,
  type ComparisonPayload,
  type ComparisonRow,
  type MatchRow,
  type PlayerOverview,
  type PlayerQuery,
  type ProBaseline,
} from '../lib/playerData'
import type { QueryState } from '../hooks/useApiQuery'
import { errorCopy } from '../lib/errorCopy'
import { Skeleton } from '../components/Skeleton'
import { PanelSkeleton } from '../components/PanelSkeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { MatchCard } from '../components/player/MatchCard'
import { MatchDetailModal } from '../components/player/MatchDetailModal'
import { PlayerTabs } from '../components/player/PlayerTabs'

const COMPARISON_EMPTY = 'Comparativa no disponible todavía.'
const HISTORY_ERROR_COPY = 'No se pudieron cargar las partidas.'

// Display metadata for the six key Support metrics.
const METRIC_LABELS: Record<string, string> = {
  cs_per_min: 'CS/min',
  visionScorePerMinute: 'Visión/min',
  controlWardsPlaced: 'Control wards',
  wardsPlaced: 'Wards',
  killParticipation: 'KP',
  damagePerMinute: 'Daño/min',
  goldPerMinute: 'Oro/min',
  kda: 'KDA',
  win: 'Winrate',
}

function fmtMetric(metric: string, value: number): string {
  if (metric === 'killParticipation' || metric === 'win') {
    return `${Math.round(value * 100)}%`
  }
  if (metric === 'damagePerMinute' || metric === 'goldPerMinute') {
    return String(Math.round(value))
  }
  return value.toFixed(2)
}

function signedPct(pct: number): string {
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
}

// --- Header: player identity ---

function OverviewHeader({
  state,
  retry,
}: {
  state: QueryState<PlayerOverview>
  retry: () => void
}) {
  if (state.phase === 'loading') {
    return (
      <div
        aria-label="Cargando"
        className="flex flex-col gap-2 rounded border border-slate-800 bg-slate-900 p-6"
      >
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    )
  }
  if (state.phase === 'error') {
    return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  }
  if (state.phase === 'empty') {
    return <EmptyState message="Sin datos todavía. Ingresa partidas primero." />
  }

  const o = state.data
  return (
    <header className="rounded border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold text-slate-100">{o.riotid}</h2>
        <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-500">
          {o.role ?? '—'}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-400">
        Campeón principal:{' '}
        <span className="text-slate-100">{o.champion ?? '—'}</span>
        {' · '}
        {o.gamesAnalyzed} partidas · {o.wins} ganadas
      </p>
      {o.championPool.length > 0 && (
        <ul aria-label="Pool de campeones" className="mt-3 flex flex-wrap gap-2">
          {o.championPool.map((c) => (
            <li
              key={c}
              className={`rounded border px-2 py-0.5 text-xs ${
                c === o.champion
                  ? 'border-amber-500 text-amber-500'
                  : 'border-slate-800 text-slate-400'
              }`}
            >
              {c}
            </li>
          ))}
        </ul>
      )}
    </header>
  )
}

// --- Score card ---

function ScoreCard({
  comparison,
  gamesAnalyzed,
}: {
  comparison: PlayerQuery<ComparisonPayload>
  gamesAnalyzed: number | null
}) {
  const { state, retry } = comparison
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') {
    return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  }
  if (state.phase === 'empty') return <EmptyState message={COMPARISON_EMPTY} />

  const { baseline, rows } = state.data
  const score = overallScore(rows, baseline)
  const avg = averagePct(rows)

  return (
    <section aria-label="Puntaje" className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Puntaje</h2>
      <div className="mt-2 flex items-baseline gap-3">
        <span className="text-5xl font-bold text-amber-500">{score}</span>
        <span
          className={`rounded px-2 py-0.5 text-xs font-medium ${
            avg >= 0 ? 'bg-blue-400/15 text-blue-400' : 'bg-red-400/15 text-red-400'
          }`}
        >
          {signedPct(avg)} vs pro
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-400">
        Basado en {gamesAnalyzed ?? 0} partidas
      </p>
    </section>
  )
}

// --- Percentile card ---

function PercentileCard({ comparison }: { comparison: PlayerQuery<ComparisonPayload> }) {
  const { state, retry } = comparison
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') {
    return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  }
  if (state.phase === 'empty') return <EmptyState message={COMPARISON_EMPTY} />

  const { baseline, rows } = state.data
  return (
    <section
      aria-label="Percentiles"
      className="rounded border border-slate-800 bg-slate-900 p-6"
    >
      <h2 className="text-lg font-semibold text-slate-100">Percentiles vs pro</h2>
      <ul className="mt-4 flex flex-col gap-4">
        {SCORE_METRICS.map((metric) => {
          const row = rows.find((r) => r.metric === metric)
          const stats = baseline.metrics[metric]
          if (!row || !stats) return null
          const label = METRIC_LABELS[metric] ?? metric
          const pos = metricPositionPct(row.player, stats)
          return (
            <li key={metric}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">{label}</span>
                <span className="font-medium text-slate-100">
                  {fmtMetric(metric, row.player)}
                </span>
              </div>
              <div
                role="img"
                aria-label={`${label}: ${fmtMetric(metric, row.player)} (mediana pro ${fmtMetric(metric, stats.median)})`}
                className="relative mt-1 h-2 rounded bg-slate-800"
              >
                <span className="absolute left-1/2 top-0 h-2 w-px -translate-x-1/2 bg-slate-500" />
                <span
                  className="absolute top-0 h-2 w-1 -translate-x-1/2 rounded bg-amber-500"
                  style={{ left: `${pos}%` }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// --- Fortalezas / A mejorar ---

function MetricColumn({
  title,
  rows,
  tone,
}: {
  title: string
  rows: ComparisonRow[]
  tone: 'win' | 'loss'
}) {
  const pctClass = tone === 'win' ? 'text-blue-400' : 'text-red-400'
  return (
    <section aria-label={title} className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      <ul className="mt-4 flex flex-col gap-3">
        {rows.map((row) => (
          <li key={row.metric} className="flex items-center justify-between gap-4 text-sm">
            <span className="text-slate-400">{METRIC_LABELS[row.metric] ?? row.metric}</span>
            <span className="text-right">
              <span className="text-slate-100">
                {fmtMetric(row.metric, row.player)} vs {fmtMetric(row.metric, row.pro)}
              </span>
              <span className={`ml-2 font-medium ${pctClass}`}>{signedPct(row.pct)}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function StrengthsCard({ comparison }: { comparison: PlayerQuery<ComparisonPayload> }) {
  const { state, retry } = comparison
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') {
    return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  }
  if (state.phase === 'empty') return <EmptyState message={COMPARISON_EMPTY} />

  const sorted = [...state.data.rows].sort((a, b) => b.pct - a.pct)
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <MetricColumn title="Fortalezas" rows={sorted.slice(0, 3)} tone="win" />
      <MetricColumn title="A mejorar" rows={sorted.slice(-3).reverse()} tone="loss" />
    </div>
  )
}

// --- Tendencia ---

const TREND_METRICS = SCORE_METRICS
type TrendMetric = (typeof SCORE_METRICS)[number]

function TrendChart({
  matches,
  comparison,
  metric,
}: {
  matches: MatchRow[]
  comparison: QueryState<ComparisonPayload>
  metric: TrendMetric
}) {
  const data = [...matches]
    .sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0))
    .map((m, i) => ({ label: m.matchId, value: m[metric], index: i }))

  const baseline: ProBaseline | null =
    comparison.phase === 'success' ? comparison.data.baseline : null
  const median = baseline?.metrics[metric]?.median

  return (
    <div className="mt-4">
      {median !== undefined && (
        <p className="text-xs text-slate-400">
          Mediana pro: {fmtMetric(metric, median)}
        </p>
      )}
      {/* ponytail: fixed chart size, no ResponsiveContainer — it needs
          ResizeObserver, which jsdom lacks (chart never renders in tests). */}
      <div className="mt-2 overflow-x-auto">
        <LineChart width={800} height={256} data={data}>
          <XAxis dataKey="label" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <Tooltip />
          {median !== undefined && (
            <ReferenceLine y={median} stroke="#94a3b8" strokeDasharray="4 4" />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </div>
    </div>
  )
}

function TrendCard({
  matches,
  comparison,
  metric,
  onMetricChange,
}: {
  matches: PlayerQuery<MatchRow[]>
  comparison: PlayerQuery<ComparisonPayload>
  metric: TrendMetric
  onMetricChange: (metric: TrendMetric) => void
}) {
  const { state, retry } = matches
  return (
    <section aria-label="Tendencia" className="rounded border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-100">Tendencia</h2>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          Métrica
          <select
            value={metric}
            onChange={(e) => onMetricChange(e.target.value as TrendMetric)}
            className="rounded border border-slate-800 bg-slate-950 px-2 py-1 text-sm text-slate-100"
          >
            {TREND_METRICS.map((key) => (
              <option key={key} value={key}>
                {METRIC_LABELS[key] ?? key}
              </option>
            ))}
          </select>
        </label>
      </div>

      {state.phase === 'loading' && <PanelSkeleton />}
      {state.phase === 'error' && (
        <ErrorState message={errorCopy(state.error)} onRetry={retry} />
      )}
      {state.phase === 'empty' && <EmptyState message="Sin partidas todavía." />}
      {state.phase === 'success' && (
        <TrendChart matches={state.data} comparison={comparison.state} metric={metric} />
      )}
    </section>
  )
}

// --- History ---

function MatchHistory({
  state,
  retry,
  onViewDetails,
}: {
  state: QueryState<MatchRow[]>
  retry: () => void
  onViewDetails: (matchId: string) => void
}) {
  if (state.phase === 'loading') {
    return (
      <div aria-label="Cargando" className="flex flex-col gap-3">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (state.phase === 'error') {
    return <ErrorState message={HISTORY_ERROR_COPY} onRetry={retry} />
  }
  if (state.phase === 'empty') {
    return <EmptyState message="Sin partidas todavía." />
  }
  return (
    <div className="flex flex-col gap-3">
      {state.data.map((row) => (
        <MatchCard key={row.matchId} row={row} onViewDetails={onViewDetails} />
      ))}
    </div>
  )
}

export function PlayerDashboardView() {
  const { puuid = '' } = useParams()
  const overview = usePlayerOverview(puuid)
  const matches = useMatchList(puuid)
  const comparison = useComparison(puuid)
  const [openMatchId, setOpenMatchId] = useState<string | null>(null)
  const [trendMetric, setTrendMetric] = useState<TrendMetric>('visionScorePerMinute')

  if (!puuid) return null

  const gamesAnalyzed =
    overview.state.phase === 'success' ? overview.state.data.gamesAnalyzed : null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Resumen</h1>
      <PlayerTabs puuid={puuid} />

      <OverviewHeader state={overview.state} retry={overview.retry} />

      <div className="grid gap-6 lg:grid-cols-2">
        <ScoreCard comparison={comparison} gamesAnalyzed={gamesAnalyzed} />
        <PercentileCard comparison={comparison} />
      </div>

      <StrengthsCard comparison={comparison} />

      <TrendCard
        matches={matches}
        comparison={comparison}
        metric={trendMetric}
        onMetricChange={setTrendMetric}
      />

      <section aria-label="Historial de partidas" className="min-w-0">
        <h2 className="mb-3 text-lg font-semibold text-slate-100">Historial</h2>
        <MatchHistory
          state={matches.state}
          retry={matches.retry}
          onViewDetails={(matchId) => setOpenMatchId(matchId)}
        />
      </section>

      {openMatchId !== null && (
        <MatchDetailModal
          puuid={puuid}
          matchId={openMatchId}
          onClose={() => setOpenMatchId(null)}
        />
      )}
    </main>
  )
}
