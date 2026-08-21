import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useHealthPoll, classifyHealth } from './useHealthPoll'

const POLL_MS = 30_000

describe('classifyHealth', () => {
  it('classifies 200 + mongodb=true as online', () => {
    expect(classifyHealth(200, true)).toBe('online')
  })

  it('classifies 200 with mongodb down as degraded', () => {
    expect(classifyHealth(200, false)).toBe('degraded')
  })

  it('classifies non-200 as offline', () => {
    expect(classifyHealth(503, true)).toBe('offline')
  })

  it('classifies missing response (network failure) as offline', () => {
    expect(classifyHealth(null, null)).toBe('offline')
  })
})

describe('useHealthPoll', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  function okResponse() {
    return new Response(JSON.stringify({ status: 'ok', mongodb: true }), {
      status: 200,
    })
  }

  it('polls /health on mount and reports online', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse())
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useHealthPoll())
    await waitFor(() => expect(result.current.status).toBe('online'))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]![0])).toContain('/health')
  })

  it('re-polls every 30 seconds', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse())
    vi.stubGlobal('fetch', fetchMock)

    renderHook(() => useHealthPoll())
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS)
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('survives a network failure and shows offline', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('backend down'))
      .mockResolvedValue(okResponse())
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useHealthPoll())
    await waitFor(() => expect(result.current.status).toBe('offline'))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS)
    })
    await waitFor(() => expect(result.current.status).toBe('online'))
  })

  it('flags degraded when mongodb is false in a healthy response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', mongodb: false }), {
        status: 200,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useHealthPoll())
    await waitFor(() => expect(result.current.status).toBe('degraded'))
  })
})
