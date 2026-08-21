import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  currentPuuid: string
  currentRiotId: string
  region: string
  regionRep: string
  setCurrentPuuid: (puuid: string) => void
  setCurrentRiotId: (riotId: string) => void
  setRegion: (region: string) => void
  setRegionRep: (regionRep: string) => void
}

// Session-scoped fields (puuid/riotId) are deliberately excluded from
// persistence via partialize: only the region keys survive a reload.
// API-side payloads still use snake_case `region_rep` — map there when the
// api client lands (WU2).
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentPuuid: '',
      currentRiotId: '',
      region: 'europe',
      regionRep: 'europe',
      setCurrentPuuid: (puuid) => set({ currentPuuid: puuid }),
      setCurrentRiotId: (riotId) => set({ currentRiotId: riotId }),
      // Region selector writes BOTH keys; the advanced control overrides
      // regionRep independently afterwards.
      setRegion: (region) => set({ region, regionRep: region }),
      setRegionRep: (regionRep) => set({ regionRep }),
    }),
    {
      name: 'heimerdinger.store',
      partialize: (s) => ({ region: s.region, regionRep: s.regionRep }),
    },
  ),
)
