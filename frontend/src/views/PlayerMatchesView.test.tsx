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
}))

import { PlayerMatchesView } from './PlayerMatchesView'

const PUUID = 'puuid-1'

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
