import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ingestPlayer, type ApiError } from '../lib/api'
import { useAppStore } from '../stores/appStore'
import { Skeleton } from '../components/Skeleton'

export const DEFAULT_COUNT = 5
export const MIN_COUNT = 1
export const MAX_COUNT = 100

export type CountResult = number | { error: string }

// Client-side clamp gate: out-of-bounds blocks submit BEFORE any request is
// sent. Blank input falls back to the default count.
export function validateCount(raw: string): CountResult {
  const trimmed = raw.trim()
  if (trimmed === '') return DEFAULT_COUNT
  const n = Number(trimmed)
  if (!Number.isInteger(n)) {
    return { error: 'Ingresá un número entre 1 y 100.' }
  }
  if (n < MIN_COUNT || n > MAX_COUNT) {
    return { error: 'La cantidad debe estar entre 1 y 100.' }
  }
  return n
}

function errorCopy(err: ApiError): string {
  switch (err.kind) {
    case 'timeout':
      return 'La búsqueda tardó demasiado. El jugador quizás ya se esté procesando; probá de nuevo en unos minutos.'
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

export function LandingView() {
  const navigate = useNavigate()
  const { region, regionRep } = useAppStore()

  const [riotId, setRiotId] = useState('')
  const [countRaw, setCountRaw] = useState('')
  const [inFlight, setInFlight] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (inFlight) return // anti-double-submit: zero extra requests

    setFormError(null)
    setFieldErrors({})

    const riotIdTrimmed = riotId.trim()
    if (!riotIdTrimmed) {
      setFieldErrors({ riotid: 'Ingresá tu Nombre#TAG.' })
      return
    }
    const count = validateCount(countRaw)
    if (typeof count !== 'number') {
      setFieldErrors({ count: count.error })
      return
    }

    setInFlight(true)
    try {
      const res = await ingestPlayer({
        riotId: riotIdTrimmed,
        count,
        region,
        regionRep,
      })
      navigate(`/player/${encodeURIComponent(res.puuid)}`)
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr.kind === 'validation') {
        setFieldErrors(apiErr.fieldErrors)
      } else {
        setFormError(errorCopy(apiErr))
      }
      // Stay on `/`: failure never navigates.
    } finally {
      setInFlight(false)
    }
  }

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-100">
          Buscar jugador
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Ingresá tu Riot ID para sincronizar tus partidas y ver tu dashboard.
        </p>
      </header>

      <form
        onSubmit={onSubmit}
        className="flex flex-col gap-4 rounded border border-slate-800 bg-slate-900 p-6"
      >
        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-300">Riot ID (Nombre#TAG)</span>
          <input
            value={riotId}
            onChange={(e) => setRiotId(e.target.value)}
            placeholder="Ej.: Faker#KR1"
            disabled={inFlight}
            className="rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-amber-500 focus:outline-none"
          />
          {fieldErrors['riotid'] && (
            <span className="text-xs text-red-400">{fieldErrors['riotid']}</span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-300">
            Cantidad de partidas (1–100, por defecto {DEFAULT_COUNT})
          </span>
          <input
            value={countRaw}
            onChange={(e) => setCountRaw(e.target.value)}
            inputMode="numeric"
            disabled={inFlight}
            className="rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-amber-500 focus:outline-none"
          />
          {fieldErrors['count'] && (
            <span className="text-xs text-red-400">{fieldErrors['count']}</span>
          )}
        </label>

        {formError && (
          <p className="rounded border border-red-400/40 bg-red-400/10 p-3 text-sm text-red-400">
            {formError}
          </p>
        )}

        <button
          type="submit"
          disabled={inFlight}
          className="rounded bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Buscar y sincronizar
        </button>
      </form>

      {inFlight && (
        <div aria-label="Cargando" className="flex flex-col gap-2">
          {/* Sync ingest can run minutes; skeleton signals work in flight. */}
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-3/4" />
        </div>
      )}
    </main>
  )
}
