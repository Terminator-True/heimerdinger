import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('../lib/api', () => ({
  getGoldReport: vi.fn(),
  getGoldMatches: vi.fn(),
}))

import { getGoldMatches, getGoldReport } from '../lib/api'
import { GoldReportView } from './GoldReportView'

const PUUID = 'puuid-1'
const mockReport = vi.mocked(getGoldReport)
const mockMatches = vi.mocked(getGoldMatches)

function renderView() {
  return render(
    <MemoryRouter initialEntries={['/player/' + PUUID + '/gold']}>
      <Routes>
        <Route path="/player/:puuid/gold" element={<GoldReportView />} />
      </Routes>
    </MemoryRouter>,
  )
}

function goldRow(over: Record<string, unknown> = {}) {
  return {
    matchId: 'M1',
    puuid: PUUID,
    summonerName: 'Faker',
    timestamp: null,
    win: true,
    champion: 'Ahri',
    role: 'MID',
    teamId: 100,
    goldEarned: 10000,
    goldSpent: 9000,
    gold_diff: 500,
    gpm: 400,
    itemsPurchased: 6,
    consumablesPurchased: 2,
    items: { ids: [1], names: ['Hextech'], gold_value: 8000, stats: {} },
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

// --- Empty puuid guard ---
describe('empty puuid guard', () => {
  it('fires zero fetches when the puuid param is empty', async () => {
    render(
      <MemoryRouter initialEntries={['/player//gold']}>
        <Routes>
          <Route path="/player/:puuid/gold" element={<GoldReportView />} />
        </Routes>
      </MemoryRouter>,
    )
    await waitFor(() => expect(mockReport).not.toHaveBeenCalled())
    expect(mockMatches).not.toHaveBeenCalled()
  })
})

// --- Panel independence ---
describe('panel independence', () => {
  it('renders each panel from its own query state', async () => {
    mockReport.mockResolvedValue({
      goldEarned: 100,
      goldEarned_median: 90,
      goldEarned_p25: 70,
      goldEarned_p75: 120,
      games_analyzed: 10,
      wins: 6,
    })
    mockMatches.mockResolvedValue([
      goldRow({ matchId: 'M1', items: { ids: [1], names: ['Hextech'], gold_value: 8000, stats: {} } }),
    ])

    renderView()

    expect(await screen.findByText(/Partidas analizadas/)).toBeTruthy()
    expect(screen.getByText(/Victorias: 6/)).toBeTruthy()
    expect(await screen.findByText('Hextech')).toBeTruthy()
    expect(await screen.findByText('Media')).toBeTruthy()
    expect(screen.getByText('Mediana')).toBeTruthy()
  })

  it('shows empty copy per panel when that panel 404s while others still load', async () => {
    mockReport.mockRejectedValue({ kind: 'not_found' })
    // matches resolves later; still present
    mockMatches.mockResolvedValue([goldRow({ matchId: 'M1' })])

    renderView()

    await waitFor(() => {
      expect(
        screen.getByText('Sin datos de oro todavía'),
      ).toBeTruthy()
    })
    // matches panel still renders independently
    expect(await screen.findByText('Hextech')).toBeTruthy()
  })

  it('hides the efficiency badge when gold_value is 0', async () => {
    mockReport.mockRejectedValue({ kind: 'not_found' })
    mockMatches.mockResolvedValue([
      goldRow({ matchId: 'M1', goldEarned: 10000, items: { ids: [1], names: ['Hextech'], gold_value: 0, stats: {} } }),
    ])

    renderView()

    await waitFor(() => {
      expect(screen.getByText('Hextech')).toBeTruthy()
    })
    expect(screen.queryByText('Eficiencia de oro')).toBeNull()
    expect(screen.queryByText('—')).toBeNull()
  })

  it('shows the efficiency badge when gold_value is nonzero', async () => {
    mockReport.mockRejectedValue({ kind: 'not_found' })
    mockMatches.mockResolvedValue([
      goldRow({ matchId: 'M1', goldEarned: 10000, items: { ids: [1], names: ['Hextech'], gold_value: 8000, stats: {} } }),
    ])

    renderView()

    await waitFor(() => {
      expect(screen.getByText('Eficiencia de oro')).toBeTruthy()
    })
    expect(screen.getByText(/1\.25/)).toBeTruthy()
  })
})
