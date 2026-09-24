# match-timeline — curvas minuto a minuto (paridad Porofessor)

## Objetivo
Ingerir `match/timeline` de Riot y exponer curvas minuto a minuto del jugador (oro, CS, XP,
nivel) con su **laner oponente**, más los hitos @10/@15/@20. Es la firma de Porofessor y lo que
faltaba para el análisis intra-partida.

## Esquema verificado (match-v5 timeline)
- `metadata.matchId`, `metadata.participants` (lista de puuids ordenada por participantId-1).
- `info.frameInterval` (60000 ms), `info.participants` = `[{participantId, puuid}]` (mapeo explícito).
- `info.frames[]`: `timestamp`, `participantFrames` (dict por participantId string), `events[]`.
- `participantFrames[id]`: `participantId`, `totalGold`, `currentGold`, `xp`, `level`,
  `minionsKilled`, `jungleMinionsKilled`, `position{x,y}`, `championStats`, `damageStats`,
  `goldPerSecond`, `timeEnemySpentControlled`.

## Decisiones
- **Guardar la timeline COMPACTADA**, no cruda: se descartan `championStats`/`damageStats`/
  `events` (que son el 90% del peso y no los leemos) y se conservan `timestamp` + los 6 campos
  numéricos por participante + el mapeo participantId→puuid. Colección `timelines` keyed por
  `matchId`. Mismo espíritu que `matches` (guardar dato crudo) pero sin el lastre inútil.
- **Derivación en lectura**: `modules/data/timeline.py` arma las series desde la timeline
  compactada + el doc de `matches` (que aporta `teamPosition`/`teamId` para ubicar al oponente).
- **Costo explícito**: `ingest_player(..., with_timeline=False)` por defecto (duplica llamadas a
  Riot). `pipeline_runner --focus` lo activa (es la ruta de coaching) con `--no-timeline` para
  salir. `auto_ingest_loop` queda igual.
- **Backfill**: `scripts/backfill_timelines.py` para partidas ya guardadas (a diferencia del
  reparseo, este SÍ llama a Riot).

## Alcance autorizado
`modules/riot_api/client.py`, nuevo `modules/data/timeline.py`, `modules/db/repositories.py`,
`modules/ingest/lib.py`, `scripts/pipeline_runner.py`, nuevo `scripts/backfill_timelines.py`,
`app/main.py`, tests de back y front, `frontend/src/{lib,schemas,views}`.

## Fuera de alcance
Eventos de timeline (kills/objetivos marcados en el tiempo), rango/LP, TUI.

## Tareas
- [ ] T-A1 `RiotClient.get_match_timeline(match_id, region_rep)`.
- [ ] T-A2 `modules/data/timeline.py`: `compact_timeline`, `build_player_timeline` (series propias,
      del oponente de línea, diffs e hitos @10/@15/@20) + self-check stdlib.
- [ ] T-A3 Persistencia `timelines` en `repositories` + integración en `ingest_player`.
- [ ] T-A4 `scripts/backfill_timelines.py` + flag en `pipeline_runner --focus`.
- [ ] T-A5 Tests (cliente respx, módulo, ingesta, backfill).
- [ ] T-B1 `GET /players/{puuid}/matches/{match_id}/timeline` + tests de API.
- [ ] T-C1 Curvas en Partidas (Recharts, selector de métrica, hitos) + schema/api/hook + tests.

## Checks
- Back: `venv/bin/python -m pytest tests/ -q` → baseline **231 passed**.
- Front: `npx -y node@22 ./node_modules/vitest/vitest.mjs run` → baseline **173 passed**.

## Delivery
- `ask-on-risk`; preferencia del usuario: **commits locales, PRs después**. Branch
  `feat/focus-support` (ya en el remoto; se pushea al cerrar cada slice relevante).

## Progreso
- Esquema verificado. Pendiente T-A.
