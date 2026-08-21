# Current Architecture — Heimerdinger

Baseline module map and data flow for the webapp-v2 migration (Hito 0). This
documents the code AS IT IS before extraction; the migration converges toward
the target layout described in the design without renames until Hito 6.

## Module Map

| Path | Responsibility | I/O |
|------|----------------|-----|
| `modules/riot_api/client.py` | `RiotClient` — Riot API v5 (account, match ids, match) over httpx | network (httpx) |
| `modules/riot_api/rate_limiter.py` | `TokenBucketLimiter` — per-process token bucket | none |
| `modules/data/match_parser.py` | `MatchParser.parse_match` — raw match → parsed player metrics (pure) | none |
| `modules/data/gold_analysis.py` | Gold/CS analysis helpers (pure) | none |
| `modules/data/report_builder.py` | `ReportBuilder` — aggregate player report, per-match report, `render_match_snapshot`, `extract_team_composition`, `extract_rich_participant` | **direct disk I/O** (`output_dir/*.json`) + DB upsert |
| `modules/db/connection.py` | `get_db(uri)` — Mongo client factory | DB |
| `modules/db/repositories.py` | `MatchesRepository` — match / player_match upserts, existence checks | DB |
| `modules/ingest/lib.py` | `ingest_player`, `resolve_team_puuids` — fetch + parse + save pipeline | Riot + DB |
| `modules/llm/ollama_client.py` | `OllamaClient.generate` — local Ollama REST | network (httpx) |
| `modules/llm/prompt_engineer.py` | `PromptEngineer` + `build_chat_context` — stats prompt assembly (pure) | none |
| `modules/llm/llm_advisor.py` | `LLMAdvisor.advise` — ties Ollama + prompt + retrieval | **direct disk I/O** (`reports/ollama_responses/{puuid}.txt`) |
| `modules/llm/retrieval.py`, `question_classifier.py`, `question_categories.json` | Retrieval + question classification | vector store |
| `modules/coaching/prompt_builder.py` | `CoachingPromptBuilder` — schema-driven coach prompt | Data Dragon (items) |
| `modules/embeddings/embedder.py`, `store.py`, `ingest.py` | Embedder + `VectorStore` + embedding ingest | model + ChromaDB |
| `modules/riot_items/` | `DataDragonClient`, `ItemCache`, item models | Data Dragon CDN + disk cache |
| `modules/config_manager.py` | team / embeddings / ddragon config loaders | **direct disk I/O** (JSON reads) |
| `modules/logger.py` | `get_logger` — shared logging | none |
| `app/main.py` | FastAPI backend exposing ingest / reports / coach / embeddings | wires `modules.*` directly |
| `tui/` | Textual UI (screens/widgets/utils) | wires `modules.*` directly |
| `scripts/ask_coach.py` | Coaching CLI (builds prompt, calls LLM, persists) | **direct disk I/O** |
| `scripts/ingest_*.py`, `pipeline_runner.py`, `auto_ingest_loop.py` | Ingest CLIs | delegate to `modules.ingest.lib` |

## Data Flow

```
Riot API v5 ──RiotClient──▶ ingest_player ──MatchesRepository──▶ Mongo
                                      │
                                      └─▶ MatchParser.parse_match ──▶ player_matches
                                                                        │
                                                                        ▼
ReportBuilder ◀── player_matches (parsed_metrics) ──▶ reports/{player}.json  + reports collection
                                                                        │
                                                                        ▼
CoachingPromptBuilder ◀── full match doc ──▶ prompt ──▶ OllamaClient ──▶ LLMAdvisor.advise
                                                                        │
                                                                        ▼
                                                            reports/ollama_responses/{puuid}.txt
```

1. **Ingest**: `scripts/ingest_*.py` / `app/main.py` call `modules.ingest.lib.ingest_player`,
   which resolves riotid → puuid, fetches match ids, fetches each match, parses
   via `MatchParser`, and upserts raw matches + parsed player metrics through
   `MatchesRepository`.
2. **Reports**: `ReportBuilder.build_player_report` reads `player_matches`
   (parsed_metrics), aggregates means/medians/percentiles, and **both** upserts
   the report to Mongo and writes `reports/{player}.json` to disk.
3. **Coaching prompt**: `CoachingPromptBuilder.build_prompt` resolves fields from
   the schema, resolves item ids to names via `DataDragonClient`, and assembles
   the ~800-token role-aware prompt.
4. **Advice**: `LLMAdvisor.advise` builds the prompt (optionally with retrieval
   context), calls `OllamaClient.generate`, and persists the raw response to
   `reports/ollama_responses/{puuid}.txt`.
5. **Consumers**: `app/main.py` (REST) and `tui/` (Textual) call the `modules.*`
   layer directly — no shared composition root yet.

## I/O Ownership (migration target)

The migration isolates direct disk I/O behind ports. Today these modules write
to disk directly and are the extraction targets:

- `ReportBuilder.save_report` / `build_match_report` → `FileOutputPort`
- `LLMAdvisor.advise` (`reports/ollama_responses/*.txt`) → `FileOutputPort`
- `config_manager` JSON reads → `ConfigSourcePort`
- `scripts/ask_coach.py` persistence → `CoachingService`

Domain code must eventually be free of Textual/Rich/Plotext imports and direct
`open()`/`Path.write` calls.
