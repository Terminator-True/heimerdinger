import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { INGEST_TIMEOUT_MS } from '../lib/api'
import { LandingView } from './LandingView'

vi.mock('../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/api')>()),
  ingestPlayer: vi.fn(),
}))

import { ingestPlayer } from '../lib/api'

const mockIngest = vi.mocked(ingestPlayer)

function LocationProbe() {
  const loc = useLocation()
  return <span data-testid="pathname">{loc.pathname}</span>
}

function renderView() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<><LandingView /><LocationProbe /></>} />
        <Route path="/player/:puuid" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

function fillForm(riotId = 'Faker#KR1', count = '') {
  fireEvent.change(screen.getByLabelText(/Riot ID/), {
    target: { value: riotId },
  })
  if (count !== '') {
    fireEvent.change(screen.getByLabelText(/Cantidad de partidas/), {
      target: { value: count },
    })
  }
}

const INGEST_OK = {
  puuid: 'PU-1',
  matches_fetched: 3,
  matches_saved: 3,
  matches_skipped: 0,
  matches_discarded: 0,
  matches_parse_errors: 0,
  matches_fetch_errors: 0,
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('LandingView ingest contract', () => {
  it('(a) double-click during flight sends zero extra requests', async () => {
    mockIngest.mockImplementation(() => new Promise(() => {})) // hang in flight
    renderView()
    fillForm()

    const submit = screen.getByRole('button', { name: 'Buscar y sincronizar' })
    fireEvent.submit(submit)
    await waitFor(() => expect(mockIngest).toHaveBeenCalledTimes(1))

    fireEvent.submit(submit) // second attempt must be a no-op
    expect(mockIngest).toHaveBeenCalledTimes(1)
  })

  it('(b) blocks out-of-bounds counts (0 and 101) BEFORE calling ingestPlayer', async () => {
    mockIngest.mockResolvedValue(INGEST_OK)
    renderView()

    // count 0 → blocked client-side, error on the count field
    fillForm('Faker#KR1', '0')
    fireEvent.submit(screen.getByRole('button', { name: 'Buscar y sincronizar' }))
    expect(
      await screen.findByText('La cantidad debe estar entre 1 y 100.'),
    ).toBeTruthy()

    // count 101 → blocked the same way
    fillForm('Faker#KR1', '101')
    fireEvent.submit(screen.getByRole('button', { name: 'Buscar y sincronizar' }))
    expect(
      await screen.findByText('La cantidad debe estar entre 1 y 100.'),
    ).toBeTruthy()

    // neither reached the network
    expect(mockIngest).not.toHaveBeenCalled()
  })

  it('(c) success navigates to /player/{returned puuid}', async () => {
    mockIngest.mockResolvedValue(INGEST_OK)
    renderView()
    fillForm()

    fireEvent.submit(screen.getByRole('button', { name: 'Buscar y sincronizar' }))

    await waitFor(() =>
      expect(screen.getByTestId('pathname').textContent).toBe('/player/PU-1'),
    )
  })

  it('(d) HTTP 422 renders fieldErrors on riotid/count fields and stays on /', async () => {
    mockIngest.mockRejectedValue({
      kind: 'validation',
      fieldErrors: {
        riotid: 'Formato inválido',
        count: 'Input should be less than or equal to 100',
      },
    })
    renderView()
    // count must be in bounds (1-100) so the request actually fires and the
    // mocked backend 422 (fieldErrors) path is exercised.
    fillForm('bad-format', '5')

    fireEvent.submit(screen.getByRole('button', { name: 'Buscar y sincronizar' }))

    expect(await screen.findByText('Formato inválido')).toBeTruthy()
    expect(
      screen.getByText('Input should be less than or equal to 100'),
    ).toBeTruthy()
    expect(screen.getByTestId('pathname').textContent).toBe('/')
  })

  it('stalled fetch past INGEST_TIMEOUT_MS shows the timeout error state and re-enables the form', async () => {
    // ingestPlayer hangs; the view surfaces the timeout error the shared
    // ingest cap (api.request → INGEST_TIMEOUT_MS) produces as {kind:'timeout'}.
    let reject!: (e: unknown) => void
    mockIngest.mockImplementation(
      () => new Promise((_res, rej) => { reject = rej }),
    )
    renderView()
    fillForm()

    const submit = screen.getByRole('button', { name: 'Buscar y sincronizar' })
    fireEvent.submit(submit)
    expect(submit.hasAttribute('disabled')).toBe(true)

    await act(async () =>
      reject({ kind: 'timeout', timeoutMs: INGEST_TIMEOUT_MS }),
    )

    await waitFor(() =>
      expect(
        screen.getByText(/La búsqueda tardó demasiado/),
      ).toBeTruthy(),
    )
    expect(screen.getByRole('button', { name: 'Buscar y sincronizar' }).hasAttribute('disabled')).toBe(false)
  })

  it('Cancelar aborts the in-flight request and re-enables the form without an error banner', async () => {
    let capturedSignal: AbortSignal | undefined
    let reject!: (e: unknown) => void
    mockIngest.mockImplementation((_params, opts) => {
      capturedSignal = opts?.signal
      opts?.signal?.addEventListener('abort', () =>
        reject(new DOMException('The operation was aborted.', 'AbortError')),
      )
      return new Promise((_res, rej) => { reject = rej }) // settles only on abort
    })
    renderView()
    fillForm()

    fireEvent.submit(screen.getByRole('button', { name: 'Buscar y sincronizar' }))
    const cancel = await screen.findByRole('button', { name: 'Cancelar' })
    expect(capturedSignal).toBeDefined()

    fireEvent.click(cancel)
    await waitFor(() => expect(capturedSignal?.aborted).toBe(true))
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Buscar y sincronizar' }).hasAttribute('disabled'),
      ).toBe(false),
    )
    expect(screen.queryByText(/error/i)).toBeNull()
  })

  it('validation fieldErrors matching no rendered field surface in the form-level banner', async () => {
    mockIngest.mockRejectedValue({
      kind: 'validation',
      fieldErrors: { team_puuids: 'Input should be a valid string' },
    })
    renderView()
    fillForm()

    fireEvent.submit(screen.getByRole('button', { name: 'Buscar y sincronizar' }))

    expect(
      await screen.findByText('Input should be a valid string'),
    ).toBeTruthy()
    expect(screen.getByTestId('pathname').textContent).toBe('/')
  })
})
