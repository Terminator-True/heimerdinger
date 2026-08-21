import { useAppStore } from '../stores/appStore'

const REGIONS = ['europe', 'americas', 'asia'] as const

export function RegionSelector() {
  const region = useAppStore((s) => s.region)
  const regionRep = useAppStore((s) => s.regionRep)
  const setRegion = useAppStore((s) => s.setRegion)
  const setRegionRep = useAppStore((s) => s.setRegionRep)

  return (
    <div className="flex items-center gap-2">
      <select
        aria-label="Región"
        value={region}
        onChange={(e) => setRegion(e.target.value)}
        className="rounded border border-slate-800 bg-slate-900 px-2 py-1 text-xs text-slate-200"
      >
        {REGIONS.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
      {/* Advanced override: region_rep diverges from the main region */}
      <input
        aria-label="Región de representación (avanzado)"
        value={regionRep}
        onChange={(e) => setRegionRep(e.target.value)}
        className="w-28 rounded border border-slate-800 bg-slate-900 px-2 py-1 text-xs text-slate-400"
      />
    </div>
  )
}
