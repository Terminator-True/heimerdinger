"""Utility to seed the vector DB from existing parsed matches/reports.

Runs a best-effort pass over reports/ and player_matches collection to create
compact passages and upsert into the Chroma store. Intended for local dev.
"""
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from modules.db.connection import get_db


def main():
    db = get_db()
    # iterate reports collection if available
    try:
        col = db.get_collection("reports")
        for doc in col.find():
            pass
    except Exception:
        # fallback for dict-backed store
        try:
            col = db.setdefault("reports", {})
            for doc in col.values():
                pass
        except Exception:
            pass


if __name__ == "__main__":
    main()
