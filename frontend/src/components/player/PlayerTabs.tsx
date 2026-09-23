import { NavLink } from 'react-router-dom'

interface PlayerTab {
  to: string
  label: string
  end: boolean
}

function tabClass({ isActive }: { isActive: boolean }): string {
  return `-mb-px border-b-2 px-3 py-2 text-sm transition-colors ${
    isActive
      ? 'border-amber-500 text-amber-500'
      : 'border-transparent text-slate-400 hover:text-slate-100'
  }`
}

// Shared player-section navigation. NavLink sets aria-current="page" on the
// active tab; `end` keeps Resumen inactive on sub-routes.
export function PlayerTabs({ puuid }: { puuid: string }) {
  const base = `/player/${encodeURIComponent(puuid)}`
  const tabs: PlayerTab[] = [
    { to: base, label: 'Resumen', end: true },
    { to: `${base}/matches`, label: 'Partidas', end: false },
    { to: `${base}/compare`, label: 'Comparativa', end: false },
    { to: `${base}/gold`, label: 'Oro', end: false },
  ]

  return (
    <nav aria-label="Secciones del jugador" className="flex flex-wrap border-b border-slate-800">
      {tabs.map((tab) => (
        <NavLink key={tab.to} to={tab.to} end={tab.end} className={tabClass}>
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
