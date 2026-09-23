import { useParams } from 'react-router-dom'
import { PlayerTabs } from '../components/player/PlayerTabs'

// ponytail: placeholder for slice D, which fills the Comparativa screen.
export function PlayerCompareView() {
  const { puuid = '' } = useParams()
  if (!puuid) return null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Comparativa</h1>
      <PlayerTabs puuid={puuid} />
      <div className="rounded border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
        En construcción
      </div>
    </main>
  )
}
