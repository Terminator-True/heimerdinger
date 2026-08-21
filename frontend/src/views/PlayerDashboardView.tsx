import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPlayerMatches, getPlayerReport, type ApiError } from '../lib/api'
import { useApiQuery, type QueryState } from '../hooks/useApiQuery'
import { Skeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { MatchCard, type MatchRow } from '../components/player/MatchCard'
import { MatchDetailModal } from '../components/player/MatchDetailModal'

type ReportData = Awaited<ReturnType<typeof getPlayerReport>>

// Error-variant reports (status/detail) parse OK but carry no payload;
// they surface as empty, not success.
function isFullReport(d: ReportData): d is Extract<ReportData, { games_analyzed: number }> {
  return 'games_analyzed' in d
}

function fmtValue(v: unknown): string {
  if (v === undefined || v === null || v === '') return '—'
  return String(v)
}

// Mirrors LandingView error copy; kept local to avoid a cross-view import.
function errorCopy(err: ApiError): string {
  switch (err.kind) {
    case 'timeout':
      return 'La consulta tardó demasiado. Probá de nuevo.'
    case 'network':
      return 'No hay conexión con el backend. Verificá que esté corriendo.'
    case 'server':
      return 'El servidor no pudo procesar la solicitud. Probá de nuevo.'
    case 'auth':
      return 'Se requiere una API key. Configurala en Ajustes.'
    default:
      return 'Ocurrió un error inesperado.'
  }
}

interface MetricRowProps {
  label: string
  value: string
}

function MetricRow({ label, value }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-sm text-slate-400">{label}</dt>
      <dd className="text-sm font-medium text-slate-100">{value}</dd>
    </div>
  )
}

function ReportSidebar({
  state,
  retry,
}: {
  state: QueryState<ReportData>
  retry: () => void
}) {
  if (state.phase === 'loading') {
    return (
      <div aria-label="Cargando" className="flex flex-col gap-2 rounded border border-slate-800 bg-slate-900 p-6">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    )
  }
  if (state.phase === 'error') {
    return <ErrorState message={errorCopy(state.error)} onRetry={retry} />
  }
  if (state.phase === 'empty' || !isFullReport(state.data)) {
    return (
      <EmptyState message="Sin datos todavía. Ingresa partidas primero." />
    )
  }

  const d = state.data
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold text-slate-100">{d.player}</h2>
      <dl className="mt-4 flex flex-col gap-2">
        <MetricRow label="Partidas analizadas" value={fmtValue(d.games_analyzed)} />
        <MetricRow label="Campeón principal" value={d.champion ?? '—'} />
        <MetricRow label="Rol" value={d.role ?? '—'} />
        <MetricRow label="KDA promedio" value={fmtValue(d.metrics['kda'])} />
        <MetricRow label="CS/min" value={fmtValue(d.metrics['cs_per_min'])} />
      </dl>
    </div>
  )
}

const HISTORY_ERROR_COPY = 'No se pudieron cargar las partidas.'

function MatchHistory({
  state,
  retry,
  onViewDetails,
}: {
  state: QueryState<Array<Record<string, unknown>>>
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
      {(state.data as unknown as MatchRow[]).map((row) => (
        <MatchCard key={row.matchId} row={row} onViewDetails={onViewDetails} />
      ))}
    </div>
  )
}

export function PlayerDashboardView() {
  const { puuid = '' } = useParams()
  const report = useApiQuery(() => getPlayerReport(puuid), [puuid])
  const matches = useApiQuery(() => getPlayerMatches(puuid, 20), [puuid])
  const [openMatchId, setOpenMatchId] = useState<string | null>(null)

  if (!puuid) return null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6 lg:flex-row">
      <aside aria-label="Resumen del jugador" className="w-full shrink-0 lg:w-72">
        <ReportSidebar state={report.state} retry={report.retry} />
      </aside>

      <section aria-label="Historial de partidas" className="min-w-0 flex-1">
        <h1 className="mb-3 text-xl font-semibold text-slate-100">Historial</h1>
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
