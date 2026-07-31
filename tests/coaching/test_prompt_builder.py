"""Tests for CoachingPromptBuilder — schema-driven prompt generation."""

import pytest
from modules.coaching.prompt_builder import (
    CoachingPromptBuilder,
    SchemaFieldResolver,
    _find_participant,
    _find_puuid_by_role,
    _fmt,
)

# ---------------------------------------------------------------------------
#  fixture: minimal match doc
# ---------------------------------------------------------------------------

@pytest.fixture
def match_doc():
    return {
        "metadata": {"matchId": "test-001"},
        "info": {
            "gameDuration": 1800,
            "gameMode": "CLASSIC",
            "queueId": 420,
            "participants": [
                {
                    "puuid": "p-top",
                    "championName": "Yone",
                    "teamPosition": "TOP",
                    "individualPosition": "TOP",
                    "win": False,
                    "teamId": 100,
                    "kills": 8,
                    "deaths": 10,
                    "assists": 3,
                    "totalMinionsKilled": 210,
                    "goldEarned": 14500,
                    "goldSpent": 14000,
                    "totalDamageDealtToChampions": 28500,
                    "visionScore": 25,
                    "wardsPlaced": 12,
                    "detectorWardsPlaced": 2,
                    "totalTimeSpentDead": 329,
                    "longestTimeSpentLiving": 235,
                    "summoner1Id": 12,
                    "summoner2Id": 4,
                    "item0": 3153,
                    "item1": 3142,
                    "challenges": {
                        "kda": 0.89,
                        "killParticipation": 0.18,
                        "goldPerMinute": 426,
                        "damagePerMinute": 727,
                        "teamDamagePercentage": 0.136,
                        "laneMinionsFirst10Minutes": 54,
                        "maxCsAdvantageOnLaneOpponent": 12,
                        "turretPlatesTaken": 2,
                        "soloTurretsLategame": 1,
                        "firstTurretKilledTime": 1200,
                        "visionScoreAdvantageLaneOpponent": 2.1,
                        "controlWardsPlaced": 1,
                        "visionScorePerMinute": 0.94,
                    },
                },
                {
                    "puuid": "p-jungle",
                    "championName": "Lee Sin",
                    "teamPosition": "JUNGLE",
                    "individualPosition": "JUNGLE",
                    "win": False,
                    "teamId": 100,
                    "kills": 3,
                    "deaths": 5,
                    "assists": 12,
                    "challenges": {
                        "kda": 2.8,
                        "jungleCsBefore10Minutes": 55,
                        "moreEnemyJungleThanOpponent": 1,
                        "scuttleCrabKills": 3,
                        "goldPerMinute": 380,
                        "damagePerMinute": 420,
                    },
                },
            ],
            "teams": [
                {"teamId": 100, "win": False, "objectives": {
                    "baron": {"kills": 1, "first": True},
                    "dragon": {"kills": 3, "first": True},
                    "tower": {"kills": 8, "first": True},
                    "inhibitor": {"kills": 1, "first": False},
                    "riftHerald": {"kills": 1, "first": True},
                }},
                {"teamId": 200, "win": True, "objectives": {
                    "baron": {"kills": 2, "first": False},
                    "dragon": {"kills": 4, "first": False},
                    "tower": {"kills": 10, "first": False},
                    "inhibitor": {"kills": 2, "first": True},
                    "riftHerald": {"kills": 0, "first": False},
                }},
            ],
        },
    }


# ---------------------------------------------------------------------------
#  _find_ helpers
# ---------------------------------------------------------------------------

def test_find_participant_found(match_doc):
    p = _find_participant(match_doc, "p-top")
    assert p is not None
    assert p["championName"] == "Yone"


def test_find_participant_not_found(match_doc):
    assert _find_participant(match_doc, "nobody") is None


def test_find_puuid_by_role(match_doc):
    assert _find_puuid_by_role(match_doc, "Top") == "p-top"
    assert _find_puuid_by_role(match_doc, "JUNGLE") == "p-jungle"
    assert _find_puuid_by_role(match_doc, "Mid") is None


# ---------------------------------------------------------------------------
#  CoachingPromptBuilder — build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_top(match_doc):
    builder = CoachingPromptBuilder()
    prompt = builder.build_prompt(match_doc, puuid="p-top", role="Top")
    assert isinstance(prompt, str)
    assert len(prompt) > 200
    # Header
    assert "DATOS DEL JUGADOR" in prompt
    assert "Yone" in prompt
    assert "Top" in prompt
    assert "No" in prompt  # win=False
    # Role-specific fields (Top)
    assert "turretPlatesTaken" in prompt
    assert "killParticipation" in prompt
    assert "benchmark" in prompt  # at least one benchmark
    # Team objectives
    assert "CONTEXTO DE EQUIPO" in prompt
    assert "baron" in prompt
    assert "us)" in prompt and "them)" in prompt
    # Coaching focus
    assert "FOCO DE COACHING" in prompt
    assert "control de oleadas" in prompt
    # Instructions
    assert "3 puntos" in prompt


def test_build_prompt_jungle(match_doc):
    builder = CoachingPromptBuilder()
    prompt = builder.build_prompt(match_doc, puuid="p-jungle", role="Jungle")
    assert "Lee Sin" in prompt
    assert "Jungle" in prompt
    # Jungle-specific fields
    assert "jungleCsBefore10Minutes" in prompt
    assert "moreEnemyJungleThanOpponent" in prompt
    # Jungle coaching focus
    assert "rutas de limpieza" in prompt


def test_build_prompt_auto_detect_puuid(match_doc):
    """build_prompt auto-detects puuid when role is given."""
    builder = CoachingPromptBuilder()
    prompt = builder.build_prompt(match_doc, role="Top")
    assert "Yone" in prompt
    assert "DATOS DEL JUGADOR" in prompt


def test_build_prompt_auto_detect_role(match_doc):
    """build_prompt auto-detects role from participant when only puuid given."""
    builder = CoachingPromptBuilder()
    prompt = builder.build_prompt(match_doc, puuid="p-top")
    assert "Yone" in prompt
    assert "Top" in prompt  # auto-detected from teamPosition


def test_build_prompt_empty_doc():
    builder = CoachingPromptBuilder()
    assert builder.build_prompt({}) == ""


def test_build_prompt_includes_snapshot_and_history(match_doc):
    """match_snapshot/history render before INSTRUCCIONES (shared helper)."""
    builder = CoachingPromptBuilder()
    prompt = builder.build_prompt(
        match_doc,
        puuid="p-top",
        role="Top",
        match_snapshot="Jugador: Alice | Victoria: Sí",
        history=[
            {"role": "user", "content": "analiza mi partida"},
            {"role": "assistant", "content": "tu CS es bajo"},
        ],
    )
    assert "MATCH SNAPSHOT" in prompt
    assert "Jugador: Alice" in prompt
    assert "CONVERSATION HISTORY" in prompt
    assert "Usuario: analiza mi partida" in prompt
    assert "Coach: tu CS es bajo" in prompt
    # context must come before the schema's own instruction block
    assert prompt.index("MATCH SNAPSHOT") < prompt.index("=== INSTRUCCIONES ===")


def test_build_prompt_missing_puuid(match_doc):
    builder = CoachingPromptBuilder()
    assert builder.build_prompt(match_doc, puuid="nobody") == ""


def test_build_prompt_all_roles(match_doc):
    """Each role produces a different prompt with role-specific content."""
    builder = CoachingPromptBuilder()
    for role, keyword in [
        ("Top", "turretPlatesTaken"),
        ("Jungle", "scuttleCrabKills"),
        ("Mid", "killsOnOtherLanesEarlyJungleAsLaner"),
        ("Bot", "skillshotsDodged"),
        ("Support", "controlWardTimeCoverageInRiverOrEnemyHalf"),
    ]:
        prompt = builder.build_prompt(match_doc, role=role)
        # Auto-detect only works if there's a participant with matching role
        # For roles not in our fixture, the prompt will be empty
        if role in ("Top", "Jungle"):
            assert keyword in prompt, f"Role {role} should contain '{keyword}'"


# ---------------------------------------------------------------------------
#  SchemaFieldResolver
# ---------------------------------------------------------------------------

def test_resolver_source_map():
    schema = {"player_base": {"combat": {"kills": {"source": "kills"}}},
              "role_specific": {"Top": {"key_metrics": {}}}}
    resolver = SchemaFieldResolver(schema, "Top")
    assert resolver._source_map.get("kills") == "kills"


def test_resolver_resolve_direct():
    schema = {"player_base": {"combat": {"kills": {"source": "kills"}}},
              "role_specific": {"Top": {"key_metrics": {}}}}
    resolver = SchemaFieldResolver(schema, "Top")
    val = resolver.resolve({"kills": 8, "challenges": {}}, "kills")
    assert val == 8


def test_resolver_resolve_challenges():
    schema = {"player_base": {"combat": {"kda": {"source": "challenges.kda"}}},
              "role_specific": {"Top": {"key_metrics": {}}}}
    resolver = SchemaFieldResolver(schema, "Top")
    val = resolver.resolve({"challenges": {"kda": 0.89}}, "kda")
    assert val == 0.89


def test_resolver_resolve_list_source():
    schema = {"player_base": {"economy": {"items": {"source": ["item0", "item1"]}}},
              "role_specific": {"Top": {"key_metrics": {}}}}
    resolver = SchemaFieldResolver(schema, "Top")
    val = resolver.resolve({"item0": 3153, "item1": 3142}, "items")
    assert val == [3153, 3142]


# ---------------------------------------------------------------------------
#  _fmt
# ---------------------------------------------------------------------------

def test_fmt_bool():
    assert _fmt(True) == "Sí"
    assert _fmt(False) == "No"


def test_fmt_none():
    assert _fmt(None) == "-"


def test_fmt_float():
    assert _fmt(3.14159, 2) == "3.14"
    # 0 decimals means no fractional part
    assert _fmt(42.0, 0) == "42"
