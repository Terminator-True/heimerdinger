import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('../lib/api', () => ({
  getMatchComposition: vi.fn(),
  getMatchSnapshot: vi.fn(),
  getMatchGold: vi.fn(),
  getPlayerMatchReport: vi.fn(),
}))

import {
  getMatchComposition,
  getMatchGold,
  getMatchSnapshot,
  getPlayerMatchReport,
} from '../lib/api'
import { MatchDetailView } from './MatchDetailView'

const MATCH = 'M1'
const mockComposition = vi.mocked(getMatchComposition)
const mockSnapshot = vi.mocked(getMatchSnapshot)
const mockGold = vi.mocked(getMatchGold)
const mockMatchReport = vi.mocked(getPlayerMatchReport)

function renderView(state?: { puuid?: string }) {
  return render(
    <MemoryRouter
      initialEntries={[
        { pathname: '/matches/' + MATCH, state },
      ]}
    >
      <Routes>
        <Route path="/matches/:matchId" element={<MatchDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('panel independence', () => {
  it('renders composition, snapshot and gold table independently', async () => {
    mockComposition.mockResolvedValue({ 100: ['Ahri', 'Lee Sin'], 200: ['Zed'] })
    mockSnapshot.mockResolvedValue({ snapshot: 'line1\nline2' })
    mockGold.mockResolvedValue({
      matchId: MATCH,
      players: [
        {
          matchId: MATCH, puuid: 'p1', summonerName: 'Faker', timestamp: null,
          win: true, champion: 'Ahri', role: 'MID', teamId: 100,
          goldEarned: 10000, goldSpent: 9000, gold_diff: 500, gpm: 400,
          itemsPurchased: 6, consumablesPurchased: 2,
          items: { ids: [1], names: ['Hextech'], gold_value: 8000, stats: {} },
        },
      ],
    })

    renderView()

    // Composition
    expect((await screen.findAllByText('Ahri')).length).toBeGreaterThan(0)
    expect(screen.getByText('Lee Sin')).toBeTruthy()
    // Snapshot rendered as plain text (no HTML injection)
    const snap = await screen.findByTestId('snapshot-text')
    expect(snap.textContent).toBe('line1\nline2')
    // Gold table
    expect(await screen.findByText('10000')).toBeTruthy()
    expect(screen.getByText('Faker')).toBeTruthy()
  })

  it('shows empty copy for a 404 panel while others still render', async () => {
    mockComposition.mockRejectedValue({ kind: 'not_found' })
    mockSnapshot.mockResolvedValue({ snapshot: 'ok' })
    mockGold.mockResolvedValue({
      matchId: MATCH,
      players: [],
    })

    renderView()

    await waitFor(() => {
      expect(screen.getByText('Composición no disponible')).toBeTruthy()
    })
    expect(await screen.findByTestId('snapshot-text')).toBeTruthy()
  })

  it('renders plain text snapshot without injecting HTML', async () => {
    mockComposition.mockRejectedValue({ kind: 'not_found' })
    mockSnapshot.mockResolvedValue({ snapshot: '<b>bold</b>' })
    mockGold.mockRejectedValue({ kind: 'not_found' })

    renderView()

    const snap = await screen.findByTestId('snapshot-text')
    expect(snap.textContent).toBe('<b>bold</b>')
    expect(snap.querySelector('b')).toBeNull()
  })

  it('renders the embedded player report when route state carries puuid', async () => {
    mockComposition.mockRejectedValue({ kind: 'not_found' })
    mockSnapshot.mockRejectedValue({ kind: 'not_found' })
    mockGold.mockRejectedValue({ kind: 'not_found' })
    mockMatchReport.mockResolvedValue({
      player: 'Faker#KR1', matchId: MATCH, champion: 'Azir',
      games_analyzed: 1, metrics: { kda: 6.5 }, role: 'Mid',
    })

    renderView({ puuid: 'p1' })

    await waitFor(() =>
      expect(mockMatchReport).toHaveBeenCalledWith('p1', MATCH),
    )
    const section = await screen.findByRole('region', { name: 'Reporte del jugador' })
    expect(within(section).getByText('Azir')).toBeTruthy()
    expect(within(section).getByText('6.5')).toBeTruthy()
  })
})
