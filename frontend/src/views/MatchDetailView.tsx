import { useLocation, useParams } from 'react-router-dom'
import { getMatchComposition, getMatchGold, getMatchSnapshot, getPlayerMatchReport } from '../lib/api'
import { useApiQuery, type QueryState } from '../hooks/useApiQuery'
import { errorCopy } from '../lib/errorCopy'
import { fmtValue } from '../lib/format'

import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { PanelSkeleton } from '../components/PanelSkeleton'

type Composition = Awaited<ReturnType<typeof getMatchComposition>>
type Snapshot = Awaited<ReturnType<typeof getMatchSnapshot>>
type GoldRow = Awaited<ReturnType<typeof getMatchGold>>['players'][number]
type MatchReport = Awaited<ReturnType<typeof getPlayerMatchReport>>

// --- Panel 1: team composition ---
function CompositionPanel({
  state,
  retry,
}: {
  state: QueryState<Composition>
  retry: () => void
}) {
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  if (state.phase === 'empty') return <EmptyState message="Composición no disponible" />

  const teams = Object.entries(state.data)
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Composición</h2>
      <div className="mt-4 flex flex-col gap-4">
        {teams.map(([teamId, champions]) => (
          <div key={teamId}>
            <h3 className="text-sm font-medium text-slate-400">Equipo {teamId}</h3>
            <ul className="mt-1 flex flex-wrap gap-2">
              {champions.map((champion) => (
                <li
                  key={champion}
                  className="rounded bg-slate-800 px-2 py-1 text-sm text-slate-200"
                >
                  {champion}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}

// --- Panel 2: snapshot as PLAIN TEXT (untrusted server string) ---
function SnapshotPanel({
  state,
  retry,
}: {
  state: QueryState<Snapshot>
  retry: () => void
}) {
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  if (state.phase === 'empty') return <EmptyState message="Resumen no disponible" />

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Resumen</h2>
      {/* Plain text node: React escapes the server string, no HTML injection. */}
      <pre
        data-testid="snapshot-text"
        className="mt-4 whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-300"
      >
        {state.data.snapshot}
      </pre>
    </div>
  )
}

// --- Panel 3: gold table ---
function GoldTable({
  state,
  retry,
}: {
  state: QueryState<GoldRow[]>
  retry: () => void
}) {
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  if (state.phase === 'empty') return <EmptyState message="Datos de oro no disponibles" />

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Oro</h2>
      <table className="mt-4 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400">
            <th className="py-2 pr-2 font-medium">Jugador</th>
            <th className="py-2 pr-2 font-medium">Campeón</th>
            <th className="py-2 pr-2 text-right font-medium">Oro ganado</th>
            <th className="py-2 pr-2 text-right font-medium">Oro gastado</th>
            <th className="py-2 text-right font-medium">Oro/min</th>
          </tr>
        </thead>
        <tbody>
          {state.data.map((row) => (
            <tr key={row.puuid + row.matchId} className="border-b border-slate-800/60">
              <td className="py-2 pr-2 text-slate-300">{row.summonerName ?? '—'}</td>
              <td className="py-2 pr-2">{row.champion}</td>
              <td className="py-2 pr-2 text-right">{fmtValue(row.goldEarned)}</td>
              <td className="py-2 pr-2 text-right">{fmtValue(row.goldSpent)}</td>
              <td className="py-2 text-right">{fmtValue(row.gpm)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// --- Optional embedded player report (route state {puuid}) ---
function PlayerReport({
  state,
  retry,
}: {
  state: QueryState<MatchReport>
  retry: () => void
}) {
  if (state.phase === 'loading') return <PanelSkeleton />
  if (state.phase === 'error') return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  if (state.phase === 'empty') return <EmptyState message="Reporte no disponible" />

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">Reporte del jugador</h2>
      <dl className="mt-4 flex flex-col gap-2">
        <div className="flex items-center justify-between gap-4">
          <dt className="text-sm text-slate-400">Campeón</dt>
          <dd className="text-sm font-medium text-slate-100">{state.data.champion ?? '—'}</dd>
        </div>
        <div className="flex items-center justify-between gap-4">
          <dt className="text-sm text-slate-400">Rol</dt>
          <dd className="text-sm font-medium text-slate-100">{state.data.role ?? '—'}</dd>
        </div>
        <div className="flex items-center justify-between gap-4">
          <dt className="text-sm text-slate-400">Partidas analizadas</dt>
          <dd className="text-sm font-medium text-slate-100">{fmtValue(state.data.games_analyzed)}</dd>
        </div>
        <div className="flex items-center justify-between gap-4">
          <dt className="text-sm text-slate-400">KDA promedio</dt>
          <dd className="text-sm font-medium text-slate-100">{fmtValue(state.data.metrics['kda'])}</dd>
        </div>
      </dl>
    </div>
  )
}

export function MatchDetailView() {
  const { matchId = '' } = useParams()
  const location = useLocation()
  const embeddedPuuid = (location.state as { puuid?: string } | null)?.puuid

  const enabled = matchId !== ''
  const composition = useApiQuery(() => getMatchComposition(matchId), [matchId], { enabled })
  const snapshot = useApiQuery(() => getMatchSnapshot(matchId), [matchId], { enabled })
  const gold = useApiQuery(
    async () => (await getMatchGold(matchId)).players,
    [matchId],
    { enabled },
  )
  const playerReport = useApiQuery(
    () => getPlayerMatchReport(embeddedPuuid ?? '', matchId),
    [embeddedPuuid, matchId],
    { enabled: embeddedPuuid !== undefined },
  )

  if (!matchId) return null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Detalle de partida</h1>
      {embeddedPuuid !== undefined && (
        <section aria-label="Reporte del jugador">
          <PlayerReport state={playerReport.state} retry={playerReport.retry} />
        </section>
      )}
      <CompositionPanel state={composition.state} retry={composition.retry} />
      <SnapshotPanel state={snapshot.state} retry={snapshot.retry} />
      <GoldTable state={gold.state} retry={gold.retry} />
    </main>
  )
}