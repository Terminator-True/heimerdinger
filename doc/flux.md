# Heimerdinger — Flujo de Datos

> Diagramas y descripción del flujo de datos end-to-end: desde la consulta a la Riot API hasta el consejo de coaching con IA.

---

## 1. Flujo Principal — Pipeline Completo

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Riot Games  │    │  MongoDB     │    │  Report      │    │  Ollama LLM  │
│  API v5      │    │              │    │  Builder     │    │  (local)     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       │  1. Resolver      │                   │                   │
       │  Riot ID → PUUID  │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │  2. Match IDs     │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │  3. Match Detail  │                   │                   │
       │  (por cada ID)    │                   │                   │
       │──────────────────>│                   │                   │
       │                   │  4. Guardar raw   │                   │
       │                   │  match en `matches`                  │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │  5. Parsear y     │                   │
       │                   │  guardar métricas  │                   │
       │                   │  en `player_matches`                 │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │  6. Leer N        │                   │
       │                   │  partidas →       │                   │
       │                   │  build reporte    │                   │
       │                   │<──────────────────│                   │
       │                   │                   │                   │
       │                   │  7. Guardar       │                   │
       │                   │  reporte en       │                   │
       │                   │  `reports`        │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │  8. LLM Adivisor  │                   │
       │                   │  construye prompt │                   │
       │                   │  + retrieval      │                   │
       │                   │──────────────────────────────────────>│
       │                   │                   │                   │
       │                   │                   │   9. Respuesta    │
       │                   │                   │   de coaching     │
       │                   │<──────────────────────────────────────│
       │                   │                   │                   │
       │                   │  10. Guardar      │                   │
       │                   │  coaching_report  │                   │
       │                   │  + exportar JSON  │                   │
```

---

## 2. Ingesta de Jugador

```
Riot ID (Name#Tagline)
       │
       ▼
┌──────────────────┐
│  ingest_player() │  modules/ingest/lib.py
│                  │
│  1. Parsear      │  "TR Terminator#1998" → name="TR Terminator", tag="1998"
│     Riot ID      │
│                  │
│  2. Resolver     │  GET /riot/account/v1/accounts/by-riot-id/{name}/{tag}
│     PUUID        │  ← { puuid: "...", gameName: "...", tagLine: "..." }
│                  │
│  3. Obtener      │  GET /lol/match/v5/matches/by-puuid/{puuid}/ids?count=N
│     Match IDs    │  ← ["EUW_123", "EUW_124", ...]
│                  │
│  4. Por cada ID: │
│     │            │
│     ├─ Existe?   │  MatchesRepository.match_exists(matchId)
│     │  └─ Sí → skip (dedup)
│     │
│     ├─ Fetch     │  GET /lol/match/v5/matches/{matchId}  (con rate limiter)
│     │             │  ← JSON gigante con info + participants + teams
│     │             │
│     ├─ Guardar   │  MatchesRepository.upsert_match(match_json)
│     │  raw       │  → Colección `matches`
│     │             │
│     ├─ Parsear   │  MatchParser.parse_match(match_json)
│     │             │  → { gameStartMillis, gameDurationSeconds, players: [...] }
│     │             │
│     └─ Guardar   │  Guarda métricas del jugador en `player_matches`
│        métricas  │  { matchId, player_puuid, kills, deaths, cs, ... }
│                  │
│  5. Resumen      │  ← { puuid, matches_fetched, matches_saved, errors }
└──────────────────┘
```

---

## 3. Generación de Reportes

```
┌────────────────────┐
│  ReportBuilder     │  modules/data/report_builder.py
│                    │
│  build_player_report(puuid, db)                        │
│                    │
│  1. Buscar todas   │  db.player_matches.find({player_puuid: puuid})
│     las partidas   │
│     del jugador    │
│                    │
│  2. Agrupar por    │  Counter(champion) → champion más usado
│     campeón más    │
│     usado          │
│                    │
│  3. Calcular       │  KDA promedio, CS/min, GPM, visión,
│     métricas       │  kill participation, daño total, muertes,
│     agregadas      │  win rate, duración promedio
│                    │
│  4. Extraer de     │  challenges.* → DPM, visionScore/min,
│     challenges     │  controlWards, skillshots, turretPlates, etc.
│                    │
│  5. Construir      │  {
│     reporte JSON   │    "player": "PUUID",
│                    │    "role": "Support",
│                    │    "champion": "Nami",
│                    │    "games_analyzed": 20,
│                    │    "metrics": { kda, cs_per_min, gpm, ... },
│                    │    "match_ids": [...]
│                    │  }
│                    │
│  6. Guardar en     │  Colección `reports`
│     MongoDB        │
└────────────────────┘
```

---

## 4. Ask the Coach — Clasificación + Retrieval + LLM

```
Pregunta del usuario: "¿Cómo mejorar mi fase de líneas?"
       │
       ▼
┌──────────────────┐
│  classify_question()  │  modules/llm/question_classifier.py
│                  │
│  1. Rule-based   │  Keyword scan contra 6 categorías
│     ───────────  │  "lane", "cs", "wave" → laning (score=3)
│                  │  Si score > 2× segundo → aceptar
│                  │
│  2. Embedding    │  Si rule-based es inconcluso:
│     (fallback)   │  all-MiniLM-L6-v2 → cosine similarity
│                  │  contra descripciones de categorías
│                  │  Si sim > 0.6 → aceptar
│                  │
│  3. General      │  Si nada funciona → category="general"
│                  │
│  Resultado:      │  ← { category_id: "laning", method: "rule", confidence: 0.8 }
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  retrieve_for_category() │  modules/llm/retrieval.py
│                  │
│  Usa category_id │
│  + role para     │
│  buscar pasajes  │
│  relevantes:     │
│                  │
│  1. Reports      │  Colección `reports` → métricas por categoría
│     ──────────   │  laning → cs_per_min, early_deaths
│                  │  vision → vision_score, wards_placed
│                  │  teamfights → damage_pct, positioning
│                  │
│  2. Player       │  Fallback: `player_matches` con métricas por partida
│     Matches      │
│                  │
│  3. Embedding    │  Si recipe no encuentra nada:
│     Store        │  ChromaDB query con embedding de la pregunta
│                  │
│  Resultado:      │  ← ["player=xxx cs=6.2 early_deaths=3", ...]
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  LLMAdvisor /     │  modules/llm/llm_advisor.py
│  PromptEngineer   │  modules/llm/prompt_engineer.py
│                  │
│  1. Construir    │  System prompt: "Eres un coach experto de LoL"
│     prompt       │  Role guidance según rol del jugador
│                  │  Stats block con métricas estructuradas
│                  │  Pasajes recuperados como contexto adicional
│                  │
│  2. Llamar a     │  POST /api/generate { model, prompt }
│     Ollama       │  ← { response: "...", done: true }
│                  │
│  3. Parsear      │  Extrae texto de respuesta
│     respuesta    │
│                  │
│  4. Guardar      │  reports/ollama_responses/ask_coach_{timestamp}.json
│     prompt+resp  │  { question, role, category, prompt, response }
│                  │
│  Resultado:      │  ← "1. Tu CS a los 10min baja vs matchups difíciles..."
└──────────────────┘
```

---

## 5. Arquitectura de Componentes

```
┌──────────────────────────────────────────────────────────────────┐
│                          CLI / TUI                                │
│  scripts/main.py  │  scripts/pipeline_runner.py  │  tui/app.py   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                     Orquestación                                  │
│  modules/ingest/lib.py  │  scripts/ask_coach.py                   │
│  modules/data/report_builder.py  │  modules/llm/llm_advisor.py    │
└──────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Riot API │ │ MongoDB  │ │ Ollama   │ │ ChromaDB │ │ Embedder │
│ Client   │ │          │ │ Client   │ │          │ │          │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

---

## 6. Flujo de Pregunta (CLI / TUI → Coach)

```
Usuario                    Script/App                  Backend
  │                           │                          │
  │  "¿Cómo mejorar           │                          │
  │   mi fase de líneas?"     │                          │
  │──────────────────────────>│                          │
  │                           │   classify_question()    │
  │                           │─────────────────────────>│
  │                           │   ← "laning"             │
  │                           │                          │
  │                           │   retrieve_for_category  │
  │                           │   ("laning", role="Top") │
  │                           │─────────────────────────>│
  │                           │   ← pasajes de reports   │
  │                           │                          │
  │                           │   build_prompt()         │
  │                           │─────────────────────────>│
  │                           │   ← prompt listo         │
  │                           │                          │
  │                           │   Ollama.generate()      │
  │                           │─────────────────────────>│
  │                           │   ← respuesta streaming  │
  │                           │                          │
  │  ← Consejo de coaching    │                          │
```

---

## 7. Colecciones en MongoDB

```
┌──────────────────────────────────────────────────────────────┐
│                         MongoDB                               │
│                                                              │
│  matches: {                                                  │
│    metadata: { matchId, ... },                               │
│    info: { gameDuration, gameMode, gameVersion,              │
│            participants: [...], teams: [...] }                │
│  }                                                           │
│                                                              │
│  player_matches: {                                           │
│    matchId, player_puuid, role, championName,                │
│    kills, deaths, assists, cs, cs_per_min, kda,              │
│    goldEarned, visionScore, damageDealtToChampions,          │
│    win, timestamp, parsed_metrics: { ... }                   │
│  }                                                           │
│                                                              │
│  reports: {                                                  │
│    player, player_puuid, role, champion,                     │
│    games_analyzed, match_ids: [...],                         │
│    metrics: { kda, cs_per_min, gpm, visionScore, ... }       │
│  }                                                           │
│                                                              │
│  coaching_reports: {                                         │
│    player, role, question, prompt, response,                 │
│    timestamp, category, passages                             │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
```
