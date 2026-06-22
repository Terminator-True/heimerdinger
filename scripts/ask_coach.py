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
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

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


def ask_coach(question: str, role: str = None, model: str = "llama3.1:8b"):
    console = Console()
    db = get_db()
    pe = PromptEngineer()

    # Classify the question and retrieve best-effort passages
    passages = []
    cat = classify_question(question)
    if role:
        # retrieval recipes prefer DB-level heuristics
        passages = retrieve_for_category(cat.get("category_id"), role, db, limit=5)

    # If no passages returned, fallback to vector store retrieval (embeddings)
    
    if not passages:
        try:
            from modules.embeddings.embedder import Embedder
            from modules.embeddings.store import VectorStore

            embedder = Embedder()
            store = VectorStore()
            q_emb = embedder.embed_texts([question])[0]
            hits = store.query(q_emb, top_k=5)
            for h in hits:
                passages.append(h.get('document') or str(h.get('metadata')))
        except Exception:
            pass

    prompt = pe.build_prompt({"puuid": "ask_coach", "games_analyzed": "N/A"}, role=role or "coach", passages=passages, language="es")

    client = OllamaClient()
    resp = client.generate(prompt=prompt, model=model)
    console.print("LLM response:")
    console.print(resp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--role", required=False)
    parser.add_argument("--model", default="llama3.1:8b")
    args = parser.parse_args()

    ask_coach(args.question, role=args.role, model=args.model)


if __name__ == "__main__":
    main()
