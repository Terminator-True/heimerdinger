import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import {
  DEFAULT_TIMEOUT_MS,
  COACH_TIMEOUT_MS,
  request,
  getRoot,
  getHealth,
  getTeam,
  getPlayerMatches,
  getPlayerReport,
  getPlayerMatchReport,
  getMatchComposition,
  getMatchSnapshot,
  getMatchGold,
  getGoldMatches,
  getGoldReport,
  askCoach,
  ingestPlayer,
  ingestTeam,
  queryEmbeddings,
  seedEmbeddings,
  type ApiError,
} from './api'
import { saveApiKey } from './settings'

// Minimal response stub: request() only consumes ok/status/json.
type FakeInit = {
  headers: Record<string, string>
  body?: string
  signal?: AbortSignal
}

let fetchMock: ReturnType<typeof vi.fn>
let lastUrl: string
let lastInit: FakeInit | undefined
let lastSignal: AbortSignal | undefined

function respond(body: unknown, status = 200) {
  fetchMock.mockImplementation(async (url: string, init?: FakeInit) => {
    lastUrl = url
    lastInit = init
    lastSignal = init?.signal as unknown as AbortSignal | undefined
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    }
  })
}

// Pending-response mock: lets fake timers elapse while the request is in
// flight so timeout arming is observable via the AbortSignal. settle(value)
// resolves the in-flight fetch with a response-like value.
function hangFetch() {
  let release!: (value: unknown) => void
  const gate = new Promise((resolve) => {
    release = resolve
  })
  fetchMock.mockImplementation((url: string, init?: FakeInit) => {
    lastUrl = url
    lastInit = init
    lastSignal = init?.signal as unknown as AbortSignal | undefined
    return gate
  })
  return {
    settle(value: unknown) {
      release(value)
      return gate
    },
  }
}

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const HEALTH_OK = { status: 'ok', mongodb: true }
const INGEST_PLAYER_OK = {
  puuid: 'p1',
  matches_fetched: 3,
  matches_saved: 3,
  matches_skipped: 0,
  matches_discarded: 0,
  matches_parse_errors: 0,
  matches_fetch_errors: 0,
}
const COACH_OK = { response: 'play safe' }
const INGEST_TEAM_OK = { team_puuids_resolved: 2, players: [{ riotid: 'a#1' }] }
const EMBEDDING_QUERY_OK = {
  hits: [{ id: 'h1', document: 'doc', metadata: {}, distance: 0.5 }],
}

describe('error mapping', () => {
  it('maps 422 detail[] to fieldErrors keyed by the last string loc segment', async () => {
    respond(
      {
        detail: [
          {
            loc: ['body', 'count'],
            msg: 'Input should be less than or equal to 100',
            type: 'less_than_equal',
          },
          {
            loc: ['body', 'team_puuids', 0],
            msg: 'Input should be a valid string',
            type: 'string_type',
          },
        ],
      },
      422,
    )
    const err = (await request('/any', {
      method: 'POST',
      body: {},
      schema: z.object({}),
    }).catch((e: ApiError) => e)) as Extract<ApiError, { kind: 'validation' }>
    expect(err.kind).toBe('validation')
    expect(err.fieldErrors).toEqual({
      count: 'Input should be less than or equal to 100',
      team_puuids: 'Input should be a valid string',
    })
  })

  it('maps 401 to auth error and fires the unauthorized event exactly once', async () => {
    const spy = vi.spyOn(window, 'dispatchEvent')
    respond({ detail: 'Unauthorized' }, 401)
    await expect(getHealth()).rejects.toMatchObject({ kind: 'auth' })
    expect(spy).toHaveBeenCalledTimes(1)
    const ev = spy.mock.calls[0]?.[0] as CustomEvent
    expect(ev.type).toBe('heimerdinger:unauthorized')
    spy.mockRestore()
  })

  it('maps 404 to not_found', async () => {
    respond({ detail: 'not found' }, 404)
    await expect(getPlayerReport('p1')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })

  it('maps other non-2xx (502) to server with status', async () => {
    respond({ detail: 'LLM request failed' }, 502)
    await expect(askCoach({ question: 'q' })).rejects.toMatchObject({
      kind: 'server',
      status: 502,
    })
  })

  it('maps fetch rejection to network', async () => {
    fetchMock.mockRejectedValue(new TypeError('network down'))
    await expect(getHealth()).rejects.toMatchObject({ kind: 'network' })
  })

  it('rejects with validation error when a 200 body fails its zod schema', async () => {
    respond({ totally: 'wrong' }, 200)
    await expect(getHealth()).rejects.toMatchObject({ kind: 'validation' })
  })
})

describe('success path', () => {
  it('requests baseUrl + path and returns parsed data', async () => {
    respond(HEALTH_OK)
    await expect(getHealth()).resolves.toEqual(HEALTH_OK)
    expect(lastUrl).toBe('http://localhost:8000/health')
  })

  it('builds query parameters for team roster lookup', async () => {
    respond([])
    await getTeam('team.json')
    expect(lastUrl).toBe('http://localhost:8000/team?team_path=team.json')
  })

  it('passes limit as query param for match listings', async () => {
    respond([])
    await getPlayerMatches('p1', 20)
    expect(lastUrl).toBe('http://localhost:8000/players/p1/matches?limit=20')
    respond([])
    await getGoldMatches('p1', 20)
    expect(lastUrl).toBe('http://localhost:8000/players/p1/gold/matches?limit=20')
    respond({ games_analyzed: 0, wins: 0 })
    await getGoldReport('p1', 20)
    expect(lastUrl).toBe('http://localhost:8000/players/p1/gold/report?limit=20')
  })

  it('hits all remaining endpoint paths', async () => {
    respond({ name: 'n', docs: '/docs', openapi: '/openapi.json' })
    await getRoot()
    expect(lastUrl).toBe('http://localhost:8000/')
    respond(HEALTH_OK)
    await getHealth()
    expect(lastUrl).toBe('http://localhost:8000/health')
    respond([])
    await getPlayerMatches('p1')
    expect(lastUrl).toBe('http://localhost:8000/players/p1/matches')
    respond({ status: 'full' })
    await getPlayerReport('p1')
    expect(lastUrl).toBe('http://localhost:8000/players/p1/report')
    respond({})
    await getPlayerMatchReport('p1', 'm1')
    expect(lastUrl).toBe('http://localhost:8000/players/p1/matches/m1/report')
    respond({ 100: ['Ahri'] })
    await getMatchComposition('m1')
    expect(lastUrl).toBe('http://localhost:8000/matches/m1/composition')
    respond({ snapshot: 'text' })
    await getMatchSnapshot('m1')
    expect(lastUrl).toBe('http://localhost:8000/matches/m1/snapshot')
    respond({ matchId: 'm1', players: [] })
    await getMatchGold('m1')
    expect(lastUrl).toBe('http://localhost:8000/matches/m1/gold')
    respond(EMBEDDING_QUERY_OK)
    await queryEmbeddings({ query: 'q' })
    expect(lastUrl).toBe('http://localhost:8000/embeddings/query')
    respond({})
    await seedEmbeddings()
    expect(lastUrl).toBe('http://localhost:8000/embeddings/seed')
  })
})

describe('headers', () => {
  it('attaches x-api-key only when the settings key is set', async () => {
    respond(HEALTH_OK)
    await getHealth()
    expect(lastInit?.headers['x-api-key']).toBeUndefined()

    saveApiKey('secret-key')
    respond(HEALTH_OK)
    await getHealth()
    expect(lastInit?.headers['x-api-key']).toBe('secret-key')
  })

  it('sets Content-Type application/json when a body is sent', async () => {
    respond(COACH_OK)
    await askCoach({ question: 'q' })
    expect(lastInit?.headers['Content-Type']).toBe('application/json')

    respond(HEALTH_OK)
    await getHealth()
    expect(lastInit?.headers['Content-Type']).toBeUndefined()
  })
})

describe('body mapping (store camelCase → API snake_case)', () => {
  it('ingestPlayer sends riotid/region_rep snake_case keys', async () => {
    respond(INGEST_PLAYER_OK)
    await ingestPlayer({
      riotId: 'Nombre#TAG',
      count: 3,
      region: 'europe',
      regionRep: 'americas',
    })
    expect(JSON.parse(lastInit?.body ?? '{}')).toEqual({
      riotid: 'Nombre#TAG',
      count: 3,
      region: 'europe',
      region_rep: 'americas',
    })
  })

  it('ingestTeam maps team_path and region_rep', async () => {
    respond(INGEST_TEAM_OK)
    await ingestTeam({ teamPath: 'team.json', regionRep: 'americas' })
    expect(JSON.parse(lastInit?.body ?? '{}')).toEqual({
      team_path: 'team.json',
      region_rep: 'americas',
    })
  })

  it('askCoach sends question/last_match/history snake_case', async () => {
    respond(COACH_OK)
    const history = [{ role: 'user' as const, content: 'hi' }]
    await askCoach({ question: 'q', lastMatch: true, history })
    expect(JSON.parse(lastInit?.body ?? '{}')).toEqual({
      question: 'q',
      last_match: true,
      history,
    })
  })

  it('queryEmbeddings maps top_k', async () => {
    respond(EMBEDDING_QUERY_OK)
    await queryEmbeddings({ query: 'q', topK: 10 })
    expect(JSON.parse(lastInit?.body ?? '{}')).toEqual({ query: 'q', top_k: 10 })
  })
})

describe('timeout arming policy', () => {
  it('arms the 15s default on regular GETs and aborts at exactly DEFAULT_TIMEOUT_MS', async () => {
    vi.useFakeTimers()
    const h = hangFetch()
    const promise = getHealth()
    await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS - 1)
    expect(lastSignal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    expect(lastSignal?.aborted).toBe(true)
    h.settle({ ok: true, status: 200, json: async () => HEALTH_OK })
    await expect(promise).resolves.toEqual(HEALTH_OK)
  })

  it('never arms an abort for ingestPlayer', async () => {
    vi.useFakeTimers()
    const h = hangFetch()
    const promise = ingestPlayer({ riotId: 'Nombre#TAG' })
    await vi.advanceTimersByTimeAsync(600_000)
    expect(lastSignal?.aborted).toBe(false)
    h.settle({ ok: true, status: 200, json: async () => INGEST_PLAYER_OK })
    await expect(promise).resolves.toEqual(INGEST_PLAYER_OK)
  })

  it('never arms an abort for ingestTeam', async () => {
    vi.useFakeTimers()
    const h = hangFetch()
    const promise = ingestTeam({})
    await vi.advanceTimersByTimeAsync(600_000)
    expect(lastSignal?.aborted).toBe(false)
    h.settle({ ok: true, status: 200, json: async () => INGEST_TEAM_OK })
    await expect(promise).resolves.toEqual(INGEST_TEAM_OK)
  })

  it('uses 120s for /coach — survives the 15s default, aborts at 120s', async () => {
    vi.useFakeTimers()
    const h = hangFetch()
    const promise = askCoach({ question: 'q' })
    await vi.advanceTimersByTimeAsync(15_000)
    expect(lastSignal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(COACH_TIMEOUT_MS - 15_000 - 1)
    expect(lastSignal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    expect(lastSignal?.aborted).toBe(true)
    h.settle({ ok: true, status: 200, json: async () => COACH_OK })
    await expect(promise).resolves.toEqual(COACH_OK)
  })

  it('never arms an abort for embeddings/seed (full re-ingestion)', async () => {
    vi.useFakeTimers()
    const h = hangFetch()
    const promise = seedEmbeddings()
    await vi.advanceTimersByTimeAsync(600_000)
    expect(lastSignal?.aborted).toBe(false)
    h.settle({ ok: true, status: 200, json: async () => ({}) })
    await expect(promise).resolves.toEqual({})
  })
})

describe('schema registry shapes', () => {
  it('parses a flat aggregate_gold report with optional percentile keys', async () => {
    respond({
      goldEarned: 9000,
      goldEarned_median: 8500,
      goldEarned_p25: null,
      games_analyzed: 12,
      wins: 7,
    })
    const data = await getGoldReport('p1')
    expect(data.games_analyzed).toBe(12)
    expect(data.wins).toBe(7)
    expect(data.goldEarned).toBe(9000)
    expect(data.goldEarned_p25).toBeNull()
    expect(data.gold_spend_ratio).toBeUndefined()
  })

  it('accepts nullable gold-row fields (gpm/timestamp/summonerName) and gold_value 0', async () => {
    respond({
      matchId: 'm1',
      players: [
        {
          matchId: 'm1',
          puuid: 'p1',
          summonerName: null,
          timestamp: null,
          win: true,
          champion: 'Ahri',
          role: 'MIDDLE',
          teamId: 100,
          goldEarned: 9000,
          goldSpent: 8800,
          gold_diff: 200,
          gpm: null,
          itemsPurchased: 18,
          consumablesPurchased: 4,
          items: { ids: [], names: [], gold_value: 0, stats: {} },
        },
      ],
    })
    const data = await getMatchGold('m1')
    expect(data.players).toHaveLength(1)
    expect(data.players[0]?.items.gold_value).toBe(0)
  })

  it('accepts nullable report champion/role and ingest-team error entries', async () => {
    respond({ status: 'full', champion: null, role: null })
    const report = await getPlayerReport('p1')
    expect(report.status).toBe('full')

    respond({
      team_puuids_resolved: 1,
      players: [{ riotid: 'bad#tag', error: 'summoner not found' }],
    })
    const team = await ingestTeam({})
    expect(team.players[0]?.error).toBe('summoner not found')
  })

  it('ignores unknown extra fields via passthrough', async () => {
    respond({ ...HEALTH_OK, extra_unknown_field: 42 })
    await expect(getHealth()).resolves.toMatchObject({ mongodb: true })
  })
})
