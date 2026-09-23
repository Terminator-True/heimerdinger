import { Bot, Search, Settings } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { MOCK_ENABLED } from '../mocks'
import { HealthDot } from './HealthDot'
import { RegionSelector } from './RegionSelector'
import { useSettings } from './settings/SettingsProvider'

const NAV_LINKS = [
  { to: '/', label: 'Búsqueda', icon: Search },
  { to: '/coach', label: 'Coach', icon: Bot },
]

function navClass({ isActive }: { isActive: boolean }) {
  return `flex items-center gap-1.5 rounded px-2.5 py-1.5 text-sm transition-colors ${
    isActive
      ? 'bg-slate-800 text-amber-500'
      : 'text-slate-300 hover:bg-slate-800 hover:text-slate-100'
  }`
}

export function Navbar() {
  const { openDialog } = useSettings()
  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-950 px-4 py-3 sm:px-6">
      <span className="flex items-center gap-2 text-sm font-semibold text-slate-100">
        Heimerdinger
        {MOCK_ENABLED && (
          <span className="rounded bg-amber-500 px-1.5 py-0.5 text-xs font-semibold uppercase text-slate-950">
            Mock
          </span>
        )}
      </span>

      <div className="flex items-center gap-1">
        {NAV_LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={navClass}>
            <Icon size={16} />
            <span className="hidden sm:inline">{label}</span>
          </NavLink>
        ))}
      </div>

      <div className="flex items-center gap-3">
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
