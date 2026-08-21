import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { getApiKey, getBaseUrl, setApiKey, setBaseUrl } from '../lib/settings'

const UNAUTHORIZED_EVENT = 'heimerdinger:unauthorized'

interface SettingsContextValue {
  open: boolean
  openDialog: () => void
  closeDialog: () => void
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const openDialog = useCallback(() => setOpen(true), [])
  const closeDialog = useCallback(() => setOpen(false), [])

  useEffect(() => {
    // Any view's 401 opens the key-entry flow; no redirect, no route guard.
    window.addEventListener(UNAUTHORIZED_EVENT, openDialog)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, openDialog)
  }, [openDialog])

  return (
    <SettingsContext.Provider value={{ open, openDialog, closeDialog }}>
      {children}
      <SettingsDialog />
    </SettingsContext.Provider>
  )
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}

function SettingsDialog() {
  const { open, closeDialog } = useSettings()
  if (!open) return null
  return <SettingsForm onClose={closeDialog} />
}

// Mounted fresh on each open so fields initialize from current stored values.
function SettingsForm({ onClose }: { onClose: () => void }) {
  const [apiKey, setKey] = useState(getApiKey)
  const [baseUrl, setUrl] = useState(getBaseUrl)

  return (
    <div
      className="fixed inset-0 flex items-center justify-center bg-slate-950/80"
      onClick={onClose}
    >
      <div
        className="w-96 rounded border border-slate-800 bg-slate-900 p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Configuración"
      >
        <h2 className="mb-4 text-base font-semibold text-slate-100">
          Configuración
        </h2>
        <label className="mb-3 block text-xs text-slate-400">
          API Key
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setKey(e.target.value)}
            className="mt-1 w-full rounded border border-slate-800 bg-slate-950 px-2 py-1.5 text-sm text-slate-200"
          />
        </label>
        <label className="mb-4 block text-xs text-slate-400">
          URL del backend
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://localhost:8000"
            className="mt-1 w-full rounded border border-slate-800 bg-slate-950 px-2 py-1.5 text-sm text-slate-200"
          />
        </label>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-800 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => {
              setApiKey(apiKey)
              setBaseUrl(baseUrl)
              onClose()
            }}
            className="rounded bg-amber-500 px-3 py-1.5 text-sm font-medium text-slate-950 hover:bg-amber-400"
          >
            Guardar
          </button>
        </div>
      </div>
    </div>
  )
}
