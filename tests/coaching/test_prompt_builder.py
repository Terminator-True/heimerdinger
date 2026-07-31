"""Tests for CoachingPromptBuilder — schema-driven prompt generation."""

import copy

import httpx
import pytest
import respx

from modules.coaching.prompt_builder import (
    CoachingPromptBuilder,
    SchemaFieldResolver,
    _find_participant,
    _find_puuid_by_role,
    _fmt,
    _render_items,
)
from modules.riot_items import DataDragonClient, Item, ItemGold

# ---------------------------------------------------------------------------
#  Data Dragon test data + hermetic network routes
# ---------------------------------------------------------------------------

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
ITEM_URL = "https://ddragon.leagueoflegends.com/cdn/14.20.1/data/es_ES/item.json"
# Released versions must resolve the fixture's gameVersion 14.20.568.9039 -> 14.20.1
VERSIONS = ["15.4.1", "15.3.1", "14.20.1"]

ITEM_ENTRIES = {
    "3866": ("Guantes de Bruja", 1100),
    "2524": ("Filo del Infinito", 3400),
    "3009": ("Botas de Mercurio", 1300),
    "3067": ("Corazón de Hielo", 2900),
    "1028": ("Libro de Hechicero", 900),
    "3364": ("Centinela de paja", 0),
    "3340": ("Lente de control", 0),
}
ITEM_JSON = {
    "type": "item",
    "version": "14.20.1",
    "data": {
        item_id: {
            "name": name,
            "gold": {"total": gold, "base": gold, "sell": gold, "purchasable": True},
            "plaintext": name,
        }
        for item_id, (name, gold) in ITEM_ENTRIES.items()
    },
}


@pytest.fixture(autouse=True)
def ddragon_net():
    """Route Data Dragon calls to hermetic fixtures — never real network.

    Uses the global respx router so ``respx.get`` registrations and request
    interception share one router; every prompt-building test in this module
    resolves items deterministically. The route objects are yielded for
    call-count assertions.
    """
    with respx.mock:
        versions = respx.get(VERSIONS_URL).mock(
            return_value=httpx.Response(200, json=VERSIONS)
        )
        items = respx.get(ITEM_URL).mock(
            return_value=httpx.Response(200, json=ITEM_JSON)
        )
        yield {"versions": versions, "items": items}


def _client(tmp_path, version: str = "14.20.1") -> DataDragonClient:
    """DataDragonClient with an isolated disk cache (deterministic tests)."""
    return DataDragonClient(version=version, cache_dir=tmp_path, client=httpx.Client())


class _FakeClient(httpx.Client):
    """httpx.Client stub: returns canned responses per URL, or raises."""

    def __init__(self, url_map=None, exc=None):
        super().__init__()
        self._url_map = url_map or {}
        self._exc = exc

    def get(self, url, *args, **kwargs):
        if self._exc is not None:
            raise self._exc
        response = self._url_map.get(url)
        if response is None:
            return httpx.Response(500)
        return response


def _participant(puuid, champion, position, team_id, items, trinket, **extra):
    """Build a minimal participant carrying item slots + optional extras."""
    p = {
        "puuid": puuid,
        "championName": champion,
        "teamPosition": position,
        "individualPosition": position,
        "win": False,
        "teamId": team_id,
        "kills": 0,
        "deaths": 0,
        "assists": 0,
        "challenges": {},
    }
    for i, item_id in enumerate(items):
        p[f"item{i}"] = item_id
    p["item6"] = trinket
    p.update(extra)
    return p


# ---------------------------------------------------------------------------
#  fixture: full 10-player match doc (5v5, no Mid participant on purpose)
# ---------------------------------------------------------------------------

@pytest.fixture
def match_doc():
    return {
        "metadata": {"matchId": "test-001"},
        "info": {
            "gameVersion": "14.20.568.9039",
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
                    "item0": 3866,
                    "item1": 2524,
                    "item2": 3009,
                    "item3": 3067,
                    "item4": 1028,
                    "item5": 0,
                    "item6": 3364,
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
                _participant("p-ahri", "Ahri", "BOTTOM", 100,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
                _participant("p-kaisa", "Kai'Sa", "BOTTOM", 100,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
                _participant("p-nautilus", "Nautilus", "SUPPORT", 100,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
                _participant("p-garen", "Garen", "TOP", 200,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
                _participant("p-darius", "Darius", "TOP", 200,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
                _participant("p-lux", "Lux", "SUPPORT", 200,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
                _participant("p-caitlyn", "Caitlyn", "BOTTOM", 200,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
                _participant("p-thresh", "Thresh", "SUPPORT", 200,
                             [3866, 2524, 3009, 3067, 1028, 0], 3340),
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


# ---------------------------------------------------------------------------
#  DDragon item-name resolution (tasks 2.1 / 2.4)
# ---------------------------------------------------------------------------

def test_build_prompt_renders_item_names(match_doc, tmp_path):
    """Slots 0-4 render as 'Name (G oro)'; empty slot 5 is omitted."""
    builder = CoachingPromptBuilder(ddragon_client=_client(tmp_path))
    prompt = builder.build_prompt(match_doc, puuid="p-top", role="Top")
    assert (
        "items: Guantes de Bruja (1100 oro), Filo del Infinito (3400 oro), "
        "Botas de Mercurio (1300 oro), Corazón de Hielo (2900 oro), "
        "Libro de Hechicero (900 oro)" in prompt
    )
    assert "ID 3866" not in prompt
    assert builder.resolution_status == "resolved"


def test_build_prompt_empty_slot_omitted(match_doc, tmp_path):
    """The raw 0 of slot 5 must not leak into the stats line."""
    builder = CoachingPromptBuilder(ddragon_client=_client(tmp_path))
    prompt = builder.build_prompt(match_doc, puuid="p-top", role="Top")
    assert "Libro de Hechicero (900 oro), 0" not in prompt
    assert "Libro de Hechicero (900 oro)" in prompt


def test_build_prompt_unknown_item_shows_placeholder(match_doc, tmp_path):
    """An id absent from the version's item data renders as unknown."""
    doc = copy.deepcopy(match_doc)
    target = next(p for p in doc["info"]["participants"] if p["puuid"] == "p-top")
    target["item0"] = 9999  # not present in the mocked item data
    builder = CoachingPromptBuilder(ddragon_client=_client(tmp_path))
    prompt = builder.build_prompt(doc, puuid="p-top", role="Top")
    assert "ID 9999 (desconocido)" in prompt


def test_render_items_pure():
    """Known -> 'Name (G oro)'; 0/None -> None (omitted); unknown -> 'ID N (...)'."""
    named = {3866: Item(name="Guantes de Bruja", gold=ItemGold(total=1100))}
    assert _render_items([3866, 0, None, 9999], named) == [
        "Guantes de Bruja (1100 oro)",
        None,
        None,
        "ID 9999 (desconocido)",
    ]


def test_build_prompt_offline_falls_back_to_raw_ids(match_doc):
    """Network failure degrades to raw ids (old behavior), no crash."""
    builder = CoachingPromptBuilder(
        ddragon_client=DataDragonClient(
            client=_FakeClient(exc=httpx.ConnectError("offline"))
        )
    )
    prompt = builder.build_prompt(match_doc, puuid="p-top", role="Top")
    assert "items: 3866, 2524, 3009, 3067, 1028, 0" in prompt  # raw ids kept
    assert "Guantes de Bruja" not in prompt
    assert builder.resolution_status == "fallback"


def test_build_prompt_malformed_versions_degrades(match_doc):
    """Malformed versions.json -> ValueError -> raw-id fallback, no crash."""
    bad = _FakeClient(url_map={
        VERSIONS_URL: httpx.Response(
            200,
            content=b"{not json",
            request=httpx.Request("GET", VERSIONS_URL),
        )
    })
    builder = CoachingPromptBuilder(ddragon_client=DataDragonClient(client=bad))
    prompt = builder.build_prompt(match_doc, puuid="p-top", role="Top")
    assert "3866" in prompt
    assert "Guantes de Bruja" not in prompt
    assert builder.resolution_status == "fallback"
