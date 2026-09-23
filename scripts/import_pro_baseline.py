"""Import an Oracle's Elixir CSV into a pro-player role baseline.

Download the CSV manually from https://oracleselixir.com/tools/downloads (or
pass ``--url`` to fetch it) and compute a per-role baseline that the coaching
reports compare players against.

Usage:
  python scripts/import_pro_baseline.py --csv 2025_LoL_esports_match_data.csv --position sup --year 2025
  python scripts/import_pro_baseline.py --url <csv-url> --position sup --league LCK --league LPL

The baseline is always written to ``config/pro_baseline.json`` and, best-effort,
persisted to the ``pro_baselines`` MongoDB collection. A missing Mongo is not
fatal.
"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure repository root is on sys.path so local `modules.*` imports resolve.
load_dotenv()
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.data.pro_baseline import (  # noqa: E402
    DEFAULT_JSON_PATH,
    canonical_position,
    compute_baseline,
    iter_metric_rows,
    save_baseline,
)
from modules.logger import get_logger  # noqa: E402

logger = get_logger()
CACHE_DIR = Path("cache")


def _download(url: str, cache_dir: Path = CACHE_DIR) -> Path:
    """Download *url* into the cache dir, reusing a non-empty cached file."""
    import httpx

    cache_dir.mkdir(parents=True, exist_ok=True)
    name = url.split("?")[0].rstrip("/").split("/")[-1] or "oracles_elixir.csv"
    dest = cache_dir / name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"Using cached file: {dest}")
        return dest

    print(f"Downloading {url} -> {dest}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return dest


def main():
    parser = argparse.ArgumentParser(
        description="Build a pro-player baseline from an Oracle's Elixir CSV.")
    parser.add_argument("--csv", help="Path to a local Oracle's Elixir CSV")
    parser.add_argument("--url", help="URL to download the CSV from (cached in cache/)")
    parser.add_argument("--position", default="sup",
                        help="OE position to filter (default: sup)")
    parser.add_argument("--league", action="append", default=None,
                        help="League filter, repeatable (e.g. LCK)")
    parser.add_argument("--year", action="append", type=int, default=None,
                        help="Year filter, repeatable (e.g. 2025)")
    parser.add_argument("--role", default=None,
                        help="Override the output role name (default: canonical position)")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_PATH),
                        help="JSON output path (default: config/pro_baseline.json)")
    args = parser.parse_args()

    if not args.csv and not args.url:
        print("error: provide --csv PATH or --url URL", file=sys.stderr)
        sys.exit(2)

    if args.csv:
        csv_path = Path(args.csv)
    else:
        csv_path = _download(args.url)
    if not csv_path.exists():
        print(f"error: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(2)

    role = args.role or canonical_position(args.position) or "Support"
    rows = iter_metric_rows(csv_path, position=args.position,
                            years=args.year, leagues=args.league)
    baseline = compute_baseline(rows, role=role)

    # Mongo persistence is best-effort: a missing driver or server must not
    # stop the JSON baseline from being written.
    persisted = False
    try:
        from modules.db.connection import get_db
        persisted = save_baseline(get_db(), baseline)
    except Exception as exc:
        logger.warning("Mongo persist skipped: %s", exc)

    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(baseline, fh, ensure_ascii=False, indent=2)

    metrics = baseline["metrics"]
    print(f"Role: {role} | games: {baseline['games']} | metrics: {len(metrics)}")
    print(f"JSON written: {out}")
    print(f"Mongo persist: {'ok' if persisted else 'skipped'}")

    if metrics:
        ranked = sorted(metrics.items(), key=lambda kv: kv[1]["mean"], reverse=True)
        print("Top metrics by mean:")
        for key, value in ranked[:3]:
            print(f"  {key}: {value['mean']}")
        print("Bottom metrics by mean:")
        for key, value in ranked[-3:]:
            print(f"  {key}: {value['mean']}")


if __name__ == "__main__":
    main()
