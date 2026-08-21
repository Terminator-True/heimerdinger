"""Mongo-backed adapter for the ReportRepositoryPort."""

from typing import Any


class ReportRepository:
    """Upsert and query documents in the ``reports`` collection.

    Accepts a pymongo-like database (``get_collection``) or a plain mapping
    (``db["reports"]`` / ``setdefault``), mirroring the duck-typing used by
    ``ReportBuilder`` so tests can pass dict-backed fakes.
    """

    def __init__(self, db: Any):
        self._db = db

    def _get_col(self) -> Any:
        try:
            return self._db.get_collection("reports")
        except Exception:
            return self._db.setdefault("reports", {})

    @staticmethod
    def _filter_for(report: dict[str, Any]) -> dict[str, Any]:
        if report.get("matchId"):
            return {"player": report.get("player"), "matchId": report.get("matchId")}
        return {"player": report.get("player")}

    def upsert_report(self, report: dict[str, Any]) -> None:
        col = self._get_col()
        try:
            col.update_one(self._filter_for(report), {"$set": report}, upsert=True)
        except Exception:
            if isinstance(col, dict):
                key = self._filter_for(report)
                if "matchId" in key:
                    col[f"{key['player']}_{key['matchId']}"] = report
                else:
                    col[key["player"]] = report

    def find_reports_by_role(self, role: str, limit: int = 10) -> list[dict[str, Any]]:
        col = self._get_col()
        try:
            return list(col.find({"role": role}).limit(limit))
        except Exception:
            if isinstance(col, dict):
                matches = [d for d in col.values() if d.get("role") == role]
                return matches[:limit]
            return []
