from typing import List, Optional


def retrieve_for_category(category_id: str, role: Optional[str], db, limit: int = 5) -> List[str]:
    out = []
    try:
        col = None
        try:
            col = db.get_collection("reports")
            docs = list(col.find({}).sort("_id", -1).limit(limit * 5))
        except Exception:
            # dict-backed
            col = db.setdefault("reports", {})
            docs = list(col.values())

        for d in docs:
            if role and d.get("role") != role:
                continue
            metrics = d.get("metrics", {})
            if category_id == "laning":
                cs = metrics.get("cs_per_min") or metrics.get("cs")
                early_deaths = metrics.get("early_deaths")
                out.append(f"player={d.get('player')} cs={cs} early_deaths={early_deaths}")
            elif category_id == "vision":
                vs = metrics.get("vision_score")
                wards = metrics.get("wards_placed")
                out.append(f"player={d.get('player')} vision_score={vs} wards={wards}")
            elif category_id == "macro":
                objectives = metrics.get("objectives_taken")
                rotations = metrics.get("rotations")
                out.append(f"player={d.get('player')} objectives={objectives} rotations={rotations}")
            elif category_id == "teamfights":
                dmg = metrics.get("damage_pct")
                pos = metrics.get("positioning_notes")
                out.append(f"player={d.get('player')} damage_pct={dmg} notes={pos}")
            elif category_id == "pacing":
                g_len = metrics.get("game_length")
                tempo = metrics.get("tempo_notes")
                out.append(f"player={d.get('player')} game_length={g_len} tempo={tempo}")
            elif category_id == "mental":
                notes = d.get("notes") or d.get("mental_notes")
                out.append(f"player={d.get('player')} notes={notes}")
            else:
                # general: compact summary
                out.append(f"player={d.get('player')} games={d.get('games_analyzed')} metrics={metrics}")

            if len(out) >= limit:
                break
    except Exception:
        # best-effort: return empty
        return []

    # compact and return
    return [str(x) for x in out[:limit]]
