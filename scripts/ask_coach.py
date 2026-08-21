"""Ask the coaching LLM using minimal context retrieved from the DB.

Usage:
  python scripts/ask_coach.py --question "Qué consejos darías a nuestro toplane?" --role Top
  python scripts/ask_coach.py --question "Analiza mi última partida" --role Mid --last-match

Behavior:
- Classifies the question via hybrid (rule + embedding) classifier.
- Retrieves relevant context passages from reports/player_matches.
- Builds a structured-stats prompt with player metrics.
- Calls Ollama to produce coaching advice.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.logger import get_logger
from modules.config_manager import get_embeddings_config
from modules.db.connection import get_db
from modules.llm.ollama_client import OllamaClient
from modules.llm.prompt_engineer import PromptEngineer
from modules.llm.question_classifier import classify_question
from modules.llm.retrieval import retrieve_for_category, detect_role, keyword_candidates
from modules.data.report_builder import get_full_match, extract_rich_participant, render_match_snapshot
from modules.coaching.prompt_builder import CoachingPromptBuilder


# ------------------------------------------------------------------
#  helpers
# ------------------------------------------------------------------

def _find_report_for_role(db, role: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Fetch most recent reports matching a role (any role when empty)."""
    try:
        col = db.get_collection("reports")
        filter_q = {"role": role} if role else {}
        docs = list(col.find(filter_q).sort("_id", -1).limit(limit))
        return docs
    except Exception:
        try:
            col = db.setdefault("reports", {})
            out = []
            for d in col.values():
                if not role or d.get("role") == role:
                    out.append(d)
            return out[:limit]
        except Exception:
            return []


def _build_last_match_report(db, role: str, puuid: Optional[str] = None) -> Dict[str, Any]:
    """Fetch the most recent player_match + full match and build a
    per-match report dict compatible with PromptEngineer.format_report_stats.

    Returns::
        {"report": {...}, "full_match": {...}} or empty dict on failure.
    """
    logger = get_logger()
    try:
        # 1. find most recent player_match for this role (or any role)
        col = db.get_collection("player_matches")
        filter_q = {}
        if role:
            filter_q["role"] = role
        try:
            pm_docs = list(col.find(filter_q).sort("_id", -1).limit(10))
        except Exception:
            pm_docs = list(col.values())[:10]
            pm_docs.sort(key=lambda x: x.get("_id") or "", reverse=True)

        if not pm_docs:
            logger.warning("No player_matches found for role=%s", role)
            return {}

        # pick the first one (most recent)
        pm = pm_docs[0]
        match_id = pm.get("matchId") or pm.get("id") or ""
        player_puuid = puuid or pm.get("player_puuid") or ""

        if not match_id or not player_puuid:
            logger.warning("Missing matchId or player_puuid in player_match")
            return {}

        # 2. fetch full match doc
        full_match = get_full_match(db, match_id)
        if not full_match:
            logger.warning("No full match doc found for matchId=%s", match_id)
            return {}

        # 3. extract rich participant data
        rich = extract_rich_participant(full_match, player_puuid)
        if not rich:
            logger.warning("Participant not found for puuid=%s in match=%s", player_puuid, match_id)
            return {}

        # 4. build a compatible report dict
        report = {
            "player": player_puuid,
            "champion": rich.get("championName"),
            "role": rich.get("individualPosition") or rich.get("teamPosition") or pm.get("role"),
            "metrics": rich,
        }
        return {"report": report, "full_match": full_match, "puuid": player_puuid}

    except Exception as e:
        logger.exception("_build_last_match_report failed: %s", e)
        return {}


def _build_aggregate_report(db, role: str) -> Dict[str, Any]:
    """Fetch the most recent aggregate report for this role.

    Prefers multi-game aggregate reports (games_analyzed > 1); falls back to
    the latest report of any kind — the `reports` collection also stores
    per-match reports written by build_match_report.
    """
    logger = get_logger()
    try:
        docs = _find_report_for_role(db, role, limit=5)
        if docs:
            aggregates = [d for d in docs if isinstance(d.get("games_analyzed"), int) and d["games_analyzed"] > 1]
            return (aggregates or docs)[0]
        logger.warning("No aggregate reports found for role=%s", role)
    except Exception as e:
        logger.exception("_build_aggregate_report failed: %s", e)
    return {}


def _role_where(question: str, caller_role: Optional[str]) -> Optional[Dict]:
    """Chroma `where` filter narrowing retrieval to a role mentioned in the
    question, or None when no role is detected or the caller already plays it.

    Stored metadata is canonical (Top/Jungle/Mid/Bot/Support, normalized at
    ingest), so the filter covers the canonical name plus case variants.
    """
    q_role = detect_role(question)
    if q_role and q_role.lower() != (caller_role or "").lower():
        return {"role": {"$in": [q_role, q_role.lower(), q_role.upper()]}}
    return None


def _semantic_passages(question: str, role: Optional[str], threshold: float) -> List[str]:
    """Query the vector store for passages relevant to `question`.

    If the question mentions a role different from the caller's, the query is
    narrowed with a role metadata filter. When no semantic hit beats the
    distance threshold (or the store is empty), falls back to lexical keyword
    search — the threshold does not apply to keyword hits.

    Returns [] on any failure (missing store, import error, empty collection)
    instead of raising — semantic retrieval is best-effort.
    """
    logger = get_logger()
    try:
        from modules.embeddings.embedder import Embedder
        from modules.embeddings.store import VectorStore
        embedder = Embedder()
        store = VectorStore()
        q_emb = embedder.embed_texts([question])[0]
        where = _role_where(question, role)
        if where is not None:
            hits = store.query(q_emb, top_k=5, where=where)
        else:
            hits = store.query(q_emb, top_k=5)
        if not hits:
            logger.warning("Semantic retrieval returned zero results (where=%s, collection empty?)", where)
        passages = [
            h.get("document") or str(h.get("metadata"))
            for h in hits
            if h.get("distance") is None or h.get("distance") <= threshold
        ]
        if not passages:
            logger.info("Semantic retrieval: below threshold (%.2f), trying keyword fallback", threshold)
            kw_hits = store.search_keywords(keyword_candidates(question), top_k=5, where=where)
            passages = [h.get("document") or str(h.get("metadata")) for h in kw_hits]
        return passages
    except Exception:
        logger.exception("Semantic retrieval failed")
        return []


# ------------------------------------------------------------------
#  main
# ------------------------------------------------------------------

def ask_coach(question: str,
              role: Optional[str] = None,
              model: str = "qwen2.5:14b",
              last_match: bool = False,
              lang: str = "es",
              history: Optional[List[Dict]] = None):
    """Entry point: classify, retrieve, format prompt, call Ollama.

    Args:
        question: the user's message.
        role: optional role filter (Top, Jungle, ...).
        model: Ollama model name.
        last_match: use only the most recent match as context.
        lang: language for the assistant's reply.
        history: optional list of {"role", "content"} previous turns.
    """
    logger = get_logger()
    db = get_db()
    pe = PromptEngineer()
    snapshot = None

    # 1. Classify question
    cat = classify_question(question)
    logger.info("Classified question: %s -> %s (method=%s, conf=%.2f)",
                question, cat.get("category_label"),
                cat.get("method"), float(cat.get("confidence", 0.0)))

    # 2. Retrieve passages
    passages: List[str] = []
    if last_match:
        # last_match=True is out of scope for the semantic-primary reorder
        # (CoachingPromptBuilder has no `passages` param) — unchanged behavior.
        logger.info("Running retrieval recipe for category=%s role=%s last_match=%s",
                    cat.get("category_id"), role, last_match)
        passages = retrieve_for_category(cat.get("category_id"), role, db,
                                         limit=5, last_match=last_match)
        logger.info("Recipe returned %d passages", len(passages))

        if not passages:
            logger.info("Falling back to embedding-based retrieval")
            try:
                from modules.embeddings.embedder import Embedder
                from modules.embeddings.store import VectorStore
                embeddings_config = get_embeddings_config()
                threshold = float(embeddings_config.get("distance_threshold", 1.0))
                embedder = Embedder()
                store = VectorStore()
                q_emb = embedder.embed_texts([question])[0]
                where = _role_where(question, role)
                if where is not None:
                    hits = store.query(q_emb, top_k=5, where=where)
                else:
                    hits = store.query(q_emb, top_k=5)
                hits = [
                    h for h in hits
                    if h.get("distance") is None or h.get("distance") <= threshold
                ]
                if not hits:
                    logger.warning("Semantic retrieval returned zero results (where=%s, collection empty?)", where)
                    hits = store.search_keywords(keyword_candidates(question), top_k=5, where=where)
                for h in hits:
                    passages.append(h.get('document') or str(h.get('metadata')))
            except Exception:
                logger.exception("Embedding retrieval failed")
    else:
        # last_match=False (aggregate report): semantic query is PRIMARY,
        # retrieve_for_category ALWAYS also runs as a structured-stats
        # complement — both merged into `passages` for PromptEngineer.
        embeddings_config = get_embeddings_config()
        threshold = float(embeddings_config.get("distance_threshold", 1.0))
        semantic_passages = _semantic_passages(question, role, threshold)

        # retrieve_for_category accepts role=None ("accept any") — the web UI
        # never sends a role, so structured stats must not be skipped here.
        structured_passages = retrieve_for_category(
            cat.get("category_id"), role, db, limit=5, last_match=last_match
        )

        passages = semantic_passages + structured_passages
        logger.info("Merged passages: %d semantic + %d structured",
                    len(semantic_passages), len(structured_passages))

    # 3. Build a player report with structured stats
    player_report: Dict[str, Any] = {"puuid": "ask_coach", "games_analyzed": "N/A"}
    prompt = None  # will be set by one of the strategies below

    if last_match:
        # Fetch last-match data for schema-driven coaching prompt
        last = _build_last_match_report(db, role or "")
        if last and last.get("full_match"):
            snapshot = render_match_snapshot(last["full_match"])
            try:
                cp_builder = CoachingPromptBuilder()
                prompt = cp_builder.build_prompt(
                    match_doc=last["full_match"],
                    puuid=last["puuid"],
                    role=role,
                    match_snapshot=snapshot,
                    history=history,
                )
                logger.info("Schema-driven prompt built (%d chars; ddragon=%s)",
                            len(prompt), cp_builder.resolution_status)
            except Exception as e:
                logger.exception("CoachingPromptBuilder failed, falling back: %s", e)

        if not prompt:
            # fallback: use PromptEngineer with rich report
            player_report = last.get("report", player_report) if last else player_report
            game_summary = None
            important_points = None
            if player_report.get("metrics"):
                m = player_report["metrics"]
                dur = m.get("gameDuration")
                win = m.get("win")
                champ = m.get("championName")
                kda = f"{m.get('kills', '-')}/{m.get('deaths', '-')}/{m.get('assists', '-')}"
                dur_str = f"{dur // 60}min" if dur else "-"
                game_summary = f"{champ or '?'} | {dur_str} | {'Victoria' if win else 'Derrota'} | KDA {kda}"
                pts = []
                if m.get("ch_goldPerMinute"):
                    pts.append(f"Gold/min: {m['ch_goldPerMinute']}")
                if m.get("ch_damagePerMinute"):
                    pts.append(f"Daño: {m['ch_damagePerMinute']} DPM")
                if m.get("wardsPlaced"):
                    pts.append(f"Wards: {m['wardsPlaced']}")
                if m.get("ch_killParticipation"):
                    pts.append(f"KP: {float(m['ch_killParticipation'])*100:.0f}%")
                if m.get("turretKills") and int(m["turretKills"]) > 0:
                    pts.append(f"Torretas: {m['turretKills']}")
                important_points = pts if pts else None
    else:
        # Fetch aggregate report
        agg = _build_aggregate_report(db, role or "")
        if agg:
            player_report = agg
        game_summary = None
        important_points = None

    # 4. Build prompt (if not already set by CoachingPromptBuilder)
    if not prompt:
        prompt = pe.build_prompt(
            player_report=player_report,
            role=role or "coach",
            passages=passages,
            language=lang,
            output_format="text",
            game_summary=game_summary,
            important_points=important_points,
            match_snapshot=snapshot,
            history=history,
        )

    # 5. Call Ollama
    logger.info("Calling Ollama model=%s; prompt length=%d chars; passages=%d",
                model, len(prompt), len(passages))
    client = OllamaClient()
    resp = client.generate(prompt=prompt, model=model)
    out_text = resp["response"] if isinstance(resp, dict) else resp
    print(out_text)

    # 6. Persist prompt+response
    try:
        out_dir = os.path.join("reports", "ollama_responses")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat().replace(":", "-")
        fname = os.path.join(out_dir, f"ask_coach_{ts}.json")
        with open(fname, "w", encoding="utf-8") as fh:
            json.dump({
                "question": question,
                "role": role,
                "category": cat,
                "player_report": player_report,
                "passages": passages,
                "prompt": prompt,
                "response": resp,
            }, fh, ensure_ascii=False, indent=2, default=str)
        logger.info("Saved prompt+response to %s", fname)
    except Exception:
        logger.exception("Failed to save prompt+response")

    return out_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--role", required=False)
    parser.add_argument("--model", default="qwen2.5:14b")
    parser.add_argument("--last-match", action="store_true",
                        help="Retrieve context only from the latest match")
    parser.add_argument("--lang", default="es",
                        help="Language for the assistant's reply (default: es).")
    args = parser.parse_args()

    ask_coach(
        question=args.question,
        role=args.role,
        model=args.model,
        last_match=args.last_match,
        lang=args.lang,
    )


if __name__ == "__main__":
    main()
