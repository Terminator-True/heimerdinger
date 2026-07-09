# ⚔ Heimerdinger — LoL Coaching Agent

**Heimerdinger** es un agente de análisis y coaching para **League of Legends** orientado a e-sports. Ingiere datos de la Riot Games API, genera reportes comparativos con benchmarks por rol, y usa un LLM local (Ollama) para producir consejos de coaching personalizados.

---

## ✨ Funcionalidades

- **Ingesta de partidas** — Resuelve Riot IDs, obtiene historial y datos completos de partidas desde la Riot API v5
- **Rate limiting** — Token bucket para clave gratuita de Riot (20 req/s)
- **Reportes por jugador** — 60+ métricas agregadas: KDA, CS/min, GPM, visión, daño, objetivos, etc.
- **Reportes por partida** — Análisis detallado partida a partida
- **Coach con IA local** — Ollama genera consejos personalizados según rol y campeón
- **Clasificación inteligente de preguntas** — Híbrido rules + sentence-transformers para categorizar consultas
- **Recuperación contextual** — Pasajes relevantes desde reports + fallback a ChromaDB
- **TUI interactiva** — Interfaz de terminal con Textual, gráficos ASCII con Plotext
- **Pipeline automatizado** — Ingesta → reportes → LLM coaching end-to-end
- **Schema-driven coaching** — 5 roles con benchmarks específicos y campos priorizados por rol

---

## Stack

| Componente | Tecnología |
|------------|-----------|
| Lenguaje | Python 3.11+ |
| API externa | Riot Games API v5 |
| Base de datos | MongoDB |
| LLM local | Ollama (llama3.1, mistral, deepseek-coder) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector store | ChromaDB |
| TUI | Textual + Rich + Plotext |
| HTTP | httpx |
| Tests | pytest + pytest-asyncio + respx |

---

## Quickstart

### 1. Requisitos

- Python 3.11+
- MongoDB (local o Docker)
- Ollama con un modelo descargado (ej: `ollama pull llama3.1:8b`)
- API key de Riot Games ([get it here](https://developer.riotgames.com/))

### 2. Configuración

```bash
# Clonar el repo
git clone <repo-url> && cd heimerdinger

# Variables de entorno
cp config/.env.example .env
# Editar .env con RIOT_API_KEY y MONGO_URI

# Dependencias
pip install -r requirements.txt

# Dependencias opcionales (embeddings)
pip install sentence-transformers chromadb

# Modelo Ollama
ollama pull llama3.1:8b

# Opcional: correr MongoDB con Docker
docker run -d -p 27017:27017 --name mongodb mongo:7
```

### 3. Uso básico

```bash
# Menú interactivo
python scripts/main.py

# Pipeline completo automático
python scripts/pipeline_runner.py --team config/team.json --games 5 --model llama3.1:8b

# Coach interactivo
python scripts/ask_coach.py --question "Analiza mi rendimiento como support" --role Support

# TUI (interfaz gráfica en terminal)
python -m tui.app
```

---

## Estructura del proyecto

```
heimerdinger/
├── config/                  # Configuración
│   ├── .env.example         # Template de variables de entorno
│   ├── team.json            # Jugadores del equipo
│   └── coaching_schema.json # Schema de coaching por rol
├── modules/                 # Backend
│   ├── riot_api/            # Cliente Riot API + rate limiter
│   ├── data/                # Match parser + report builder
│   ├── db/                  # Conexión MongoDB + repositorios
│   ├── ingest/              # Lógica de ingesta de partidas
│   ├── llm/                 # Ollama, prompts, clasificación, retrieval
│   ├── embeddings/          # sentence-transformers + ChromaDB
│   ├── coaching/            # Schema-driven prompt builder
│   ├── config_manager.py    # Carga de equipos
│   └── logger.py            # Logger estructurado
├── scripts/                 # Entrypoints CLI
│   ├── main.py              # Menú interactivo
│   ├── ask_coach.py         # Coach interactivo
│   ├── pipeline_runner.py   # Pipeline completo
│   └── ...
├── tui/                     # Frontend TUI (Textual)
│   ├── app.py               # Entrypoint
│   ├── screens/             # 5 pantallas
│   ├── widgets/             # StatCard, ChartWidget
│   └── utils/               # Formatters, benchmarks
├── tests/                   # 17 archivos de test
├── front-end.md             # Documentación de la TUI
├── back-end.md              # Documentación del backend
├── flux.md                  # Flujo de datos
└── User.md                  # Guía de usuario
```

---

## Documentación

| Archivo | Contenido |
|---------|-----------|
| [`front-end.md`](front-end.md) | Documentación de la interfaz TUI (Textual) |
| [`back-end.md`](back-end.md) | Arquitectura y módulos del backend |
| [`flux.md`](flux.md) | Flujo de datos end-to-end |
| [`User.md`](User.md) | Guía de usuario funcional |
| [`start.md`](start.md) | Plan de inicio del proyecto (visión original) |

---

## Roles y equipo

El archivo `config/team.json` define los 5 jugadores con sus roles y campeones. Por defecto:

| Jugador | Rol | Campeones principales |
|---------|-----|----------------------|
| TR Terminator#1998 | Support | Nami, Vel'Koz, Leona, Thresh |
| TR Adria Kila#DKS | Mid | Sylas, Aatrox, Lux, Ekko |
| TR Arkinos#777 | Jungle | Shyvana, Lee Sin, Kayn |
| TR alex132mini#ASF | Top | Dr. Mundo, Garen, Mordekaiser, Yone |
| TR Markos316#GGWP | ADC | Swain, Twitch, Kai'Sa, Jhin |

---

## Tests

```bash
# Todos los tests
pytest tests/

# Tests con coverage
pytest tests/ --cov=modules --cov-report=term-missing
```

---

## Licencia

Proyecto privado — uso educativo y competitivo para e-sports.
