"""Small PromptEngineer that builds prompts for coaching/advice tasks.

This module contains templates and a small helper to interpolate a player's
report into a context-rich prompt. Templates are intentionally small; they show
placeholders and explanation in the docstrings.

Placeholders used in templates:
- {role}  : the advisor role (e.g. 'coach')
- {player_name} : player's display name if available
- {report_summary} : a short summary of the player's report
"""
from typing import Dict, Optional, List
import os


class PromptEngineer:
    """Builds prompts for the LLM to produce coaching-style advice.

    Example usage:
        pe = PromptEngineer()
        prompt = pe.build_prompt({'name': 'Alice', 'notes': 'missed two catches'}, role='coach')

    The system_template and user_template are intentionally small; they're the
    starting point for more sophisticated prompt engineering later.
    """

    # base system instruction — role gets interpolated
    system_template = (
        "You are a helpful {role} who provides concise, actionable coaching "
        "and a short summary. Be positive and specific."
    )

    # role-specific guidance for common MOBA roles
    role_guidance = {
        "Top": "Focus on lane control, wave management, and trading patterns.",
        "Jungle": "Focus on pathing, objective timing, gank windows, and vision control.",
        "Mid": "Focus on roaming, wave manipulation, trading, and matchup awareness.",
        "Bot": "Focus on CS, trading with support, positioning in lane and teamfights.",
        "Support": "Focus on vision, roaming, peeling, engage/disengage calls, and warding.",
        # generic fallback
        "coach": "Provide general coaching: concrete drills, areas to improve, and quick wins."
    }

    user_template = (
        "Player: {player_name}\n"
        "Report: {report_summary}\n"
        "Role Guidance: {role_guidance}\n"
        "Provide concrete advice, next steps, and a 1-2 sentence summary."
    )

    def build_prompt(self, player_report: Dict, role: str = "coach", meta: Optional[Dict] = None, passages: Optional[List[str]] = None) -> str:
        """Compose a richer prompt for the LLM.

        The prompt includes:
          - a short system instruction tailored to the role
          - the player's report summary
          - role-specific guidance
          - an explicit instruction to respond with a JSON payload inside
            triple backticks (```), containing the keys:
                areas_of_improvement (list of strings)
                exercises (list of strings)
                strengths (list of strings)
                summary (short string)

        Args:
            player_report: dict containing at least `name` or `summary`/`notes`.
            role: one of Top, Jungle, Mid, Bot, Support, or 'coach'.
            meta: optional dict with extra context (ignored for now)

        Returns:
            A single string with the composed prompt.
        """
        name = player_report.get("name") or player_report.get("player_name") or player_report.get("puuid") or "Player"
        summary = player_report.get("summary") or player_report.get("notes") or "Compact report: games_analyzed=%s" % player_report.get("games_analyzed") if isinstance(player_report, dict) else str(player_report)

        system = self.system_template.format(role=role)
        guidance = self.role_guidance.get(role, self.role_guidance["coach"]) if role else self.role_guidance["coach"]

        user = self.user_template.format(player_name=name, report_summary=summary, role_guidance=guidance)

        json_instruction = """

IMPORTANT: Respond with a JSON object only, enclosed in triple backticks ```
The JSON MUST contain the following keys:
 - areas_of_improvement: an array of short strings
 - exercises: an array of short strings (practical exercises or drills)
 - strengths: an array of short strings
 - summary: a short 1-2 sentence summary string
Place only the JSON between the backticks. Example:
```
{"areas_of_improvement": ["..."], "exercises": ["..."], "strengths": ["..."], "summary": "..."}
```
"""

        # combine into a single prompt string. If passages are provided, include them
        passage_section = ""
        if passages:
            passage_section = "\nCONTEXT PASSAGES:\n" + "\n".join([f"- {p}" for p in passages[:8]]) + "\n"

        # include a compact summary line
        compact = f"\nCOMPACT SUMMARY: Player={name} Games={player_report.get('games_analyzed', 'N/A')}\n"

        return f"SYSTEM: {system}\n\nUSER: {user}{passage_section}{compact}{json_instruction}"
