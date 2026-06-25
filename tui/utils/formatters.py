"""Formatting helpers for displaying LoL data in the TUI."""


def format_kda(kills: float, deaths: float, assists: float) -> str:
    """Format KDA as a compact string: 5.1 (5/2/8)."""
    kda_ratio = (kills + assists) / max(deaths, 1)
    return f"{kda_ratio:.1f} ({int(kills)}/{int(deaths)}/{int(assists)})"


def format_gpm(gpm: float) -> str:
    return f"{gpm:.0f}"


def format_cs_per_min(cs: float, duration_seconds: float) -> str:
    mins = max(duration_seconds / 60, 1)
    return f"{cs / mins:.1f}"


def format_winrate(wins: int, total: int) -> str:
    if total == 0:
        return "—"
    pct = (wins / total) * 100
    return f"{pct:.0f}%"


def format_duration(seconds: int) -> str:
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"


def format_kda_ratio(kills: float, deaths: float, assists: float) -> float:
    """Return the raw KDA ratio number."""
    return round((kills + assists) / max(deaths, 1), 2)


def shorten_name(riotid: str, max_len: int = 10) -> str:
    """Shorten a RiotID for table display; keep the tag visible."""
    if "#" in riotid:
        name, tag = riotid.rsplit("#", 1)
        if len(riotid) <= max_len + 3:
            return riotid
        return f"{name[:max_len]}..#{tag}"
    return riotid[:max_len]
