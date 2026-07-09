# Heimerdinger — Backend

> Arquitectura, módulos y componentes del backend de coaching de League of Legends.

---

## Stack tecnológico

| Componente | Tecnología | Propósito |
|------------|-----------|-----------|
| Lenguaje | Python 3.11+ | Runtime principal |
| API externa | Riot Games API v5 | Datos de invocadores, partidas, timeline |
| Base de datos | MongoDB | Persistencia de partidas, reportes, config |
| LLM local | Ollama (llama3.1, mistral, etc.) | Generación de consejos de coaching |
| Embeddings | sentence-transformers | Clasificación semántica de preguntas |
| Vector store | ChromaDB | Recuperación contextual por similitud |
| HTTP | httpx | Cliente para APIs REST |
| CLI | rich | Menús interactivos, tablas, paneles |

---

## Estructura del proyecto

```
heimerdinger/
├── config/                      # Configuración
│   ├── .env.example             # Template de variables de entorno
│   ├── team.json                # Jugadores del equipo
│   └── coaching_schema.json     # Schema de métricas por rol con benchmarks
├── modules/
│   ├── riot_api/                # Integración con Riot Games API
│   │   ├── client.py            # Cliente HTTP con endpoints v5
│   │   └── rate_limiter.py      # Token bucket rate limiter
│   ├── data/                    # Procesamiento de datos
│   │   ├── match_parser.py      # Parseo de partidas (CS, KDA, métricas)
│   │   └── report_builder.py    # Constructor de reportes por jugador/partida
│   ├── db/                      # Persistencia
│   │   ├── connection.py        # Conexión MongoDB
│   │   └── repositories.py      # CRUD de partidas con dedup
│   ├── ingest/                  # Ingesta de datos
│   │   └── lib.py               # Orquestación de ingesta por jugador
│   ├── llm/                     # Módulo de lenguaje (LLM local)
│   │   ├── ollama_client.py     # Cliente Ollama (sync + async streaming)
│   │   ├── prompt_engineer.py   # Constructor de prompts con stats estructurados
│   │   ├── llm_advisor.py       # Orquestador de consejos con retrieval
│   │   ├── question_categories.json  # Taxonomía de 6 categorías
│   │   ├── question_classifier.py    # Clasificador híbrido (reglas + embeddings)
│   │   └── retrieval.py         # Recuperación de pasajes por categoría
│   ├── embeddings/              # Búsqueda semántica
│   │   ├── embedder.py          # Wrapper de sentence-transformers
│   │   └── store.py             # Wrapper de ChromaDB
│   ├── coaching/                # Coach schema-driven
│   │   ├── prompt_builder.py    # Builder de prompts desde coaching_schema.json
│   │   └── __init__.py
│   ├── config_manager.py        # Carga de equipos desde JSON
│   └── logger.py                # Logger estructurado (Rich + rotación)
├── scripts/                     # Entrypoints CLI
│   ├── main.py                  # Menú principal interactivo
│   ├── ingest_one_player.py     # Ingesta de un jugador
│   ├── ingest_team.py           # Ingesta de un equipo completo
│   ├── ask_coach.py             # Coach interactivo con clasificación + retrieval
│   ├── pipeline_runner.py       # Pipeline completo (ingest → report → LLM)
│   ├── seed_vector_store.py     # Seed de ChromaDB desde datos existentes
│   └── run_new_tests.py         # Lanzador de tests
├── tui/                         # Frontend TUI (ver front-end.md)
├── tests/                       # Tests (17 archivos)
└── reports/                     # Outputs generados (gitignored)
```

---

## Módulos del backend

### 1. Riot API (`modules/riot_api/`)

Cliente HTTP para la Riot Games API v5 con rate limiting.

**Endpoints implementados:**
- `GET /riot/account/v1/accounts/by-riot-id/{name}/{tag}` — Resolución de Riot ID → PUUID
- `GET /lol/match/v5/matches/by-puuid/{puuid}/ids` — Historial de partidas
- `GET /lol/match/v5/matches/{matchId}` — Datos completos de partida

**Rate limiter:** Token bucket (20 tokens/s, capacity 20) para clave gratuita.

**Manejo de errores:** Códigos HTTP 401, 403, 404, 429 con mensajes específicos.

### 2. Data Processing (`modules/data/`)

**Match Parser:** Normaliza el JSON de Riot v5 a métricas planas por jugador:
- CS, CS/min, KDA, gold, visión, daño
- Maneja formatos mixtos (segundos vs milisegundos en duración)
- Defensivo contra payloads mínimos (tests)

**Report Builder:** Construye reportes de coaching con 60+ métricas:
- `build_player_report()` — Reporte agregado (N partidas, stats promedio)
- `build_match_report()` — Reporte por partida individual
- Extrae datos de `challenges.*` (kill participation, DPM, vision score, etc.)
- Incluye datos de equipo (objetivos, bans, equipo ganador)

### 3. Base de datos (`modules/db/`)

**Conexión:** MongoDB vía `pymongo`. URI configurable via `MONGO_URI` en `.env`.

**Colecciones:**
| Colección | Propósito |
|-----------|-----------|
| `matches` | Documentos completos de partidas (Riot API raw) |
| `player_matches` | Métricas parseadas por jugador + partida |
| `reports` | Reportes agregados por jugador |
| `coaching_reports` | Consejos generados por el LLM |

**Repositories:** `MatchesRepository` con upsert por `metadata.matchId`, dedup automático, índice único.

### 4. Ingesta (`modules/ingest/`)

Orquestación centralizada de la ingesta:
1. Resuelve Riot ID → PUUID
2. Obtiene IDs de partidas
3. Fetch de cada partida (con rate limiting)
4. Persiste en MongoDB (dedup)
5. Parse y guarda métricas por jugador
6. Devuelve resumen (fetched, saved, errors)

### 5. LLM (`modules/llm/`)

**Ollama Client:** 
- Generación síncrona con polling de `done: false`
- Timeout configurable (default 30s)
- Soporte para streaming (usado por la TUI)

**Prompt Engineer:**
- System prompt: "Eres un coach experto de LoL"
- Role guidance específico: Top/Jungle/Mid/Bot/Support
- Stats block formateado con métricas clave
- Template personalizable por rol

**LLM Advisor:**
- Toma un reporte de jugador + rol
- Carga embedding store para retrieval contextual
- Construye prompt con métricas + pasajes recuperados
- Llama a Ollama y parsea respuesta
- Guarda prompt+response en `reports/ollama_responses/`

**Question Classifier:**
- **Rule-based:** Keywords por categoría (laning, vision, macro, teamfights, pacing, mental)
- **Embedding:** `all-MiniLM-L6-v2` para clasificación semántica (fallback)
- **Confidence score:** Solo acepta embedding si similitud > 0.6

**Retrieval Recipes:**
- 6 categorías con estrategias de extracción específicas
- Escanea reports y player_matches
- Fallback a ChromaDB si recipe no encuentra nada

### 6. Embeddings (`modules/embeddings/`)

**Embedder:** `sentence-transformers` (all-MiniLM-L6-v2). Retorna vectores JSON-serializables.

**Vector Store:** ChromaDB con persistencia opcional. API: `upsert_docs()`, `query()`. Fallback automático a cliente in-memory si duckdb+parquet no está disponible.

### 7. Coaching Schema (`modules/coaching/`)

Builder de prompts desde `config/coaching_schema.json`:
- Resuelve campos de la API siguiendo rutas del schema
- Aplica benchmarks por rol
- Mantiene prompt ~800 tokens para LLaMA
- 5 roles + modo coach (team aggregate)

---

## Scripts CLI

| Script | Propósito |
|--------|-----------|
| `main.py` | Menú interactivo (5 opciones) con Rich |
| `ingest_one_player.py` | Ingesta vía argumentos CLI |
| `ingest_team.py` | Ingesta de equipo desde JSON |
| `ask_coach.py` | Coach con clasificación + retrieval + Ollama |
| `pipeline_runner.py` | Pipeline completo con flags (--per-match, --skip-fetch, --model) |
| `seed_vector_store.py` | Seed de ChromaDB desde datos existentes |

---

## Tests

17 archivos de test cubriendo:

| Área | Archivos |
|------|----------|
| Riot Client | `test_riot_client.py`, `test_rate_limiter.py` |
| Match Parser | `test_match_parser.py`, `test_match_parser_edgecases.py` |
| Ingesta | `test_ingest_player.py`, `test_ingest_parsed_edgecases.py`, `test_ingest_parsed_integration.py` |
| Report Builder | `test_report_builder.py` |
| LLM | `test_llm_advisor.py`, `test_llm_response_parsing.py`, `test_prompt_engineer.py` |
| Question Classifier | `test_question_classification.py` |
| Retrieval | `test_retrieval_recipes.py` |
| Repositories | `test_repositories.py` |
| Embeddings | `test_embeddings.py`, `test_store_mock.py` |
| Coaching | `tests/coaching/` |
