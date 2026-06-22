# E-Sports LoL Analytics Agent — Phase 1 Slice

This repository contains a minimal first slice to ingest match data from Riot Games API and store matches into MongoDB.

Quickstart
1. Copy config/.env.example to .env and fill RIOT_API_KEY and MONGO_URI
2. Start MongoDB (e.g., docker-compose up -d mongodb) or use a local instance
3. pip install -r requirements.txt
4. python scripts/ingest_one_player.py --name "SummonerName" --count 5 --region europe
