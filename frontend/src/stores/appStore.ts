import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  currentPuuid: string
  currentRiotId: string
  region: string
  region_rep: string
  setCurrentPuuid: (puuid: string) => void
  setCurrentRiotId: (riotId: string) => void
  setRegion: (region: string) => void
  setRegionRep: (regionRep: string) => void
}

// Session-scoped fields (puuid/riotId) are deliberately excluded from
// persistence via partialize: only the region keys survive a reload.
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentPuuid: '',
      currentRiotId: '',
      region: 'europe',
      region_rep: 'europe',
      setCurrentPuuid: (puuid) => set({ currentPuuid: puuid }),
      setCurrentRiotId: (riotId) => set({ currentRiotId: riotId }),
      // Region selector writes BOTH keys; the advanced control overrides
      // region_rep independently afterwards.
      setRegion: (region) => set({ region, region_rep: region }),
      setRegionRep: (region_rep) => set({ region_rep }),
    }),
    {
      name: 'heimerdinger.store',
      partialize: (s) => ({ region: s.region, region_rep: s.region_rep }),
    },
  ),
)
