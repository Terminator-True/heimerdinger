# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

## Mock mode vs real API

By default the player screens hit the real backend. Set `VITE_MOCK=true` to
render the whole player UI from the synthetic Support fixture in
`src/mocks/player.ts` with **zero network calls**:

```bash
VITE_MOCK=true npm run dev
```

`VITE_MOCK` is read in `src/mocks/index.ts` and swapped at the single data
seam in `src/lib/playerData.ts`. Both modes return the same shapes, so the
views never branch on the data source.

Real endpoints consumed by the seam:

- `GET /players/{puuid}/report` — identity, dominant role/champion, games and
  metric rollups (with `pro_reference`/`deltas` when a baseline exists).
- `GET /players/{puuid}/comparison?role=` — player vs pro baseline rows
  (`{metric, player, pro, delta, pct, p25, median, p75, n}`); returns
  `baseline: null, rows: []` when no baseline is imported (the UI renders its
  explicit "Comparativa no disponible todavía." state).
- `GET /players/{puuid}/matches?limit=N` — match history; the rich
  `parsed_metrics` keys (`ch_visionScorePerMinute`, `ch_controlWardsPlaced`,
  `ch_killParticipation`, …) are normalized to canonical names in
  `playerData.ts` so views never see the `ch_` prefix.
- `GET /players/{puuid}/matches/{match_id}/timeline` — per-minute curves for
  one match: the player's `series` (gold/CS/XP/level), the lane
  `opponent`/`opponentSeries`, the `diff` and the `@10`/`@15`/`@20`
  `milestones` (`null` when the game ended before that minute). Curves require
  the compacted timeline to have been captured (ingest or
  `scripts/backfill_timelines.py`); a match ingested without it returns **404**,
  which the Partidas "Curvas" panel renders as a not-captured message — the
  app never fabricates a curve.
- `GET /pro/baseline/{role}` — full stored pro baseline document (404 when
  absent).

## Player routes

- `/player/:puuid` — Resumen (dashboard)
- `/player/:puuid/matches` — Partidas: champion/result filters plus an inline
  per-match phase breakdown (Laning, Economía, Visión, Combate, Objetivos) and
  the per-minute "Curvas" panel (Oro/CS/XP/Nivel vs the lane opponent plus the
  @10/@15/@20 milestones)
- `/player/:puuid/compare` — Comparativa: metric table vs the pro baseline
- `/player/:puuid/gold` — Reporte de oro

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
