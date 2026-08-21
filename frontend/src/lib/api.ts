import type { z, ZodType } from 'zod'
import { getApiKey, getBaseUrl } from './settings'
import {
  rootSchema,
  healthSchema,
  teamRosterSchema,
  ingestPlayerSchema,
  ingestTeamSchema,
  playerMatchesSchema,
  playerReportSchema,
  matchReportSchema,
  compositionSchema,
  snapshotSchema,
  matchGoldSchema,
  goldMatchesSchema,
  aggregateGoldSchema,
  coachResponseSchema,
  embeddingsQuerySchema,
  embeddingsSeedSchema,
} from '../schemas/endpoints'

export const DEFAULT_TIMEOUT_MS = 15_000
export const COACH_TIMEOUT_MS = 120_000

// Thrown (not returned) on every failure; views/hook branch on `kind`.
// not_found is normal control flow (404-as-empty), never a crash.
export type ApiError =
  | { kind: 'validation'; fieldErrors: Record<string, string> }
  | { kind: 'auth' }
  | { kind: 'not_found' }
  | { kind: 'server'; status: number }
  | { kind: 'network' }

type RequestOpts = {
  method?: 'GET' | 'POST'
  body?: unknown
  schema: ZodType
  timeoutMs?: number
}

// AbortController armed ONLY when timeoutMs is provided:
// - regular endpoints pass DEFAULT_TIMEOUT_MS (15s)
// - /ingest/player + /ingest/team + /embeddings/seed pass none → no abort
//   (sync ingestion can run minutes)
// - POST /coach passes COACH_TIMEOUT_MS — the 15s default MUST NOT arm there
//   because local Ollama inference routinely exceeds 15s.
export async function request<S extends ZodType>(
  path: string,
  opts: RequestOpts & { schema: S },
): Promise<z.output<S>> {
  const headers: Record<string, string> = {}
  const apiKey = getApiKey()
  if (apiKey) headers['x-api-key'] = apiKey
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'

  const controller = new AbortController()
  const timer =
    opts.timeoutMs !== undefined
      ? setTimeout(() => controller.abort(), opts.timeoutMs)
      : undefined

  let res: Response
  try {
    const init: RequestInit = {
      method: opts.method ?? 'GET',
      headers,
      signal: controller.signal,
    }
    if (opts.body !== undefined) init.body = JSON.stringify(opts.body)
    res = await fetch(getBaseUrl() + path, init)
  } catch {
    if (timer !== undefined) clearTimeout(timer)
    throw { kind: 'network' } satisfies ApiError
  }

  try {
    if (res.status === 401) {
      // Global contract consumed by SettingsProvider: opens the key dialog
      // from any view without redirect loops.
      window.dispatchEvent(new CustomEvent('heimerdinger:unauthorized'))
      throw { kind: 'auth' } satisfies ApiError
    }
    if (res.status === 404) throw { kind: 'not_found' } satisfies ApiError

    if (res.status === 422) {
      throw await toValidationError(res)
    }
    if (!res.ok) throw { kind: 'server', status: res.status } satisfies ApiError

    const raw: unknown = await res.json().catch(() => null)
    const parsed = opts.schema.safeParse(raw)
    if (!parsed.success) {
      // Bad shape on a healthy 200 = backend contract break; surface as a
      // validation error state, never crash the view.
      throw {
        kind: 'validation',
        fieldErrors: issuesToFieldErrors(parsed.error.issues),
      } satisfies ApiError
    }
    return parsed.data
  } finally {
    if (timer !== undefined) clearTimeout(timer)
  }
}

async function toValidationError(res: Response): Promise<ApiError> {
  // FastAPI HTTPValidationError: detail[] of {loc, msg}; key = last STRING
  // segment of loc (loc may end in an index like ['body','team_puuids',0]).
  const payload = (await res.json().catch(() => null)) as {
    detail?: Array<{ loc?: unknown[]; msg?: unknown }>
  } | null
  const fieldErrors: Record<string, string> = {}
  for (const item of payload?.detail ?? []) {
    if (!item || typeof item !== 'object' || typeof item.msg !== 'string') continue
    const loc = Array.isArray(item.loc) ? item.loc : []
    const lastString = [...loc].reverse().find((seg): seg is string => typeof seg === 'string')
    if (lastString !== undefined) fieldErrors[lastString] = item.msg
  }
  return { kind: 'validation', fieldErrors }
}

function issuesToFieldErrors(issues: Array<{ path: PropertyKey[]; message: string }>): Record<string, string> {
  const out: Record<string, string> = {}
  for (const issue of issues) {
    const lastString = [...issue.path].reverse().find((seg): seg is string => typeof seg === 'string')
    out[lastString ?? ''] = issue.message
  }
  return out
}

function get<S extends ZodType>(
  path: string,
  schema: S,
): ReturnType<typeof request<S>> {
  return request(path, { schema, timeoutMs: DEFAULT_TIMEOUT_MS })
}

// --- Endpoints (14 per explore inventory; camelCase args mapped to API snake_case bodies) ---

export function getRoot(): Promise<z.output<typeof rootSchema>> {
  return get('/', rootSchema)
}

export function getHealth(): Promise<z.output<typeof healthSchema>> {
  return get('/health', healthSchema)
}

export function getTeam(teamPath: string): Promise<z.output<typeof teamRosterSchema>> {
  return get(`/team?team_path=${encodeURIComponent(teamPath)}`, teamRosterSchema)
}

export function ingestPlayer(params: {
  riotId: string
  count?: number
  region?: string
  regionRep?: string
  teamPuuids?: string[]
  minTeamMembers?: number
}): Promise<z.output<typeof ingestPlayerSchema>> {
  return request('/ingest/player', {
    method: 'POST',
    body: {
      riotid: params.riotId,
      count: params.count,
      region: params.region,
      region_rep: params.regionRep,
      team_puuids: params.teamPuuids,
      min_team_members: params.minTeamMembers,
    },
    schema: ingestPlayerSchema,
    // no timeoutMs: sync ingest may run minutes
  })
}

export function ingestTeam(params: {
  teamPath?: string
  count?: number
  region?: string
  regionRep?: string
}): Promise<z.output<typeof ingestTeamSchema>> {
  return request('/ingest/team', {
    method: 'POST',
    body: {
      team_path: params.teamPath,
      count: params.count,
      region: params.region,
      region_rep: params.regionRep,
    },
    schema: ingestTeamSchema,
    // no timeoutMs
  })
}

export function getPlayerMatches(
  puuid: string,
  limit?: number,
): Promise<z.output<typeof playerMatchesSchema>> {
  const qs = limit === undefined ? '' : `?limit=${limit}`
  return get(`/players/${encodeURIComponent(puuid)}/matches${qs}`, playerMatchesSchema)
}

export function getPlayerReport(puuid: string): Promise<z.output<typeof playerReportSchema>> {
  return get(`/players/${encodeURIComponent(puuid)}/report`, playerReportSchema)
}

export function getPlayerMatchReport(
  puuid: string,
  matchId: string,
): Promise<z.output<typeof matchReportSchema>> {
  return get(
    `/players/${encodeURIComponent(puuid)}/matches/${encodeURIComponent(matchId)}/report`,
    matchReportSchema,
  )
}

export function getMatchComposition(
  matchId: string,
): Promise<z.output<typeof compositionSchema>> {
  return get(`/matches/${encodeURIComponent(matchId)}/composition`, compositionSchema)
}

export function getMatchSnapshot(matchId: string): Promise<z.output<typeof snapshotSchema>> {
  return get(`/matches/${encodeURIComponent(matchId)}/snapshot`, snapshotSchema)
}

export function getMatchGold(matchId: string): Promise<z.output<typeof matchGoldSchema>> {
  return get(`/matches/${encodeURIComponent(matchId)}/gold`, matchGoldSchema)
}

export function getGoldMatches(
  puuid: string,
  limit?: number,
): Promise<z.output<typeof goldMatchesSchema>> {
  const qs = limit === undefined ? '' : `?limit=${limit}`
  return get(`/players/${encodeURIComponent(puuid)}/gold/matches${qs}`, goldMatchesSchema)
}

export function getGoldReport(
  puuid: string,
  limit?: number,
): Promise<z.output<typeof aggregateGoldSchema>> {
  const qs = limit === undefined ? '' : `?limit=${limit}`
  return get(`/players/${encodeURIComponent(puuid)}/gold/report${qs}`, aggregateGoldSchema)
}

export function askCoach(params: {
  question: string
  role?: string
  model?: string
  lastMatch?: boolean
  lang?: string
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
}): Promise<z.output<typeof coachResponseSchema>> {
  return request('/coach', {
    method: 'POST',
    body: {
      question: params.question,
      role: params.role,
      model: params.model,
      last_match: params.lastMatch,
      lang: params.lang,
      history: params.history,
    },
    schema: coachResponseSchema,
    timeoutMs: COACH_TIMEOUT_MS,
  })
}

export function queryEmbeddings(params: {
  query: string
  topK?: number
  where?: Record<string, unknown>
}): Promise<z.output<typeof embeddingsQuerySchema>> {
  return request('/embeddings/query', {
    method: 'POST',
    body: { query: params.query, top_k: params.topK, where: params.where },
    schema: embeddingsQuerySchema,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  })
}

export function seedEmbeddings(): Promise<z.output<typeof embeddingsSeedSchema>> {
  // No timeout: full re-ingestion can run minutes (explore CRITICAL risk).
  return request('/embeddings/seed', { method: 'POST', schema: embeddingsSeedSchema })
}
