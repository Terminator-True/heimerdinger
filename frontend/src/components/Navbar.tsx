import { Settings } from 'lucide-react'
import { HealthDot } from './HealthDot'
import { RegionSelector } from './RegionSelector'
import { useSettings } from './settings/SettingsProvider'

export function Navbar() {
  const { openDialog } = useSettings()
  return (
    <nav className="flex items-center justify-between border-b border-slate-800 bg-slate-950 px-6 py-3">
      <span className="text-sm font-semibold text-slate-100">Heimerdinger</span>
      <div className="flex items-center gap-4">
        <HealthDot />
        <RegionSelector />
        <button
          type="button"
          onClick={openDialog}
          aria-label="Configuración"
          className="rounded border border-slate-800 p-1.5 text-slate-300 hover:bg-slate-800"
        >
          <Settings size={16} />
        </button>
      </div>
    </nav>
  )
}
