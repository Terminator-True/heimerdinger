# Guía de uso — E-Sports LoL Analytics Agent

Este repositorio contiene un pipeline CLI para recolectar datos de partidas de League of Legends (Riot API), parsearlos, comparar métricas y generar informes con apoyo de un LLM local (Ollama).

Resumen rápido
- Lenguaje: Python 3.11+
- Entrypoints principales:
  - scripts/ingest_one_player.py — Ingesta de N partidas para un RiotID (ej: "TR Terminator#1998").
  - scripts/ingest_team.py — Ingesta de todo un equipo desde config/team.json.
  - scripts/pipeline_runner.py — Orquesta ingest → parse → report → LLM advice para cada jugador del equipo.

Requisitos previos
- Python 3.11+ y pip
- MongoDB disponible (puede correr en localhost o en Docker)
- (Opcional) Ollama en http://localhost:11434 para la fase de coaching local

Instalación rápida
1. Crear y activar virtualenv (recomendado):
   python -m venv env
   env\Scripts\activate  (Windows)  o  source env/bin/activate (Unix)
2. Instalar dependencias:
   pip install -r requirements.txt
3. Copiar ejemplo de variables de entorno:
   cp config/.env.example .env   (o crear .env manualmente)
   Rellenar RIOT_API_KEY y MONGO_URI en .env

Ejecuciones comunes
- Ingestar un jugador (ejemplo):
  python scripts/ingest_one_player.py --riotid "TR Terminator#1998" --count 10 --region europe

- Ingestar un equipo definido en config/team.json:
  python scripts/ingest_team.py --team config/team.json --games 20 --region europe

- Correr el pipeline completo (ingesta → report → LLM):
  python scripts/pipeline_runner.py --team config/team.json --games 20 --region europe --model llama3.1:8b

Outputs y persistencia
- Raw matches: colección `matches` en MongoDB.
- Parsed métricas por jugador: colección `player_matches` en MongoDB.
- Informes agregados: colección `reports` en MongoDB y archivos `reports/{player_puuid}.json` en disco.

Pruebas
- Ejecutar la suite de tests con pytest:
  pytest -q

Notas operativas y troubleshooting
- Si Python no encuentra el paquete `modules`, ejecutá desde la raíz del repo o exportá PYTHONPATH a la raíz del repo.
- Error 401 Unauthorized al resolver RiotID: verificar que RIOT_API_KEY en .env es correcta y válida. Probar con:
  Invoke-RestMethod -Method Get -Headers @{ 'X-Riot-Token' = $env:RIOT_API_KEY } -Uri '<endpoint-de-prueba>'
- Si ves errores relacionados con respx/httpx en tests, puede ser incompatibilidad de versiones: fijar/pinear versiones de dev dependencies en requirements-dev.txt.
- Logs: se generan con modules/logger.py y rotan en logs/app.log.

Buenas prácticas
- No commitear .env ni claves. Usar secrets en CI.
- Ejecutar tests en un entorno limpio antes de abrir PRs.
- Para trabajo en equipo, considerar re-run de sdd-init en modo `openspec` o `hybrid` para generar artefactos file-based.

Contacto
- Si algo falla, pasame el output exacto del error y lo reviso.
