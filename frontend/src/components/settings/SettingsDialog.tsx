import { useState } from 'react'
import { getApiKey, getBaseUrl, saveApiKey, setBaseUrl } from '../../lib/settings'
import { useSettings } from './SettingsProvider'

export function SettingsDialog() {
  const { open, closeDialog } = useSettings()
  if (!open) return null
  return <SettingsForm onClose={closeDialog} />
}

// Mounted fresh on each open so fields initialize from current stored values.
function SettingsForm({ onClose }: { onClose: () => void }) {
  const [apiKey, setKey] = useState(getApiKey)
  const [baseUrl, setUrl] = useState(getBaseUrl)
  const [saveError, setSaveError] = useState(false)

  function handleSave() {
    const ok = saveApiKey(apiKey) && setBaseUrl(baseUrl)
    if (!ok) {
      setSaveError(true)
      return
    }
    onClose()
  }

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
        {saveError && (
          <p role="alert" className="mb-3 text-xs text-red-400">
            No se pudo guardar la configuración (almacenamiento no disponible).
          </p>
        )}
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
            onClick={handleSave}
            className="rounded bg-amber-500 px-3 py-1.5 text-sm font-medium text-slate-950 hover:bg-amber-400"
          >
            Guardar
          </button>
        </div>
      </div>
    </div>
  )
}
