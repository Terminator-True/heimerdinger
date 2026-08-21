import { describe, it, expect } from 'vitest'
import { useAppStore } from './appStore'

const STORAGE_KEY = 'heimerdinger.store'

function persisted(): Record<string, unknown> {
  const raw = localStorage.getItem(STORAGE_KEY)
  expect(raw).not.toBeNull()
  // zustand persist envelope: { state: {...}, version: n }
  const envelope = JSON.parse(raw!) as { state?: Record<string, unknown> }
  return (envelope.state ?? envelope) as Record<string, unknown>
}

describe('appStore', () => {
  it('starts with europe defaults and empty session state', () => {
    expect(useAppStore.getState()).toMatchObject({
      currentPuuid: '',
      currentRiotId: '',
      region: 'europe',
      region_rep: 'europe',
    })
  })

  it('setters update each field', () => {
    useAppStore.getState().setCurrentPuuid('puuid-1')
    useAppStore.getState().setCurrentRiotId('Nombre#TAG')
    useAppStore.getState().setRegion('americas')
    expect(useAppStore.getState()).toMatchObject({
      currentPuuid: 'puuid-1',
      currentRiotId: 'Nombre#TAG',
      region: 'americas',
    })
  })

  it('persists ONLY the region keys, never session state', () => {
    useAppStore
      .getState()
      .setCurrentPuuid('secret-puuid')
    useAppStore.getState().setRegion('asia')
    useAppStore.getState().setRegionRep('asia')

    const saved = persisted()
    expect(saved).toEqual({ region: 'asia', region_rep: 'asia' })
    expect(JSON.stringify(saved)).not.toContain('secret-puuid')
  })
})
