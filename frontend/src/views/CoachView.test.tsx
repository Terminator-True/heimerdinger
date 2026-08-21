import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

vi.mock('../lib/api', () => ({
  askCoach: vi.fn(),
}))

import { askCoach } from '../lib/api'
import { CoachView } from './CoachView'

const mockAsk = vi.mocked(askCoach)

function renderView() {
  return render(<CoachView />)
}

function typeAndSend(text: string) {
  fireEvent.change(screen.getByPlaceholderText(/escribí/i), {
    target: { value: text },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('coach chat', () => {
  it('renders a user message and sanitized assistant response as plain text', async () => {
    mockAsk.mockResolvedValue({ response: 'Hola' })
    renderView()
    typeAndSend('¿Cómo estoy?')
    expect(await screen.findByText('Hola')).toBeTruthy()
    expect(screen.getByText('¿Cómo estoy?')).toBeTruthy()
  })

  it('accumulates full prior history on each request', async () => {
    mockAsk.mockResolvedValue({ response: 'Primera' })
    renderView()
    typeAndSend('Pregunta uno')
    await screen.findByText('Primera')

    mockAsk.mockResolvedValue({ response: 'Segunda' })
    typeAndSend('Pregunta dos')
    await screen.findByText('Segunda')

    const calls = mockAsk.mock.calls
    expect(calls.length).toBe(2)
    // Second request sends history = both prior turns (user + assistant).
    expect(calls[1]![0].history).toEqual([
      { role: 'user', content: 'Pregunta uno' },
      { role: 'assistant', content: 'Primera' },
    ])
    // First request sends empty history.
    expect(calls[0]![0].history).toEqual([])
  })

  it('sends lastMatch flag when the toggle is on', async () => {
    mockAsk.mockResolvedValue({ response: 'ok' })
    renderView()
    fireEvent.click(screen.getByLabelText(/última partida/i))
    typeAndSend('¿Qué jugué?')
    await screen.findByText('ok')
    expect(mockAsk.mock.calls[0]![0].lastMatch).toBe(true)
  })

  it('blocks a blank question from submitting', async () => {
    renderView()
    const input = screen.getByPlaceholderText(/escribí/i)
    fireEvent.change(input, { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(mockAsk).not.toHaveBeenCalled()
  })

  it('keeps the prior conversation intact and shows copy on timeout', async () => {
    mockAsk.mockResolvedValue({ response: 'Primera' })
    renderView()
    typeAndSend('Pregunta uno')
    await screen.findByText('Primera')

    mockAsk.mockRejectedValue({ kind: 'timeout', timeoutMs: 120000 })
    typeAndSend('Pregunta dos')
    expect(
      await screen.findByText('Ollama tardó demasiado. Probá de nuevo.'),
    ).toBeTruthy()
    // Prior assistant reply still rendered.
    expect(screen.getByText('Primera')).toBeTruthy()
    expect(screen.getByText('Pregunta uno')).toBeTruthy()
  })

  it('shows server copy and retry affordance on a server error', async () => {
    mockAsk.mockRejectedValue({ kind: 'server', status: 502 })
    renderView()
    typeAndSend('Hola')
    expect(
      await screen.findByText('Verificá que Ollama esté corriendo localmente.'),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: /reintentar/i })).toBeTruthy()
  })

  it('fills and sends on a quick prompt', async () => {
    mockAsk.mockResolvedValue({ response: 'respuesta' })
    renderView()
    fireEvent.click(screen.getByRole('button', { name: /en qué fallé/i }))
    await screen.findByText('respuesta')
    expect(mockAsk.mock.calls[0]![0].question).toContain('fallé')
  })

  it('sends the failed question ONCE in the retry body and shows it once in the list', async () => {
    mockAsk
      .mockRejectedValueOnce({ kind: 'server', status: 502 })
      .mockResolvedValueOnce({ response: 'ok' })
    renderView()
    typeAndSend('Pregunta duplicada?')
    // Error banner appears; the failed question is NOT in the message list yet.
    expect(
      await screen.findByText('Verificá que Ollama esté corriendo localmente.'),
    ).toBeTruthy()
    expect(screen.queryByText('Pregunta duplicada?')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    await screen.findByText('ok')

    expect(mockAsk).toHaveBeenCalledTimes(2)
    // Retry body sends the question exactly once, history unchanged (still empty).
    expect(mockAsk.mock.calls[1]![0].question).toBe('Pregunta duplicada?')
    expect(mockAsk.mock.calls[1]![0].history).toEqual([])
    // Message list shows the question exactly once.
    expect(screen.getAllByText('Pregunta duplicada?')).toHaveLength(1)
  })

  it('does not dispatch a second request while busy', async () => {
    let resolveAsk: (v: unknown) => void
    mockAsk.mockReturnValue(
      new Promise((resolve) => {
        resolveAsk = resolve
      }) as never,
    )
    renderView()
    typeAndSend('Primera')
    expect(screen.getByText('El coach está pensando…')).toBeTruthy()
    typeAndSend('Segunda')
    expect(mockAsk).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveAsk!({ response: 'listo' })
    })
  })

  it('aborts the in-flight fetch on unmount', async () => {
    mockAsk.mockImplementation(
      (_params: unknown, opts?: { signal?: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          const onAbort = () => reject(new DOMException('aborted', 'AbortError'))
          opts?.signal?.addEventListener('abort', onAbort, { once: true })
        }),
    )
    const { unmount } = renderView()
    typeAndSend('Pregunta')
    expect(mockAsk).toHaveBeenCalledTimes(1)

    await act(async () => {
      unmount()
    })
    expect(mockAsk.mock.calls[0]![1]?.signal?.aborted).toBe(true)
  })

  it('renders a hostile coach response as escaped text, never as an element', async () => {
    const hostile = '<img src=x onerror=alert(1)>'
    mockAsk.mockResolvedValue({ response: hostile })
    renderView()
    typeAndSend('Hola')
    expect(await screen.findByText(hostile)).toBeTruthy()
    expect(document.querySelector('img')).toBeNull()
  })
})
