import os
import pandas as pd
import numpy as np
import re
from bs4 import BeautifulSoup
from io import StringIO  # Import StringIO

# Constants
YEARS = ["2025"]
GAME_LINEUP_CSV_DIR = "data/parsed_csvs/gameLineup_csv"
SCORES_DIR_TEMPLATE = "data/scrapped_htmls/boxscore_stats/{year}/scores"
PARSED_FILES_TRACKER = "data/parsed_csvs/gameLineup_csv/parsed_files.txt"

def parse_html(box_score_path):
    """
    Parse the HTML file and return a BeautifulSoup object after cleaning up unwanted elements.
    
    Args:
        box_score_path (str): Path to the HTML file.
    
    Returns:
        BeautifulSoup: Parsed HTML soup.
    """
    with open(box_score_path, encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, features="lxml")  # Specify the parser
    [s.decompose() for s in soup.select("tr.over_header")]
    [s.decompose() for s in soup.select("tr.thead")]
    
    return soup

def is_parsed(file_path):
    """Check if the file has already been parsed."""
    if os.path.exists(PARSED_FILES_TRACKER):
        with open(PARSED_FILES_TRACKER, 'r') as f:
            parsed_files = f.read().splitlines()
        return file_path in parsed_files
    return False

def mark_as_parsed(file_path):
    """Mark the file as parsed by appending it to the tracker."""
    with open(PARSED_FILES_TRACKER, 'a') as f:
        f.write(file_path + '\n')

def read_season_info(soup):
    """Extract the season year from the HTML soup."""
    nav = soup.select("#bottom_nav_container")[0]
    hrefs = [a["href"] for a in nav.find_all('a')]
    season = os.path.basename(hrefs[1]).split("_")[0]
    
    return season

def read_line_score(soup):
    """Extract the team names and total points from the line score section of the HTML."""
    line_score = pd.DataFrame(columns=["team", "total"])
    
    try:
        line_score = pd.read_html(StringIO(str(soup)), attrs={'id': 'line_score'})[0]  # Wrap in StringIO
        cols = list(line_score.columns)
        cols[0] = "team"
        cols[-1] = "total"
        line_score.columns = cols
        line_score = line_score[["team", "total"]]
    except ValueError as e:
        if "No tables found" not in str(e):
            raise e

    if line_score.empty:
        # Manually extract teams and scores if table is absent
        line_score = extract_teams_and_scores(soup)
    
    return line_score

def extract_teams_and_scores(soup):
    """Extract team names and points when line score table is not found."""
    team_elements = soup.select("span > strong")
    teams = [element.text.strip() for element in team_elements if element.text.strip()]
    
    # Extract points from the first and ninth 'tfoot' elements
    tfoot_elements = soup.find_all("tfoot")
    pts_elements = []
    for i in range(len(tfoot_elements)):
        if i == 0 or i == 8:
            last_row = tfoot_elements[i].find("tr")
            pts_element = last_row.find("td", {"class": "right", "data-stat": "pts"})
            pts_elements.append(int(pts_element.text) if pts_element else np.nan)

    return pd.DataFrame({"team": teams, "total": pts_elements})

def read_stats(soup, team, stat):
    """Extract and clean player stats for a given team from the HTML."""
    df = pd.read_html(StringIO(str(soup)), attrs={'id': f'box-{team}-game-{stat}'}, index_col=0)[0]  # Wrap in StringIO
    df = df[~df.index.str.contains('Reserves')]

    df.reset_index(inplace=True)
    df.index = range(len(df))
    
    # Omit the last row (summary or footer)
    df = df[:-1]

    # Clean the 'MP' (minutes played) column
    df['MP'] = df['MP'].replace(r'^(\D*)$', np.nan, regex=True)
    df['MP'] = pd.to_datetime(df['MP'], format='%M:%S', errors='coerce').dt.minute
    df = df[df['MP'] > 0]  # Only keep rows where minutes played > 0
    
    return df

def process_box_scores(year):
    """Process box scores for a given year by extracting team and player data."""
    score_dir = SCORES_DIR_TEMPLATE.format(year=year)
    box_scores = [os.path.join(score_dir, f) for f in os.listdir(score_dir) if f.endswith(".html")]
    
    players_list, team_names, season_years = [], [], []
    
    for box_score_path in box_scores:
        if is_parsed(box_score_path):
            continue  # Skip if already parsed

        season_year = re.findall(r"\d{4}", score_dir)[0]
        soup = parse_html(box_score_path)
        
        line_score = read_line_score(soup)
        teams = list(line_score["team"])

        for team in teams:
            try:
                basic = read_stats(soup, team, "basic")
                players = basic.iloc[:, 0].values.flatten()  # Extract player names
                players_list.append(players)
                team_names.append(team)
                season_years.append(season_year)
            except IndexError:
                continue
        
        # Mark the file as parsed
        mark_as_parsed(box_score_path)
    
    # Create a DataFrame of players and team data
    players_df = pd.DataFrame(players_list)
    team_labels = [f"Player {i+1}" for i in range(len(players_df.columns))]
    players_df.columns = team_labels
    players_df.insert(0, "Team", team_names)
    players_df.insert(1, "Season Year", season_years)
    
    return players_df

def merge_with_existing_data(new_df, csv_file_path):
    """Merge the newly created player DataFrame with existing season data."""
    if os.path.exists(csv_file_path):
        seasons_df = pd.read_csv(csv_file_path, index_col=0)
        seasons_df.reset_index(drop=True, inplace=True)
        seasons_df.index += len(new_df)
        combined_df = pd.concat([new_df, seasons_df], ignore_index=True)
    else:
        combined_df = new_df
    
    return combined_df

def main():
    # Create the output directory if it doesn't exist
    os.makedirs(GAME_LINEUP_CSV_DIR, exist_ok=True)
    
    total_games = sum(len(os.listdir(SCORES_DIR_TEMPLATE.format(year=year))) for year in YEARS)
    progress = 0
    
    all_players_df = pd.DataFrame()
    
    for year in YEARS:
        players_df = process_box_scores(year)
        all_players_df = pd.concat([all_players_df, players_df], ignore_index=True)

        progress += len(players_df)
        if progress % 100 == 0:
            print(f"Progress: {progress} / {total_games}")
    
    # Merge with the existing lineup data
    final_df = merge_with_existing_data(all_players_df, os.path.join(GAME_LINEUP_CSV_DIR, "gameLineup.csv"))
    final_df.to_csv(os.path.join(GAME_LINEUP_CSV_DIR, "gameLineup_running.csv"))

if __name__ == "__main__":
    main()
