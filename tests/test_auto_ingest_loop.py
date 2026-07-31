"""Tests for auto_ingest_loop — per-player failure isolation."""

from argparse import Namespace
from unittest.mock import patch, MagicMock

from scripts.auto_ingest_loop import _run_cycle


@patch("scripts.auto_ingest_loop.run_ingestion")
@patch("scripts.auto_ingest_loop.ingest_player")
@patch("scripts.auto_ingest_loop.get_team")
def test_run_cycle_continues_after_player_error(mock_get_team, mock_ingest_player, mock_run_ingestion):
    mock_get_team.return_value = [
        {"riotid": "Broken#EUW"},
        {"riotid": "Fine#EUW"},
    ]
    mock_ingest_player.side_effect = [Exception("boom"), {"puuid": "ok"}]
    mock_run_ingestion.return_value = {"reports": 1, "player_matches": 1}

    args = Namespace(team="team.json", games=5, region="europe", region_rep="europe", skip_fetch=False)
    summary = _run_cycle(args, MagicMock())

    assert mock_ingest_player.call_count == 2
    mock_run_ingestion.assert_called_once()
    assert summary == {"players_ok": 1, "players_failed": 1}
