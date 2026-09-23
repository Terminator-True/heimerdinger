"""Tests for modules/config_manager.py focus-player config."""
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest

from modules.config_manager import get_focus_player


def test_unset_riotid_returns_none(monkeypatch):
    monkeypatch.delenv("FOCUS_RIOTID", raising=False)
    monkeypatch.delenv("FOCUS_ROLE", raising=False)
    assert get_focus_player() is None


def test_blank_riotid_returns_none(monkeypatch):
    monkeypatch.setenv("FOCUS_RIOTID", "   ")
    monkeypatch.setenv("FOCUS_ROLE", "Support")
    assert get_focus_player() is None


def test_explicit_riotid_and_role(monkeypatch):
    monkeypatch.setenv("FOCUS_RIOTID", "TR Terminator#1998")
    monkeypatch.setenv("FOCUS_ROLE", "Support")
    assert get_focus_player() == {"riotid": "TR Terminator#1998", "role": "Support"}


def test_missing_role_defaults_to_support(monkeypatch):
    monkeypatch.setenv("FOCUS_RIOTID", "TR Terminator#1998")
    monkeypatch.delenv("FOCUS_ROLE", raising=False)
    assert get_focus_player() == {"riotid": "TR Terminator#1998", "role": "Support"}


def test_blank_role_defaults_to_support(monkeypatch):
    monkeypatch.setenv("FOCUS_RIOTID", "TR Terminator#1998")
    monkeypatch.setenv("FOCUS_ROLE", "   ")
    assert get_focus_player()["role"] == "Support"


def test_invalid_riotid_without_hash_raises(monkeypatch):
    monkeypatch.setenv("FOCUS_RIOTID", "TR Terminator")
    monkeypatch.setenv("FOCUS_ROLE", "Support")
    with pytest.raises(ValueError):
        get_focus_player()


def test_invalid_riotid_empty_tagline_raises(monkeypatch):
    monkeypatch.setenv("FOCUS_RIOTID", "TR Terminator#")
    monkeypatch.setenv("FOCUS_ROLE", "Support")
    with pytest.raises(ValueError):
        get_focus_player()


def test_whitespace_is_stripped(monkeypatch):
    monkeypatch.setenv("FOCUS_RIOTID", "  TR Terminator#1998  ")
    monkeypatch.setenv("FOCUS_ROLE", "  Support  ")
    assert get_focus_player() == {"riotid": "TR Terminator#1998", "role": "Support"}
