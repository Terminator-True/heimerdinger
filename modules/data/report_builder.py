import json
from collections import Counter
from statistics import mean
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


class ReportBuilder:
    """Build coaching-style reports from parsed player metrics.

    Usage:
        rb = ReportBuilder()
        report = rb.build_player_report(player_puuid, db, pro_reference=None)
    """

    def __init__(self, output_dir: Optional[str] = "reports"):
        self.output_dir = Path(output_dir)

    def _iter_player_matches(self, player_puuid: str, db) -> Iterable[Dict[str, Any]]:
        """Yield player_matches documents for the given player_puuid.

        Accepts a pymongo-like Database (has get_collection) or a simple mapping
        that exposes get_collection(name) or direct dict access.
        """
        try:
            col = db.get_collection("player_matches")
        except Exception:
            # try dict-like
            col = db["player_matches"]

        # Expect the collection to support find()
        try:
            for d in col.find({"player_puuid": player_puuid}):
                yield d
        except Exception:
            # If the collection is a simple list/dict, attempt a fallback
            if hasattr(col, "values"):
                for d in col.values():
                    if d.get("player_puuid") == player_puuid:
                        yield d

    def build_player_report(self, player_puuid: str, db, pro_reference: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        docs = list(self._iter_player_matches(player_puuid, db))
        games = len(docs)
        if games == 0:
            report = {
                "player": player_puuid,
                "role": None,
                "champion": None,
                "games_analyzed": 0,
                "metrics": {},
                "pro_reference": None,
                "deltas": {},
            }
            return report

        cs_vals = []
        kda_vals = []
        champions = []
        roles = []

        for d in docs:
            parsed = d.get("parsed_metrics") or d.get("metrics") or {}
            # parsed_metrics may have nested numeric values; be defensive
            cs = parsed.get("cs_per_min")
            if cs is None:
                # maybe stored as cs and duration elsewhere; skip
                pass
            else:
                try:
                    cs_vals.append(float(cs))
                except Exception:
                    pass

            kda = parsed.get("kda")
            if kda is not None:
                try:
                    kda_vals.append(float(kda))
                except Exception:
                    pass

            champ = d.get("championName") or parsed.get("championName") or parsed.get("champion")
            if champ:
                champions.append(champ)

            role = d.get("role") or parsed.get("role")
            if role:
                roles.append(role)

        metrics = {}
        if cs_vals:
            metrics["cs_per_min"] = mean(cs_vals)
        if kda_vals:
            metrics["kda"] = mean(kda_vals)

        champion = Counter(champions).most_common(1)[0][0] if champions else None
        role = Counter(roles).most_common(1)[0][0] if roles else None

        deltas = {}
        if pro_reference:
            # compute player's metric minus pro_reference (negative means below pro)
            for k, v in metrics.items():
                pref = pro_reference.get(k)
                if pref is None:
                    deltas[k] = None
                else:
                    deltas[k] = round(v - float(pref), 3)

        report = {
            "player": player_puuid,
            "role": role,
            "champion": champion,
            "games_analyzed": games,
            "metrics": {k: round(v, 3) for k, v in metrics.items()},
            "pro_reference": pro_reference if pro_reference is not None else None,
            "deltas": deltas,
        }

        # Persist report to DB and disk idempotently
        self.save_report(report, db)

        return report

    def save_report(self, report: Dict[str, Any], db) -> None:
        # Save to DB (reports collection) idempotently
        try:
            col = db.get_collection("reports")
        except Exception:
            col = db.setdefault("reports", {})

        # Upsert-like behavior for pymongo collection
        try:
            # Try pymongo style update
            filter_q = {"player": report.get("player")}
            col.update_one(filter_q, {"$set": report}, upsert=True)
        except Exception:
            # Fallback for dict-backed collection
            if isinstance(col, dict):
                col[report.get("player")] = report

        # Persist to disk under reports/{player_puuid}.json
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            out_path = self.output_dir / f"{report.get('player')}.json"
            with out_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2)
        except Exception:
            # Disk failures should not raise during report creation
            pass
