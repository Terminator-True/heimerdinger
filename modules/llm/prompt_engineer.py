"""PromptEngineer — builds prompts for coaching/advice tasks with structured stats.

Usage:
    pe = PromptEngineer()
    prompt = pe.build_prompt(player_report, role='Top', passages=[...])
"""
from typing import Dict, Optional, List


MAX_HISTORY_TURNS = 6


def build_chat_context(match_snapshot: Optional[str] = None,
                       history: Optional[List[Dict]] = None) -> str:
    """Render match snapshot + conversation history + a follow-up instruction.

    The snapshot section appears only when *match_snapshot* is truthy; the
    history section renders one line per turn (``Usuario:``/``Coach:``), capped
    at MAX_HISTORY_TURNS, skipping non-dict turns and non-list history.
    Returns "" when both inputs are empty.
    """
    sections = []
    if match_snapshot:
        sections.append("MATCH SNAPSHOT (todos los jugadores):\n" + match_snapshot.strip())
    if isinstance(history, list):
        turn_lines = []
        for turn in history[-MAX_HISTORY_TURNS:]:
            if not isinstance(turn, dict):
                continue
            t_role = (turn.get("role") or "").lower()
            speaker = "Usuario" if t_role in ("user", "usuario", "human") else "Coach"
            turn_lines.append(f"{speaker}: {turn.get('content') or ''}")
        if turn_lines:
            sections.append("CONVERSATION HISTORY:\n" + "\n".join(turn_lines))
    if not sections:
        return ""
    return (
        "\n" + "\n\n".join(sections) + "\n\n"
        "Responde a la PREGUNTA MÁS RECIENTE del usuario usando el contexto disponible. "
        "No hagas preguntas de aclaración; responde directamente.\n\n"
    )


class PromptEngineer:
    """Builds prompts for the LLM to produce coaching-style advice.

    The prompt now includes a structured stats block formatted like:

        Jugador: Faker | Campeón: Yone | Rol: Top | Partida: 30min | Victoria: No

        KDA: 8/10/3 | KP: 18% | CS: 54@10min | Gold/min: 426
        Visión: 11 wards, 2 control wards, visionScore: 0.94/min
        Daño: 727 DPM | 13.6% del equipo
        Objetivos: 4 torretas, 1 barón
        Muertes: 329s muerto en total | max streak vivo: 235s

        Actúa como coach de LoL. Analiza el rendimiento e identifica
        los 3 principales puntos de mejora con consejos específicos.
    """

    # ------------------------------------------------------------------
    #  Templates
    # ------------------------------------------------------------------

    system_template = (
        "Eres un coach experto de League of Legends con 10+ años de experiencia. "
        "Tu trabajo es analizar estadísticas de partida y dar consejos "
        "concretos, accionables y específicos para el rol del jugador. "
        "Sé directo, constructivo y específico — nada de frases genéricas."
    )

    # Role-specific guidance
    role_guidance = {
        "Top": "Céntrate en control de oleadas, trades cortos, y visión en la zona superior.",
        "Jungle": "Céntrate en rutas de limpieza, temporización de objetivos, ventanas de gank y control de visión.",
        "Mid": "Céntrate en rotaciones, manipulación de oleadas, trades y conocimiento de enfrentamientos.",
        "Bot": "Céntrate en CS, trades con el support, posicionamiento en línea y teamfights.",
        "Support": "Céntrate en visión, rotaciones, peel, engage/disengage y priorización de wards.",
        "coach": "Proporciona entrenamiento general: ejercicios concretos, áreas a mejorar y quick wins."
    }

    # Main user template — {stats_block} is injected by the formatter
    user_template = (
        "{stats_block}\n\n"
        "Role Guidance: {role_guidance}\n\n"
        "Actúa como coach de LoL. Analiza el rendimiento e identifica "
        "los 3 principales puntos de mejora con consejos específicos."
    )

    # ------------------------------------------------------------------
    #  Structured stat formatter
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(val, decimals: int = 1) -> str:
        """Format a numeric value, returning '-' if None."""
        if val is None:
            return "-"
        try:
            f = float(val)
            return f"{f:.{decimals}f}"
        except (ValueError, TypeError):
            return str(val)

    @staticmethod
    def _pct(val, decimals: int = 1) -> str:
        """Format a decimal as percentage string, returning '-' if None."""
        if val is None:
            return "-"
        try:
            return f"{float(val) * 100:.{decimals}f}%"
        except (ValueError, TypeError):
            return "-"

    @classmethod
    def format_report_stats(cls, report: Dict) -> str:
        """Format a player report into the structured stats block.

        Accepts either an aggregate report (with a 'metrics' dict containing
        means) or a per-match dict with raw values.

        Returns a string like:
            Jugador: Faker | Campeón: Yone | Rol: Top | Partida: 30min | Victoria: No
            ...
        """
        metrics = report.get("metrics") or report

        # --- header line ---
        name = report.get("player") or report.get("player_name") or report.get("puuid") or "Jugador"
        champ = report.get("champion") or metrics.get("championName") or "-"
        role = report.get("role") or metrics.get("individualPosition") or metrics.get("teamPosition") or "-"

        # game duration (seconds → minutes)
        dur_sec = metrics.get("gameDuration")
        dur_min_str = f"{dur_sec // 60}min" if dur_sec else "-"

        # win
        raw_win = metrics.get("win")
        if raw_win is True or raw_win == "True" or raw_win == 1:
            win_str = "Sí"
        elif raw_win is False or raw_win == "False" or raw_win == 0:
            win_str = "No"
        else:
            win_str = "-"

        lines = [f"Jugador: {name} | Campeón: {champ} | Rol: {role} | Partida: {dur_min_str} | Victoria: {win_str}"]
        lines.append("")

        # --- KDA line ---
        kills = cls._fmt(metrics.get("kills"))
        deaths = cls._fmt(metrics.get("deaths"))
        assists = cls._fmt(metrics.get("assists"))
        kp = cls._pct(metrics.get("ch_killParticipation"))
        cs10 = cls._fmt(metrics.get("ch_laneMinionsFirst10Minutes"), 0)
        gpm = cls._fmt(metrics.get("ch_goldPerMinute"), 0)
        lines.append(f"KDA: {kills}/{deaths}/{assists} | KP: {kp} | CS: {cs10}@10min | Gold/min: {gpm}")

        # --- Vision line ---
        wards = cls._fmt(metrics.get("wardsPlaced"), 0)
        ctrl_wards = cls._fmt(metrics.get("detectorWardsPlaced") or metrics.get("ch_controlWardsPlaced"), 0)
        vs_pm = cls._fmt(metrics.get("ch_visionScorePerMinute"), 2)
        lines.append(f"Visión: {wards} wards, {ctrl_wards} control wards, visionScore: {vs_pm}/min")

        # --- Damage line ---
        dpm = cls._fmt(metrics.get("ch_damagePerMinute"), 0)
        team_dmg_pct = cls._pct(metrics.get("ch_teamDamagePercentage"))
        lines.append(f"Daño: {dpm} DPM | {team_dmg_pct} del equipo")

        # --- Objectives line ---
        turrets = cls._fmt(metrics.get("turretKills"), 0)
        barons = cls._fmt(metrics.get("baronKills"), 0)
        dragons = cls._fmt(metrics.get("dragonKills"), 0)
        # Compute inhibitorKills if available
        inhibs = cls._fmt(metrics.get("inhibitorKills"), 0)
        obj_parts = [f"{turrets} torretas", f"{barons} barón"]
        if dragons != "-":
            obj_parts.append(f"{dragons} dragón")
        if inhibs != "-" and float(inhibs) > 0:
            obj_parts.append(f"{inhibs} inhibidor")
        lines.append(f"Objetivos: {' | '.join(obj_parts)}")

        # --- Deaths line ---
        dead = cls._fmt(metrics.get("totalTimeSpentDead"), 0)
        streak = cls._fmt(metrics.get("longestTimeSpentLiving"), 0)
        lines.append(f"Muertes: {dead}s muerto en total | max streak vivo: {streak}s")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  Prompt builder
    # ------------------------------------------------------------------

    def build_prompt(self,
                     player_report: Dict,
                     role: str = "coach",
                     meta: Optional[Dict] = None,
                     passages: Optional[List[str]] = None,
                     language: str = "es",
                     output_format: str = "text",
                     game_summary: Optional[str] = None,
                     important_points: Optional[List[str]] = None,
                     match_snapshot: Optional[str] = None,
                     history: Optional[List[Dict]] = None) -> str:
        """Compose a coaching prompt with structured stats.

        Args:
            player_report: dict with player info and 'metrics' sub-dict.
            role: one of Top, Jungle, Mid, Bot, Support, or 'coach'.
            meta: optional extra context (ignored for now).
            passages: optional context passages from retrieval.
            language: response language (default 'es').
            output_format: 'text' for plain paragraph, 'json' for structured JSON.
            game_summary: optional short game-level description.
            important_points: optional list of bullet-point highlights.
            match_snapshot: optional multi-line snapshot of all players in the match.
            history: optional list of {"role", "content"} turns; last 6 used.

        Returns:
            A single string with the composed prompt.
        """
        # Build the structured stats block from the report
        stats_block = self.format_report_stats(player_report)

        system = self.system_template
        guidance = self.role_guidance.get(role, self.role_guidance["coach"])

        user = self.user_template.format(
            stats_block=stats_block,
            role_guidance=guidance,
        )

        # ----- optional sections -----
        passage_section = ""
        if passages:
            passage_section = "\nCONTEXT PASSAGES:\n" + "\n".join(f"- {p}" for p in passages[:8]) + "\n"

        game_section = ""
        if game_summary:
            game_section += "\nGAME SUMMARY: " + game_summary.strip() + "\n"
        if important_points:
            pts = important_points[:6]
            game_section += "IMPORTANT POINTS:\n" + "\n".join(f"- {p.strip()}" for p in pts) + "\n"

        # ----- optional multi-turn / snapshot context -----
        context = build_chat_context(match_snapshot, history)

        # ----- language instruction -----
        lang_instruction = ""
        if language:
            if language.lower() in ("es", "español", "castellano", "spanish"):
                lang_instruction = "Por favor, responde exclusivamente en castellano.\n\n"
            else:
                lang_instruction = f"Please respond in {language}.\n\n"

        # ----- output format instruction -----
        text_instruction = (
            "IMPORTANTE: Responde con 2-4 párrafos cortos en español. "
            "Primero un breve análisis del rendimiento, luego lista "
            "exactamente 3 puntos de mejora con consejos específicos "
            "para cada uno. Sé concreto y accionable."
        )

        json_instruction = """
IMPORTANT: Respond with a JSON object only, enclosed in triple backticks ```.
The JSON MUST contain the following keys:
 - areas_of_improvement: an array of 3 short strings (specific improvement points)
 - exercises: an array of 3 short strings (practical exercises/drills for each point)
 - strengths: an array of short strings
 - summary: a short 1-2 sentence summary string
Example:
```
{"areas_of_improvement": ["..."], "exercises": ["..."], "strengths": ["..."], "summary": "..."}
```
"""

        chosen_instruction = text_instruction if output_format == "text" else json_instruction

        # ----- assemble -----
        return (
            f"SYSTEM: {system}\n\n"
            f"USER: {user}"
            f"{game_section}"
            f"{context}"
            f"{passage_section}"
            f"{lang_instruction}"
            f"{chosen_instruction}"
        )
