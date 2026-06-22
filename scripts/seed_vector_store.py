"""Utility to seed the vector DB from existing parsed matches/reports.

Runs a best-effort pass over reports/ and player_matches collection to create
compact passages and upsert into the Chroma store. Intended for local dev.
"""
from modules.data.report_builder import index_report_passages
from modules.db.connection import get_db
from modules.data.report_builder import ReportBuilder


def main():
    db = get_db()
    # iterate reports collection if available
    try:
        col = db.get_collection("reports")
        for doc in col.find():
            try:
                index_report_passages(doc)
            except Exception:
                pass
    except Exception:
        # fallback for dict-backed store
        try:
            col = db.setdefault("reports", {})
            for doc in col.values():
                try:
                    index_report_passages(doc)
                except Exception:
                    pass
        except Exception:
            pass


if __name__ == "__main__":
    main()
