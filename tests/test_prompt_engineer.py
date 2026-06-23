"""Tests for PromptEngineer — structured stat formatting and prompt building."""

from modules.llm.prompt_engineer import PromptEngineer


# ------------------------------------------------------------------
#  format_report_stats
# ------------------------------------------------------------------

def test_format_report_stats_full_match():
    """Formats a full per-match report like the user's example."""
    report = {
        "player": "Faker",
        "champion": "Yone",
        "role": "Top",
        "metrics": {
            "gameDuration": 1800,
            "win": False,
            "kills": 8,
            "deaths": 10,
            "assists": 3,
            "ch_killParticipation": 0.18,
            "ch_laneMinionsFirst10Minutes": 54,
            "ch_goldPerMinute": 426,
            "wardsPlaced": 11,
            "detectorWardsPlaced": 2,
            "ch_visionScorePerMinute": 0.94,
            "ch_damagePerMinute": 727,
            "ch_teamDamagePercentage": 0.136,
            "turretKills": 4,
            "baronKills": 1,
            "dragonKills": 2,
            "totalTimeSpentDead": 329,
            "longestTimeSpentLiving": 235,
        },
    }

    result = PromptEngineer.format_report_stats(report)

    # Header
    assert "Jugador: Faker" in result
    assert "Campeón: Yone" in result
    assert "Rol: Top" in result
    assert "Partida: 30min" in result
    assert "Victoria: No" in result

    # KDA line
    assert "KDA: 8.0/10.0/3.0" in result
    assert "KP: 18.0%" in result
    assert "CS: 54@10min" in result
    assert "Gold/min: 426" in result

    # Vision line
    assert "Visión: 11 wards" in result
    assert "2 control wards" in result
    assert "visionScore: 0.94/min" in result

    # Damage line
    assert "Daño: 727 DPM" in result
    assert "13.6% del equipo" in result

    # Objectives line
    assert "4 torretas" in result
    assert "1 barón" in result
    assert "2 dragón" in result

    # Deaths line
    assert "329s muerto" in result
    assert "235s" in result


def test_format_report_stats_aggregate():
    """Formats an aggregate report (no per-match fields like gameDuration)."""
    report = {
        "player": "Player1",
        "role": "Mid",
        "metrics": {
            "kills": 5.2,
            "deaths": 4.1,
            "assists": 6.3,
            "ch_killParticipation": 0.45,
            "ch_goldPerMinute": 412,
            "wardsPlaced": 9.5,
            "ch_visionScorePerMinute": 0.72,
            "ch_damagePerMinute": 510,
            "ch_teamDamagePercentage": 0.18,
            "turretKills": 1.2,
            "baronKills": 0.3,
        },
    }

    result = PromptEngineer.format_report_stats(report)

    # Header with fallbacks
    assert "Jugador: Player1" in result
    assert "Campeón: -" in result  # no championName
    assert "Rol: Mid" in result
    # No gameDuration → Partida: -
    assert "Partida: -" in result
    # No win → Victoria: -
    assert "Victoria: -" in result

    # KDA
    assert "KDA: 5.2/4.1/6.3" in result
    assert "KP: 45.0%" in result

    # Some fields may be missing — just check no crash
    assert isinstance(result, str)
    assert len(result) > 100


def test_format_report_stats_no_metrics():
    """Fallback gracefully when report has no metrics."""
    report = {"player": "Test", "role": "Jungle"}
    result = PromptEngineer.format_report_stats(report)
    assert "Jugador: Test" in result
    assert isinstance(result, str)


def test_format_report_stats_empty():
    """Empty dict returns defaults."""
    result = PromptEngineer.format_report_stats({})
    assert "Jugador: Jugador" in result  # default fallback
    assert isinstance(result, str)


def test_format_report_stats_win_true():
    """win=True produces 'Sí'."""
    result = PromptEngineer.format_report_stats({
        "player": "P", "metrics": {"win": True}
    })
    assert "Victoria: Sí" in result


def test_format_report_stats_pct_none():
    """None KP shows '-'."""
    result = PromptEngineer.format_report_stats({
        "player": "P", "metrics": {"kills": 1, "deaths": 2, "assists": 3}
    })
    assert "KP: -" in result


# ------------------------------------------------------------------
#  build_prompt
# ------------------------------------------------------------------

def test_build_prompt_includes_stats_block():
    """The prompt output must contain the formatted stats block."""
    pe = PromptEngineer()
    report = {
        "player": "TestPlayer",
        "champion": "Ahri",
        "role": "Mid",
        "metrics": {"kills": 10, "deaths": 2, "assists": 8, "win": True, "gameDuration": 1500},
    }

    prompt = pe.build_prompt(report, role="Mid", language="es", output_format="text")

    # Must include the stats header and KDA
    assert "Jugador: TestPlayer" in prompt
    assert "KDA: 10.0/2.0/8.0" in prompt
    # Must ask for 3 improvement points
    assert "3 puntos de mejora" in prompt
    # Must include role guidance for Mid
    assert "rotaciones" in prompt
    # Language instruction
    assert "castellano" in prompt


def test_build_prompt_no_crash_on_empty_report():
    """Should not crash when report is mostly empty."""
    pe = PromptEngineer()
    prompt = pe.build_prompt({}, role="coach", language="es", output_format="text")
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_build_prompt_includes_passages():
    """Passages should appear in the prompt."""
    pe = PromptEngineer()
    passages = ["player=test cs=7.5", "player=test vision=25"]
    prompt = pe.build_prompt(
        {"player": "P", "metrics": {"kills": 1}},
        role="Top",
        passages=passages,
        language="es",
        output_format="text",
    )
    assert "CONTEXT PASSAGES" in prompt
    assert "cs=7.5" in prompt


def test_build_prompt_includes_game_summary():
    """game_summary and important_points should be included."""
    pe = PromptEngineer()
    prompt = pe.build_prompt(
        {"player": "P", "metrics": {"kills": 1}},
        role="Top",
        game_summary="Yone | 30min | Derrota | KDA 8/10/3",
        important_points=["Gold/min: 426", "Daño: 727 DPM"],
        language="es",
        output_format="text",
    )
    assert "GAME SUMMARY" in prompt
    assert "Yone | 30min" in prompt
    assert "IMPORTANT POINTS" in prompt
    assert "Gold/min: 426" in prompt


def test_build_prompt_role_guidance():
    """Each role should get its specific guidance in the prompt."""
    pe = PromptEngineer()
    for role, keyword in [("Top", "control de oleadas"), ("Jungle", "gank"),
                          ("Mid", "rotaciones"), ("Bot", "CS"),
                          ("Support", "visión")]:
        prompt = pe.build_prompt(
            {"player": "P", "metrics": {}},
            role=role,
            language="es",
            output_format="text",
        )
        assert keyword in prompt, f"Role {role} should contain '{keyword}'"
