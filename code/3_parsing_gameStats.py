import os
import pandas as pd
import numpy as np
pd.set_option('display.max_columns', None)

from bs4 import BeautifulSoup
from io import StringIO

# File to keep track of parsed files
PARSED_FILES_LOG = "data/parsed_csvs/scores_csv/parsed_files2025.txt"

# Load the list of parsed files from the log file
def load_parsed_files():
    if os.path.exists(PARSED_FILES_LOG):
        with open(PARSED_FILES_LOG, "r") as f:
            return set(line.strip() for line in f)
    return set()

# Save the parsed file name to the log file
def save_parsed_file(file_name):
    with open(PARSED_FILES_LOG, "a") as f:
        f.write(f"{file_name}\n")

# Maintain a set of parsed files
parsed_files = load_parsed_files()

"""
Defining functions for parsing
"""
def parse_html(box_score):
    with open(box_score, encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    [s.decompose() for s in soup.select("tr.over_header")]
    [s.decompose() for s in soup.select("tr.thead")]
    return soup

def read_season_info(soup):
    nav = soup.select("#bottom_nav_container")[0]
    hrefs = [a["href"] for a in nav.find_all('a')]
    season = os.path.basename(hrefs[1]).split("_")[0]
    return season

def read_line_score(soup):
    line_score = pd.DataFrame(columns=["team", "total"])
    
    try:
        # Wrap the HTML string with StringIO
        line_score = pd.read_html(StringIO(str(soup)), attrs={'id': 'line_score'})[0]
        cols = list(line_score.columns)
        cols[0] = "team"
        cols[-1] = "total"
        line_score.columns = cols
        line_score = line_score[["team", "total"]]
    except ValueError as e:
        if "No tables found" not in str(e):
            raise e
        pass  # Skip the file if table not found
    
    if line_score.empty:
        team_elements = soup.select("span > strong")
        teams = [element.text.strip() for element in team_elements if element.text.strip()]
        
        tfoot_elements = soup.find_all("tfoot")
        pts_elements = []
        for i in range(len(tfoot_elements)):
            if i == 0 or i == 8:
                last_row = tfoot_elements[i].find("tr")
                pts_element = last_row.find("td", {"class": "right", "data-stat": "pts"})
                if pts_element:
                    pts_elements.append(int(pts_element.text))
                else:
                    pts_elements.append(np.nan)
        
        line_score = pd.concat([line_score, pd.DataFrame({"team": teams, "total": pts_elements})], ignore_index=True)
        
    return line_score


def read_stats(soup, team, stat):
    # Wrap the HTML string with StringIO
    df = pd.read_html(StringIO(str(soup)), attrs={'id': f'box-{team}-game-{stat}'}, index_col=0)[0]
    df = df.apply(pd.to_numeric, errors="coerce")
    return df


"""
Parsing the html files to obtain usable csv
"""
# Define the list of years
years = ["2025"]
         
games = [] # Initialize an empty list to store game dataframes

total_games = sum(len(os.listdir(f"data/scrapped_htmls/boxscore_stats/{year}/scores")) for year in years)

# Iterate over each year
for year in years:
    SCORE_DIR = f"data/scrapped_htmls/boxscore_stats/{year}/scores"
    scores_csv_dir = f"data/scrapped_htmls/boxscore_stats/{year}/scores_csv"

    os.makedirs(scores_csv_dir, exist_ok=True)
    
    box_scores = os.listdir(SCORE_DIR)
    box_scores = [os.path.join(SCORE_DIR, f) for f in box_scores if f.endswith(".html")]
    
    base_cols = None
    for box_score in box_scores:
        # Check if the file has already been parsed
        if box_score in parsed_files:
            print(f"Skipping {box_score} as it has already been parsed.")
            continue

        soup = parse_html(box_score)

        line_score = read_line_score(soup)
        teams = list(line_score["team"])

        summaries = []
        for team in teams:
            basic = read_stats(soup, team, "basic")
            advanced = read_stats(soup, team, "advanced")

            totals = pd.concat([basic.iloc[-1,:], advanced.iloc[-1,:]])
            totals.index = totals.index.str.lower()

            maxes = pd.concat([basic.iloc[:-1].max(), advanced.iloc[:-1].max()])
            maxes.index = maxes.index.str.lower() + "_max"

            summary = pd.concat([totals, maxes])

            if base_cols is None:
                base_cols = list(summary.index.drop_duplicates(keep="first"))
                base_cols = [b for b in base_cols if "bpm" not in b]

            summary = summary[base_cols]

            summaries.append(summary)
        summary = pd.concat(summaries, axis=1).T

        game = pd.concat([summary, line_score], axis=1)

        game["home"] = [0,1]

        game_opp = game.iloc[::-1].reset_index()
        game_opp.columns += "_opp"

        full_game = pd.concat([game, game_opp], axis=1)
        full_game["season"] = read_season_info(soup)

        full_game["date"] = os.path.basename(box_score)[:8]
        full_game["date"] = pd.to_datetime(full_game["date"], format="%Y%m%d") 

        full_game["won"] = full_game["total"] > full_game["total_opp"]
        games.append(full_game)

        # Mark this file as parsed and save it to the log
        parsed_files.add(box_score)
        save_parsed_file(box_score)

        if len(games) % 100 == 0:
            progress = len(games) + sum(len(os.listdir(f"data/{y}/scores")) for y in years[:years.index(year)])
            print(f"{progress} / {total_games}")
            
# Concatenate all game dataframes into one dataframe
games_df = pd.concat(games, ignore_index=True)
games_df.head()
games_df.shape


games_df.to_csv("data/parsed_csvs/scores_csv/nba_games_2025.csv")

games_df = pd.read_csv("data/parsed_csvs/scores_csv/nba_games_2025.csv", index_col = 0)

# List of features
column_headers = ['mp', 'mp.1', 'fg', 'fga', 'fg%', '3p', '3pa', '3p%', 'ft', 'fta', 'ft%', 'orb', 'drb', 'trb', 'ast', 
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
            'ortg_max_opp', 'drtg_max_opp', 'team_opp', 'total_opp', 'home_opp', 'season', 'date', 'won']

# # Count the number of items in the list
# count = len(column_headers)

# # Print the count
# print("Total number of items in the list:", count)

# # print(games_df.columns)
# # print(f"Number of columns: {len(games_df.columns)}")

games_df.columns = column_headers

seasons_df = pd.read_csv("data/parsed_csvs/scores_csv/nba_games.csv", index_col = 0)
seasons_df.reset_index(drop=True, inplace=True)
seasons_df.index += len(games_df)

combined_df = pd.concat([games_df, seasons_df], ignore_index=True)  

combined_df.to_csv("data/parsed_csvs/scores_csv/nba_games_running.csv")

# """
# Observed some total scores were missing in the data. The following steps were used to identify and fill the values
# """
# # Assuming combined_df is your DataFrame
# mask = combined_df['total'].isnull()
# null_rows = combined_df[mask]

# # print(null_rows)
# # null_rows.to_csv("data/parsed_csvs/scores_csv/null_rows_2024.csv")

# """Inputing some missing scores with researched info from nba.com"""

# index_values = [6599, 6619, 6737, 6787, 7131, 7137, 7191, 7207]
# replacement_values = [130, 117, 110, 122, 127, 114, 138, 113]

# for index, value in zip(index_values, replacement_values):
#     combined_df.loc[index, 'total'] = value

# combined_df.to_csv("data/parsed_csvs/scores_csv/nba_games_running.csv")