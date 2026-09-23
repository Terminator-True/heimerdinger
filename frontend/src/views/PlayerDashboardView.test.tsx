import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

// MOCK_ENABLED is read from ../mocks by src/lib/playerData.ts at call time.
// Expose it as a getter over a mutable flag so a single test file can exercise
// both the mock and the real data paths.
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
  getPlayerMatchReport: vi.fn(),
}))

import {
  getPlayerMatchReport,
  getPlayerMatches,
  getPlayerReport,
} from '../lib/api'
import { PlayerDashboardView } from './PlayerDashboardView'

const PUUID = 'puuid-1'
const mockReport = vi.mocked(getPlayerReport)
const mockMatches = vi.mocked(getPlayerMatches)
const mockMatchReport = vi.mocked(getPlayerMatchReport)

function renderView() {
  return render(
    <MemoryRouter initialEntries={['/player/' + PUUID]}>
      <Routes>
        <Route path="/player/:puuid" element={<PlayerDashboardView />} />
      </Routes>
    </MemoryRouter>,
  )
}

function row(over: Partial<Record<string, unknown>> = {}) {
  return {
    player_puuid: PUUID,
    matchId: 'M1',
    championName: 'Ahri',
    role: 'MID',
    timestamp: null,
    win: undefined,
    parsed_metrics: {},
    ...over,
  }
}

function realReport(over: Partial<Record<string, unknown>> = {}) {
  return {
    player: 'Faker#KR1',
    role: 'Mid',
    champion: 'Ahri',
    games_analyzed: 20,
    metrics: { kda: 3.4, cs_per_min: 7.8 },
    pro_reference: null,
    deltas: {},
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  flags.mock = false
})

// --- Header (player overview) ---

describe('overview header section', () => {
  it('renders identity, role, champion and games/wins on success', async () => {
    mockReport.mockResolvedValue(realReport())
    mockMatches.mockResolvedValue([])

    renderView()

    expect(await screen.findByText('Faker#KR1')).toBeTruthy()
    expect(screen.getByText('Mid')).toBeTruthy()
    expect(screen.getByText('Ahri')).toBeTruthy()
    expect(screen.getByText(/20 partidas/)).toBeTruthy()
  })

  it('shows em-dash for missing role and champion', async () => {
    mockReport.mockResolvedValue(
      realReport({ role: null, champion: null, games_analyzed: 3 }),
    )
    mockMatches.mockResolvedValue([])

    renderView()

    await screen.findByText('Faker#KR1')
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
  })

  it('shows empty copy on not_found', async () => {
    mockReport.mockRejectedValue({ kind: 'not_found' })
    mockMatches.mockResolvedValue([])

    renderView()

    await waitFor(() => {
      expect(
        screen.getByText('Sin datos todavía. Ingresa partidas primero.'),
      ).toBeTruthy()
    })
  })

  it('shows ErrorState with retry on server error', async () => {
    mockReport.mockRejectedValue({ kind: 'server', status: 500 })
    mockMatches.mockResolvedValue([])

    renderView()

    expect(
      await screen.findByText(/El servidor no pudo procesar la solicitud/),
    ).toBeTruthy()

    mockReport.mockResolvedValue(realReport({ champion: 'Ahri' }))
    fireEvent.click(screen.getByText('Reintentar'))
    await waitFor(() => {
      expect(screen.getByText('Ahri')).toBeTruthy()
    })
  })
})

// --- Comparison seam (real mode has no endpoint yet) ---

describe('comparison seam', () => {
  it('degrades score/percentiles/strengths to empty when mock is off', async () => {
    mockReport.mockResolvedValue(realReport())
    mockMatches.mockResolvedValue([])

    renderView()

    await waitFor(() => {
      expect(
        screen.getAllByText('Comparativa no disponible todavía.'),
      ).toHaveLength(3)
    })
  })
})

// --- History (match list) ---

describe('match history section', () => {
  it('renders one card per row with metrics and win borders', async () => {
    mockReport.mockResolvedValue(realReport({ games_analyzed: 0 }))
    mockMatches.mockResolvedValue([
      row({ matchId: 'WIN', win: true, parsed_metrics: { kda: 5, cs_per_min: 8, goldEarned: 12000, gameDuration: 1800 } }),
      row({ matchId: 'LOSS', win: false, parsed_metrics: {} }),
      row({ matchId: 'UNKNOWN', parsed_metrics: {} }),
    ])

    renderView()

    await screen.findByRole('article', { name: 'WIN' })
    expect(
      screen.getByRole('article', { name: 'WIN' }).className,
    ).toContain('border-blue-400')
    expect(
      screen.getByRole('article', { name: 'LOSS' }).className,
    ).toContain('border-red-400')
    // unknown win flag → neutral border, no color class
    const neutral = screen.getByRole('article', { name: 'UNKNOWN' }).className
    expect(neutral).not.toContain('border-blue-400')
    expect(neutral).not.toContain('border-red-400')

    const card = within(screen.getByRole('article', { name: 'WIN' }))
    expect(card.getByText('Ahri')).toBeTruthy()
    expect(card.getByText('5')).toBeTruthy()
    expect(card.getByText('8')).toBeTruthy()
    expect(card.getByText('12000')).toBeTruthy()
    expect(card.getByText('30:00')).toBeTruthy()
  })

  it('derives the win flag from parsed_metrics when top-level is absent', async () => {
    mockReport.mockResolvedValue(realReport({ games_analyzed: 0 }))
    mockMatches.mockResolvedValue([
      row({ matchId: 'PM-WIN', parsed_metrics: { win: true } }),
      row({ matchId: 'PM-LOSS', parsed_metrics: { win: false } }),
    ])

    renderView()

    await screen.findByRole('article', { name: 'PM-WIN' })
    expect(
      screen.getByRole('article', { name: 'PM-WIN' }).className,
    ).toContain('border-blue-400')
    expect(
      screen.getByRole('article', { name: 'PM-LOSS' }).className,
    ).toContain('border-red-400')
  })

  it('shows em-dash for absent parsed_metrics fields', async () => {
    mockReport.mockResolvedValue(realReport({ games_analyzed: 0 }))
    mockMatches.mockResolvedValue([row({ matchId: 'EMPTY-M' })])

    renderView()

    const card = await screen.findByRole('article', { name: 'EMPTY-M' })
    expect(within(card).getAllByText('—').length).toBeGreaterThanOrEqual(4)
  })

  it('shows empty copy for an empty history', async () => {
    mockReport.mockRejectedValue({ kind: 'not_found' })
    mockMatches.mockResolvedValue([])

    renderView()

    const history = await screen.findByRole('region', {
      name: 'Historial de partidas',
    })
    await waitFor(() => {
      expect(within(history).getByText('Sin partidas todavía.')).toBeTruthy()
    })
  })

  it('shows error state with retry for a failed history fetch', async () => {
    mockReport.mockRejectedValue({ kind: 'not_found' })
    mockMatches.mockRejectedValue({ kind: 'network' })

    renderView()

    const history = await screen.findByRole('region', {
      name: 'Historial de partidas',
    })
    await waitFor(() => {
      expect(
        within(history).getByText('No se pudieron cargar las partidas.'),
      ).toBeTruthy()
      expect(within(history).getByText('Reintentar')).toBeTruthy()
    })

    mockMatches.mockResolvedValue([])
    fireEvent.click(within(history).getByText('Reintentar'))
    await waitFor(() => {
      expect(within(history).getByText('Sin partidas todavía.')).toBeTruthy()
    })
  })
})

// --- Empty puuid guard ---

describe('empty puuid guard', () => {
  it('fires zero fetches when the puuid param is empty', async () => {
    render(
      <MemoryRouter initialEntries={['/player/']}>
        <Routes>
          <Route path="/player/:puuid?" element={<PlayerDashboardView />} />
        </Routes>
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(mockReport).not.toHaveBeenCalled(),
    )
    expect(mockMatches).not.toHaveBeenCalled()
  })
})

// --- Detail modal ---

describe('match detail modal', () => {
  async function openModal() {
    mockReport.mockRejectedValue({ kind: 'not_found' })
    mockMatches.mockResolvedValue([row({ matchId: 'MODAL-1' })])
    renderView()
    const btn = await screen.findByText('Ver detalles')
    fireEvent.click(btn)
  }

  it('fetches the match report and renders details on success', async () => {
    mockMatchReport.mockResolvedValue({
      player: 'Faker#KR1',
      matchId: 'MODAL-1',
      champion: 'Azir',
      games_analyzed: 1,
      metrics: { kda: 6.5 },
      role: 'Mid',
    })

    await openModal()

    await waitFor(() => {
      expect(mockMatchReport).toHaveBeenCalledWith(PUUID, 'MODAL-1')
    })
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Azir')).toBeTruthy()
    expect(within(dialog).getByText('Mid')).toBeTruthy()
    expect(within(dialog).getByText('6.5')).toBeTruthy()
  })

  it('shows fallback copy on error or not_found', async () => {
    mockMatchReport.mockRejectedValue({ kind: 'not_found' })
    await openModal()
    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByText('Detalle de partida no disponible'),
    ).toBeTruthy()
  })

  it('closes via Escape', async () => {
    mockMatchReport.mockRejectedValue({ kind: 'not_found' })
    await openModal()
    await screen.findByRole('dialog')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('closes via the X button and backdrop click', async () => {
    mockMatchReport.mockRejectedValue({ kind: 'not_found' })
    await openModal()
    await screen.findByRole('dialog')

    fireEvent.click(screen.getByLabelText('Cerrar'))
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(await screen.findByText('Ver detalles'))
    await screen.findByRole('dialog')
    fireEvent.click(screen.getByTestId('modal-backdrop'))
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

// --- Mock mode (VITE_MOCK=true) ---

describe('mock mode', () => {
  beforeEach(() => {
    flags.mock = true
  })

  it('renders the score, percentile, strengths/weaknesses and trend chart', async () => {
    renderView()

    const score = await screen.findByRole('region', { name: 'Puntaje' })
    expect(within(score).getByText(/Basado en 20 partidas/)).toBeTruthy()

    const percentiles = screen.getByRole('region', { name: 'Percentiles' })
    expect(within(percentiles).getByText('Visión/min')).toBeTruthy()
    expect(within(percentiles).getByText('Control wards')).toBeTruthy()
    expect(within(percentiles).getByText('CS/min')).toBeTruthy()
    expect(within(percentiles).getByText('KP')).toBeTruthy()
    expect(within(percentiles).getByText('Daño/min')).toBeTruthy()
    expect(within(percentiles).getByText('KDA')).toBeTruthy()

    const strengths = screen.getByRole('region', { name: 'Fortalezas' })
    const weaknesses = screen.getByRole('region', { name: 'A mejorar' })
    expect(within(strengths).getByText('KDA')).toBeTruthy()
    expect(within(weaknesses).getByText('CS/min')).toBeTruthy()
    expect(within(weaknesses).getByText('Daño/min')).toBeTruthy()

    const trend = screen.getByRole('region', { name: 'Tendencia' })
    expect(within(trend).getByRole('combobox', { name: 'Métrica' })).toBeTruthy()
    expect(within(trend).getByText(/Mediana pro/)).toBeTruthy()
  })

  it('uses the fixture without touching the real endpoints', async () => {
    renderView()

    expect(await screen.findByText('TR Terminator#1998')).toBeTruthy()
    expect(await screen.findByRole('article', { name: 'DEMO-020' })).toBeTruthy()
    expect(mockReport).not.toHaveBeenCalled()
    expect(mockMatches).not.toHaveBeenCalled()
  })

  it('updates the pro median when the trend metric changes', async () => {
    renderView()

    const trend = await screen.findByRole('region', { name: 'Tendencia' })
    // Default metric is Visión/min → pro median 2.40.
    expect(within(trend).getByText(/Mediana pro: 2\.40/)).toBeTruthy()

    fireEvent.change(within(trend).getByRole('combobox', { name: 'Métrica' }), {
      target: { value: 'kda' },
    })
    expect(within(trend).getByText(/Mediana pro: 2\.80/)).toBeTruthy()
  })
})
