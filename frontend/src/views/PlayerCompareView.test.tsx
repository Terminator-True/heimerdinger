import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const flags = vi.hoisted(() => ({ mock: false }))

vi.mock('../mocks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../mocks')>()
  return {
    ...actual,
    get MOCK_ENABLED() {
      return flags.mock
    },
  }
})

vi.mock('../lib/api', () => ({
  getPlayerReport: vi.fn(),
  getPlayerComparison: vi.fn(),
  getPlayerMatches: vi.fn(),
}))

import { getPlayerComparison } from '../lib/api'
import { PlayerCompareView } from './PlayerCompareView'

const PUUID = 'puuid-1'
const mockComparison = vi.mocked(getPlayerComparison)

function renderView() {
  return render(
    <MemoryRouter initialEntries={['/player/' + PUUID + '/compare']}>
      <Routes>
        <Route path="/player/:puuid/compare" element={<PlayerCompareView />} />
      </Routes>
    </MemoryRouter>,
  )
}

function rowLabels(): string[] {
  return screen.getAllByRole('rowheader').map((n) => n.textContent ?? '')
}

beforeEach(() => {
  vi.clearAllMocks()
  flags.mock = true
})

describe('PlayerCompareView table', () => {
  it('renders the table with the payload-derived baseline caption and columns', () => {
    renderView()

    expect(
      screen.getByText(/Baseline: Oracle's Elixir — Support, 2025 · 4\.820 partidas/),
    ).toBeTruthy()

    for (const header of ['Métrica', 'Tú', 'Mediana pro', 'p25', 'p75', 'Percentil']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeTruthy()
    }
    expect(screen.getByRole('columnheader', { name: /Delta/ })).toBeTruthy()
    expect(screen.getByRole('rowheader', { name: 'KDA' })).toBeTruthy()
  })
})

describe('PlayerCompareView filters', () => {
  it('filters rows by phase chip', () => {
    renderView()
    expect(screen.getByRole('rowheader', { name: 'KDA' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Visión' }))

    expect(screen.queryByRole('rowheader', { name: 'KDA' })).toBeNull()
    expect(screen.getByRole('rowheader', { name: 'Visión/min' })).toBeTruthy()
    expect(screen.getByRole('rowheader', { name: 'Control wards' })).toBeTruthy()
    expect(screen.getByRole('rowheader', { name: 'Wards' })).toBeTruthy()
  })

  it('hides positive rows with "solo brechas negativas"', () => {
    renderView()
    expect(screen.getByRole('rowheader', { name: 'KDA' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Solo brechas negativas' }))

    expect(screen.queryByRole('rowheader', { name: 'KDA' })).toBeNull()
    expect(screen.queryByRole('rowheader', { name: 'Visión/min' })).toBeNull()
    expect(screen.getByRole('rowheader', { name: 'CS/min' })).toBeTruthy()
    expect(screen.getByRole('rowheader', { name: 'Daño/min' })).toBeTruthy()
  })
})

describe('PlayerCompareView sort', () => {
  it('reorders rows when the Delta header is toggled', () => {
    renderView()
    const before = rowLabels()

    fireEvent.click(screen.getByRole('button', { name: /Delta/ }))

    const after = rowLabels()
    expect(after).not.toEqual(before)
    expect([...after].sort()).toEqual([...before].sort())
  })
})

describe('PlayerCompareView real mode', () => {
  it('shows the empty message when the comparison endpoint is absent', async () => {
    flags.mock = false
    mockComparison.mockRejectedValue({ kind: 'not_found' })
    renderView()

    // Real mode resolves asynchronously (404-as-empty), so await the state.
    expect(await screen.findByText('Comparativa no disponible todavía.')).toBeTruthy()
  })
})
