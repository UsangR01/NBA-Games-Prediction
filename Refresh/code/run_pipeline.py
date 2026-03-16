"""
NBA Pipeline Orchestrator
=========================
Runs the full Refresh/code pipeline in order.

Usage
-----
    # Parse, prepare, feature-engineer, and update next-game info (default)
    python Refresh/code/run_pipeline.py

    # Also scrape fresh HTML first (slow — Playwright required)
    python Refresh/code/run_pipeline.py --with-scraping

    # Only refresh schedule + injury data and re-run downstream steps
    python Refresh/code/run_pipeline.py --refresh-only

    # Run everything including ML model training at the end
    python Refresh/code/run_pipeline.py --with-ml

Flags can be combined, e.g.:
    python Refresh/code/run_pipeline.py --with-scraping --with-ml
"""

import argparse
import subprocess
import sys
import os
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Resolve paths relative to this file so the script works from any CWD
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))   # sandbox/
REFRESH_CODE = SCRIPT_DIR                                   # sandbox/Refresh/code/

def _script(name):
    return os.path.join(REFRESH_CODE, name)


# ---------------------------------------------------------------------------
# Pipeline stage definitions
# ---------------------------------------------------------------------------
SCRAPING_STAGES = [
    ("Scrape game box scores",   [_script("1_scraping_gamesStats.py"), "--once"]),
    ("Scrape player stats",      [_script("2_scraping_playerStats.py"), "--once"]),
]

PARSE_STAGES = [
    ("Parse game stats",         _script("3_parsing_gameStats.py")),
    ("Parse player stats",       _script("4_parsing_playerStats.py")),
    ("Parse game lineups",       _script("5_parsing_gameLineup.py")),
    ("Parse schedule HTML",      _script("8_parsing_schedules.py")),
]

INJURY_STAGE = [
    ("Scrape injury updates",    _script("9_injury_updates_bb-ref-dot-com.py")),
]

PREP_STAGES = [
    ("Data preparation (merge game + player + lineup)",  _script("6_data_preparation.py")),
    ("Schedule & lineup prep (next-game info)",          _script("10_schedules_data_prep.py")),
    ("Feature engineering",                              _script("7_feature_engineering.py")),
]

ML_STAGE = [
    ("Model training & evaluation",  _script("12_model_training.py")),
]


# ---------------------------------------------------------------------------
# Runner helpers
# ---------------------------------------------------------------------------
def _timestamp():
    return datetime.now().strftime("%H:%M:%S")


def _log(msg, level="INFO"):
    print(f"[{_timestamp()}] [{level}] {msg}", flush=True)


def run_stage(label, script_path):
    """Run a single Python script as a subprocess. Aborts pipeline on failure.
    script_path may be a str or a list [path, arg1, arg2, ...]."""
    _log(f"START  {label}")
    start = time.time()

    cmd = [sys.executable] + (script_path if isinstance(script_path, list) else [script_path])
    result = subprocess.run(
        cmd,
        cwd=ROOT_DIR,         # all scripts use paths relative to the sandbox root
    )

    elapsed = time.time() - start
    if result.returncode != 0:
        _log(f"FAILED {label}  (exit {result.returncode}, {elapsed:.1f}s)", level="ERROR")
        sys.exit(result.returncode)

    _log(f"DONE   {label}  ({elapsed:.1f}s)")


def run_stages(stages):
    for label, path in stages:
        run_stage(label, path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="NBA data pipeline orchestrator")
    parser.add_argument(
        "--with-scraping",
        action="store_true",
        help="Also run scraping scripts (1, 2) before parsing. Requires Playwright.",
    )
    parser.add_argument(
        "--refresh-only",
        action="store_true",
        help="Only refresh injuries + schedule then re-run prep/feature-engineering. "
             "Skips all scraping and parsing of game/player/lineup HTML.",
    )
    parser.add_argument(
        "--with-ml",
        action="store_true",
        help="Run model training and evaluation (12_model_training.py) at the end.",
    )
    args = parser.parse_args()

    pipeline_start = time.time()
    _log("=" * 60)
    _log("NBA PIPELINE START")
    _log("=" * 60)

    if args.refresh_only:
        _log("Mode: refresh-only (injuries → schedule prep → feature engineering)")
        run_stages(INJURY_STAGE)
        run_stages(PREP_STAGES)
    else:
        if args.with_scraping:
            _log("Mode: full pipeline WITH scraping")
            run_stages(SCRAPING_STAGES)
        else:
            _log("Mode: parse -> prep -> feature engineering (use --with-scraping to also scrape)")

        run_stages(PARSE_STAGES)
        run_stages(INJURY_STAGE)
        run_stages(PREP_STAGES)

    if args.with_ml:
        run_stages(ML_STAGE)

    elapsed = time.time() - pipeline_start
    _log("=" * 60)
    _log(f"NBA PIPELINE COMPLETE  (total {elapsed:.1f}s)")
    _log("=" * 60)


if __name__ == "__main__":
    main()
