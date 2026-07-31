from modules.llm.retrieval import retrieve_for_category, detect_role, keyword_candidates


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


def test_detect_role():
    assert detect_role("cómo viene el farm del jungler") == "Jungle"
    assert detect_role("kills del top") == "Top"
    assert detect_role("el supp") == "Support"
    assert detect_role("mid laner") == "Mid"
    assert detect_role("¿qué tal el adc?") == "Bot"
    assert detect_role("hola coach, cómo va todo") is None


def test_detect_role_rejects_ranking_and_false_positives():
    # "top 3" is a ranking, not the lane
    assert detect_role("dame tus top 3 consejos") is None
    # "apoyo" is generic help, not the Support role
    assert detect_role("necesito apoyo con mi macro") is None
    # "soporte técnico" is tech support, not the role; bare "soporte" is
    assert detect_role("soporte técnico") is None
    assert detect_role("mi soporte técnico") is None
    assert detect_role("el soporte") == "Support"
    # bare "bot" is not enough; lane/adc context is required
    assert detect_role("el bot jugó bien") is None
    assert detect_role("cómo va el botlane") == "Bot"
    assert detect_role("cómo va el bot lane") == "Bot"
    assert detect_role("cómo va el bot laner") == "Bot"
    assert detect_role("cómo va el tirador") == "Bot"


def test_keyword_candidates_expands_synonyms_and_drops_stopwords():
    kw = keyword_candidates("¿cómo viene el farm del jungler?")
    assert "cs" in kw  # farm/farmeo -> cs
    assert "jungler" in kw
    for stop in ("el", "del", "como", "cómo"):
        assert stop not in kw
    assert len(set(kw)) == len(kw)  # deduped


def test_keyword_candidates_drops_numeric_tokens():
    kw = keyword_candidates("dame tus top 3 consejos")
    assert "3" not in kw
    assert all(not t.isdigit() for t in kw)
