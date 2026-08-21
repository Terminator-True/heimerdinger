"""Domain ports (interfaces) for Heimerdinger services.

Domain services depend on these Protocols, never on concrete infrastructure.
Concrete adapters live in ``modules/adapters/`` and are wired in
``modules/composition.py``. Existing classes (RiotClient, OllamaClient,
VectorStore, Embedder, MatchesRepository) satisfy their ports structurally.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class RiotClientPort(Protocol):
    """Access to the Riot Games API v5."""

    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> Dict[str, Any]:
        ...

    def get_match_ids_by_puuid(
        self,
        puuid: str,
        count: int = 20,
        start: int = 0,
        region_rep: str = "europe",
    ) -> List[str]:
        ...

    def get_match_by_id(self, match_id: str, region_rep: str = "europe") -> Dict[str, Any]:
        ...


@runtime_checkable
class RateLimiterPort(Protocol):
    """Global rate limiter for outbound Riot API calls."""

    def acquire(self) -> bool:
        ...


@runtime_checkable
class MatchRepositoryPort(Protocol):
    """Persistence for raw and parsed match documents."""

    def match_exists(self, match_id: str) -> bool:
        ...

    def player_match_exists(self, match_id: str, puuid: str) -> bool:
        ...

    def upsert_match(self, match_json: Dict[str, Any], skip_if_exists: bool = False) -> bool:
        ...

    def upsert_parsed_player_match(self, player_parsed: Dict[str, Any]) -> None:
        ...


@runtime_checkable
class ReportRepositoryPort(Protocol):
    """Persistence for player and match reports."""

    def upsert_report(self, report: Dict[str, Any]) -> None:
        ...

    def find_reports_by_role(self, role: str, limit: int = 10) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class EmbedderPort(Protocol):
    """Text embedding backend."""

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        ...


@runtime_checkable
class VectorStorePort(Protocol):
    """Semantic vector store (e.g. ChromaDB)."""

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...

    def search_keywords(
        self,
        keywords: List[str],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class LLMClientPort(Protocol):
    """Local LLM inference client (e.g. Ollama)."""

    def generate(self, prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        ...


@runtime_checkable
class ConfigSourcePort(Protocol):
    """Read-only access to application configuration."""

    def get_team(self, name_or_path: str) -> Dict[str, Any]:
        ...

    def get_embeddings_config(self) -> Dict[str, Any]:
        ...

    def get_ddragon_config(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class FileOutputPort(Protocol):
    """File-system output for reports and LLM debug artifacts."""

    def write_report(self, report: Dict[str, Any], filename: str) -> None:
        ...

    def write_ollama_response(
        self,
        puuid: str,
        prompt: str,
        raw: Any,
        model: str,
    ) -> None:
        ...

    def write_coach_exchange(self, payload: Dict[str, Any], ts: str) -> None:
        ...
