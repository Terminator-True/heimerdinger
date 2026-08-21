import { useCallback, useEffect, useState, type DependencyList } from 'react'
import type { ApiError } from '../lib/api'

export type QueryState<T> =
  | { phase: 'loading' }
  | { phase: 'error'; error: ApiError }
  | { phase: 'empty' }
  | { phase: 'success'; data: T }

// Empty is normal control flow. A payload is empty when the parsed array has
// zero rows OR when a report object carries status:"empty".
export function isEmptyPayload(data: unknown): boolean {
  if (Array.isArray(data)) return data.length === 0
  if (
    typeof data === 'object' &&
    data !== null &&
    (data as { status?: unknown }).status === 'empty'
  ) {
    return true
  }
  return false
}

interface QueryResult<T> {
  state: QueryState<T>
  retry: () => void
}

// Generic 4-state data hook (loading|error|empty|success). The fetcher runs
// whenever `deps` change or retry() is called; stale responses are dropped.
// `opts.enabled === false` skips the request entirely (zero fetches) — used to
// gate on inputs like a missing puuid.
export function useApiQuery<T>(
  fetcher: () => Promise<T>,
  deps: DependencyList,
  opts?: { enabled?: boolean },
): QueryResult<T> {
  const [state, setState] = useState<QueryState<T>>({ phase: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (opts?.enabled === false) return
    let cancelled = false
    setState({ phase: 'loading' })
    fetcher()
      .then((data) => {
        if (!cancelled) {
          setState(
            isEmptyPayload(data)
              ? { phase: 'empty' }
              : { phase: 'success', data },
          )
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          // 404 means "no data yet", never an app error.
          setState(
            isApiError(err) && err.kind === 'not_found'
              ? { phase: 'empty' }
              : {
                  phase: 'error',
                  error: isApiError(err)
                    ? err
                    : { kind: 'network' },
                },
          )
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetcher identity changes per render; deps are the contract
  }, [...deps, attempt, opts?.enabled])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { state, retry }
}

function isApiError(err: unknown): err is ApiError {
  return typeof err === 'object' && err !== null && 'kind' in err
}
