# player-ui-mock — pantallas centradas en un jugador (con datos mock)

## Objetivo
Diseñar/construir las pantallas del front-end con **datos mock**, para pulir el layout antes de
decidir cuántos endpoints hacen falta. Todo centrado en **un jugador**.

## Contexto (investigación previa)
Basado en Blitz.gg y Porofessor.gg (`professor.gg` es el dominio alterno de Porofessor). El modelo
útil para nosotros son 4 capas: perfil/historial, **benchmarking por métrica**, **desglose por
fases**, **tendencias**.

## Decisiones de diseño
- **Rutas con tab bar compartido** (URLs compartibles, consistente con el router actual):
  - `/player/:puuid` → **Resumen**
  - `/player/:puuid/matches` → **Partidas** (desglose por fases)
  - `/player/:puuid/compare` → **Comparativa** (vs baseline pro)
  - `/player/:puuid/gold` → **Oro** (vista existente, se conserva)
- **Mock por env**: `VITE_MOCK=true` → las vistas leen fixtures; el Navbar muestra un badge `MOCK`.
  Un solo mecanismo de switch (sin store ni toggle persistido).
- **Seam de datos**: `src/lib/playerData.ts` expone `usePlayerOverview / useMatchList / useComparison`.
  Hoy devuelven fixtures; mañana solo cambia ese archivo para pegarle a la API. Ese es el punto
  donde "cambiamos la cantidad de endpoints" sin tocar las vistas.
- **Tokens existentes**: `bg-slate-950`, cards `slate-900`, bordes `slate-800`, acento `amber-500`,
  win `blue-400`, loss `red-400`, fuente Inter. Prohibido hex custom.
- **Desglose por fases** (una fase por bloque, valor + barra + delta vs pro):
  Laning · Economía · Visión · Combate · Objetivos.
- **Comparativa**: tabla Métrica | Tú | Mediana pro | p25 | p75 | Delta | Percentil.
- `TeamView` se quita del Navbar (contradice el foco single-player); la ruta se conserva.

## Alcance autorizado
`frontend/src/mocks/**` (nuevo), `frontend/src/lib/playerData.ts` (nuevo),
`frontend/src/components/player/PlayerTabs.tsx` (nuevo),
`frontend/src/views/PlayerDashboardView.tsx`, nuevos `PlayerMatchesView.tsx` y
`PlayerCompareView.tsx`, `frontend/src/App.tsx`, `frontend/src/components/Navbar.tsx`,
tests por vista, `frontend/README.md`.

## Fuera de alcance
Backend (ningún endpoint), `TeamView`, `CoachView`, `GoldReportView`, ingesta.

## Tareas
- [ ] C1 Fixtures mock coherentes (1 jugador Support, 20 partidas, baseline pro con percentiles).
- [ ] C2 Seam `playerData.ts` (mock vs API real, misma forma).
- [ ] C3 `PlayerTabs` + rutas + Navbar (badge MOCK, sacar "Equipo").
- [ ] C4 Pantalla **Resumen** (score vs pro, percentiles, fortalezas/a mejorar, tendencia).
- [ ] C5 Tests del slice C.
- [ ] D1 Pantalla **Partidas** con desglose por fases.
- [ ] D2 Pantalla **Comparativa** (tabla + filtros por fase / solo brechas).
- [ ] D3 Tests del slice D + README.

## Checks
- `npm test` (vitest), `npm run build` (tsc -b + vite build), `npm run lint` (oxlint).
- Todo en `frontend/`. Deben quedar verdes; los tests existentes no se debilitan.

## Delivery
- Estrategia: `ask-on-risk`; preferencia ya expresada por el usuario = **commits locales, PRs después**.
- Branch: `feat/focus-support` (se reutiliza; es la rama de la sesión).

## Route / triggers
- Mapping: **delegado** a `explore` — hecho (inventario de front/API).
- Writer (2+ archivos no triviales): **delegado** por slice (C, luego D).

## Progreso
- Mapa del front/API + investigación de Blitz/Porofessor hechos. Pendiente slice C.
