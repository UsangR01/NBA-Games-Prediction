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

# Stage 4 — Schedule / Injury Updates (in Refresh/code/)
python Refresh/code/9_injury_updates_bb-ref-dot-com.py
python Refresh/code/10_schedules_data_prep.py
python Refresh/code/11_updating_nextGame_info.py
```

Install dependencies:
```bash
pip install -r requirements.txt
playwright install  # required for async scraping scripts
```

## Code Architecture

### Two Code Directories

- `code/` — stable, numbered scripts (steps 1–7)
- `Refresh/code/` — updated/extended versions of the same scripts plus steps 9–11 (injury, schedule, next-game updates)

When a script exists in both directories, `Refresh/code/` is the more current version.

### Data Pipeline (ETL Flow)

```
basketball-reference.com
        ↓ (Playwright async scraping)
data/scrapped_htmls/
        ↓ (BeautifulSoup parsing)
data/parsed_csvs/
  ├── scores_csv/         ← game box scores
  ├── playerStats_csv/    ← advanced player stats (PER, WS/48, TS%, etc.)
  └── gameLineup_csv/     ← which players appeared in each game
        ↓ (pandas merge + aggregation)
data/preprocessed_cleaned_csv/
  └── fullGame_stats.csv  ← merged game + top-5 player composite features
        ↓ (rolling windows, Elo, shooting %)
data/feature_engineered_csv/
  └── (ML-ready feature files)
```

### Key Design Patterns

- **Parsed-file tracking**: scripts log processed filenames with timestamps to avoid re-parsing already-handled HTML files. Look for `parsed_files_*.txt` alongside output CSVs.
- **Running / cumulative files**: each stage maintains a `*_running.csv` that appends new data to the full historical dataset (2014–present). Per-season files are also written.
- **Top-player composite features**: `6_data_preparation.py` ranks the top 5 players per team per game by WS/48 and creates "Big 3"–"Big 5" PER composite columns.
- **Elo ratings**: `7_feature_engineering.py` maintains team Elo (K=32, initial=1500) across the full historical dataset; ratings carry over between seasons.
- **Season targeting**: scraping scripts default to the 2025 season. To target other seasons, change the year variable near the top of each scraping script.

### Important Files

| File | Purpose |
|------|---------|
| `code/3_parsing_gameStats.py` | Core parser — produces the primary game stats CSV used by all downstream steps |
| `code/6_data_preparation.py` | Joins all three parsed datasets; creates top-player composite features |
| `code/7_feature_engineering.py` | Last transformation step before ML; rolling averages, Elo, cumulative stats |
| `nba_injuries.csv` (root) | Current injury report (player, team, status, description) |
| `data/parsed_csvs/scores_csv/nba_games_all.csv` | Full historical game stats (2014–2025, ~16 MB) |
