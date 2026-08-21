import { useState, type FormEvent } from 'react'
import { getTeam, ingestTeam, type ApiError } from '../lib/api'
import { useApiQuery } from '../hooks/useApiQuery'
import { errorCopy } from '../lib/errorCopy'
import { PanelSkeleton } from '../components/PanelSkeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'

type RosterRow = Awaited<ReturnType<typeof getTeam>>[number]
type IngestPlayer = Awaited<ReturnType<typeof ingestTeam>>['players'][number]

function isSuccess(p: IngestPlayer): p is IngestPlayer & { error?: undefined } {
  return !('error' in p && p.error !== undefined)
}

export function TeamView() {
  const roster = useApiQuery(() => getTeam('team.json'), [])
  const [teamPath, setTeamPath] = useState('team.json')
  const [busy, setBusy] = useState(false)
  const [abortRef, setAbortRef] = useState<AbortController | null>(null)
  const [result, setResult] = useState<IngestPlayer[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    const controller = new AbortController()
    setAbortRef(controller)
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const data = await ingestTeam({ teamPath }, { signal: controller.signal })
      setResult(data.players)
    } catch (err) {
      // Caller abort surfaces as network per api.ts; a user cancel is not an
      // error, so report it as a neutral notice instead.
      setError(controller.signal.aborted ? 'Ingesta cancelada.' : errorCopy(err as ApiError))
    } finally {
      setBusy(false)
      setAbortRef(null)
    }
  }

  function onCancel() {
    abortRef?.abort()
  }

  const ok = (result ?? []).filter(isSuccess)
  const failed = (result ?? []).filter((p) => !isSuccess(p))

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Equipo</h1>

      <section aria-label="Plantel del equipo" className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold text-slate-100">Plantel</h2>
        {roster.state.phase === 'loading' && <PanelSkeleton />}
        {roster.state.phase === 'error' && (
          <ErrorState message={errorCopy(roster.state.error)} onRetry={roster.retry} />
        )}
        {(roster.state.phase === 'empty' ||
          (roster.state.phase === 'success' && roster.state.data.length === 0)) && (
          <EmptyState message="El equipo no tiene jugadores todavía." />
        )}
        {roster.state.phase === 'success' && roster.state.data.length > 0 && (
          <ul className="flex flex-col gap-2">
            {roster.state.data.map((p: RosterRow) => (
              <li
                key={p.riotid}
                className="flex items-center justify-between rounded border border-slate-800 bg-slate-900 px-3 py-2"
              >
                <span className="text-sm text-slate-100">{p.riotid}</span>
                <span className="text-xs text-slate-400">{p.role}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Ingesta del equipo" className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-slate-100">Ingestar equipo</h2>
        <form onSubmit={onSubmit} className="flex gap-2">
          <input
            type="text"
            value={teamPath}
            onChange={(e) => setTeamPath(e.target.value)}
            placeholder="team.json"
            aria-label="Ruta del equipo"
            className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-500"
          />
          <button
            type="submit"
            disabled={busy || teamPath.trim() === ''}
            className="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
          >
            Ingestar equipo
          </button>
          {busy && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded border border-slate-800 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              Cancelar
            </button>
          )}
        </form>

        {busy && (
          <div aria-label="Ingestando" className="flex flex-col gap-2">
            <PanelSkeleton />
          </div>
        )}

        {error !== null && (
          <p className="text-sm text-red-400">{error}</p>
        )}

        {result !== null && (
          <div className="flex flex-col gap-4">
            {ok.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-slate-300">
                  Jugadores ingestados
                </h3>
                <ul
                  aria-label="Jugadores ingestados"
                  className="flex flex-col gap-2"
                >
                  {ok.map((p) => (
                    <li
                      key={p.riotid}
                      className="rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                    >
                      {p.riotid}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {failed.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-red-400">
                  Jugadores con error
                </h3>
                <ul aria-label="Jugadores con error" className="flex flex-col gap-2">
                  {failed.map((p) => (
                    <li
                      key={p.riotid}
                      className="rounded border border-red-900 bg-red-950 px-3 py-2 text-sm text-slate-100"
                    >
                      <span>{p.riotid}</span>
                      <span className="ml-2 text-xs text-red-400">{p.error}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result.length === 0 && (
              <p className="text-sm text-slate-400">No se procesaron jugadores.</p>
            )}
          </div>
        )}
      </section>
    </main>
  )
}
