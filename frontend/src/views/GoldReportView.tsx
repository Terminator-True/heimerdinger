import { useParams } from 'react-router-dom'
import { Bar, BarChart, Tooltip, XAxis, YAxis } from 'recharts'
import { getGoldMatches, getGoldReport } from '../lib/api'
import { useApiQuery, type QueryState } from '../hooks/useApiQuery'
import { errorCopy } from '../lib/errorCopy'
import { fmtValue } from '../lib/format'
import { goldEarnedSeries, goldEfficiency } from '../lib/gold'

import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { PanelSkeleton } from '../components/PanelSkeleton'

type AggregateGold = Awaited<ReturnType<typeof getGoldReport>>
type GoldRow = Awaited<ReturnType<typeof getGoldMatches>>[number]

const GOLD_LIMIT = 20

// --- Panel 1: percentile chart from flat aggregate keys ---
function PercentileChart({
  state,
  retry,
}: {
  state: QueryState<AggregateGold>
  retry: () => void
}) {
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  if (state.phase === 'empty') {
    return <EmptyState message="Sin datos de oro todavía" />
  }

  const d = state.data
  const series = goldEarnedSeries(d)

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Oro ganado por partida</h2>
      <p className="mt-1 text-sm text-slate-400">
        Partidas analizadas: {fmtValue(d.games_analyzed)} · Victorias: {fmtValue(d.wins)}
      </p>
      {series.length === 0 ? (
        <EmptyState message="Sin datos de oro todavía" />
      ) : (
        <div className="mt-4 h-64">
          {/* ponytail: fixed chart size, no ResponsiveContainer — it needs
              ResizeObserver, which jsdom lacks (chart never renders in tests). */}
          <BarChart width={800} height={256} data={series}>
            <XAxis dataKey="label" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="value" fill="#f59e0b" radius={[4, 4, 0, 0]} />
          </BarChart>
        </div>
      )}
    </div>
  )
}

// --- Panel 2: per-match item timeline (simple table) ---
interface TimelineRow {
  key: string
  champion: string
  items: string
  value: number
  accumulated: number
}

function ItemTimeline({
  state,
  retry,
}: {
  state: QueryState<GoldRow[]>
  retry: () => void
}) {
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  if (state.phase === 'empty') return <EmptyState message="Sin datos de oro todavía" />

  const rows = state.data.reduce<{ rows: TimelineRow[]; total: number }>(
    (acc, row) => {
      const value = row.items.gold_value
      const total = acc.total + value
      return {
        rows: [
          ...acc.rows,
          {
            key: row.matchId,
            champion: row.champion,
            items: row.items.names.join(', ') || '—',
            value,
            accumulated: total,
          },
        ],
        total,
      }
    },
    { rows: [], total: 0 },
  ).rows

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Timeline de ítems</h2>
      <table className="mt-4 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400">
            <th className="py-2 pr-2 font-medium">Partida</th>
            <th className="py-2 pr-2 font-medium">Campeón</th>
            <th className="py-2 pr-2 font-medium">Ítems</th>
            <th className="py-2 pr-2 text-right font-medium">Valor</th>
            <th className="py-2 text-right font-medium">Acumulado</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-b border-slate-800/60">
              <td className="py-2 pr-2 text-slate-300">{r.key}</td>
              <td className="py-2 pr-2">{r.champion}</td>
              <td className="py-2 pr-2 text-slate-300">{r.items}</td>
              <td className="py-2 pr-2 text-right">{fmtValue(r.value)}</td>
              <td className="py-2 text-right text-amber-400">{fmtValue(r.accumulated)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// --- Panel 3: gold efficiency badge ---
function EfficiencyBadge({
  state,
  retry,
}: {
  state: QueryState<GoldRow[]>
  retry: () => void
}) {
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  if (state.phase === 'empty') return <EmptyState message="Sin datos de oro todavía" />

  // Ratio over the LATEST match only. The backend sorts rows by _id DESC
  // (most recent FIRST), so data[0] is the latest match. HIDDEN entirely
  // when either field is absent or gold_value === 0 (unknown). The '—' copy
  // would only mislead here, so a hidden badge renders nothing.
  const latest = state.data[0]
  const ratio = latest ? goldEfficiency(latest) : null
  if (ratio === null) return null

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Eficiencia de oro</h2>
      <p className="mt-1 text-sm text-slate-400">
        {ratio.toFixed(2)} (oro ganado por valor de ítems)
      </p>
    </div>
  )
}

export function GoldReportView() {
  const { puuid = '' } = useParams()
  const enabled = puuid !== ''

  const report = useApiQuery(() => getGoldReport(puuid, GOLD_LIMIT), [puuid], { enabled })
  const matches = useApiQuery(() => getGoldMatches(puuid, GOLD_LIMIT), [puuid], { enabled })

  if (!puuid) return null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Reporte de oro</h1>
      <PercentileChart state={report.state} retry={report.retry} />
      <ItemTimeline state={matches.state} retry={matches.retry} />
      <EfficiencyBadge state={matches.state} retry={matches.retry} />
    </main>
  )
}
