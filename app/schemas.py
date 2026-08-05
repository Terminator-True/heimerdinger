"""Pydantic request models for the Heimerdinger API.

Responses are deliberately untyped: the underlying modules already return
plain dicts, and wrapping them in response models would duplicate schemas
that live in the DB. Request models enforce what the API accepts.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestPlayerRequest(BaseModel):
    riotid: str = Field(..., description="RiotID in the form 'Name#Tagline'")
    count: int = Field(5, ge=1, le=100)
    region: str = "europe"
    region_rep: str = "europe"
    team_puuids: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="When set, a match is only ingested if at least "
        "min_team_members of these puuids are present in it.",
    )
    min_team_members: int = Field(5, ge=1)


class IngestTeamRequest(BaseModel):
    team_path: str = "team.json"
    count: int = Field(5, ge=1, le=100)
    region: str = "europe"
    region_rep: str = "europe"


class CoachRequest(BaseModel):
    question: str
    role: Optional[str] = None
    model: str = "llama3.1:8b"
    last_match: bool = False
    lang: str = "es"
    history: Optional[List[Dict[str, Any]]] = None


class EmbeddingQueryRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=20)
    where: Optional[Dict[str, Any]] = None
