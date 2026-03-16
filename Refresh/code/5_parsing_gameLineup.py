import os
import pandas as pd
import numpy as np
import re
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime

# Constants — auto-detect current NBA season
def _get_current_season():
    from datetime import datetime
    now = datetime.now()
    return now.year if now.month <= 6 else now.year + 1

_current = _get_current_season()
YEARS = [str(_current - 1), str(_current)]
BASE_DIR = "Refresh/data/parsed_csvs/gameLineup_csv"
SCORES_DIR_TEMPLATE = "Refresh/data/scrapped_htmls/boxscore_stats/{year}/scores"
PARSED_FILES_TRACKER = f"{BASE_DIR}/parsed_files.txt"
LINEUP_CSV_TEMPLATE = f"{BASE_DIR}/gameLineup_{{}}.csv"

def load_parsed_files():
    """Load parsed files with timestamps from the tracker."""
    parsed_files = {}
    if os.path.exists(PARSED_FILES_TRACKER):
        with open(PARSED_FILES_TRACKER, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    file_path, timestamp = parts
                    parsed_files[file_path] = float(timestamp)
    return parsed_files

def save_parsed_file(file_path):
    """Save a parsed file with timestamp to the tracker."""
    current_time = datetime.now().timestamp()
    os.makedirs(os.path.dirname(PARSED_FILES_TRACKER), exist_ok=True)
    with open(PARSED_FILES_TRACKER, "a") as f:
        f.write(f"{file_path},{current_time}\n")

def should_parse_file(file_path, parsed_files):
    """Determine if a file should be parsed based on modification time."""
    if not os.path.exists(file_path):
        return False
    
    current_mtime = os.path.getmtime(file_path)
    
    # If file hasn't been parsed before or has been modified
    if file_path not in parsed_files:
        return True
    
    return current_mtime > parsed_files[file_path]

def parse_html(box_score_path):
    """Parse the HTML file and return a BeautifulSoup object."""
    with open(box_score_path, encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, features="lxml")
    [s.decompose() for s in soup.select("tr.over_header")]
    [s.decompose() for s in soup.select("tr.thead")]
    
    return soup

def read_line_score(soup):
    """Extract the team names and total points."""
    line_score = pd.DataFrame(columns=["team", "total"])
    
    try:
        line_score = pd.read_html(StringIO(str(soup)), attrs={'id': 'line_score'})[0]
        cols = list(line_score.columns)
        cols[0] = "team"
        cols[-1] = "total"
        line_score.columns = cols
        line_score = line_score[["team", "total"]]
    except ValueError as e:
        if "No tables found" not in str(e):
            raise e

    if line_score.empty:
        line_score = extract_teams_and_scores(soup)
    
    return line_score

def extract_teams_and_scores(soup):
    """Extract team names and points when line score table is not found."""
    team_elements = soup.select("span > strong")
    teams = [element.text.strip() for element in team_elements if element.text.strip()]
    
    tfoot_elements = soup.find_all("tfoot")
    pts_elements = []
    for i in range(len(tfoot_elements)):
        if i == 0 or i == 8:
            last_row = tfoot_elements[i].find("tr")
            pts_element = last_row.find("td", {"class": "right", "data-stat": "pts"})
            pts_elements.append(int(pts_element.text) if pts_element else np.nan)

    return pd.DataFrame({"team": teams, "total": pts_elements})

def read_stats(soup, team, stat):
    """Extract and clean player stats for a given team."""
    try:
        df = pd.read_html(StringIO(str(soup)), attrs={'id': f'box-{team}-game-{stat}'}, index_col=0)[0]
        df = df[~df.index.str.contains('Reserves')]

        df.reset_index(inplace=True)
        df.index = range(len(df))
        
        df = df[:-1]  # Omit the last row

        df['MP'] = df['MP'].replace(r'^(\D*)$', np.nan, regex=True)
        df['MP'] = pd.to_datetime(df['MP'], format='%M:%S', errors='coerce').dt.minute
        df = df[df['MP'] > 0]
        
        return df
    except Exception as e:
        print(f"Error reading stats for team {team}: {str(e)}")
        return None

def load_existing_data(year):
    """Load existing lineup data if available."""
    csv_path = LINEUP_CSV_TEMPLATE.format(year)
    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except Exception as e:
            print(f"Error loading existing data: {str(e)}")
    return None

def process_box_scores(year):
    """Process box scores for a given year."""
    score_dir = SCORES_DIR_TEMPLATE.format(year=year)
    parsed_files = load_parsed_files()
    
    new_game_data = []
    files_processed = 0
    
    box_scores = [os.path.join(score_dir, f) for f in os.listdir(score_dir) if f.endswith(".html")]
    
    # Filter files that need processing
    files_to_process = [bs for bs in box_scores if should_parse_file(bs, parsed_files)]
    
    if not files_to_process:
        print(f"No new or modified files to process for year {year}")
        return None

    print(f"Found {len(files_to_process)} new or modified files to process for year {year}")
    
    for box_score_path in files_to_process:
        try:
            game_date = os.path.basename(box_score_path)[:8]
            soup = parse_html(box_score_path)
            line_score = read_line_score(soup)
            teams = list(line_score["team"])

            for team in teams:
                basic = read_stats(soup, team, "basic")
                if basic is not None:
                    players = basic.iloc[:, 0].values.flatten()
                    game_data = {
                        'Date': game_date,
                        'Team': team,
                        'Season': year
                    }
                    for i, player in enumerate(players, 1):
                        game_data[f'Player {i}'] = player
                    new_game_data.append(game_data)

            save_parsed_file(box_score_path)
            files_processed += 1
            
            if files_processed % 10 == 0:
                print(f"Processed {files_processed} / {len(files_to_process)} files")
                
        except Exception as e:
            print(f"Error processing {box_score_path}: {str(e)}")
            continue

    if new_game_data:
        return pd.DataFrame(new_game_data)
    return None

def combine_and_save_data(new_df, year):
    """Combine new data with existing data and save."""
    if new_df is None or new_df.empty:
        print("No new data to save")
        return

    existing_df = load_existing_data(year)
    
    if existing_df is not None and not existing_df.empty:
        # Remove existing entries for games being updated
        existing_df['Date'] = existing_df['Date'].astype(str)
        new_df['Date'] = new_df['Date'].astype(str)
        
        existing_dates = set(existing_df['Date'].unique())
        new_dates = set(new_df['Date'].unique())
        
        # Keep only rows from existing data that aren't being updated
        existing_df = existing_df[~existing_df['Date'].isin(new_dates)]
        
        # Combine data
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Sort by date
        combined_df = combined_df.sort_values(['Date', 'Team']).reset_index(drop=True)
    else:
        combined_df = new_df

    # Save the combined data
    csv_path = LINEUP_CSV_TEMPLATE.format(year)
    combined_df.to_csv(csv_path, index=False)
    print(f"\nSuccessfully updated data for {year}:")
    print(f"- {len(new_df)} new or updated game lineups")
    print(f"- {len(combined_df)} total game lineups in dataset")

def main():
    os.makedirs(BASE_DIR, exist_ok=True)
    
    for year in YEARS:
        print(f"\nProcessing year {year}...")
        new_data = process_box_scores(year)
        combine_and_save_data(new_data, year)

if __name__ == "__main__":
    main()