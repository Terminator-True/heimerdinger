// Demo data switch. Set VITE_MOCK=true to run the UI on the fixture in
// ./player.ts with zero network calls (see src/lib/playerData.ts).
export const MOCK_ENABLED = import.meta.env.VITE_MOCK === 'true'

export * from './player'
