import { useEffect, useState } from 'react'
import { getBaseUrl } from '../lib/settings'

export type HealthStatus = 'online' | 'degraded' | 'offline'

// Pure classification so the status rules are testable without fetch mocks.
export function classifyHealth(
  httpStatus: number | null,
  mongodb: boolean | null,
): HealthStatus {
  if (httpStatus === null || !httpStatus.toString().startsWith('2')) {
    return 'offline'
  }
  return mongodb === true ? 'online' : 'degraded'
}

const POLL_INTERVAL_MS = 30_000

/**
 * Polls GET /health on mount and every 30s. Network failures and non-200
 * responses degrade to 'offline' instead of crashing the shell.
 */
export function useHealthPoll(): { status: HealthStatus } {
  const [status, setStatus] = useState<HealthStatus>('offline')

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const res = await fetch(`${getBaseUrl()}/health`)
        const body = res.ok
          ? ((await res.json()) as { mongodb?: unknown })
          : null
        const mongodb =
          body && typeof body.mongodb === 'boolean' ? body.mongodb : null
        const next = classifyHealth(res.ok ? res.status : null, mongodb)
        if (!cancelled) setStatus(next)
      } catch {
        // Backend down is normal control flow for the indicator, not a crash.
        if (!cancelled) setStatus('offline')
      }
    }

    void poll()
    const id = setInterval(() => void poll(), POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return { status }
}
