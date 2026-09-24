import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

// MOCK_ENABLED is read lazily by src/lib/playerData.ts, so a getter over a
// mutable flag lets this file run against the fixture without real fetches.
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
  getPlayerMatches: vi.fn(),
  getPlayerComparison: vi.fn(),
  getMatchTimeline: vi.fn(),
}))

import { buildMockTimeline } from '../mocks'
import { valueAtMinute } from '../lib/timeline'
import { getMatchTimeline, getPlayerComparison, getPlayerMatches } from '../lib/api'
import { PlayerMatchesView } from './PlayerMatchesView'

const PUUID = 'puuid-1'

const REAL_MATCH = {
  player_puuid: PUUID,
  matchId: 'M-1',
  championName: 'Ahri',
  role: 'MID',
  timestamp: 1_700_000_000_000,
  parsed_metrics: { win: true, kda: 2, cs_per_min: 1, goldEarned: 9000, gameDuration: 1700 },
}

function renderView() {
  return render(
    <MemoryRouter initialEntries={['/player/' + PUUID + '/matches']}>
      <Routes>
        <Route path="/player/:puuid/matches" element={<PlayerMatchesView />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  flags.mock = true
})

describe('PlayerMatchesView phase breakdown', () => {
  it('prompts until a match is selected, then renders the five phase sections', async () => {
    renderView()

    const card = await screen.findByRole('article', { name: 'DEMO-020' })
    expect(screen.getByText('Seleccioná una partida para ver el desglose.')).toBeTruthy()

    fireEvent.click(within(card).getByText('Ver detalles'))

    for (const label of ['Laning', 'Economía', 'Visión', 'Combate', 'Objetivos']) {
      expect(screen.getByRole('heading', { name: label })).toBeTruthy()
    }
  })

  it('selects a match inline without leaving the list', async () => {
    renderView()

    const card = await screen.findByRole('article', { name: 'DEMO-018' })
    fireEvent.click(within(card).getByText('Ver detalles'))

    // Still on the Partidas screen, breakdown swapped in on the right.
    expect(screen.getByRole('heading', { name: 'Partidas' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Desglose por fase · DEMO-018' })).toBeTruthy()
  })
})

describe('PlayerMatchesView filters', () => {
  it('narrows the list by champion', async () => {
    renderView()
    await screen.findByRole('article', { name: 'DEMO-020' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Campeón' }), {
      target: { value: 'Leona' },
    })

    expect(screen.queryByRole('article', { name: 'DEMO-020' })).toBeNull()
    expect(screen.getByRole('article', { name: 'DEMO-018' })).toBeTruthy()
  })

  it('narrows the list by result', async () => {
    renderView()
    await screen.findByRole('article', { name: 'DEMO-020' })

    fireEvent.click(screen.getByRole('button', { name: 'Derrotas' }))

    expect(screen.queryByRole('article', { name: 'DEMO-020' })).toBeNull()
    expect(screen.getByRole('article', { name: 'DEMO-018' })).toBeTruthy()
  })

  it('combines champion and result filters', async () => {
    renderView()
    await screen.findByRole('article', { name: 'DEMO-020' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Campeón' }), {
      target: { value: 'Leona' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Victorias' }))

    expect(screen.queryByRole('article', { name: 'DEMO-018' })).toBeNull()
    expect(screen.getByRole('article', { name: 'DEMO-012' })).toBeTruthy()
  })
})

describe('PlayerMatchesView timeline curves', () => {
  async function selectMatch(id: string) {
    renderView()
    const card = await screen.findByRole('article', { name: id })
    fireEvent.click(within(card).getByText('Ver detalles'))
  }

  it('renders the Curvas panel with the chart and milestones', async () => {
    await selectMatch('DEMO-020')

    expect(screen.getByRole('heading', { name: 'Curvas' })).toBeTruthy()
    expect(screen.getByRole('img', { name: /Curva de Oro por minuto/ })).toBeTruthy()

    const expected = buildMockTimeline('DEMO-020')
    const goldAt10 = valueAtMinute(expected.series, 10, 'gold')
    const row = screen.getByRole('row', { name: /@10/ })
    expect(within(row).getByRole('cell', { name: String(goldAt10) })).toBeTruthy()
    expect(screen.getByRole('row', { name: /@15/ })).toBeTruthy()
    expect(screen.getByRole('row', { name: /@20/ })).toBeTruthy()
  })

  it('switches the plotted metric and the milestone values', async () => {
    await selectMatch('DEMO-020')

    const expected = buildMockTimeline('DEMO-020')
    const goldAt10 = valueAtMinute(expected.series, 10, 'gold')
    const csAt10 = valueAtMinute(expected.series, 10, 'cs')

    expect(screen.getByRole('columnheader', { name: 'Oro' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'CS' }))

    expect(screen.getByRole('columnheader', { name: 'CS' })).toBeTruthy()
    expect(screen.getByRole('img', { name: /Curva de CS por minuto/ })).toBeTruthy()
    const row = screen.getByRole('row', { name: /@10/ })
    expect(within(row).getByRole('cell', { name: String(csAt10) })).toBeTruthy()
    expect(within(row).queryByRole('cell', { name: String(goldAt10) })).toBeNull()
  })

  it('shows the not-captured message when the timeline is missing', async () => {
    flags.mock = false
    vi.mocked(getPlayerMatches).mockResolvedValue([REAL_MATCH])
    vi.mocked(getPlayerComparison).mockRejectedValue({ kind: 'not_found' })
    vi.mocked(getMatchTimeline).mockRejectedValue({ kind: 'not_found' })

    await selectMatch('M-1')

    expect(await screen.findByText(/no fueron capturadas/)).toBeTruthy()
    expect(screen.getByText(/backfill_timelines\.py/)).toBeTruthy()
  })
})
