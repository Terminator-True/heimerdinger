import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'

// Every view is exercised through the real route table. API fns never settle,
// which pins each view to its loading state — exactly what a route render
// check needs: prove the component mounts and its heading renders.
vi.mock('../lib/api', () => ({
  getRoot: vi.fn(() => new Promise(() => {})),
  getHealth: vi.fn(() => new Promise(() => {})),
  getTeam: vi.fn(() => new Promise(() => {})),
  ingestTeam: vi.fn(() => new Promise(() => {})),
  ingestPlayer: vi.fn(() => new Promise(() => {})),
  askCoach: vi.fn(() => new Promise(() => {})),
  getPlayerMatches: vi.fn(() => new Promise(() => {})),
  getPlayerReport: vi.fn(() => new Promise(() => {})),
  getPlayerMatchReport: vi.fn(() => new Promise(() => {})),
  getMatchComposition: vi.fn(() => new Promise(() => {})),
  getMatchSnapshot: vi.fn(() => new Promise(() => {})),
  getMatchGold: vi.fn(() => new Promise(() => {})),
  getGoldMatches: vi.fn(() => new Promise(() => {})),
  getGoldReport: vi.fn(() => new Promise(() => {})),
  queryEmbeddings: vi.fn(() => new Promise(() => {})),
  seedEmbeddings: vi.fn(() => new Promise(() => {})),
}))

import App from '../App'

const ROUTES: Array<[path: string, heading: string]> = [
  ['/', 'Buscar jugador'],
  ['/player/puuid-1', 'Historial'],
  ['/player/puuid-1/gold', 'Reporte de oro'],
  ['/matches/M1', 'Detalle de partida'],
  ['/coach', 'Coach IA'],
  ['/team', 'Equipo'],
]

afterEach(() => {
  cleanup()
  // Restore the jsdom URL so BrowserRouter state never leaks across tests.
  window.history.pushState({}, '', '/')
})

describe('route smoke check — all SPA views mount', () => {
  it.each(ROUTES)('renders %s', (path, heading) => {
    window.history.pushState({}, '', path)
    render(<App />)
    expect(screen.getByRole('heading', { name: heading })).toBeTruthy()
  })

  it('redirects unknown paths to /', () => {
    window.history.pushState({}, '', '/nonexistent')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Buscar jugador' })).toBeTruthy()
  })
})