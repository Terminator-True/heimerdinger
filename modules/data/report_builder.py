import json
from collections import Counter
from statistics import mean, median
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from modules.logger import get_logger

logger = get_logger(__name__)


def get_full_match(db, match_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the full match document from the `matches` collection."""
    try:
        col = db.get_collection("matches")
        return col.find_one({"metadata.matchId": match_id})
    except Exception:
        try:
            col = db.setdefault("matches", {})
            for v in col.values():
                if v.get("metadata", {}).get("matchId") == match_id:
                    return v
        except Exception:
            pass
    return None


def _snapshot_value(val: Any) -> str:
    """Format a snapshot stat as an integer when possible, else '-' for None."""
    if val is None:
        return "-"
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else str(f)
    except (ValueError, TypeError):
        return str(val)


def _snapshot_win(win: Any) -> str:
    """Map win bool to Spanish Sí/No, '-' when missing."""
    if isinstance(win, str):
        win = win.strip().lower()
    if win == 1 or win == "1":  # True == 1, so bools are covered here
        return "Sí"
    if win == 0 or win == "0":  # False == 0
        return "No"
    return "-"


def render_match_snapshot(full_match_doc: Dict[str, Any]) -> str:
    """Render one compact Spanish line per participant, grouped by team.

    Output example::

        Equipo 1:
        Jugador: Alice | Rol: TOP | Campeón: Garen | KDA: 3/2/5 | CS@10: 42 | GPM: 410 | DPM: 520 | Visión: 21 | Victoria: Sí
        Equipo 2:
        Jugador: Bob | Rol: JUNGLE | Campeón: Lee Sin | KDA: 1/4/2 | CS@10: 30 | GPM: 380 | DPM: 300 | Visión: 15 | Victoria: No

    Returns an empty string when the match doc has no participants.
    """
    if not full_match_doc:
        return ""
    info = full_match_doc.get("info") or {}
    participants: List[Dict] = info.get("participants") or []
    if not participants:
        return ""

    # team order: info.teams first, then any participant teamIds not listed in
    # the teams doc (deduped, participant order); fall back to sorted teamIds.
    teams: List[Dict] = info.get("teams") or []
    team_ids = [t.get("teamId") for t in teams if t.get("teamId") is not None]
    for p in participants:
        tid = p.get("teamId")
        if tid is not None and tid not in team_ids:
            team_ids.append(tid)
    if not team_ids:
        team_ids = sorted({p.get("teamId") for p in participants if p.get("teamId") is not None})

    by_team: Dict[int, List[Dict]] = {}
    for p in participants:
        by_team.setdefault(p.get("teamId") or 100, []).append(p)

    blocks = []
    for idx, tid in enumerate(team_ids, start=1):
        lines = [f"Equipo {idx}:"]
        for p in by_team.get(tid, []):
            ch = p.get("challenges") or {}
            role = (p.get("individualPosition") or p.get("teamPosition") or "").upper()
            kda = f"{_snapshot_value(p.get('kills'))}/{_snapshot_value(p.get('deaths'))}/{_snapshot_value(p.get('assists'))}"
            lines.append(
                f"Jugador: {p.get('summonerName') or '-'} | Rol: {role or '-'} | "
                f"Campeón: {p.get('championName') or '-'} | KDA: {kda} | "
                f"CS@10: {_snapshot_value(ch.get('laneMinionsFirst10Minutes'))} | "
                f"GPM: {_snapshot_value(ch.get('goldPerMinute'))} | "
                f"DPM: {_snapshot_value(ch.get('damagePerMinute'))} | "
                f"Visión: {_snapshot_value(p.get('visionScore'))} | "
                f"Victoria: {_snapshot_win(p.get('win'))}"
            )
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def extract_rich_participant(full_match_doc: Dict[str, Any], player_puuid: str) -> Dict[str, Any]:
    """Extract ALL coaching-relevant fields organized by category.

    Works on the full Riot API match document stored in `matches` collection.
    Returns a flat dict with keys grouped semantically (prefixes).
    Returns an empty dict if participant cannot be found.
    """
    if not full_match_doc:
        return {}

    info = full_match_doc.get("info") or {}
    participants: List[Dict] = info.get("participants") or []

    # find the participant matching our puuid
    target = None
    for p in participants:
        if p.get("puuid") == player_puuid:
            target = p
            break
    if not target:
        return {}

    result: Dict[str, Any] = {}

    # ----- identity  (match-level) -----
    meta = full_match_doc.get("metadata") or {}
    result["matchId"] = meta.get("matchId")
    result["gameDuration"] = info.get("gameDuration")
    result["gameMode"] = info.get("gameMode")
    result["queueId"] = info.get("queueId")
    result["gameVersion"] = info.get("gameVersion")

    # ----- basic performance -----
    for k in ("kills", "deaths", "assists", "championName",
              "individualPosition", "teamPosition", "win", "totalMinionsKilled"):
        if k in target:
            result[k] = target[k]

    # ----- economy -----
    for k in ("goldEarned", "goldSpent"):
        if k in target:
            result[k] = target[k]

    # ----- challenges (nested) -----
    ch = target.get("challenges") or {}
    challenge_fields = (
        "goldPerMinute", "laneMinionsFirst10Minutes",
        "maxCsAdvantageOnLaneOpponent",
        "damagePerMinute", "teamDamagePercentage", "killParticipation",
        "visionScorePerMinute", "controlWardsPlaced",
        "controlWardTimeCoverageInRiverOrEnemyHalf",
        "baronTakedowns", "turretPlatesTaken",
        "firstTurretKilled", "firstTurretKilledTime",
        "skillshotsHit", "skillshotsDodged", "abilityUses",
        "enemyChampionImmobilizations",
        "soloKills", "multikills",
        "deathsByEnemyChamps", "maxKillDeficit",
    )
    for k in challenge_fields:
        if k in ch:
            result[f"ch_{k}"] = ch[k]

    # ----- damage & impact -----
    for k in ("totalDamageDealtToChampions",
              "damageDealtToObjectives", "damageDealtToBuildings"):
        if k in target:
            result[k] = target[k]

    # ----- vision -----
    for k in ("visionScore", "wardsPlaced", "wardsKilled", "detectorWardsPlaced"):
        if k in target:
            result[k] = target[k]

    # ----- objectives (participant-level) -----
    for k in ("dragonKills", "baronKills", "inhibitorKills", "turretKills"):
        if k in target:
            result[k] = target[k]

    # ----- mechanics / cc -----
    for k in ("totalTimeCCDealt", "timeCCingOthers"):
        if k in target:
            result[k] = target[k]

    # ----- mistakes / deaths -----
    for k in ("totalTimeSpentDead", "longestTimeSpentLiving"):
        if k in target:
            result[k] = target[k]

    # ----- build & items -----
    for i in range(7):
        k = f"item{i}"
        if k in target:
            result[k] = target[k]
    if "legendaryItemUsed" in target:
        result["legendaryItemUsed"] = target["legendaryItemUsed"]
    if "perks" in target:
        result["perks"] = target["perks"]

    # ----- team-level objectives & bans -----
    teams: List[Dict] = info.get("teams") or []
    player_team_id = target.get("teamId")
    for team in teams:
        if team.get("teamId") != player_team_id:
            continue
        result["team_win"] = team.get("win")
        obj = team.get("objectives") or {}
        for obj_key in ("baron", "dragon", "tower", "inhibitor", "riftHerald"):
            o = obj.get(obj_key) or {}
            result[f"team_{obj_key}Kills"] = o.get("kills")
            result[f"team_{obj_key}First"] = o.get("first")
        bans = team.get("bans") or []
        result["team_bans"] = [b.get("championId") for b in bans[:5]
                               if b.get("championId") is not None]
        break

    return result


class ReportBuilder:
    """Build coaching-style reports from parsed player metrics.

    Usage:
        rb = ReportBuilder()
        report = rb.build_player_report(player_puuid, db, pro_reference=None)
    """

    def __init__(self, output_dir: Optional[str] = "reports"):
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    #  helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _percentile(data: list, pct: float) -> Optional[float]:
        """Simple linear-interpolation percentile (0..100)."""
        if not data:
            return None
        d = sorted(data)
        n = len(d)
        if n == 1:
            return d[0]
        rank = (pct / 100.0) * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        weight = rank - lo
        return d[lo] * (1 - weight) + d[hi] * weight

    def _iter_player_matches(self, player_puuid: str, db) -> Iterable[Dict[str, Any]]:
        """Yield player_matches documents for the given player_puuid.

        Accepts a pymongo-like Database (has get_collection) or a simple mapping
        that exposes get_collection(name) or direct dict access.
        """
        try:
            col = db.get_collection("player_matches")
        except Exception:
            col = db["player_matches"]

        try:
            for d in col.find({"player_puuid": player_puuid}):
                yield d
        except Exception:
            if hasattr(col, "values"):
                for d in col.values():
                    if d.get("player_puuid") == player_puuid:
                        yield d

    # ------------------------------------------------------------------
    #  aggregate helpers  (used by build_player_report)
    # ------------------------------------------------------------------

    @staticmethod
    def _accumulate_numeric(acc: Dict[str, List[float]], key: str, value: Any):
        """Append *value* to the list for *key* if it is a number."""
        if value is None:
            return
        try:
            acc.setdefault(key, []).append(float(value))
        except (ValueError, TypeError):
            pass  # non-numeric — skip

    @staticmethod
    def _aggregate(acc: Dict[str, List[float]], names: Iterable[str]) -> Dict[str, Any]:
        """Return a flat metrics dict with mean, median, p25, p75 per key."""
        out: Dict[str, Any] = {}
        for name in names:
            vals = acc.get(name)
            if not vals:
                continue
            try:
                m = mean(vals)
                med = median(vals)
                p25 = ReportBuilder._percentile(vals, 25)
                p75 = ReportBuilder._percentile(vals, 75)
                out[name] = round(m, 3)
                out[f"{name}_median"] = round(med, 3) if med is not None else None
                out[f"{name}_p25"] = round(p25, 3) if p25 is not None else None
                out[f"{name}_p75"] = round(p75, 3) if p75 is not None else None
            except Exception:
                pass
        return out

    # ------------------------------------------------------------------
    #  report builders
    # ------------------------------------------------------------------

    def build_player_report(self, player_puuid: str, db,
                            pro_reference: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        try:
            docs = list(self._iter_player_matches(player_puuid, db))
            games = len(docs)
            if games == 0:
                logger.warning("No matches found for player %s", player_puuid)
                return {"status": "empty", "player": player_puuid,
                        "detail": "No player matches found in DB"}

            cs_vals: List[float] = []
            kda_vals: List[float] = []
            champions: List[str] = []
            roles: List[str] = []

            for d in docs:
                parsed = d.get("parsed_metrics") or d.get("metrics") or {}

                # --- legacy basic stats ---
                cs = parsed.get("cs_per_min")
                if cs is not None:
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

            # --- build metrics ---
            metrics: Dict[str, Any] = {}

            if cs_vals:
                metrics["cs_per_min"] = mean(cs_vals)
            if kda_vals:
                metrics["kda"] = mean(kda_vals)

            # accumulate any additional numeric fields from parsed_metrics
            numeric_acc: Dict[str, List[float]] = {}
            seen_numeric_keys: set = set()
            for d in docs:
                parsed = d.get("parsed_metrics") or d.get("metrics") or {}
                for pk, pv in parsed.items():
                    if pk in ("cs_per_min", "kda", "championName", "champion", "role",
                              "puuid", "summonerName", "timestamp", "matchId"):
                        continue
                    self._accumulate_numeric(numeric_acc, pk, pv)
                    seen_numeric_keys.add(pk)
            aggregated = self._aggregate(numeric_acc, seen_numeric_keys)
            metrics.update(aggregated)

            # mode for categoricals
            champion = Counter(champions).most_common(1)[0][0] if champions else None
            role = Counter(roles).most_common(1)[0][0] if roles else None

            # deltas
            deltas: Dict[str, Any] = {}
            if pro_reference:
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
                "metrics": metrics,
                "pro_reference": pro_reference if pro_reference is not None else None,
                "deltas": deltas,
            }

            self.save_report(report, db)
            return report
        except Exception as exc:
            logger.warning("build_player_report failed for %s: %s", player_puuid, exc)
            return {"status": "error", "player": player_puuid, "detail": str(exc)}

    # ------------------------------------------------------------------

    def save_report(self, report: Dict[str, Any], db) -> None:
        try:
            col = db.get_collection("reports")
        except Exception:
            col = db.setdefault("reports", {})

        try:
            filter_q = {"player": report.get("player")}
            col.update_one(filter_q, {"$set": report}, upsert=True)
        except Exception:
            if isinstance(col, dict):
                col[report.get("player")] = report

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            out_path = self.output_dir / f"{report.get('player')}.json"
            with out_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------

    def build_match_report(self, match_doc: Dict[str, Any], db) -> Dict[str, Any]:
        """Single-match report from parsed_metrics without full-match N+1 lookups."""
        try:
            parsed = match_doc.get('parsed_metrics') or match_doc.get('metrics') or {}
            player = match_doc.get('player_puuid') or parsed.get('player')
            match_id = match_doc.get('matchId') or match_doc.get('id') or parsed.get('matchId')

            metrics = dict(parsed) if isinstance(parsed, dict) else {}

            report = {
                'player': player,
                'matchId': match_id,
                'champion': match_doc.get('champion') or parsed.get('champion'),
                'games_analyzed': 1,
                'metrics': metrics,
                'role': match_doc.get('role') or parsed.get('role'),
            }

            # save to DB
            try:
                col = db.get_collection('reports')
                col.update_one({'player': report.get('player'), 'matchId': report.get('matchId')},
                               {'$set': report}, upsert=True)
            except Exception:
                rcol = db.setdefault('reports', {})
                rcol[f"{report.get('player')}_{report.get('matchId')}"] = report

            # persist to disk
            out_dir = self.output_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{report.get('player')}_{report.get('matchId')}.json"
            try:
                with out_path.open('w', encoding='utf-8') as fh:
                    json.dump(report, fh, ensure_ascii=False, indent=2)
            except Exception:
                pass

            return report
        except Exception as exc:
            logger.warning("build_match_report failed for match %s: %s", match_id, exc)
            return {"status": "error", "matchId": match_doc.get("matchId") or "unknown", "detail": str(exc)}



