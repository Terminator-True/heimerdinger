from modules.llm.retrieval import retrieve_for_category


def make_db():
    return {
        "reports": {
            "1": {"player": "Alice", "role": "Top", "metrics": {"cs_per_min": 7.2, "early_deaths": 1}, "games_analyzed": 5},
            "2": {"player": "Bob", "role": "Support", "metrics": {"vision_score": 30, "wards_placed": 12}, "games_analyzed": 8},
            "3": {"player": "Cara", "role": "Jungle", "metrics": {"objectives_taken": 3, "rotations": 5}, "games_analyzed": 6},
        }
    }


def test_retrieve_each_category():
    db = make_db()
    cats = ["laning", "vision", "macro", "teamfights", "pacing", "mental", "general"]
    for c in cats:
        out = retrieve_for_category(c, None, db, limit=2)
        assert isinstance(out, list)
        # Allow empty but must be list
