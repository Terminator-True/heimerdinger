"""Ingestion pipeline: render Mongo docs (reports, player_matches) into
one-chunk-per-doc text, embed them, and upsert into the VectorStore.

ponytail: one chunk per document (no sub-chunking/overlap) — source docs are
already small, aggregated metric sets, not prose. Revisit only if free-text
notes/commentary fields are added later.
"""
from typing import Any, Dict, Optional

from modules.config_manager import get_embeddings_config
from modules.logger import get_logger


def render_report_text(doc: Dict[str, Any]) -> str:
    role = doc.get("role")
    games_analyzed = doc.get("games_analyzed")
    metrics = doc.get("metrics", {}) or {}
    metrics_str = ", ".join(f"{k}: {v}" for k, v in metrics.items())
    return f"Role: {role} | Games analyzed: {games_analyzed} | {metrics_str}"


def render_match_text(doc: Dict[str, Any]) -> str:
    match_id = doc.get("matchId") or doc.get("id")
    puuid = doc.get("player_puuid") or doc.get("player")
    role = doc.get("role")
    date = doc.get("date")
    metrics = doc.get("parsed_metrics") or doc.get("metrics") or {}
    metrics_str = ", ".join(f"{k}: {v}" for k, v in metrics.items())
    return f"Match {match_id} | Player {puuid} | Role: {role} | Date: {date} | {metrics_str}"


def _get_reports_docs(db):
    try:
        col = db.get_collection("reports")
        return list(col.find({}))
    except Exception:
        col = db.setdefault("reports", {})
        return list(col.values())


def _get_player_matches_docs(db):
    try:
        col = db.get_collection("player_matches")
        return list(col.find({}))
    except Exception:
        col = db.setdefault("player_matches", {})
        return list(col.values())


def ingest_reports(db, store, embedder) -> int:
    """Ingest all `reports` docs as one chunk per document. Returns count ingested."""
    logger = get_logger()
    docs = _get_reports_docs(db)
    if not docs:
        return 0

    ids = [f"report:{d.get('_id')}" for d in docs]
    texts = [render_report_text(d) for d in docs]
    metadatas = [
        {
            "source_type": "report",
            "puuid": d.get("player") or d.get("player_puuid"),
            "role": d.get("role"),
            "report_id": str(d.get("_id")),
            "games_analyzed": d.get("games_analyzed"),
        }
        for d in docs
    ]
    embeddings = embedder.embed_texts(texts)
    store.upsert_docs(ids=ids, texts=texts, embeddings=embeddings, metadatas=metadatas)
    logger.info("ingest_reports: upserted %d chunks", len(ids))
    return len(ids)


def ingest_player_matches(db, store, embedder) -> int:
    """Ingest all `player_matches` docs as one chunk per document. Returns count ingested."""
    logger = get_logger()
    docs = _get_player_matches_docs(db)
    if not docs:
        return 0

    def match_id_of(d):
        return d.get("matchId") or d.get("id")

    def puuid_of(d):
        return d.get("player_puuid") or d.get("player")

    ids = [f"match:{match_id_of(d)}:{puuid_of(d)}" for d in docs]
    texts = [render_match_text(d) for d in docs]
    metadatas = [
        {
            "source_type": "player_match",
            "match_id": match_id_of(d),
            "puuid": puuid_of(d),
            "role": d.get("role"),
            "date": d.get("date"),
        }
        for d in docs
    ]
    embeddings = embedder.embed_texts(texts)
    store.upsert_docs(ids=ids, texts=texts, embeddings=embeddings, metadatas=metadatas)
    logger.info("ingest_player_matches: upserted %d chunks", len(ids))
    return len(ids)


def run_ingestion(db=None) -> Dict[str, int]:
    """Run full ingestion for reports + player_matches. Wires config/embedder/store."""
    from modules.db.connection import get_db
    from modules.embeddings.embedder import Embedder
    from modules.embeddings.store import VectorStore

    if db is None:
        db = get_db()

    config = get_embeddings_config()
    embedder = Embedder(model_name=config["embedding_model"])
    store = VectorStore(
        persist_directory=config["persist_directory"],
        collection_name=config["collection_name"],
    )

    reports_count = ingest_reports(db, store, embedder)
    matches_count = ingest_player_matches(db, store, embedder)
    return {"reports": reports_count, "player_matches": matches_count}
