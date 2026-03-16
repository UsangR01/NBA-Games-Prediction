# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NBA data pipeline for scraping, parsing, and feature-engineering historical game statistics (2014–2025) from basketball-reference.com, with the goal of producing ML-ready features for game outcome prediction.

## Running Scripts

Scripts are numbered and must be run in order. Each stage depends on the output of the previous.

```bash
# Stage 1 — Scraping (requires Playwright)
python code/1_scraping_gamesStats.py      # scrapes box score HTML
python code/2_scraping_playerStats.py     # scrapes player advanced stats HTML

# Stage 2 — Parsing
python code/3_parsing_gameStats.py        # HTML → nba_games_<year>.csv + running combined
python code/4_parsing_playerStats.py      # HTML → playerStats CSVs
python code/5_parsing_gameLineup.py       # HTML → gameLineup_running.csv

# Stage 3 — Data Preparation & Feature Engineering
python code/6_data_preparation.py         # merges game + player + lineup data
python code/7_feature_engineering.py      # calculates rolling stats, Elo, shooting %

# Stage 4 — Schedule / Injury Updates (Refresh/code/ only, operates on Refresh/data/)
python Refresh/code/9_injury_updates_bb-ref-dot-com.py   # scrapes injury report (requests, not Playwright)
python Refresh/code/8_parsing_schedules.py               # parses standings HTML → schedule CSV
python Refresh/code/10_schedules_data_prep.py            # transforms player stats into team roster format
python Refresh/code/11_updating_nextGame_info.py         # merges schedule + injury data for next-game features
```

Install dependencies:
```bash
pip install -r requirements.txt
playwright install  # required for scraping scripts 1 and 2 only
```

## Code Architecture

### Two Code Directories, Two Data Directories

- `code/` + `data/` — full historical pipeline (2014–2025), used for initial build and training data
- `Refresh/code/` + `Refresh/data/` — current-season incremental updates; mirrors `code/` structure but writes to `Refresh/data/`

When a script exists in both directories, `Refresh/code/` is the more current version and uses an OOP style (`DataPreprocessor`, `NBAInjuryScraper`, `GameScheduleScraper` classes) vs. the procedural style in `code/`.

### Data Pipeline (ETL Flow)

```
basketball-reference.com
        ↓ (Playwright async scraping — scripts 1, 2)
data/scrapped_htmls/
  ├── boxscore_stats/<year>/scores/    ← per-game HTML
  ├── boxscore_stats/<year>/standings/ ← schedule/standings HTML
  └── playerStats/                     ← advanced player stats HTML
        ↓ (BeautifulSoup parsing — scripts 3, 4, 5, 8)
data/parsed_csvs/
  ├── scores_csv/         ← game box scores (nba_games_<year>.csv + nba_games_running.csv)
  ├── playerStats_csv/    ← advanced player stats (PER, WS/48, TS%, etc.)
  ├── gameLineup_csv/     ← which players appeared in each game
  └── gameSchedules_csv/  ← upcoming schedule (Refresh only)
        ↓ (pandas merge + aggregation — script 6)
data/preprocessed_cleaned_csv/
  └── fullGame_stats.csv  ← merged game + top-5 player composite features
        ↓ (rolling windows, Elo, shooting % — script 7)
data/feature_engineered_csv/
  ├── fullGame_without_nextGame_features.csv
  └── fullGame_with_nextGame_features.csv   ← ML-ready, includes prediction target
```

### Key Design Patterns

- **Parsed-file tracking**: each parsing script logs processed filenames to a `parsed_files_*.txt` file to skip already-handled HTML on re-runs.
- **Running / cumulative files**: `*_running.csv` files append new data to the full historical dataset. Per-season files (e.g. `nba_games_2025.csv`) are written separately.
- **Top-player selection**: `6_data_preparation.py` selects the top 5 players per team per season by WS/48. Priority order: MPG ≥ 26, then MPG 18–26, then rest of roster as fallback.
- **PER_Combined feature**: sum of PER values for the top players who actually appeared in that specific game (checked against the lineup). This is the key player-quality feature.
- **Elo ratings**: `7_feature_engineering.py` maintains team Elo (K=32, initial=1500) across the full dataset in chronological order; ratings persist across seasons.
- **ML target column**: the `target` column is `won` shifted by −1 per team (i.e., outcome of the *next* game), set to `2` for the last game of each team.
- **Team code normalization**: Charlotte Hornets scrape as `CHO` but are normalized to `CHA` during preprocessing.
- **Season targeting**: scraping scripts default to 2025. Change the `year` variable near the top of each script to target other seasons.

### Important Files

| File | Purpose |
|------|---------|
| `code/3_parsing_gameStats.py` | Core parser — produces the primary game stats CSV; each row is one team's view of a game with opponent stats mirrored as `_opp` columns |
| `code/6_data_preparation.py` | Joins game stats + lineups + player stats; computes `PER_Combined` and `Big1`–`Big5` flags |
| `code/7_feature_engineering.py` | Last transformation before ML: rolling 4-game averages, Elo, head-to-head stats, rest days, next-game info |
| `Refresh/code/9_injury_updates_bb-ref-dot-com.py` | Uses `requests` (not Playwright) to scrape injury table; outputs `nba_injuries.csv` and `nba_injuries_processed.csv` |
| `data/parsed_csvs/scores_csv/nba_games_all.csv` | Full historical game stats (2014–2025, ~16 MB) |
| `nba_injuries.csv` (root) | Current injury report (player, team, status, description) |
