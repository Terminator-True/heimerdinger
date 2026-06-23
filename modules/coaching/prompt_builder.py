"""Schema-driven prompt builder for role-aware coaching.

Reads config/coaching_schema.json, resolves fields from the Riot API match doc
using the schema's source paths, applies benchmarks, and assembles a compact
~800-token prompt following the schema's prompt_template.

Usage:
    builder = CoachingPromptBuilder()
    prompt = builder.build_prompt(match_doc, puuid, "Top")
    # prompt is ready for LLaMA (~800 tokens)
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
#  helpers
# ---------------------------------------------------------------------------

def _load_schema(path: Optional[str] = None) -> Dict[str, Any]:
    """Load coaching_schema.json from config/ (or explicit path)."""
    if path is None:
        path = str(Path(__file__).resolve().parents[2] / "config" / "coaching_schema.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt(val: Any, decimals: int = 1) -> str:
    """Format a value for prompt display."""
    if val is None:
        return "-"
    if isinstance(val, bool):
        return "Sí" if val else "No"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def _find_participant(match_doc: Dict[str, Any], puuid: str) -> Optional[Dict[str, Any]]:
    """Find the participant dict matching *puuid*."""
    participants = match_doc.get("info", {}).get("participants", [])
    for p in participants:
        if p.get("puuid") == puuid:
            return p
    return None


def _find_puuid_by_role(match_doc: Dict[str, Any], role: str) -> Optional[str]:
    """Find a player puuid by teamPosition (TOP / JUNGLE / MIDDLE / BOTTOM / UTILITY)."""
    role_upper = role.upper()
    participants = match_doc.get("info", {}).get("participants", [])
    for p in participants:
        pos = (p.get("teamPosition") or p.get("individualPosition") or "").upper()
        if pos == role_upper:
            return p.get("puuid")
    return None


# ---------------------------------------------------------------------------
#  SchemaFieldResolver  —  maps field names → source paths, resolves values
# ---------------------------------------------------------------------------

class SchemaFieldResolver:
    """Resolves field values from a participant dict using schema source paths.

    Builds a flat {field_name: source_path} map from:
      - player_base.* (every category)
      - role_specific[role].key_metrics.* (every sub-category)
    """

    def __init__(self, schema: Dict[str, Any], role: str):
        self.schema = schema
        self.role = role
        self._source_map: Dict[str, Any] = {}
        self._benchmark_map: Dict[str, str] = {}
        self._format_map: Dict[str, str] = {}  # "percent" etc.
        self._build_maps()

    # ------------------------------------------------------------------
    #  map construction
    # ------------------------------------------------------------------

    def _build_maps(self):
        """Fill _source_map and _benchmark_map from schema."""
        # player_base
        for cat in ("identity", "combat", "economy", "damage",
                     "survival", "vision", "mechanics", "objectives",
                     "pings", "perks"):
            for fname, fdef in self.schema.get("player_base", {}).get(cat, {}).items():
                if not isinstance(fdef, dict):
                    continue  # skip strings like "description"
                src = fdef.get("source")
                if src is not None:
                    self._source_map[fname] = src
                fmt = fdef.get("format")
                if fmt:
                    self._format_map[fname] = fmt

        # role_specific.key_metrics
        for cat_name, cat in self.schema.get("role_specific", {}).get(self.role, {}).get("key_metrics", {}).items():
            if not isinstance(cat, dict):
                continue
            for fname, fdef in cat.items():
                if not isinstance(fdef, dict):
                    continue
                src = fdef.get("source")
                if src is not None:
                    self._source_map[fname] = src
                bm = fdef.get("benchmark")
                if bm:
                    self._benchmark_map[fname] = bm
                fmt = fdef.get("format")
                if fmt:
                    self._format_map[fname] = fmt

    # ------------------------------------------------------------------
    #  value resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_path(data: Any, path: str) -> Any:
        """Resolve a dotted path (e.g. 'challenges.kda') from a dict."""
        if not data or not path:
            return None
        parts = path.split(".")
        cur = data
        for p in parts:
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return None
        return cur

    def resolve(self, participant: Dict[str, Any], field_name: str) -> Any:
        """Resolve a single field from participant data.

        Strategy (in order):
          1. Schema source path → resolve dotted path
          2. Direct key on participant
          3. challenges sub-dict key
        """
        # 1. schema source
        source = self._source_map.get(field_name)
        if source is not None:
            if isinstance(source, list):
                # list of keys → return list of values
                return [participant.get(k) for k in source]
            return self._resolve_path(participant, source)

        # 2. direct
        val = participant.get(field_name)
        if val is not None:
            return val

        # 3. challenges
        ch = participant.get("challenges", {})
        return ch.get(field_name)

    def resolve_many(self, participant: Dict[str, Any],
                     field_names: List[str]) -> Dict[str, Any]:
        """Resolve multiple fields, returning {name: value}."""
        out = {}
        for fn in field_names:
            out[fn] = self.resolve(participant, fn)
        return out

    def get_benchmark(self, field_name: str) -> Optional[str]:
        return self._benchmark_map.get(field_name)


# ---------------------------------------------------------------------------
#  PromptAssembler  —  formats extracted data into the prompt template
# ---------------------------------------------------------------------------

class PromptAssembler:
    """Assembles the final coaching prompt from extracted data.

    Follows the schema's prompt_template structure to keep output
    consistent and under ~800 tokens.
    """

    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema

    # ------------------------------------------------------------------
    #  field formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_fields(fields: Dict[str, Any],
                       benchmarks: Dict[str, str],
                       formats: Dict[str, str],
                       skip_keys: set) -> str:
        """Format resolved fields as compact key=value lines.

        Fields matching *skip_keys* (already shown in header) are omitted.
        Applies format directives (e.g. percent) from the schema.
        """
        lines = []
        for key, val in fields.items():
            if key in skip_keys:
                continue

            # apply format
            fmt = formats.get(key)
            if fmt == "percent" and val is not None:
                try:
                    val = f"{float(val) * 100:.1f}%"
                except (ValueError, TypeError):
                    pass
            elif key == "items" and isinstance(val, list):
                # filter out None, present as IDs
                ids = [str(x) for x in val if x is not None]
                val = ", ".join(ids) if ids else "-"
            else:
                val = _fmt(val)

            text = f"{key}: {val}"
            bm = benchmarks.get(key)
            if bm:
                text += f"  (benchmark: {bm})"
            lines.append(text)
        return "\n".join(lines)

    @staticmethod
    def _format_team_objectives(team_obj: Dict[str, Any],
                                 enemy_obj: Dict[str, Any]) -> str:
        """Format team objectives comparison."""
        lines = []
        for k in ("win", "baron_kills", "dragon_kills", "tower_kills",
                   "inhibitor_kills", "riftHerald_kills",
                   "baron_first", "dragon_first", "tower_first"):
            mine = team_obj.get(k, "-")
            theirs = enemy_obj.get(k, "-")
            if k.endswith("_first"):
                label = k.replace("_first", " first")
                lines.append(f"  {label}: {'1st' if mine else '--'} (us) / {'1st' if theirs else '--'} (them)")
            else:
                label = k.replace("_kills", "")
                lines.append(f"  {label}: {mine} (us) / {theirs} (them)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  assemble
    # ------------------------------------------------------------------

    def assemble(self, *,
                 riot_id: str,
                 champion_name: str,
                 team_position: str,
                 win: Any,
                 campos_del_rol: str,
                 team_objectives: str,
                 coaching_focus: str) -> str:
        """Build the final prompt string from parts."""
        template = self.schema.get("prompt_template", {})
        structure = template.get("structure", "")

        # If the template is missing, build a sensible default
        if not structure:
            structure = (
                "Eres un coach experto de League of Legends. "
                "Analiza la siguiente partida y proporciona feedback "
                "específico y accionable para el jugador.\n"
                "\n"
                "=== DATOS DEL JUGADOR ===\n"
                "Nombre: {riotId}\n"
                "Campeón: {championName}\n"
                "Rol: {teamPosition}\n"
                "Resultado: {win}\n"
                "\n"
                "=== ESTADÍSTICAS CLAVE ===\n"
                "{campos_del_rol}\n"
                "\n"
                "=== CONTEXTO DE EQUIPO ===\n"
                "{team_objectives}\n"
                "\n"
                "=== FOCO DE COACHING PARA {teamPosition} ===\n"
                "{coaching_focus}\n"
                "\n"
                "=== INSTRUCCIONES ===\n"
                "Identifica exactamente 3 puntos débiles con datos concretos.\n"
                "Para cada punto débil da 1 ejercicio o acción específica para mejorar.\n"
                "Sé directo, usa números, evita generalidades.\n"
                "Responde exclusivamente en castellano."
            )

        return structure.format(
            riotId=riot_id,
            championName=champion_name,
            teamPosition=team_position,
            win=_fmt(win),
            campos_del_rol=campos_del_rol,
            team_objectives=team_objectives,
            coaching_focus=coaching_focus,
        )


# ---------------------------------------------------------------------------
#  CoachingPromptBuilder  —  public API
# ---------------------------------------------------------------------------

class CoachingPromptBuilder:
    """Main entry point for schema-driven prompt building.

    Usage:
        builder = CoachingPromptBuilder()
        prompt = builder.build_prompt(match_doc, puuid, "Top")
        # prompt is ~800 tokens, ready for LLaMA
    """

    def __init__(self, schema_path: Optional[str] = None):
        self.schema = _load_schema(schema_path)
        self.assembler = PromptAssembler(self.schema)

    def build_prompt(self, match_doc: Dict[str, Any],
                     puuid: Optional[str] = None,
                     role: Optional[str] = None) -> str:
        """Build a coaching prompt for the given match + player.

        Args:
            match_doc: Full Riot API match document.
            puuid: Player to analyse. If None, auto-detected from *role*.
            role: Role string (Top, Jungle, Mid, Bot, Support, coach).
                  If None, auto-detected from participant data.

        Returns:
            A ~800-token prompt string ready for LLaMA.
        """
        if not match_doc:
            return ""

        info = match_doc.get("info", {})

        # resolve puuid from role if not given
        if not puuid and role:
            puuid = _find_puuid_by_role(match_doc, role)

        # find participant
        participant = _find_participant(match_doc, puuid or "")
        if not participant:
            return ""

        # resolve role from participant if not given
        if not role:
            role = (participant.get("teamPosition")
                    or participant.get("individualPosition")
                    or "coach")

        # normalise role name for schema lookup
        role_key = self._resolve_role_key(role)

        # build the field resolver for this role
        resolver = SchemaFieldResolver(self.schema, role_key)

        # get llm_prompt_fields list
        prompt_fields = self._get_prompt_fields(role_key)

        # resolve all fields
        resolved = resolver.resolve_many(participant, prompt_fields)

        # format role fields (skip those shown in header)
        header_keys = {"championName", "win"}
        campos = self.assembler._format_fields(
            resolved, resolver._benchmark_map, resolver._format_map, header_keys
        )

        # team objectives
        team_id = participant.get("teamId", 100)
        enemy_id = 200 if team_id == 100 else 100
        team_obj = self._extract_team_objectives(info, team_id)
        enemy_obj = self._extract_team_objectives(info, enemy_id)
        team_obj_text = self.assembler._format_team_objectives(team_obj, enemy_obj)

        # coaching focus
        focus = self._get_focus(role_key)

        # identity fields
        riot_id = participant.get("riotIdGameName") or participant.get("puuid", "?")
        champ = resolved.get("championName", participant.get("championName", "?"))
        win = resolved.get("win", participant.get("win", "?"))

        # assemble
        return self.assembler.assemble(
            riot_id=riot_id,
            champion_name=champ,
            team_position=role_key if role_key != "coach" else "Coach",
            win=win,
            campos_del_rol=campos,
            team_objectives=team_obj_text,
            coaching_focus=focus,
        )

    # ------------------------------------------------------------------
    #  internals
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_role_key(role: str) -> str:
        """Normalise user-provided role to schema key."""
        r = role.strip().upper()
        mapping = {
            "TOP": "Top",
            "JUNGLE": "Jungle",
            "JUNGLA": "Jungle",
            "MID": "Mid",
            "MIDDLE": "Mid",
            "BOT": "Bot",
            "BOTTOM": "Bot",
            "ADC": "Bot",
            "SUPPORT": "Support",
            "UTILITY": "Support",
            "SUP": "Support",
        }
        return mapping.get(r, "coach")

    def _get_prompt_fields(self, role_key: str) -> List[str]:
        """Return the llm_prompt_fields list for this role."""
        rs = self.schema.get("role_specific", {})
        fields = rs.get(role_key, {}).get("llm_prompt_fields", [])
        if not fields:
            # fallback: use player_base identity + combat
            pb = self.schema.get("player_base", {})
            defaults = ["championName", "win", "kills", "deaths", "assists",
                        "goldPerMinute", "damagePerMinute", "visionScore",
                        "totalTimeSpentDead"]
            for d in defaults:
                if d not in fields:
                    fields.append(d)
        return fields

    def _get_focus(self, role_key: str) -> str:
        """Return coaching_focus text from schema."""
        rs = self.schema.get("role_specific", {})
        default = (
            "Proporciona entrenamiento general: ejercicios concretos, "
            "áreas a mejorar y quick wins."
        )
        return rs.get(role_key, {}).get("coaching_focus", default)

    @staticmethod
    def _extract_team_objectives(info: Dict[str, Any],
                                  team_id: int) -> Dict[str, Any]:
        """Extract objectives for a single team."""
        teams = info.get("teams", [])
        for team in teams:
            if team.get("teamId") != team_id:
                continue
            obj = team.get("objectives", {})
            return {
                "win": team.get("win"),
                "baron_kills": _fmt(obj.get("baron", {}).get("kills"), 0),
                "dragon_kills": _fmt(obj.get("dragon", {}).get("kills"), 0),
                "tower_kills": _fmt(obj.get("tower", {}).get("kills"), 0),
                "inhibitor_kills": _fmt(obj.get("inhibitor", {}).get("kills"), 0),
                "riftHerald_kills": _fmt(obj.get("riftHerald", {}).get("kills"), 0),
                "baron_first": obj.get("baron", {}).get("first", False),
                "dragon_first": obj.get("dragon", {}).get("first", False),
                "tower_first": obj.get("tower", {}).get("first", False),
            }
        return {}

    def find_puuid_by_role(self, match_doc: Dict[str, Any],
                           role: str) -> Optional[str]:
        """Convenience: find a player's puuid by their role in this match."""
        return _find_puuid_by_role(match_doc, role)
