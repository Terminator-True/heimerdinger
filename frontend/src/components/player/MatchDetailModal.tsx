import { useEffect } from 'react'
import { getPlayerMatchReport } from '../../lib/api'
import { useApiQuery } from '../../hooks/useApiQuery'
import { Skeleton } from '../Skeleton'

interface MatchDetailModalProps {
  puuid: string
  matchId: string
  onClose: () => void
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-sm text-slate-400">{label}</dt>
      <dd className="text-sm font-medium text-slate-100">{value}</dd>
    </div>
  )
}

function fmtValue(v: unknown): string {
  if (v === undefined || v === null || v === '') return '—'
  return String(v)
}

// Fully independent query state: opening one modal never disturbs the
// sidebar/history queries behind it. Focus is not trapped — Escape,
// backdrop click and the X button all close.
export function MatchDetailModal({ puuid, matchId, onClose }: MatchDetailModalProps) {
  const { state, retry } = useApiQuery(
    () => getPlayerMatchReport(puuid, matchId),
    [puuid, matchId],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      data-testid="modal-backdrop"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Detalle de partida ${matchId}`}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded border border-slate-800 bg-slate-900 p-6"
      >
        <div className="flex items-start justify-between">
          <h2 className="text-lg font-semibold text-slate-100">
            Detalle de partida
          </h2>
          <button
            type="button"
            aria-label="Cerrar"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-100"
          >
            ✕
          </button>
        </div>

        {state.phase === 'loading' && (
          <div aria-label="Cargando" className="mt-4 flex flex-col gap-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-3/4" />
          </div>
        )}

        {state.phase === 'error' && (
          <p className="mt-4 text-sm text-red-400">
            Detalle de partida no disponible
            {' '}
            <button
              type="button"
              onClick={retry}
              className="ml-1 rounded border border-slate-800 px-2 py-0.5 text-xs text-amber-500 hover:bg-slate-800"
            >
              Reintentar
            </button>
          </p>
        )}

        {state.phase === 'empty' && (
          <p className="mt-4 text-sm text-slate-400">
            Detalle de partida no disponible
          </p>
        )}

        {state.phase === 'success' && (
          <dl className="mt-4 flex flex-col gap-2">
            <Stat label="Campeón" value={state.data.champion ?? '—'} />
            <Stat label="Rol" value={state.data.role ?? '—'} />
            <Stat
              label="Partidas analizadas"
              value={fmtValue(state.data.games_analyzed)}
            />
            <Stat
              label="KDA promedio"
              value={fmtValue(state.data.metrics['kda'])}
            />
            <Stat
              label="CS/min"
              value={fmtValue(state.data.metrics['cs_per_min'])}
            />
          </dl>
        )}
      </div>
    </div>
  )
}
