# 🎮 E-Sports LoL Analytics Agent — Plan de Inicio del Proyecto

> Documento de planificación para un agente de análisis de partidas de League of Legends orientado a competición en liga española (Septiembre).

---

## 🧠 Skills del Agente

El agente orquestador utilizará las siguientes capacidades a lo largo de las tres fases:

### Skills de Datos
- **riot_api_collector** — Conexión y consulta a la Riot Games API (summoner data, match history, champion stats, rank)
- **match_parser** — Parseo y normalización de datos de partidas (timeline, KDA, CS/min, vision score, damage, etc.)
- **player_comparator** — Comparativa entre jugadores del equipo y referencias profesionales (mismo campeón + misma línea)
- **data_persister** — Almacenamiento y recuperación de datos en MongoDB (Docker)

### Skills de Análisis e IA
- **report_builder** — Construcción de reportes estructurados por jugador y por partida
- **llm_advisor** — Interfaz con modelo LLM local (Ollama) para generación de consejos personalizados
- **prompt_engineer** — Generación de prompts optimizados para el LLM según rol, campeón y métricas del jugador

### Skills de Orquestación
- **pipeline_runner** — Ejecución del pipeline completo end-to-end desde consola
- **config_manager** — Gestión de configuraciones (IDs de jugadores, API keys, modelo Ollama activo)
- **logger** — Registro de ejecuciones, errores y outputs del agente

### Skills Futuras (Fase 3 — Visión)
- **video_frame_extractor** — Extracción de frames de vídeos de partidas
- **image_analyzer** — Análisis visual de partidas mediante modelo multimodal
- **event_detector** — Detección de eventos clave en pantalla (teamfights, objetivos, muertes)

---

## 🏗️ Arquitectura General

```
┌─────────────────────────────────────────────────────────┐
│                    CLI / Console Runner                  │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │       Agent Orchestrator     │
          └──┬──────────┬───────────────┘
             │          │
    ┌─────────▼──┐  ┌───▼──────────┐
    │  Riot API  │  │  Ollama LLM  │
    │  Module    │  │  Module      │
    └─────────┬──┘  └───┬──────────┘
              │          │
          ┌───▼──────────▼───┐
          │    MongoDB        │
          │  (Docker Dev)     │
          └───────────────────┘
```

**Stack tecnológico:**
- **Lenguaje:** Python 3.11+
- **Base de datos:** MongoDB (Docker)
- **LLM local:** Ollama (modelo recomendado: `llama3`, `mistral` o `deepseek-coder`)
- **API externa:** Riot Games API (clave gratuita)
- **Librerías clave:** `httpx`, `pymongo`, `ollama`, `python-dotenv`, `rich` (output consola)

---

## 📅 Fases del Proyecto

---

## FASE 1 — Integración con Riot Games API y Recolección de Datos

**Objetivo:** Recopilar datos de los jugadores del equipo y generar comparativas con jugadores profesionales que usen los mismos campeones y líneas.

### Paso 1.1 — Configuración del entorno
- Crear repositorio del proyecto con estructura base:
  ```
  /esports-agent
    /config          # Variables de entorno y configuración de jugadores
    /modules
      /riot_api      # Módulo de conexión a Riot
      /data          # Parsers y modelos de datos
      /db            # Conexión y operaciones MongoDB
    /scripts         # Entry points de consola
    /reports         # Outputs generados
  ```
- Configurar `docker-compose.yml` con MongoDB
- Crear `.env` con `RIOT_API_KEY` y configuración de conexión a Mongo
- Instalar dependencias base (`httpx`, `pymongo`, `python-dotenv`, `rich`)

### Paso 1.2 — Módulo de conexión a Riot API
- Implementar cliente HTTP con rate limiting (Riot limita a 20 req/s en clave gratuita)
- Endpoints a integrar:
  - `GET /lol/summoner/v4/summoners/by-name/{name}` — Datos del invocador
  - `GET /lol/league/v4/entries/by-summoner/{id}` — Rank y LP
  - `GET /lol/match/v5/matches/by-puuid/{puuid}/ids` — Historial de partidas
  - `GET /lol/match/v5/matches/{matchId}` — Datos completos de partida
  - `GET /lol/match/v5/matches/{matchId}/timeline` — Timeline de eventos
- Implementar manejo de errores y reintentos

### Paso 1.3 — Modelo de datos y persistencia
- Definir esquemas MongoDB para:
  - `players` — Datos de los jugadores del equipo
  - `matches` — Partidas completas parseadas
  - `player_stats` — Métricas agregadas por jugador/campeón/línea
  - `pro_references` — Datos de referencia de jugadores profesionales
- Implementar `data_persister` con operaciones CRUD básicas
- Script de ingesta inicial: recopilar últimas N partidas de cada jugador del equipo

### Paso 1.4 — Módulo de comparativas
- Definir métricas clave por línea:
  - **Top:** CS/min, daño al tanque, split push pressure, KDA
  - **Jungla:** Objetivos robados, ganks efectivos, delta de CS, tiempo de farmeo
  - **Mid:** CS/min, roaming score, daño a campeones, control de visión
  - **Bot (ADC):** DPM, CS/min, posicionamiento en teamfight (supervivencia), KDA
  - **Support:** Visión score/min, asistencias, controles de visión colocados
- Obtener datos de referencia de jugadores profesionales de la LEC/Superliga usando los mismos campeones
- Implementar `player_comparator` que genere un informe diferencial (percentil del jugador vs. referencia pro)

### Paso 1.5 — Generación de reporte estructurado (Fase 1 Output)
- Implementar `report_builder` que genere un objeto de reporte por jugador:
  ```json
  {
    "player": "NickInvocador",
    "role": "Mid",
    "champion": "Ahri",
    "games_analyzed": 20,
    "metrics": { "cs_per_min": 6.2, "kda": 3.1, ... },
    "pro_reference": { "player": "Faker", "cs_per_min": 8.5, "kda": 4.8 },
    "deltas": { "cs_per_min": -2.3, "kda": -1.7 }
  }
  ```
- Guardar reporte en MongoDB colección `reports` y exportar como JSON a `/reports/`
- Output en consola con tabla formateada usando `rich`

**Entregable Fase 1:** Script ejecutable que genera reportes comparativos por jugador desde consola.

---

## FASE 2 — Integración con LLM Local (Ollama) y Consejos Personalizados

**Objetivo:** Usar el reporte generado en Fase 1 como contexto para que un LLM local genere consejos de mejora personalizados para cada jugador del equipo.

### Paso 2.1 — Setup de Ollama
- Instalar Ollama en la máquina de desarrollo
- Seleccionar y descargar modelo base (recomendado: `llama3.1:8b` o `mistral:7b`)
- Configurar endpoint local de Ollama (`http://localhost:11434`)
- Crear módulo `llm_advisor` con cliente de Ollama vía API REST

### Paso 2.2 — Ingeniería de prompts por rol
- Crear sistema de prompts especializados según línea y campeón:
  - **System prompt:** Define al LLM como coach experto en LoL competitivo español
  - **User prompt:** Inyecta el reporte diferencial del jugador con métricas y deltas
- Incluir contexto específico:
  - Meta actual del parche
  - Estilo de juego esperado según la línea
  - Debilidades detectadas en las métricas vs. referencia pro
- Implementar `prompt_engineer` con plantillas por rol

### Paso 2.3 — Generación de consejos
- Para cada jugador del equipo, ejecutar el pipeline:
  1. Cargar reporte desde MongoDB
  2. Construir prompt personalizado
  3. Llamar a Ollama y obtener respuesta
  4. Parsear y estructurar los consejos generados
- Estructura del output de consejos:
  ```
  === Informe de Coach IA para: [NickJugador] | [Línea] | [Campeón] ===

  📊 Métricas analizadas: CS/min 6.2 (-2.3 vs pro), KDA 3.1 (-1.7 vs pro)

  🎯 Áreas de mejora:
  1. [Consejo concreto sobre farmeo]
  2. [Consejo sobre rotaciones]
  3. [Consejo sobre macrojuego]

  ✅ Puntos fuertes detectados:
  - [Fortaleza 1]

  📌 Ejercicios recomendados para esta semana:
  - [Ejercicio práctico 1]
  - [Ejercicio práctico 2]
  ```

### Paso 2.4 — Persistencia y presentación de consejos
- Guardar consejos en MongoDB colección `coaching_reports` con timestamp
- Exportar informe completo del equipo como archivo `.txt` o `.md` en `/reports/`
- Output en consola con formato visual usando `rich` (paneles por jugador)

### Paso 2.5 — Pipeline completo end-to-end
- Implementar `pipeline_runner` como script de consola principal:
  ```
  python run_analysis.py --team mi_equipo --games 20 --output consola
  ```
- Flags de ejecución:
  - `--team` — Nombre del equipo (carga jugadores desde config)
  - `--games` — Número de partidas a analizar
  - `--player` — Analizar solo un jugador específico
  - `--skip-fetch` — Usar datos ya en MongoDB sin llamar a Riot API
  - `--model` — Seleccionar modelo Ollama a usar

**Entregable Fase 2:** Pipeline completo en consola que analiza al equipo completo y genera coaching personalizado por IA local.

---

## FASE 3 — Análisis Visual de Partidas mediante Vídeo (Fase Futura)

> ⚠️ Esta fase se documenta como planificación a futuro. No forma parte del sprint inicial.

**Objetivo:** Complementar los datos de la API con información visual extraída de grabaciones de partidas, permitiendo detectar patrones que la API no captura (posicionamiento, rotaciones visuales, decisiones en teamfights).

### Paso 3.1 — Módulo de ingesta de vídeo
- Integración con OBS / archivos locales de grabación
- Extracción de frames en momentos clave (cada N segundos, o por evento del timeline)
- Uso de `ffmpeg` para extracción de frames

### Paso 3.2 — Análisis de imagen con modelo multimodal
- Integración con modelo multimodal local (LLaVA vía Ollama, o similar)
- Detección en pantalla de:
  - Minimapa y posicionamiento de jugadores
  - Estado de objetivos (dragones, baron, torres)
  - Momentos de teamfight y posicionamiento durante combates
  - UI del jugador (ítems, habilidades, cooldowns visibles)

### Paso 3.3 — Fusión de datos API + Visión
- Correlacionar eventos del timeline de la API con momentos del vídeo
- Enriquecer el reporte de Fase 1 con datos visuales
- Alimentar al LLM de Fase 2 con contexto visual adicional

### Paso 3.4 — Integración con pipeline existente
- Añadir flag `--video` al `pipeline_runner`
- Flujo: vídeo → frames → análisis visual → merge con reporte API → LLM con contexto enriquecido

**Entregable Fase 3:** Pipeline híbrido (API + Visión) capaz de analizar partidas completas a partir de grabaciones de vídeo.

---

## 🗓️ Timeline Sugerido

| Fase | Duración estimada | Objetivo |
|------|-------------------|----------|
| Fase 1 | 2–3 semanas | API integrada, datos en Mongo, reporte comparativo generado |
| Fase 2 | 2 semanas | LLM local generando consejos personalizados por consola |
| Fase 3 | A definir | Análisis visual de vídeos integrado al pipeline |

**Meta total Fases 1+2:** Listo antes de Agosto para tener 4+ semanas de análisis antes de la competición de Septiembre.

---

## 📁 Estructura de Archivos Sugerida

```
esports-agent/
├── .env                          # API keys y config (no commitear)
├── docker-compose.yml            # MongoDB dev environment
├── requirements.txt
├── run_analysis.py               # Entry point principal
├── config/
│   ├── team.json                 # Jugadores del equipo (nick, línea, campeones)
│   └── settings.py               # Config global
├── modules/
│   ├── riot_api/
│   │   ├── client.py             # Cliente HTTP Riot API
│   │   ├── endpoints.py          # Definición de endpoints
│   │   └── rate_limiter.py       # Control de rate limiting
│   ├── data/
│   │   ├── match_parser.py       # Parser de partidas
│   │   ├── player_comparator.py  # Lógica de comparativas
│   │   └── report_builder.py     # Constructor de reportes
│   ├── db/
│   │   ├── connection.py         # Conexión MongoDB
│   │   └── repositories.py       # Operaciones CRUD
│   └── llm/
│       ├── ollama_client.py      # Cliente Ollama
│       ├── prompt_engineer.py    # Plantillas de prompts
│       └── llm_advisor.py        # Lógica de generación de consejos
├── scripts/
│   ├── ingest_team.py            # Ingesta inicial de datos del equipo
│   └── pipeline_runner.py        # Orquestador del pipeline completo
└── reports/                      # Outputs generados
```

---

*Documento generado como punto de partida para el agente de análisis E-sports. Actualizar conforme avance el proyecto.*