import { z } from 'zod'

// Per-endpoint response schemas built verbatim from the explore Response
// Shape Notes. Every schema uses .passthrough(): the backend deliberately
// returns plain dicts (app/schemas.py docstring), so unknown extra fields
// must NOT fail parsing.
//
// Nullability is deliberate per design Rev 2 — the backend emits None in
// HEALTHY responses; no blanket catch-all.

// GET / — {name, docs, openapi}
export const rootSchema = z
  .object({
    name: z.string(),
    docs: z.string(),
    openapi: z.string(),
  })
  .passthrough()

// GET /health — {status, mongodb}
export const healthSchema = z
  .object({ status: z.string(), mongodb: z.boolean() })
  .passthrough()

// GET /team?team_path=… — raw config roster entries (riotid/role keys)
export const teamRosterSchema = z
  .array(
    z
      .object({
        riotid: z.string(),
        role: z.string().optional(),
      })
      .passthrough(),
  )

// POST /ingest/player
export const ingestPlayerSchema = z
  .object({
    puuid: z.string(),
    matches_fetched: z.number(),
    matches_saved: z.number(),
    matches_skipped: z.number(),
    matches_discarded: z.number(),
    matches_parse_errors: z.number(),
    matches_fetch_errors: z.number(),
  })
  .passthrough()

// POST /ingest/team — players[] splits into ok entries and {riotid, error}
export const ingestTeamSchema = z
  .object({
    team_puuids_resolved: z.number(),
    players: z
      .array(
        z
          .object({
            riotid: z.string(),
            error: z.string().optional(),
          })
          .passthrough(),
      ),
  })
  .passthrough()

// GET /players/{puuid}/matches — array of cleaned player_matches docs
export const playerMatchSchema = z
  .object({
    player_puuid: z.string(),
    matchId: z.string(),
    championName: z.string(),
    role: z.string(),
    timestamp: z.number().nullable(), // participant → gameStart → gameCreation may all be missing
    parsed_metrics: z.record(z.string(), z.unknown()),
  })
  .passthrough()
export const playerMatchesSchema = z.array(playerMatchSchema)
// Note: arrays need no passthrough in zod — element schemas carry looseness.

// GET /players/{puuid}/report — status:"empty" is mapped to empty by the hook;
// champion/role are null when Counter lists are empty (report_builder.py)
export const playerReportSchema = z
  .object({
    status: z.string(),
    games_analyzed: z.number().optional(),
    champion: z.string().nullable().optional(),
    role: z.string().nullable().optional(),
  })
  .passthrough()

// GET /players/{puuid}/matches/{match_id}/report — build_match_report dict,
// shape kept loose on purpose
export const matchReportSchema = z.object({}).passthrough()

// GET /matches/{match_id}/composition — Record<teamId(str), champion[]>
export const compositionSchema = z.record(z.string(), z.array(z.string()))

// GET /matches/{match_id}/snapshot
export const snapshotSchema = z
  .object({ snapshot: z.string() })
  .passthrough()

// Gold row shared by /gold endpoints.
// items.gold_value is NON-null number but CAN BE 0 (= unknown via
// _resolve_items failure paths); consumers must never divide by 0.
export const goldItemsSchema = z
  .object({
    ids: z.array(z.number()),
    names: z.array(z.string()),
    gold_value: z.number(),
    stats: z.record(z.string(), z.unknown()),
  })
  .passthrough()

export const goldRowSchema = z
  .object({
    matchId: z.string(),
    puuid: z.string(),
    summonerName: z.string().nullable(),
    timestamp: z.number().nullable(),
    win: z.boolean(),
    champion: z.string(),
    role: z.string(),
    teamId: z.union([z.string(), z.number()]),
    goldEarned: z.number(),
    goldSpent: z.number(),
    gold_diff: z.number(),
    gpm: z.number().nullable(), // challenges.goldPerMinute may be absent
    itemsPurchased: z.number(),
    consumablesPurchased: z.number(),
    items: goldItemsSchema,
  })
  .passthrough()

// GET /matches/{match_id}/gold — {matchId, players: [gold_row]}
export const matchGoldSchema = z
  .object({ matchId: z.string(), players: z.array(goldRowSchema) })
  .passthrough()

// GET /players/{puuid}/gold/matches — gold_row[]
export const goldMatchesSchema = z.array(goldRowSchema)

// GET /players/{puuid}/gold/report — FLAT aggregate_gold shape:
// for each metric with samples: <metric>, <metric>_median/_p25/_p75
// (individually nullable); metrics without samples are OMITTED entirely.
const AGG_METRICS = [
  'goldEarned',
  'goldSpent',
  'gold_diff',
  'gpm',
  'item_gold_value',
] as const

const aggregateFields = Object.fromEntries(
  AGG_METRICS.flatMap((m) => [m, `${m}_median`, `${m}_p25`, `${m}_p75`]).map(
    (key) => [key, z.number().nullable().optional()],
  ),
) as {
  [k: string]: z.ZodOptional<z.ZodNullable<z.ZodNumber>>
}

export const aggregateGoldSchema = z
  .object({
    ...aggregateFields,
    gold_spend_ratio: z.number().optional(), // absent when no ratios computed
    games_analyzed: z.number(),
    wins: z.number(),
  })
  .passthrough()

// POST /coach
export const coachResponseSchema = z
  .object({ response: z.string() })
  .passthrough()

// POST /embeddings/query
export const embeddingsQuerySchema = z
  .object({
    hits: z.array(
      z
        .object({
          id: z.string(),
          document: z.string(),
          metadata: z.record(z.string(), z.unknown()),
          distance: z.number(),
        })
        .passthrough(),
    ),
  })
  .passthrough()

// POST /embeddings/seed — return shape unverified at runtime; keep loose
export const embeddingsSeedSchema = z.object({}).passthrough()
