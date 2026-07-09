# User Guide — Heimerdinger

> Guía de usuario para navegar y usar todas las funcionalidades de Heimerdinger.

---

## Índice

- [Menú Principal (CLI)](#menú-principal-cli)
- [Ingestar un Jugador](#ingestar-un-jugador)
- [Ingestar un Equipo](#ingestar-un-equipo)
- [Ask the Coach](#ask-the-coach)
- [Pipeline Completo](#pipeline-completo)
- [TUI — Terminal User Interface](#tui--terminal-user-interface)
- [Preguntas al Coach](#preguntas-al-coach)
- [FAQ y Troubleshooting](#faq-y-troubleshooting)

---

## Menú Principal (CLI)

```bash
python scripts/main.py
```

Muestra un menú con 5 opciones:

```
Heimdinger  —  League of Legends Coaching
Ingesta • Análisis • Coaching con IA

  1    Ingestar un solo jugador
  2    Ingestar un equipo (desde archivo)
  3    Ask the Coach — modo interactivo
  4    Pipeline completo (ingest + reportes)
  5    Salir
```

Seleccioná un número y presioná Enter.

---

## Ingestar un Jugador

**Opción 1** del menú, o directamente:

```bash
python scripts/ingest_one_player.py --riotid "TR Terminator#1998" --count 5 --region europe
```

**Datos que se guardan:**
- Cuenta del invocador (PUUID, Riot ID)
- Partidas completas (raw JSON de Riot) en colección `matches`
- Métricas parseadas por partida en `player_matches`

**Rate limiting:** El cliente usa un token bucket de 20 req/s. Las requests se encolan automáticamente.

**Si falla:**
- `401 Unauthorized` — revisá `RIOT_API_KEY` en `.env`
- `404 Not Found` — el Riot ID puede ser incorrecto
- `429 Rate limit` — esperá un minuto y reintentá

---

## Ingestar un Equipo

**Opción 2** del menú, o:

```bash
python scripts/ingest_team.py --team config/team.json --games 5
```

El archivo `config/team.json` tiene esta estructura:

```json
[
  { "riotid": "TR Terminator#1998", "role": "Support", "champions": ["Nami", "Leona"] },
  { "riotid": "TR Adria Kila#DKS", "role": "Mid", "champions": ["Sylas", "Ekko"] }
]
```

El script itera cada jugador, lo ingesta y muestra un resumen al final:
`Listo: 5/5 jugadores ingestados.`

---

## Ask the Coach

**Opción 3** del menú (modo interactivo), o:

```bash
python scripts/ask_coach.py --question "¿Cómo mejorar mi fase de líneas?" --role Top --model llama3.1:8b
```

### Modo interactivo

1. El script pide **una sola vez**: modelo, rol, si usar última partida, idioma
2. Después solo se muestran las preguntas y respuestas — sin logs, sin ruido
3. Escribí `salir`, `quit`, `exit` o `q` para terminar

### Categorías de preguntas

El coach clasifica tu pregunta automáticamente en:

| Categoría | Ejemplos |
|-----------|----------|
| `laning` | Fase de líneas, CS, trades, wave management |
| `vision` | Wards, visión, control de mapa, ward clearance |
| `macro` | Rotaciones, objetivos, dragón, barón, torres |
| `teamfights` | Teamfights, engage, peel, posicionamiento |
| `pacing` | Tempo, ritmo de juego, cuándo acelerar |
| `mental` | Tilt, mental, confianza, enfoque, mindset |
| `general` | Cualquier otra cosa |

### Clasificación híbrida

El sistema primero intenta clasificar por **reglas (keywords)**. Si es inconcluso, usa **sentence-transformers** (embedding similarity). Si ambos fallan, la pregunta se trata como `general`.

### Recuperación de contexto

El coach busca pasajes relevantes en MongoDB:
1. **Recipes por categoría** — Busca métricas específicas según la categoría
2. **Vector store (fallback)** — ChromaDB con embeddings de partidas previas

### Última partida vs. agregado

- **`--last-match`**: Analiza solo la partida más reciente con datos detallados
- **Sin flag**: Usa reportes agregados (promedio de N partidas)

### Streaming en TUI

En la interfaz TUI (pantalla Coach), las respuestas de Ollama aparecen **en vivo** carácter por carácter, como un chat real.

---

## Pipeline Completo

**Opción 4** del menú, o:

```bash
python scripts/pipeline_runner.py \
  --team config/team.json \
  --games 5 \
  --model llama3.1:8b \
  --max-llm-per-player 1 \
  --region europe
```

### Flags disponibles

| Flag | Default | Descripción |
|------|---------|-------------|
| `--team` | `config/team.json` | Archivo del equipo |
| `--games` | `1` | Partidas por jugador |
| `--region` | `europe` | Región de la API |
| `--model` | `llama3.1:8b` | Modelo Ollama para coaching |
| `--per-match` | `false` | Generar reportes por partida (vs agregados) |
| `--max-llm-per-player` | `0` | Llamadas a LLaMA (0 = deshabilitado) |
| `--skip-fetch` | `false` | Usar datos ya descargados |

### Flujo del pipeline

Por cada jugador del equipo:
1. **Ingesta** → Resuelve PUUID, fetch de partidas, guarda en MongoDB
2. **Reportes** → Métricas agregadas o por partida
3. **LLM** (opcional) → Construye prompt con reporte + retrieval → llama a Ollama

---

## TUI — Terminal User Interface

```bash
python -m tui.app
# o con hot-reload:
textual run tui/app.py
```

### Pantallas

| Tecla | Pantalla | Descripción |
|-------|----------|-------------|
| `1` | Dashboard | Overview del equipo con stat cards y tabla |
| `2` | Ingestar | Formulario para ingestar un jugador |
| `3` | Coach | Chat interactivo con streaming de Ollama |
| `4` | Pipeline | Pipeline completo con progreso en vivo |

### Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `Q` | Salir |
| `F1` | Ayuda / atajos |
| `F5` | Refrescar pantalla |
| `Esc` | Volver / cerrar modal |
| `↑ ↓` | Navegar listas / tabla |
| `Enter` | Seleccionar / enviar |
| `Tab` | Navegar campos de formulario |
| `Ctrl+L` | Limpiar log |
| `Ctrl+P` | Cambiar jugador activo (Coach) |

### Dashboard

Muestra:
- **4 stat cards**: Win Rate, Avg KDA, Avg GPM, Visión
- **Tabla del equipo**: Nick, Rol, KDA, GPM, WR
- **Gráfico**: Win rate trend (barras ASCII)
- **Status de config**: .env, Ollama, Riot (checkmarks)

Click en una fila de jugador → abre el detalle con gráficos.

### Pantalla de Jugador

Dos columnas:
- **Izquierda**: Últimas partidas con resultado (✓/✗), KDA, GPM
- **Derecha**: Métricas agregadas con barras de benchmark:
  - KDA medio, GPM medio, CS@10, Vision/min, Kill Participation
- **Gráficos**: KDA trend (línea), GPM por partida (línea)
- **Feedback IA**: Botón para generar consejo con LLaMA

### Pantalla de Coach

Chat interactivo con:
- Selector de modelo Ollama
- Selector de jugador activo y rol
- Streaming de respuestas en vivo
- Historial de mensajes

### Pantalla de Pipeline

Orquestación visual con:
- Configuración (team file, partidas, modelo)
- Árbol de progreso por jugador con barras
- Botones: EJECUTAR, Pausar, Abortar
- Log con eventos timestamped

---

## Preguntas al Coach

### Ejemplos de preguntas efectivas

```
❓ ¿Por qué pierdo tantas partidas con Darius?
❓ ¿Cómo mejorar mi visión como support?
❓ En qué debería enfocarme en teamfights con Ahri?
❓ Mi CS baja mucho después de los 15 minutos, qué hago?
❓ Cómo controlar el tilt cuando pierdo 3 partidas seguidas?
```

El coach usa el **rol seleccionado** para enfocar el análisis. Si no seleccionás rol, da consejos generales.

### FAQ

**P: ¿Necesito Ollama sí o sí?**
R: Sí, para el modo Coach. El pipeline de ingesta y reportes funciona sin Ollama.

**P: ¿Qué modelo de Ollama recomiendan?**
R: `llama3.1:8b` es el mejor balance velocidad/calidad. `mistral:7b` también funciona bien.

**P: ¿Cuántas partidas debería analizar?**
R: 5-10 partidas dan una muestra representativa. Menos de 3 no es estadísticamente significativo.

**P: ¿Los reportes se borran al cerrar?**
R: No, quedan en MongoDB. Usá `--skip-fetch` en pipelines posteriores para evitar llamar a la API de Riot de nuevo.

---

## Troubleshooting

### Error: `RIOT_API_KEY no está configurada`

Creá un archivo `.env` en la raíz del proyecto:

```
RIOT_API_KEY=RGAPI_xxxxxxxxxxxxxxxxxxxx
MONGO_URI=mongodb://localhost:27017/heimerdinger
REGION=europe
```

### Error: `Ollama returned HTTP 000`

Ollama no está corriendo. Inicialo con:

```bash
ollama serve
# en otra terminal:
ollama pull llama3.1:8b
```

### Error: `MongoDB connection refused`

Asegurate que MongoDB esté corriendo:

```bash
# Con Docker:
docker run -d -p 27017:27017 --name mongodb mongo:7
# O local:
mongod --dbpath /data/db
```

### La TUI no arranca

```bash
pip install textual plotext
# Verificar versión:
python -c "import textual; print(textual.__version__)"  # ≥ 0.60
```

### Los gráficos Plotext se ven mal

Ajustá el tamaño de la terminal. Plotext necesita al menos 80×24. Probá con:

```bash
textual run tui/app.py
```

Que tiene hot-reload y mejor manejo de tamaño.
