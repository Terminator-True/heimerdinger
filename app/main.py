"""Heimerdinger FastAPI backend.

Exposes the existing Heimerdinger modules (ingest, reports, coach, embeddings)
as REST endpoints. All endpoints are synchronous (`def`, NOT `async def`) so
FastAPI runs the blocking work — pymongo, httpx, sentence-transformers,
Ollama — in the threadpool. Nothing in this codebase is async, so we don't
fake it with async wrappers.

Authentication: if ``API_TOKEN`` is set in the environment, every endpoint
except ``/`` and ``/health`` requires ``X-API-Key: <token>``. If it is unset,
the API runs open (dev mode) and logs a warning — do NOT bind beyond loopback
without setting it.

Run from the repo root:
    uvicorn app.main:app --reload
"""
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from modules.logger import get_logger

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
load_dotenv()

from modules.config_manager import CONFIG_DIR, get_team
from modules.db.connection import get_db
from modules.ingest.lib import ingest_player, resolve_team_puuids
from modules.riot_api.client import RiotClient
from modules.data.report_builder import (
    ReportBuilder,
    get_full_match,
    extract_team_composition,
    render_match_snapshot,
)

from app.schemas import (
    CoachRequest,
    EmbeddingQueryRequest,
    IngestPlayerRequest,
    IngestTeamRequest,
)

logger = get_logger(__name__)

API_TOKEN = os.getenv("API_TOKEN")

app = FastAPI(title="Heimerdinger API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Reject requests without the configured API key when API_TOKEN is set."""
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(401, "invalid or missing API key")


# Endpoints that touch data / cost (ingest -> Riot quota, coach -> Ollama,
# embeddings -> model) live behind the auth dependency. Liveness meta stays
# public.
api = APIRouter(dependencies=[Depends(require_api_key)])

if not API_TOKEN:
    logger.warning(
        "API_TOKEN is not set — Heimerdinger API has NO authentication. "
        "Set API_TOKEN in .env before binding beyond loopback."
    )


# ---------------------------------------------------------------------------
#  dependencies
# ---------------------------------------------------------------------------

_db = None
_embedder = None
_vector_store = None


def get_db_dep() -> Any:
    """Cached MongoDB handle. pymongo connects lazily and pools internally,
    so a single client is safe to share across requests/threads."""
    global _db
    if _db is None:
        _db = get_db(os.getenv("MONGO_URI"))
    return _db


def get_embedder():
    """Cached sentence-transformers model (heavy to load per request)."""
    global _embedder
    if _embedder is None:
        from modules.embeddings.embedder import Embedder

        _embedder = Embedder()
    return _embedder


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        from modules.embeddings.store import VectorStore

        _vector_store = VectorStore()
    return _vector_store


def _clean(obj: Any) -> Any:
    """Recursively normalize values FastAPI's JSON encoder can't serialize:
    Mongo ObjectIds -> str, numpy scalars -> python numbers."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if hasattr(obj, "item"):  # numpy scalar (e.g. np.float32 distance)
        try:
            return obj.item()
        except Exception:
            return float(obj)
    return obj


def _valid_team_path(team_path: str) -> bool:
    """Only plain filenames are allowed — never a path (prevents arbitrary
    local file reads). get_team then resolves the name under config/."""
    return "/" not in team_path and "\\" not in team_path and ".." not in team_path


def _team_or_404(team_path: str) -> List[Dict[str, Any]]:
    if not _valid_team_path(team_path):
        raise HTTPException(400, "team_path must be a filename under config/, not a path")
    try:
        return get_team(team_path)
    except FileNotFoundError:
        raise HTTPException(404, f"team file not found: {team_path}")


# ---------------------------------------------------------------------------
#  meta (public)
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"name": "Heimerdinger API", "docs": "/docs", "openapi": "/openapi.json"}


@app.get("/health")
def health(db: Any = Depends(get_db_dep)):
    try:
        db.list_collection_names()
        db_ok = True
    except Exception:
        db_ok = False
    if not db_ok:
        raise HTTPException(503, "mongodb unavailable")
    return {"status": "ok", "mongodb": True}


# ---------------------------------------------------------------------------
#  team
# ---------------------------------------------------------------------------

@api.get("/team")
def team(team_path: str = Query("team.json")):
    return _team_or_404(team_path)


# ---------------------------------------------------------------------------
#  ingest
# ---------------------------------------------------------------------------

@api.post("/ingest/player")
def ingest_player_endpoint(req: IngestPlayerRequest):
    try:
        return ingest_player(
            riotid=req.riotid,
            count=req.count,
            region=req.region,
            region_rep=req.region_rep,
            team_puuids=req.team_puuids,
            min_team_members=req.min_team_members,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.exception("POST /ingest/player failed: %s", exc)
        raise HTTPException(500, "ingest failed")


@api.post("/ingest/team")
def ingest_team(req: IngestTeamRequest):
    team = _team_or_404(req.team_path)
    client = RiotClient(region=req.region)
    team_puuids = resolve_team_puuids(team, client)
    results = []
    for player in team:
        riotid = player.get("riotid")
        if not riotid:
            continue
        try:
            summary = ingest_player(
                riotid=riotid,
                count=req.count,
                region=req.region,
                region_rep=req.region_rep,
                team_puuids=team_puuids,
                min_team_members=5,
            )
        except (ValueError, RuntimeError) as exc:
            results.append({"riotid": riotid, "error": str(exc)})
            continue
        results.append({"riotid": riotid, **summary})
    return {"team_puuids_resolved": len(team_puuids), "players": results}


# ---------------------------------------------------------------------------
#  players / reports
# ---------------------------------------------------------------------------

@api.get("/players/{puuid}/matches")
def list_player_matches(
    puuid: str,
    limit: int = Query(50, ge=1, le=500),
    db: Any = Depends(get_db_dep),
):
    col = db.get_collection("player_matches")
    docs = list(col.find({"player_puuid": puuid}).sort("_id", -1).limit(limit))
    return [_clean(d) for d in docs]


@api.get("/players/{puuid}/report")
def player_report(puuid: str, db: Any = Depends(get_db_dep)):
    report = ReportBuilder().build_player_report(puuid, db)
    if report.get("status") == "empty":
        raise HTTPException(404, report.get("detail", "no player matches"))
    return report


@api.get("/players/{puuid}/matches/{match_id}/report")
def match_report(puuid: str, match_id: str, db: Any = Depends(get_db_dep)):
    col = db.get_collection("player_matches")
    doc = col.find_one({"player_puuid": puuid, "matchId": match_id})
    if not doc:
        raise HTTPException(404, "player_match not found")
    return ReportBuilder().build_match_report(doc, db)


# ---------------------------------------------------------------------------
#  matches
# ---------------------------------------------------------------------------

@api.get("/matches/{match_id}/composition")
def match_composition(match_id: str, db: Any = Depends(get_db_dep)):
    match = get_full_match(db, match_id)
    if not match:
        raise HTTPException(404, "match not found")
    return extract_team_composition(match)


@api.get("/matches/{match_id}/snapshot")
def match_snapshot(match_id: str, db: Any = Depends(get_db_dep)):
    match = get_full_match(db, match_id)
    if not match:
        raise HTTPException(404, "match not found")
    return {"snapshot": render_match_snapshot(match)}


# ---------------------------------------------------------------------------
#  coach
# ---------------------------------------------------------------------------

@api.post("/coach")
def coach(req: CoachRequest):
    try:
        # Imported lazily: ask_coach pulls in the whole retrieval/prompt stack.
        from scripts.ask_coach import ask_coach

        text = ask_coach(
            question=req.question,
            role=req.role,
            model=req.model,
            last_match=req.last_match,
            lang=req.lang,
            history=req.history,
        )
    except Exception as exc:
        logger.exception("POST /coach failed: %s", exc)
        raise HTTPException(502, "LLM request failed")
    return {"response": text}


# ---------------------------------------------------------------------------
#  embeddings
# ---------------------------------------------------------------------------

@api.post("/embeddings/seed")
def embeddings_seed(db: Any = Depends(get_db_dep)):
    from modules.embeddings.ingest import run_ingestion

    try:
        return run_ingestion(db=db)
    except Exception as exc:
        logger.exception("POST /embeddings/seed failed: %s", exc)
        raise HTTPException(500, "embedding ingestion failed")


@api.post("/embeddings/query")
def embeddings_query(req: EmbeddingQueryRequest):
    try:
        embedder = get_embedder()
        store = get_vector_store()
        emb = embedder.embed_texts([req.query])[0]
    except Exception as exc:
        logger.exception("POST /embeddings/query failed: %s", exc)
        raise HTTPException(503, "embedding stack unavailable")
    return {"hits": _clean(store.query(emb, top_k=req.top_k, where=req.where))}


app.include_router(api)