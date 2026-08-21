import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

vi.mock('../lib/api', () => ({
  getTeam: vi.fn(),
  ingestTeam: vi.fn(),
}))

import { getTeam, ingestTeam } from '../lib/api'
import { TeamView } from './TeamView'

const mockGetTeam = vi.mocked(getTeam)
const mockIngest = vi.mocked(ingestTeam)

const ROSTER = [
  { riotid: 'PlayerA#NA1', role: 'top' },
  { riotid: 'PlayerB#NA1', role: 'mid' },
]

function renderView() {
  return render(<TeamView />)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('roster overview', () => {
  it('lists riotid and role for each roster player', async () => {
    mockGetTeam.mockResolvedValue(ROSTER)
    renderView()
    expect(await screen.findByText('PlayerA#NA1')).toBeTruthy()
    expect(screen.getByText('top')).toBeTruthy()
    expect(screen.getByText('PlayerB#NA1')).toBeTruthy()
    expect(screen.getByText('mid')).toBeTruthy()
  })

  it('shows empty copy for an empty roster', async () => {
    mockGetTeam.mockResolvedValue([])
    renderView()
    expect(
      await screen.findByText('El equipo no tiene jugadores todavía.'),
    ).toBeTruthy()
  })

  it('shows empty copy on 404 (no team config)', async () => {
    mockGetTeam.mockRejectedValue({ kind: 'not_found' })
    renderView()
    expect(
      await screen.findByText('El equipo no tiene jugadores todavía.'),
    ).toBeTruthy()
  })
})

describe('team ingest form', () => {
  it('ingests the default team.json and shows a partial-failure split', async () => {
    mockGetTeam.mockResolvedValue(ROSTER)
    mockIngest.mockResolvedValue({
      team_puuids_resolved: 2,
      players: [
        { riotid: 'PlayerA#NA1' },
        { riotid: 'PlayerB#NA1', error: 'no matches found' },
      ],
    })
    renderView()
    await screen.findByText('PlayerA#NA1')

    fireEvent.click(screen.getByRole('button', { name: /ingestar equipo/i }))

    const success = await screen.findByRole('list', { name: /ingestados/i })
    expect(within(success).getByText('PlayerA#NA1')).toBeTruthy()

    const failed = screen.getByRole('list', { name: /con error/i })
    expect(within(failed).getByText('PlayerB#NA1')).toBeTruthy()
    expect(within(failed).getByText('no matches found')).toBeTruthy()
    expect(mockIngest).toHaveBeenCalledWith(
      expect.objectContaining({ teamPath: 'team.json' }),
      expect.anything(),
    )
  })

  it('disables submit and shows a cancel button while in flight', async () => {
    mockGetTeam.mockResolvedValue(ROSTER)
    let resolveIngest: (v: unknown) => void
    mockIngest.mockReturnValue(
      new Promise((resolve) => {
        resolveIngest = resolve
      }) as never,
    )
    renderView()
    await screen.findByText('PlayerA#NA1')

    fireEvent.click(screen.getByRole('button', { name: /ingestar equipo/i }))

    expect(
      screen.getByRole('button', { name: /ingestar equipo/i }).hasAttribute('disabled'),
    ).toBe(true)
    const cancel = await screen.findByRole('button', { name: 'Cancelar' })
    expect(cancel).toBeTruthy()

    resolveIngest!({ team_puuids_resolved: 1, players: [] })
    await waitFor(() =>
      expect(
        screen
          .getByRole('button', { name: /ingestar equipo/i })
          .hasAttribute('disabled'),
      ).toBe(false),
    )
  })
})
