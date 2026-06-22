"""Ask the coaching LLM using minimal context retrieved from the DB.

Usage:
  python scripts/ask_coach.py --question "Hola! Que consejos darías a nuestro toplane?" --role Top

Behavior:
- First attempt a fast regex/SQL-like scan on reports to find relevant player(s)/matches.
- If regex scan yields insufficient context, fallback to embedding retrieval (if available).
- Build a compact prompt and call Ollama to produce coaching advice.
"""
import argparse
import os
import sys
from pathlib import Path
from rich.console import Console
from datetime import datetime
import json
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.logger import get_logger
from modules.db.connection import get_db
from modules.llm.ollama_client import OllamaClient
from modules.llm.prompt_engineer import PromptEngineer
from modules.llm.question_classifier import classify_question
from modules.llm.retrieval import retrieve_for_category


def find_context_by_role(db, role: str, limit: int = 3):
    # Simple heuristic: find recent reports where role matches
    try:
        col = db.get_collection("reports")
        docs = list(col.find({"role": role}).sort("_id", -1).limit(limit))
        return docs
    except Exception:
        # fallback for dict-backed storage
        try:
            col = db.setdefault("reports", {})
            out = []
            for d in col.values():
                if d.get("role") == role:
                    out.append(d)
            return out[:limit]
        except Exception:
            return []


def ask_coach(question: str, role: str = None, model: str = "llama3.1:8b", last_match: bool = False):
    console = Console()
    logger = get_logger()
    db = get_db()
    pe = PromptEngineer()

    # Classify the question and retrieve best-effort passages
    passages = []
    cat = classify_question(question)
    logger.info("Classified question: %s -> %s (method=%s, conf=%.2f)", question, cat.get("category_label"), cat.get("method"), float(cat.get("confidence", 0.0)))
    if cat.get("matched_keywords"):
        logger.debug("Matched keywords: %s", cat.get("matched_keywords"))
    if role:
        # retrieval recipes prefer DB-level heuristics
        logger.info("Running retrieval recipe for category=%s role=%s last_match=%s", cat.get("category_id"), role, last_match)
        passages = retrieve_for_category(cat.get("category_id"), role, db, limit=5, last_match=last_match)
        logger.info("Recipe returned %d passages", len(passages))
        logger.debug("Passages: %s", passages[:5])

    # If no passages returned, fallback to vector store retrieval (embeddings)
    
    if not passages:
        try:
            from modules.embeddings.embedder import Embedder
            from modules.embeddings.store import VectorStore

            logger.info("Falling back to embedding-based retrieval")
            embedder = Embedder()
            store = VectorStore()
            q_emb = embedder.embed_texts([question])[0]
            hits = store.query(q_emb, top_k=5)
            logger.info("Embedding retrieval returned %d hits", len(hits))
            for h in hits:
                passages.append(h.get('document') or str(h.get('metadata')))
        except Exception:
            logger.exception("Embedding retrieval failed")
            pass

    # prefer a short plain text answer for single-match queries
    output_fmt = "text" if last_match else "text"
    # Add a compact game-level summary and important points if last_match
    game_summary = None
    important_points = None
    if last_match and passages:
        # use the first passage as a short game summary candidate
        game_summary = passages[0][:200]
        important_points = [p for p in passages[1:4]] if len(passages) > 1 else None

    prompt = pe.build_prompt({"puuid": "ask_coach", "games_analyzed": "N/A"}, role=role or "coach", passages=passages, language="es", output_format=output_fmt, game_summary=game_summary, important_points=important_points)

    logger.info("Calling Ollama model=%s; prompt length=%d chars; passages=%d", model, len(prompt), len(passages))
    client = OllamaClient()
    resp = client.generate(prompt=prompt, model=model)

    # Persist prompt+response for debugging with a timestamped filename
    try:
        out_dir = os.path.join("reports", "ollama_responses")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.utcnow().isoformat().replace(":", "-")
        fname = os.path.join(out_dir, f"ask_coach_{ts}.json")
        with open(fname, "w", encoding="utf-8") as fh:
            json.dump({"question": question, "role": role, "category": cat, "passages": passages, "prompt": prompt, "response": resp}, fh, ensure_ascii=False, indent=2)
        logger.info("Saved ollama prompt+response to %s", fname)
    except Exception:
        logger.exception("Failed to save prompt+response")

    console.print("LLM response:")
    console.print(resp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--role", required=False)
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--last-match", action="store_true", help="Retrieve context only from the latest match for the role")
    parser.add_argument("--lang", default="es", help="Language for the assistant's reply (default: es).")
    args = parser.parse_args()

    # pass language through to PromptEngineer if needed in future
    ask_coach(args.question, role=args.role, model=args.model, last_match=args.last_match)


if __name__ == "__main__":
    main()
