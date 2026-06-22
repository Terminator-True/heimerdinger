from typing import List, Optional
from modules.logger import get_logger


def _get_reports_docs(db, scan_limit: int):
    try:
        col = db.get_collection("reports")
        docs = list(col.find({}).sort("_id", -1).limit(scan_limit))
        return docs
    except Exception:
        col = db.setdefault("reports", {})
        return list(col.values())[:scan_limit]


def _get_player_matches_docs(db, scan_limit: int):
    try:
        col = db.get_collection("player_matches")
        docs = list(col.find({}).sort("_id", -1).limit(scan_limit))
        return docs
    except Exception:
        col = db.setdefault("player_matches", {})
        return list(col.values())[:scan_limit]


def retrieve_for_category(category_id: str, role: Optional[str], db, limit: int = 5) -> List[str]:
    logger = get_logger()
    out: List[str] = []
    try:
        scan_limit = max(50, limit * 10)
        docs = _get_reports_docs(db, scan_limit)
        docs_scanned = 0

        # flexible key names mapping per metric
        for d in docs:
            docs_scanned += 1
            # if role provided, prefer matching, else accept any
            if role and (d.get("role") or "").lower() != role.lower():
                continue

            metrics = d.get("metrics", {}) or {}
            player = d.get("player") or d.get("player_puuid")

            if category_id == "laning":
                cs = metrics.get("cs_per_min") or metrics.get("cs") or metrics.get("cs_min")
                early_deaths = metrics.get("early_deaths") or metrics.get("deaths_early")
                if cs is not None or early_deaths is not None:
                    out.append(f"player={player} cs={cs} early_deaths={early_deaths}")
            elif category_id == "vision":
                vs = metrics.get("vision_score") or metrics.get("vision")
                wards = metrics.get("wards_placed") or metrics.get("wards")
                if vs is not None or wards is not None:
                    out.append(f"player={player} vision_score={vs} wards={wards}")
            elif category_id == "macro":
                objectives = metrics.get("objectives_taken") or metrics.get("objectives")
                rotations = metrics.get("rotations") or metrics.get("roams")
                if objectives is not None or rotations is not None:
                    out.append(f"player={player} objectives={objectives} rotations={rotations}")
            elif category_id == "teamfights":
                dmg = metrics.get("damage_pct") or metrics.get("damage_share")
                pos = metrics.get("positioning_notes") or metrics.get("positioning")
                if dmg is not None or pos is not None:
                    out.append(f"player={player} damage_pct={dmg} notes={pos}")
            elif category_id == "pacing":
                g_len = metrics.get("game_length") or metrics.get("duration")
                tempo = metrics.get("tempo_notes") or metrics.get("tempo")
                if g_len is not None or tempo is not None:
                    out.append(f"player={player} game_length={g_len} tempo={tempo}")
            elif category_id == "mental":
                notes = d.get("notes") or d.get("mental_notes") or metrics.get("mental_notes")
                if notes:
                    out.append(f"player={player} notes={notes}")
            else:
                # general: compact summary
                out.append(f"player={player} games={d.get('games_analyzed')} metrics={metrics}")

            if len(out) >= limit:
                break

        logger.info("retrieve_for_category: scanned %d docs from reports; found %d passages for category=%s", docs_scanned, len(out), category_id)

        # If nothing found in reports, try player_matches as a fallback to extract per-match info
        if not out:
            pm_docs = _get_player_matches_docs(db, scan_limit)
            pm_scanned = 0
            for pm in pm_docs:
                pm_scanned += 1
                if role and (pm.get("role") or "").lower() != role.lower():
                    continue
                parsed = pm.get("parsed_metrics") or pm.get("metrics") or {}
                player = pm.get("player_puuid") or pm.get("player")
                match_id = pm.get("matchId") or pm.get("id")

                if category_id == "laning":
                    cs = parsed.get("cs_per_min") or parsed.get("cs")
                    early_deaths = parsed.get("early_deaths") or parsed.get("deaths_early")
                    if cs is not None or early_deaths is not None:
                        out.append(f"player={player} match={match_id} cs={cs} early_deaths={early_deaths}")
                elif category_id == "vision":
                    vs = parsed.get("vision_score")
                    wards = parsed.get("wards_placed")
                    if vs is not None or wards is not None:
                        out.append(f"player={player} match={match_id} vision_score={vs} wards={wards}")
                elif category_id == "macro":
                    objectives = parsed.get("objectives_taken")
                    if objectives is not None:
                        out.append(f"player={player} match={match_id} objectives={objectives}")
                elif category_id == "teamfights":
                    dmg = parsed.get("damage_pct") or parsed.get("damage_share")
                    if dmg is not None:
                        out.append(f"player={player} match={match_id} damage_pct={dmg}")
                elif category_id == "pacing":
                    tempo = parsed.get("tempo_notes")
                    if tempo:
                        out.append(f"player={player} match={match_id} tempo={tempo}")
                elif category_id == "mental":
                    notes = parsed.get("mental_notes")
                    if notes:
                        out.append(f"player={player} match={match_id} notes={notes}")
                else:
                    out.append(f"player={player} match={match_id} metrics={parsed}")

                if len(out) >= limit:
                    break

            logger.info("retrieve_for_category: scanned %d docs from player_matches; found %d passages for category=%s", pm_scanned if 'pm_scanned' in locals() else 0, len(out), category_id)

    except Exception as e:
        logger.exception("retrieve_for_category failed: %s", e)
        return []

    return [str(x) for x in out[:limit]]
