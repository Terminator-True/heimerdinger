"""Ask the coaching LLM using minimal context retrieved from the DB.

Thin CLI wrapper over ``modules.coaching.service.CoachingService``.

Usage:
  python scripts/ask_coach.py --question "Qué consejos darías a nuestro toplane?" --role Top
  python scripts/ask_coach.py --question "Analiza mi última partida" --role Mid --last-match

Behavior (unchanged, snapshot-guarded):
- Classifies the question via hybrid (rule + embedding) classifier.
- Retrieves relevant context passages from reports/player_matches.
- Builds a structured-stats prompt with player metrics.
- Calls Ollama to produce coaching advice.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.coaching.service import CoachingService


def ask_coach(question: str,
              role: str = None,
              model: str = "llama3.1:8b",
              last_match: bool = False,
              lang: str = "es",
              history: list = None):
    """Entry point: classify, retrieve, format prompt, call Ollama."""
    return CoachingService().ask_coach(
        question=question,
        role=role,
        model=model,
        last_match=last_match,
        lang=lang,
        history=history,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--role", required=False)
    parser.add_argument("--model", default="llama3.1:8b")
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
