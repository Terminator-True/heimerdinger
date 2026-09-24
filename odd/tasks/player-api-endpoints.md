# player-api-endpoints — endpoints reales para las pantallas del jugador

## Objetivo
Reemplazar los datos mock del front por **endpoints reales** que alimenten Resumen, Partidas y
Comparativa, y enriquecer la ingesta para que las métricas ricas de Support (visión/min, control
wards, KP) existan de verdad y no solo en el mock.

## Problema (causa raíz)
`player_matches.parsed_metrics` guarda solo la forma mínima de `match_parser`
(`kills/deaths/assists/cs/cs_per_min/kda/goldEarned/visionScore/damageDealtToChampions/win`).
Las métricas ricas que el mock promete (`ch_visionScorePerMinute`, `ch_controlWardsPlaced`,
`ch_killParticipation`, `ch_damagePerMinute`, `ch_goldPerMinute`, wards, objetivos) las produce
`extract_rich_participant` desde el doc completo de `matches`, pero **nunca se persisten**.
Sin eso, la Comparativa contra pros queda con ~9 métricas y sin las que importan en Support.

Además `app/main.py:248` llama `build_player_report` **sin** `pro_reference`, así que
`pro_reference` es siempre `null` y `deltas` siempre `{}` por API.

## Decisiones
- **Enriquecer en la ingesta** (no un endpoint `/rich` por partida): se mergean al
  `parsed_metrics` solo los campos **numéricos/bool** de `extract_rich_participant` (se descartan
  `perks`, `item0..6`, `team_bans`, strings) para no inflar el doc ni meter ruido no numérico.
  Así `build_player_report`, el trend y el desglose por fases salen de `player_matches` sin N+1.
- **Re-parseo offline**: `scripts/reparse_matches.py` re-deriva `player_matches` desde los
  `matches` ya guardados, **sin llamadas a Riot**, para enriquecer datos existentes.
- **Sin endpoint de trend**: `/players/{puuid}/matches` ya devuelve `parsed_metrics` por partida;
  la serie temporal se arma en el cliente. Menos endpoints, mismo resultado.
- **Sin endpoint `/rich`**: con el enriquecimiento, la fila de `player_matches` ya trae todo.

## Alcance autorizado
`modules/ingest/lib.py`, `modules/data/pro_baseline.py`, `app/main.py`, `app/schemas.py`,
nuevo `scripts/reparse_matches.py`, `tests/test_ingest_player.py`, `tests/test_pro_baseline.py`,
`tests/test_api.py`, nuevo `tests/test_reparse_matches.py`,
`frontend/src/lib/playerData.ts`, `frontend/src/schemas/endpoints.ts`, tests de front.

## Fuera de alcance
Timeline (`match/timeline`), rango/LP (`league-v4`), recomendador de builds/runas, TUI.

## Endpoints
| Método | Ruta | Devuelve |
|---|---|---|
| GET (fix) | `/players/{puuid}/report` | ahora con `pro_reference` y `deltas` reales |
| GET (nuevo) | `/players/{puuid}/comparison?role=` | `{player, role, games_analyzed, baseline:{role,source,games,season}, rows:[{metric,player,pro,delta,pct,p25,median,p75,n}]}`; `baseline:null, rows:[]` si no hay baseline; 404 si el jugador no tiene partidas |
| GET (nuevo) | `/pro/baseline/{role}` | doc completo del baseline; 404 si no existe |

## Tareas
- [ ] E-a1 Merge de métricas ricas en `ingest_player`.
- [ ] E-a2 `scripts/reparse_matches.py` (offline, `--player/--all`, `--dry-run`, `--limit`).
- [ ] E-a3 Tests de ingesta enriquecida + reparseo.
- [ ] E-b1 `load_baseline(db, role)` en `pro_baseline` (doc completo, fallback JSON).
- [ ] E-b2 Fix de `/report` + `/comparison` + `/pro/baseline/{role}`.
- [ ] E-b3 Tests de API.
- [ ] F1 `playerData.ts` contra la API real + schemas zod (mock sigue funcionando con `VITE_MOCK`).
- [ ] F2 Desglose por fases leyendo las filas enriquecidas de `/matches`.
- [ ] F3 Tests de front.

## Checks (VERIFICADOS, ya funcionan en este host)
- Backend: `venv/bin/python -m pytest tests/ -q` → **baseline 213 passed**.
- Frontend: `npx -y node@22 ./node_modules/vitest/vitest.mjs run` → **baseline 162 passed**.

## Nota de entorno
Se creó `venv/` (gitignored) bootstrapeando pip con `get-pip.py` porque el Python del sistema es
PEP 668 y no tiene pip/ensurepip. Se instalaron solo deps core (sin `sentence-transformers` ni
`chromadb`: no entran en disco). Docker **no** es viable: `/var` está al 100%.

## Delivery
- `ask-on-risk`; preferencia del usuario: **commits locales, PRs después**.
- Branch: `feat/focus-support` (ya pusheada al remoto).

## Progreso
- Plan creado. Pendiente E-a.
