"""Ingestion pipeline: render Mongo docs (reports, player_matches) into
one-chunk-per-doc text, embed them, and upsert into the VectorStore.

ponytail: one chunk per document (no sub-chunking/overlap) — source docs are
already small, aggregated metric sets, not prose. Revisit only if free-text
notes/commentary fields are added later.
"""
from typing import Any, Dict, Optional

from modules.config_manager import get_embeddings_config
from modules.logger import get_logger


# Spanish narrative labels for known metric keys. The raw key is kept in
# parentheses so chunks share vocabulary with both natural-language questions
# and structured queries ("farm", "asesinatos", "oro", "visión", ...).
_METRIC_LABELS: Dict[str, str] = {
    "cs_per_min": "Farmeo (cs_per_min)",
    "cs": "Farmeo (cs)",
    "cs_min": "Farmeo (cs_min)",
    "kda": "KDA (kda)",
    "kills": "Asesinatos (kills)",
    "deaths": "Muertes (deaths)",
    "early_deaths": "Muertes tempranas (early_deaths)",
    "deaths_early": "Muertes tempranas (deaths_early)",
    "assists": "Asistencias (assists)",
    "vision_score": "Visión (vision_score)",
    "vision": "Visión (vision)",
    "wards_placed": "Centinelas (wards_placed)",
    "wards": "Centinelas (wards)",
    "damage_pct": "Daño (damage_pct)",
    "damage_share": "Daño (damage_share)",
    "damage": "Daño (damage)",
    "gold": "Oro (gold)",
    "gold_per_min": "Oro por minuto (gold_per_min)",
    "objectives_taken": "Objetivos (objectives_taken)",
    "objectives": "Objetivos (objectives)",
    "rotations": "Rotaciones (rotations)",
    "roams": "Rotaciones (roams)",
    "game_length": "Duración (game_length)",
    "duration": "Duración (duration)",
    "tempo": "Ritmo (tempo)",
    "tempo_notes": "Ritmo (tempo_notes)",
    "mental_notes": "Notas mentales (mental_notes)",
}

# Keys handled by render_match_text (rendered as header/fields or intentionally
# not metric lines); anything else is appended verbatim so no metric is dropped
# from the chunk.
_MATCH_METRIC_KEYS = {
    "kills", "deaths", "assists", "cs", "laneMinionsFirst10Minutes",
    "goldEarned", "visionScore", "damageDealtToChampions", "championName",
    "role", "teamId", "timestamp", "win", "puuid", "summonerName",
}

# Riot teamPosition vocabulary -> canonical role names. Ingestion normalizes
# metadata ONCE so role where-filters (Top/Jungle/Mid/Bot/Support) actually
# match stored docs.
_ROLE_CANONICAL: Dict[str, str] = {
    "TOP": "Top",
    "JUNGLE": "Jungle",
    "MIDDLE": "Mid",
    "BOTTOM": "Bot",
    "UTILITY": "Support",
}


def _canonical_role(role: Optional[str]) -> Optional[str]:
    """Normalize a Riot teamPosition value to the canonical role name.

    Maps TOP/JUNGLE/MIDDLE/BOTTOM/UTILITY to Top/Jungle/Mid/Bot/Support,
    tolerates case variants (top, MIDDLE, Support), and returns unknown
    values as-is (None stays None).
    """
    if role is None:
        return None
    return _ROLE_CANONICAL.get(str(role).upper(), role)


def _metric_part(key: str, value: Any) -> str:
    label = _METRIC_LABELS.get(key, key)
    return f"{label}: {value if value is not None else '-'}"


def render_report_text(doc: Dict[str, Any]) -> str:
    role = doc.get("role") or "desconocido"
    games_analyzed = doc.get("games_analyzed")
    metrics = doc.get("metrics", {}) or {}
    parts = [
        f"Reporte del jugador en rol {role} tras "
        f"{games_analyzed if games_analyzed is not None else '-'} partidas."
    ]
    parts.extend(_metric_part(k, v) for k, v in metrics.items())
    return " ".join(parts)


def render_match_text(doc: Dict[str, Any]) -> str:
    match_id = doc.get("matchId") or doc.get("id")
    role = doc.get("role")
    metrics = doc.get("parsed_metrics") or doc.get("metrics") or {}
    champ = doc.get("championName") or metrics.get("championName")
    kills, deaths, assists = metrics.get("kills"), metrics.get("deaths"), metrics.get("assists")
    cs = metrics.get("cs")
    gold = metrics.get("goldEarned")
    dmg = metrics.get("damageDealtToChampions")
    vision = metrics.get("visionScore")
    win = metrics.get("win")

    parts = [f"Partida {match_id or '-'} | Rol {role or '-'} | Campeón {champ or '-'}"]
    if kills is not None or deaths is not None or assists is not None:
        k = kills if kills is not None else "-"
        d = deaths if deaths is not None else "-"
        a = assists if assists is not None else "-"
        parts.append(f"KDA {k}/{d}/{a} (kills/muertes/asistencias)")
    if cs is not None:
        parts.append(f"Farmeo total (cs): {cs}")
    cs10 = metrics.get("laneMinionsFirst10Minutes")
    if cs10 is not None:
        parts.append(f"Farmeo a los 10 minutos (laneMinionsFirst10Minutes): {cs10}")
    if gold is not None:
        parts.append(f"Oro total (goldEarned): {gold}")
    if dmg is not None:
        parts.append(f"Daño a campeones (damageDealtToChampions): {dmg}")
    if vision is not None:
        parts.append(f"Visión (visionScore): {vision}")
    if win is not None:
        parts.append(f"Victoria {'Sí' if win else 'No'}")
    extras = {k: v for k, v in metrics.items() if k not in _MATCH_METRIC_KEYS and v is not None}
    if extras:
        parts.append(", ".join(f"{k}: {v}" for k, v in extras.items()))
    return " | ".join(parts)


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
            "role": _canonical_role(d.get("role")),
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
            "role": _canonical_role(d.get("role")),
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
