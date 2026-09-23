# focus-support — coaching centrado en una sola persona (Support)

## Objetivo
Pasar el pipeline de coaching de un modelo "por rol / por equipo" a un modelo **"una sola
persona a la vez"** (por defecto **Support**), configurable desde `.env`, y enriquecer los
consejos con una **comparativa contra baselines de supports pro** (Oracle's Elixir).

## Problema (causa raíz)
- `scripts/ask_coach.py` filtra el contexto por **rol**, no por jugador
  (`col.find({"role": role})`): da consejos sobre la última partida de *cualquier* Support.
- La ingesta descarta toda partida sin los 5 integrantes del `team.json`
  (`ingest_player(..., min_team_members=5)`), así que no se ven las partidas de soloQ/duo.
- No existe comparativa pro: `pro_reference` / `deltas` en `ReportBuilder.build_player_report`
  están scaffoldeados y nadie los alimenta.

## Decisiones tomadas
- **Fuente pro**: Oracle's Elixir CSV (elegido por el usuario). Import explícito con
  `--csv <path>`; opcional `--url` para descargar. Sin dependencias nuevas (stdlib `csv`).
- **Punto de configuración del foco**: `.env` → `FOCUS_RIOTID`, `FOCUS_ROLE` (default `Support`).
- **Mapeo de métricas** OE → canónicas: alias map explícito y solo se comparan métricas presentes
  en ambos lados (intersección), para no inventar equivalencias.
- **Ventana de comparación**: por defecto el año más reciente presente en el CSV; filtros
  `--year/--league/--position` opcionales. Comparar 2026 soloQ contra pros de 2014 es inválido.

## Alcance autorizado
`modules/config_manager.py`, `modules/ingest/lib.py`, `scripts/ingest_one_player.py`,
`scripts/pipeline_runner.py`, `scripts/ask_coach.py`, `app/schemas.py`, `app/main.py`,
nuevos `modules/data/pro_baseline.py`, `scripts/import_pro_baseline.py`,
`config/.env.example`, tests, README/doc.

## Fuera de alcance
TUI, embeddings/vector store, ingesta por equipo (se conserva), refactor general.

## Tareas
- [ ] A1 `get_focus_player()` en `config_manager` + vars en `.env.example`.
- [ ] A2 Persistir mapeo riotid→puuid en colección `players` durante la ingesta +
      `resolve_focus_puuid()` offline-first (DB, fallback Riot API).
- [ ] A3 `ask_coach` con scope por jugador (última partida y agregado) + CLI `--focus/--puuid`;
      `CoachRequest.puuid` en la API.
- [ ] A4 `pipeline_runner --focus`: ingesta single-player sin filtro de equipo.
- [ ] A5 Tests de config / ingesta / ask_coach.
- [ ] B1 `modules/data/pro_baseline.py`: CSV → baseline por posición (mean/median/p25/p75, n).
- [ ] B2 `scripts/import_pro_baseline.py`.
- [ ] B3 Wire `pro_reference` (deltas ya existen) + sección "comparativa vs pros" en el prompt.
- [ ] B4 Tests de baseline + docs.

## Respuesta a los "5 roles" y al coach de equipo
`config/coaching_schema.json` conserva los 5 roles; el foco solo cambia **qué jugador** se
analiza por defecto, no elimina la capacidad por rol.

## Checks
- `python3 -m pytest tests/ -q` → **BLOQUEADO en este host**: no hay pip/venv ni deps
  (`pymongo` ausente). Validación alternativa: Docker `python:3.12-slim` con deps core, o
  self-check stdlib para la lógica pura del baseline.
- Self-check stdlib obligatorio para `pro_baseline` (branch/loop/parser → lógica no trivial).

## Delivery
- Estrategia: `ask-on-risk`. Checkpoint **antes del commit del slice B** si el acumulado
  supera ~400 líneas autoradas.
- Branch: `feat/focus-support` (creada desde `main`). Push/PR/merge quedan a decisión del usuario.

## Route / triggers
- Mapping (4+ archivos): **delegado** a `explore` — hecho.
- Writer (2+ archivos no triviales): **delegado** por slice.
- TDD: modo no configurado (sin cache `sdd-init`); se aplican checks funcionales + tests unitarios.

## Progreso
- **Slice A — COMMITEADO** (`4716b16`, 366 líneas autoradas):
  - `get_focus_player()` + `FOCUS_RIOTID`/`FOCUS_ROLE` en `.env.example` (verificado ejecutando
    la función con env vacío/lleno).
  - `players` collection (riotid→puuid) en la ingesta + `resolve_focus_puuid()` offline-first.
  - `ask_coach` acotado por jugador (`player` / `player_puuid`) + `--puuid`/`--focus`;
    `CoachRequest.puuid` y `/coach` lo propagan.
  - `pipeline_runner --focus` ingesta SIN el gate de equipo de 5.
  - Tests: `tests/test_config_manager.py` (9) + 3 tests de scoping en `tests/test_ask_coach.py`.
- **Slice B — IMPLEMENTADO, SIN COMMITEAR** (~990 líneas: 880 nuevos + 112 modificados):
  - `modules/data/pro_baseline.py` (471), `scripts/import_pro_baseline.py` (125),
    `tests/test_pro_baseline.py` (284), wiring en `prompt_engineer`/`ask_coach`/`pipeline_runner`,
    README.
  - Gatekeeper encontró y corrigió un defecto real: el mapa OE apuntaba a claves inexistentes
    (`totalDamageDealtToChampions`), dejando la comparativa vacía. Ahora hay
    `METRIC_KEY_ALIASES` + `comparison_rows` reference-driven (verificado: 4 filas reales,
    `wardsKilled` correctamente descartado por no existir del lado jugador).
  - Checks: self-check stdlib `OK`, `py_compile OK`, pytest **bloqueado** (sin pip/venv/deps).

## Delivery — RESUELTO
Acumulado autorado ≈ **1350 líneas** (A 366 + B ~990), por encima del budget de 400 por PR.
Decisión del usuario: **commit local en `feat/focus-support` ahora, PRs se deciden después**.
Sin push/PR/merge: siguen siendo decisión del usuario. Cuando se abran PRs habrá que partir
(ningún tramo de B entra en 400 líneas sin subdividir).

## Seguimiento (fuera de este change)
- La comparativa pro todavía NO se inyecta en la ruta última-partida
  (`CoachingPromptBuilder`), solo en la agregada (`PromptEngineer`).
- `wardsPerMinute` no existe como clave en nuestros reportes → no compara (correcto: sin inventar).
