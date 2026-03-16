import os
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime

pd.set_option('display.max_columns', None)

# Constants
BASE_DIR = "data/scrapped_htmls/boxscore_stats"
OUTPUT_DIR = "data/parsed_csvs/scores_csv"
PARSED_FILES_LOG = os.path.join(OUTPUT_DIR, "parsed_files_all.txt")
FINAL_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "nba_games_all.csv")

# ---------------- Helper Functions ----------------

def load_parsed_files(log_path=PARSED_FILES_LOG):
    """Load the list of parsed files with timestamps from the log file."""
    parsed_files = {}
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    file_path, timestamp = parts
                    parsed_files[file_path] = float(timestamp)
    return parsed_files

def save_parsed_file(file_path, log_path=PARSED_FILES_LOG):
    """Save the parsed file name with timestamp to the log file."""
    current_time = datetime.now().timestamp()
    ensure_directory_exists(os.path.dirname(log_path))
    with open(log_path, "a") as f:
        f.write(f"{file_path},{current_time}\n")

def ensure_directory_exists(directory_path):
    """Ensure a directory exists, if not, create it."""
    os.makedirs(directory_path, exist_ok=True)

def load_existing_games():
    """Load existing combined games data if it exists."""
    if os.path.exists(FINAL_OUTPUT_FILE):
        return pd.read_csv(FINAL_OUTPUT_FILE, index_col=0)
    return None

def save_combined_games(games_df):
    """Save combined games data to CSV."""
    ensure_directory_exists(OUTPUT_DIR)
    games_df.to_csv(FINAL_OUTPUT_FILE)
    print(f"Saved combined data to {FINAL_OUTPUT_FILE}")

def should_parse_file(file_path, parsed_files):
    """Determine if a file should be parsed based on modification time."""
    if not os.path.exists(file_path):
        return False
    
    current_mtime = os.path.getmtime(file_path)
    
    # If file hasn't been parsed before or has been modified
    if file_path not in parsed_files:
        return True
    
    return current_mtime > parsed_files[file_path]

# ---------------- Parsing Functions ----------------

def parse_html(file_path):
    """Parse an HTML file and return a BeautifulSoup object."""
    with open(file_path, encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    [s.decompose() for s in soup.select("tr.over_header")]
    [s.decompose() for s in soup.select("tr.thead")]
    return soup

def read_season_info(soup):
    """Read and return the season info from the parsed HTML."""
    nav = soup.select("#bottom_nav_container")[0]
    hrefs = [a["href"] for a in nav.find_all('a')]
    season = os.path.basename(hrefs[1]).split("_")[0]
    return season

def read_line_score(soup):
    """Extract line score information from the parsed HTML."""
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
        pass

    if line_score.empty:
        teams, pts_elements = extract_missing_line_score_data(soup)
        line_score = pd.concat([line_score, pd.DataFrame({"team": teams, "total": pts_elements})], ignore_index=True)
        
    return line_score

def extract_missing_line_score_data(soup):
    """Extract missing line score data when the table is not found."""
    team_elements = soup.select("span > strong")
    teams = [element.text.strip() for element in team_elements if element.text.strip()]
    
    tfoot_elements = soup.find_all("tfoot")
    pts_elements = []
    for i in range(len(tfoot_elements)):
        if i == 0 or i == 8:
            last_row = tfoot_elements[i].find("tr")
            pts_element = last_row.find("td", {"class": "right", "data-stat": "pts"})
            pts_elements.append(int(pts_element.text) if pts_element else np.nan)
    
    return teams, pts_elements

def read_stats(soup, team, stat):
    """Read statistics data from the parsed HTML for a given team and stat."""
    df = pd.read_html(StringIO(str(soup)), attrs={'id': f'box-{team}-game-{stat}'}, index_col=0)[0]
    df = df.apply(pd.to_numeric, errors="coerce")
    return df

# ---------------- Game Data Handling ----------------

def create_team_summary(basic, advanced, base_cols=None):
    """Create a summary of team data using basic and advanced stats."""
    # Rename duplicate columns in basic stats
    basic_cols = basic.columns.tolist()
    if 'MP' in basic_cols:
        basic = basic.rename(columns={'MP': 'MP.1'})
    
    totals = pd.concat([basic.iloc[-1, :], advanced.iloc[-1, :]])
    totals.index = totals.index.str.lower()
    
    maxes = pd.concat([basic.iloc[:-1].max(), advanced.iloc[:-1].max()])
    maxes.index = maxes.index.str.lower() + "_max"
    
    # Rename duplicate max columns
    if 'mp_max' in maxes.index:
        maxes = maxes.rename({'mp_max': 'mp_max.1'})
    
    summary = pd.concat([totals, maxes])
    
    if base_cols is None:
        base_cols = list(summary.index.drop_duplicates(keep="first"))
        base_cols = [b for b in base_cols if "bpm" not in b]
    
    summary = summary[base_cols]
    return summary

def process_game_data(soup, base_cols=None):
    """Process the game data from the parsed HTML."""
    line_score = read_line_score(soup)
    teams = list(line_score["team"])
    
    summaries = []
    for team in teams:
        try:
            basic = read_stats(soup, team, "basic")
            advanced = read_stats(soup, team, "advanced")
            
            # Handle duplicate column names in basic stats
            if 'MP' in basic.columns:
                basic = basic.rename(columns={'MP': 'MP.1'})
            
            summary = create_team_summary(basic, advanced, base_cols)
            summaries.append(summary)
        except Exception as e:
            print(f"Error processing stats for team {team}: {str(e)}")
            raise
    
    # Ensure we have stats for both teams
    if len(summaries) != 2:
        raise ValueError(f"Expected stats for 2 teams, got {len(summaries)}")
    
    summary = pd.concat(summaries, axis=1).T
    
    # Ensure no duplicate column names
    summary.columns = pd.Index(summary.columns).drop_duplicates(keep='first')
    
    game = pd.concat([summary, line_score], axis=1)
    game["home"] = [0, 1]
    
    # Add missing columns with NA values
    for col in ['gmsc', 'mp.1']:
        if col not in game.columns:
            game[col] = pd.NA
    
    return game

def combine_game_data(game, soup, box_score):
    """
    Combine game data with opponent information and other metadata.
    Ensures consistent team ordering where home team is always second.
    """
    # Create opponent data with reversed order
    game_opp = game.iloc[::-1].reset_index()
    game_opp.columns += "_opp"
    
    # Get home/away status
    home_status = game['home'].tolist()
    
    # Reorder based on home/away status to ensure away team is first, home team second
    if home_status[0] == 1:  # If first team is home team
        game = game.iloc[::-1].reset_index(drop=True)  # Flip the order
        game_opp = game_opp.iloc[::-1].reset_index(drop=True)
        home_status = home_status[::-1]
    
    # Combine the data
    full_game = pd.concat([game, game_opp], axis=1)
    full_game["season"] = read_season_info(soup)
    full_game["date"] = os.path.basename(box_score)[:8]
    full_game["date"] = pd.to_datetime(full_game["date"], format="%Y%m%d")
    full_game["won"] = full_game["total"] > full_game["total_opp"]
    
    # Update home status after reordering
    full_game["home"] = home_status
    return full_game

def assign_column_headers(df):
    """
    Assign predefined column headers to the DataFrame with validation and error handling.
    """
    # First, fix any duplicate column names in the current DataFrame
    current_cols = df.columns.tolist()
    new_cols = []
    seen = set()
    
    for col in current_cols:
        if col in seen:
            if 'mp' in col.lower():
                if col.endswith('_opp'):
                    new_cols.append('mp_opp.1')
                else:
                    new_cols.append('mp.1')
            else:
                new_cols.append(f"{col}_1")
        else:
            new_cols.append(col)
            seen.add(col)
    
    df.columns = new_cols
    
    # Define expected columns
    column_headers = [
        'mp', 'mp.1', 'fg', 'fga', 'fg%', '3p', '3pa', '3p%', 'ft', 'fta', 'ft%', 'orb', 'drb', 'trb', 'ast',
        'stl', 'blk', 'tov', 'pf', 'pts', 'gmsc', '+/-', 'ts%', 'efg%', '3par', 'ftr', 'orb%', 'drb%', 'trb%',
        'ast%', 'stl%', 'blk%', 'tov%', 'usg%', 'ortg', 'drtg', 'mp_max', 'mp_max.1', 'fg_max', 'fga_max',
        'fg%_max', '3p_max', '3pa_max', '3p%_max', 'ft_max', 'fta_max', 'ft%_max', 'orb_max', 'drb_max', 'trb_max',
        'ast_max', 'stl_max', 'blk_max', 'tov_max', 'pf_max', 'pts_max', 'gmsc_max', '+/-_max', 'ts%_max',
        'efg%_max', '3par_max', 'ftr_max', 'orb%_max', 'drb%_max', 'trb%_max', 'ast%_max', 'stl%_max', 'blk%_max',
        'tov%_max', 'usg%_max', 'ortg_max', 'drtg_max', 'team', 'total', 'home', 'index_opp', 'mp_opp',
        'mp_opp.1', 'fg_opp', 'fga_opp', 'fg%_opp', '3p_opp', '3pa_opp', '3p%_opp', 'ft_opp', 'fta_opp',
        'ft%_opp', 'orb_opp', 'drb_opp', 'trb_opp', 'ast_opp', 'stl_opp', 'blk_opp', 'tov_opp', 'pf_opp',
        'pts_opp', 'gmsc_opp', '+/-_opp', 'ts%_opp', 'efg%_opp', '3par_opp', 'ftr_opp', 'orb%_opp', 'drb%_opp',
        'trb%_opp', 'ast%_opp', 'stl%_opp', 'blk%_opp', 'tov%_opp', 'usg%_opp', 'ortg_opp', 'drtg_opp',
        'mp_max_opp', 'mp_max_opp.1', 'fg_max_opp', 'fga_max_opp', 'fg%_max_opp', '3p_max_opp', '3pa_max_opp',
        '3p%_max_opp', 'ft_max_opp', 'fta_max_opp', 'ft%_max_opp', 'orb_max_opp', 'drb_max_opp', 'trb_max_opp',
        'ast_max_opp', 'stl_max_opp', 'blk_max_opp', 'tov_max_opp', 'pf_max_opp', 'pts_max_opp', 'gmsc_max_opp',
        '+/-_max_opp', 'ts%_max_opp', 'efg%_max_opp', '3par_max_opp', 'ftr_max_opp', 'orb%_max_opp', 'drb%_max_opp',
        'trb%_max_opp', 'ast%_max_opp', 'stl%_max_opp', 'blk%_max_opp', 'tov%_max_opp', 'usg%_max_opp',
        'ortg_max_opp', 'drtg_max_opp', 'team_opp', 'total_opp', 'home_opp', 'season', 'date', 'won'
    ]

    # Create a new DataFrame with all expected columns
    new_df = pd.DataFrame(index=df.index, columns=column_headers)
    
    # Copy data from old DataFrame to new one
    for col in df.columns:
        if col in column_headers:
            new_df[col] = df[col]
    
    # Fill missing columns with NA
    new_df = new_df.fillna(pd.NA)
    
    return new_df

def parse_multiple_seasons(start_year=2014, end_year=2024):
    """Parse HTML files for multiple seasons and combine into a single dataset."""
    parsed_files = load_parsed_files()
    all_games = []
    
    for year in range(start_year, end_year + 1):
        score_dir = os.path.join(BASE_DIR, str(year), "scores")
        
        if not os.path.exists(score_dir):
            print(f"Directory not found for year {year}, skipping...")
            continue
            
        print(f"\nProcessing season {year}...")
        ensure_directory_exists(OUTPUT_DIR)
        
        box_scores = [os.path.join(score_dir, f) for f in os.listdir(score_dir) if f.endswith(".html")]
        files_to_parse = [bs for bs in box_scores if should_parse_file(bs, parsed_files)]
        
        if not files_to_parse:
            print(f"No new or modified files to parse for season {year}")
            continue
            
        print(f"Found {len(files_to_parse)} files to parse for season {year}")
        
        season_games = []
        base_cols = None
        
        for box_score in files_to_parse:
            try:
                soup = parse_html(box_score)
                game = process_game_data(soup, base_cols)
                full_game = combine_game_data(game, soup, box_score)
                
                season_games.append(full_game)
                save_parsed_file(box_score)
                
                if len(season_games) % 10 == 0:
                    print(f"Processed {len(season_games)} / {len(files_to_parse)} games")
                    
            except Exception as e:
                print(f"Error processing {box_score}: {str(e)}")
                continue
        
        if season_games:
            # Combine season games
            season_games_df = pd.concat(season_games, ignore_index=True)
            season_games_df = assign_column_headers(season_games_df)
            
            # Add to all games
            all_games.append(season_games_df)
            
            print(f"Successfully processed season {year}:")
            print(f"- {len(season_games)} games added")
        else:
            print(f"No new games to add for season {year}")
    
    if all_games:
        # Combine all seasons
        all_games_df = pd.concat(all_games, ignore_index=True)
        
        # Load existing data if any
        existing_games = load_existing_games()
        if existing_games is not None:
            # Remove any existing games with the same dates as new games
            existing_dates = pd.to_datetime(existing_games['date'])
            new_dates = pd.to_datetime(all_games_df['date'])
            existing_games = existing_games[~existing_dates.isin(new_dates)]
            
            # Combine with existing games
            all_games_df = pd.concat([existing_games, all_games_df], ignore_index=True)
        
        # Sort by date and ensure proper team ordering
        all_games_df['date'] = pd.to_datetime(all_games_df['date'])
        
        # Create a game identifier to keep pairs together
        all_games_df['game_id'] = (all_games_df.index // 2).astype(int)
        
        # Sort by date and game_id to keep teams from same game together
        all_games_df = all_games_df.sort_values(['date', 'game_id', 'home'])
        
        # Drop the temporary game_id column
        all_games_df = all_games_df.drop('game_id', axis=1).reset_index(drop=True)
        
        # Save the combined games data
        save_combined_games(all_games_df)
        print(f"\nFinal dataset statistics:")
        print(f"- Total games: {len(all_games_df) // 2}")
        print(f"- Date range: {all_games_df['date'].min().date()} to {all_games_df['date'].max().date()}")
    else:
        print("\nNo new games to add to the dataset")

if __name__ == "__main__":
    print("Starting NBA game data processing...")
    parse_multiple_seasons(2014, 2024)
    print("Processing complete!")