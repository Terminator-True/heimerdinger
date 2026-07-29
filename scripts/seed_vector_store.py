"""CLI to populate the vector DB from Mongo reports/player_matches.

Usage:
  python scripts/seed_vector_store.py
"""
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.embeddings.ingest import run_ingestion


def main():
    counts = run_ingestion()
    print(
        f"Ingested {counts['reports']} reports and "
        f"{counts['player_matches']} player_matches into the vector store."
    )


if __name__ == "__main__":
    main()
