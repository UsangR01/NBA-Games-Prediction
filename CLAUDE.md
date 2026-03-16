# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NBA data pipeline for scraping, parsing, and feature-engineering game statistics (2014–present) from basketball-reference.com, producing ML-ready features for game outcome prediction.

## Directory Purpose

| Directory | Role |
|-----------|------|
| `code/` | Original 2014–2024 historical pipeline (procedural scripts, now stable/reference only) |
| `data/` | Output data from the `code/` pipeline |
| `Refresh/code/` | Rebuilt 2025 pipeline — scrapes new data, combines with 2014–2024 history, and keeps everything up to date. **This is the active codebase.** |
| `Refresh/data/` | Output data from the `Refresh/code/` pipeline |

`Refresh/code/` scripts are OOP-style rewrites of the originals (`DataPreprocessor`, `NBAInjuryScraper`, `GameScheduleScraper` classes). When a script exists in both directories, prefer `Refresh/code/`.

## Running the Pipeline

### One-command run (recommended)

```bash
# Parse, prepare, feature-engineer, update injuries & schedule (no scraping)
python Refresh/code/run_pipeline.py

# Also scrape fresh HTML first (slow, requires Playwright)
python Refresh/code/run_pipeline.py --with-scraping

# Only refresh injuries + schedule, then re-run downstream steps
python Refresh/code/run_pipeline.py --refresh-only

# Full pipeline + ML model training
python Refresh/code/run_pipeline.py --with-ml
```

### Manual step-by-step

```bash
# Stage 1 — Scraping (requires Playwright)
python Refresh/code/1_scraping_gamesStats.py     # scrapes box score HTML for 2025
python Refresh/code/2_scraping_playerStats.py    # scrapes player advanced stats HTML

# Stage 2 — Parsing
python Refresh/code/3_parsing_gameStats.py       # HTML → nba_games_2025.csv
python Refresh/code/4_parsing_playerStats.py     # HTML → playerStats_2025.csv
python Refresh/code/5_parsing_gameLineup.py      # HTML → gameLineup_2025.csv
python Refresh/code/8_parsing_schedules.py       # standings HTML → NBA_2025_games_schedule.csv

# Stage 3 — Injury Updates (uses requests, no Playwright needed)
python Refresh/code/9_injury_updates_bb-ref-dot-com.py  # → nba_injuries.csv + nba_injuries_processed.csv

# Stage 4 — Data Preparation & Feature Engineering
python Refresh/code/6_data_preparation.py        # merges 2025 game + player + lineup → fullGame_stats.csv
python Refresh/code/10_schedules_data_prep.py    # next-game schedule + healthy lineups
python Refresh/code/7_feature_engineering.py     # rolling stats, Elo, head-to-head → feature-engineered CSVs

# Stage 5 — ML Training
python Refresh/code/12_model_training.py         # train, compare, and save best model
```

Install dependencies:
```bash
pip install -r requirements.txt
playwright install  # required for scraping scripts 1 and 2 only
```

## Data Pipeline (ETL Flow)

```
basketball-reference.com
        ↓ (Playwright async scraping — scripts 1, 2)
Refresh/data/scrapped_htmls/
  ├── boxscore_stats/2025/scores/    ← per-game box score HTML
  ├── boxscore_stats/2025/standings/ ← schedule/standings HTML
  └── playerStats/                   ← advanced player stats HTML
        ↓ (BeautifulSoup parsing — scripts 3, 4, 5, 8)
Refresh/data/parsed_csvs/
  ├── scores_csv/         ← nba_games_2025.csv
  ├── playerStats_csv/    ← playerStats_2025.csv (PER, WS/48, TS%, etc.)
  ├── gameLineup_csv/     ← gameLineup_2025.csv
  └── gameSchedules_csv/  ← NBA_2025_games_schedule.csv
        ↓ (merge 2025 data with 2014–2024 history from data/)
        ↓ (pandas merge + aggregation — script 6)
Refresh/data/preprocessed_cleaned_csv/
  └── fullGame_stats.csv  ← merged game + top-5 player composite features
        ↓ (rolling windows, Elo, shooting % — script 7)
Refresh/data/feature_engineered_csv/
  ├── fullGame_without_nextGame_features.csv
  └── fullGame_with_nextGame_features.csv   ← ML-ready, includes prediction target
```

## Key Design Patterns

- **Parsed-file tracking**: parsing scripts log processed filenames to `parsed_files_*.txt` alongside their output CSVs to skip already-handled HTML on re-runs.
- **Top-player selection**: selects top 5 players per team per season by WS/48. Priority: MPG ≥ 26, then MPG 18–26, then rest of roster as fallback.
- **PER_Combined feature**: sum of PER values for the top-5 players who actually appeared in that game's lineup. This is the primary player-quality feature.
- **Elo ratings**: maintained chronologically across the full dataset (K=32, initial=1500); ratings carry over between seasons.
- **ML target column**: `target` = `won` shifted by −1 per team (outcome of the *next* game). Set to `2` for a team's final game of the season (no next game).
- **Team code normalization**: Charlotte Hornets scrape as `CHO`, normalized to `CHA` in preprocessing.
- **Season targeting**: scraping scripts default to 2025. Change the `year` variable near the top of each scraping script to target other seasons.

## Important Files

| File | Purpose |
|------|---------|
| `Refresh/code/3_parsing_gameStats.py` | Core parser — each row is one team's view of a game; opponent stats are mirrored as `_opp` columns |
| `Refresh/code/6_data_preparation.py` | Joins game stats + lineups + player stats; computes `PER_Combined` |
| `Refresh/code/7_feature_engineering.py` | Final transformation before ML: rolling 4-game averages, Elo, head-to-head, rest days, next-game info |
| `Refresh/code/9_injury_updates_bb-ref-dot-com.py` | Scrapes injury table via `requests`; splits status/description fields |
| `data/parsed_csvs/scores_csv/nba_games_all.csv` | Full 2014–2024 historical game stats (~16 MB), used as base when combining with 2025 |

## TODO

- [x] Set up incremental pipeline (`run_pipeline.py`) — scrapes new data and syncs with 2014–2024 history.
- [x] Feature engineering runs automatically as part of each pipeline run.
- [x] Next-game info and player availability processed each run (scripts 10, 11).
- [x] ML model training script (`12_model_training.py`) — compares RidgeClassifier, LogisticRegression, RandomForest, GradientBoosting using TimeSeriesSplit; saves best model.
- [x] Cleaned up duplicate code: `11_updating_nextGame_info.py` now delegates to `6_data_preparation.py`; hardcoded Windows path in `7_feature_engineering.py` replaced with dynamic `__file__`-relative path.
- [ ] Tune hyperparameters for the best model and re-evaluate.
