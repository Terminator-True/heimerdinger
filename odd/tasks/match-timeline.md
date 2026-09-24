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
- **T-A COMMITEADO** (`3ff72f6`): `RiotClient.get_match_timeline`, `modules/data/timeline.py`
  (compactado + series/diff/hitos + self-check stdlib), colección `timelines` en `repositories`,
  `ingest_player(..., with_timeline=False)` best-effort con contadores `timelines_saved/failed`,
  `scripts/backfill_timelines.py`, y `pipeline_runner --focus` con timeline por defecto
  (`--no-timeline` para salir; el loop de equipo queda igual). Tests: 231 → **249 passed**.
- **T-B COMMITEADO** (`7b0239d`): `GET /players/{puuid}/matches/{match_id}/timeline`. 404 explícito
  si la timeline no está capturada (con el hint del backfill) en vez de serie vacía.
  Tests: 249 → **253 passed**.
- **T-C COMMITEADO** (`ece51ff`): panel **Curvas** en Partidas (Recharts jugador vs laner oponente,
  selector Oro/CS/XP/Nivel, hitos @10/@15/@20 + diff de oro), schemas zod, `useMatchTimeline` en el
  seam, generador mock determinístico. Tests: 173 → **185 passed**; build y lint en 0.

## Detalle de la regla de hitos
Los hitos son el valor del **último frame con `minute <= target`**, y `null` si la partida terminó
antes (partida de 18 min → `goldAt15` sí, `goldAt20` no). Nunca se inventa un frame.

## Pendiente / follow-up
- Los eventos de la timeline (`events`: kills, objetivos, torres) se descartan al compactar. Si
  queremos marcadores sobre la curva, hay que volver a guardarlos y refetchear.
- Capturar timelines duplica las llamadas a Riot: por eso `with_timeline` es explícito y
  `auto_ingest_loop` no lo usa.
- Sigue afuera el rango/LP (`league-v4`).
