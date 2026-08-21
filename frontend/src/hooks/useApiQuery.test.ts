import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useApiQuery, isEmptyPayload } from './useApiQuery'

function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('isEmptyPayload', () => {
  it('flags empty arrays as empty', () => {
    expect(isEmptyPayload([])).toBe(true)
  })

  it('does not flag non-empty arrays', () => {
    expect(isEmptyPayload([{ a: 1 }])).toBe(false)
  })

  it('flags report payloads with status "empty"', () => {
    expect(isEmptyPayload({ status: 'empty' })).toBe(true)
  })

  it('does not flag other objects', () => {
    expect(isEmptyPayload({ status: 'ok' })).toBe(false)
    expect(isEmptyPayload({ games_analyzed: 3 })).toBe(false)
    expect(isEmptyPayload(null)).toBe(false)
  })
})

describe('useApiQuery', () => {
  it('starts loading and settles into success with data', async () => {
    const d = deferred<{ n: number }>()
    const fetcher = vi.fn(() => d.promise)

    const { result } = renderHook(() => useApiQuery(fetcher, []))
    expect(result.current.state.phase).toBe('loading')

    await act(async () => d.resolve({ n: 1 }))
    await waitFor(() => expect(result.current.state.phase).toBe('success'))
    if (result.current.state.phase === 'success') {
      expect(result.current.state.data).toEqual({ n: 1 })
    }
  })

  it('maps not_found errors to the empty state (404-as-empty)', async () => {
    const d = deferred<never>()
    const { result } = renderHook(() => useApiQuery<never>(() => d.promise, []))

    await act(async () => d.reject({ kind: 'not_found' }))
    await waitFor(() => expect(result.current.state.phase).toBe('empty'))
  })

  it('maps an empty parsed array to empty without calling it success', async () => {
    const d = deferred<string[]>()
    const { result } = renderHook(() => useApiQuery(() => d.promise, []))

    await act(async () => d.resolve([]))
    await waitFor(() => expect(result.current.state.phase).toBe('empty'))
  })

  it('maps a status:"empty" payload to empty', async () => {
    const d = deferred<{ status: string }>()
    const { result } = renderHook(() => useApiQuery(() => d.promise, []))

    await act(async () => d.resolve({ status: 'empty' }))
    await waitFor(() => expect(result.current.state.phase).toBe('empty'))
  })

  it('surfaces non-404 errors in the error state', async () => {
    const d = deferred<never>()
    const { result } = renderHook(() => useApiQuery<never>(() => d.promise, []))

    await act(async () =>
      d.reject({ kind: 'network' }),
    )
    await waitFor(() => expect(result.current.state.phase).toBe('error'))
    if (result.current.state.phase === 'error') {
      expect(result.current.state.error).toEqual({ kind: 'network' })
    }
  })

  it('retry re-runs the fetcher after a failure', async () => {
    const d1 = deferred<{ ok: boolean }>()
    const d2 = deferred<{ ok: boolean }>()
    const promises = [
      { ...d1, reject: d1.reject as (e: unknown) => void },
      d2,
    ]
    let call = 0
    const fetcher = vi.fn(() => {
      const p = promises[Math.min(call, promises.length - 1)]!
      call += 1
      return p.promise as Promise<{ ok: boolean }>
    })
    const { result } = renderHook(() => useApiQuery(fetcher, []))

    await act(async () => promises[0]!.reject({ kind: 'server', status: 500 }))
    await waitFor(() => expect(result.current.state.phase).toBe('error'))

    act(() => result.current.retry())
    await waitFor(() => expect(result.current.state.phase).toBe('loading'))

    await act(async () => promises[1]!.resolve({ ok: true }))
    await waitFor(() => expect(result.current.state.phase).toBe('success'))
  })

  it('re-runs when deps change and ignores stale responses', async () => {
    const a = deferred<string>()
    const b = deferred<string>()
    let next = a.promise
    const fetcher = vi.fn(() => next)
    const { result, rerender } = renderHook(
      ({ dep }: { dep: string }) => useApiQuery(fetcher, [dep]),
      { initialProps: { dep: 'a' } },
    )

    // Switch deps while the first request is still in flight.
    next = b.promise
    rerender({ dep: 'b' })
    await act(async () => {
      a.resolve('stale')
      b.resolve('fresh')
    })

    await waitFor(() => expect(result.current.state.phase).toBe('success'))
    if (result.current.state.phase === 'success') {
      expect(result.current.state.data).toBe('fresh')
    }
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('skips the fetch entirely when enabled is false (zero requests)', async () => {
    const fetcher = vi.fn(() => Promise.resolve({ n: 1 }))
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useApiQuery(fetcher, [], { enabled }),
      { initialProps: { enabled: false } },
    )

    rerender({ enabled: false })
    expect(fetcher).not.toHaveBeenCalled()

    // Flipping to true fires the request exactly once.
    rerender({ enabled: true })
    await waitFor(() => expect(result.current.state.phase).toBe('success'))
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
