# Heimerdinger — Frontend (TUI)

> Terminal User Interface construida con **Textual** para coaching de League of Legends.

---

## Stack

| Librería | Versión | Rol |
|----------|---------|-----|
| `textual` | ≥ 0.60 | Framework TUI — layouts, widgets, CSS, bindings |
| `rich` | ≥ 13.0 | Tablas, colores, paneles, markup en terminal |
| `plotext` | ≥ 5.2 | Gráficos ASCII (barras, líneas, scatter) |

---

## Estructura

```
tui/
├── app.py                  # Entrypoint — HeimdingertApp
├── heimdinger.tcss         # CSS de Textual (paleta LoL)
├── screens/
│   ├── dashboard.py        # Overview del equipo + stat cards + tabla
│   ├── ingest_screen.py    # Formulario de ingesta con log en vivo
│   ├── player_screen.py    # Detalle individual + gráficos + feedback IA
│   ├── coach_screen.py     # Chat interactivo con streaming de Ollama
│   └── pipeline_screen.py  # Pipeline completo con progreso por jugador
├── widgets/
│   ├── stat_card.py        # Tarjeta de métrica individual
│   ├── chart_widget.py     # Wrapper de plotext para gráficos ASCII
│   └── __init__.py
└── utils/
    ├── formatters.py       # Formateo de KDA, GPM, duración, nombres
    ├── benchmarks.py       # Comparación vs benchmarks por rol
    └── __init__.py
```

---

## Paleta visual

Inspirada en el HUD de League of Legends:

| Variable | Color | Uso |
|----------|-------|-----|
| `#0A0E1A` | Fondo primario | Base de pantallas |
| `#111827` | Fondo secundario | Paneles, sidebar |
| `#1C2333` | Fondo elevado | Tarjetas, modales |
| `#C89B3C` | Gold (acento) | Títulos, bordes activos, botones primary |
| `#0BC4C4` | Teal | Métricas positivas, highlights |
| `#E84057` | Rojo peligro | Muertes, métricas bajo benchmark |
| `#E8E8E8` | Texto primario | Contenido principal |
| `#8892A4` | Texto secundario | Labels, hints, info |
| `#2A3447` | Borde | Separadores, bordes de widgets |

---

## Pantallas

### 1. Dashboard (`dashboard.py`)

Pantalla principal con:

- **Sidebar** de navegación (Dashboard, Ingestar, Coach, Pipeline)
- **4 StatCards** con resumen del equipo: Win Rate, Avg KDA, Avg GPM, Visión
- **DataTable** del equipo: filas por jugador con Nick, Rol, KDA, GPM, WR
- **ChartWidget** con win rate trend (plotext bar chart)
- Config-check visual: .env ✓, Ollama ✓, Riot ✓

Navegación por teclado + click en filas para ir al detalle del jugador.

### 2. Ingestar Jugador (`ingest_screen.py`)

Formulario con:
- `Input` para Riot ID (Name#Tagline)
- `Input` para cantidad de partidas
- `Select` para región (europe/americas/asia/sea)
- Botón **▶ INGESTAR** que lanza worker asíncrono
- `RichLog` con log en tiempo real del progreso
- `ProgressBar` de partidas ingestadas

Toda llamada a Riot API corre en `asyncio.to_thread()` para no bloquear la TUI.

### 3. Detalle de Jugador (`player_screen.py`)

Dos columnas:
- **Izquierda**: Últimas partidas con resultado (✓/✗), KDA, GPM
- **Derecha**: Métricas agregadas con barras de benchmark:
  - KDA medio, GPM medio, CS@10, Vision/min, Kill Participation
- **Gráficos Plotext**: KDA trend (línea), GPM por partida (línea)
- **Feedback IA**: Botón para generar consejo con LLaMA

### 4. Ask the Coach (`coach_screen.py`)

Chat interactivo con:
- Selector de modelo Ollama
- Selector de jugador activo y rol
- Historial de mensajes (burbujas usuario/IA)
- **Streaming en vivo** de respuestas de Ollama vía `httpx.AsyncClient`
- Input de pregunta + botón ▶ Enviar
- Atajo `Ctrl+L` para limpiar chat, `Ctrl+P` para cambiar jugador

### 5. Pipeline Completo (`pipeline_screen.py`)

Orquestación visual con:
- Panel de configuración: team file, partidas, modelo LLM
- Árbol de progreso por jugador (Ingest → Report → LLM)
- `ProgressBar` individual por fase y jugador
- Botones: **▶ EJECUTAR**, **⏸ Pausar**, **✕ Abortar**
- `RichLog` con eventos timestamped

---

## Navegación por teclado

| Tecla | Acción |
|-------|--------|
| `Q` | Salir |
| `F1` | Ayuda / atajos |
| `F5` | Refrescar datos |
| `1` `2` `3` `4` | Dashboard / Ingestar / Coach / Pipeline |
| `↑ ↓` | Navegar sidebar / tabla |
| `Enter` | Seleccionar ítem |
| `Esc` | Volver / cerrar modal |
| `Tab` | Navegar campos de formulario |
| `Ctrl+L` | Limpiar log |
| `Ctrl+P` | Cambiar jugador activo (Coach) |

---

## Integración con backend

La TUI **no duplica lógica**: llama directamente a los módulos del backend:

| Acción TUI | Módulo backend |
|------------|----------------|
| Ingestar jugador | `modules.ingest.lib.ingest_player` |
| Cargar equipo | `modules.config_manager.get_team` |
| Generar reportes | `modules.data.report_builder.ReportBuilder` |
| Chat con coach | `scripts.ask_coach.ask_coach` |
| Pipeline completo | `modules.llm.llm_advisor.LLMAdvisor` + `ingest_player` |

Toda operación bloqueante (Riot API, Ollama, MongoDB) se ejecuta en workers asíncronos.

---

## Entrypoint

```bash
python -m tui.app
# o con hot-reload:
textual run tui/app.py
```
