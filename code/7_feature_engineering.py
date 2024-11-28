import pandas as pd
import warnings

# Configurations
pd.set_option('display.max_columns', None)  # Display all columns
warnings.filterwarnings('ignore')

# Constants
DATA_PATH = "data/preprocessed_cleaned_csv/fullGame_stats.csv"
OUTPUT_PATH = "data/feature_engineered_csv/fullGame_without_nextGame_features.csv"
NEXT_GAME_OUTPUT_PATH = "data/feature_engineered_csv/fullGame_with_nextGame_features.csv"
INITIAL_ELO_RATING = 1500
K_FACTOR = 32
REMOVED_COLUMNS = ["season", "date", "won", "target", "team", 'total', 'home', 'team_opp', 'total_opp', 'home_opp']
PLACEHOLDER_VALUE = "Not Played"

def load_and_prepare_data(file_path):
    """Load the data and prepare it for processing."""
    df = pd.read_csv(file_path, index_col=0)
    
    # Convert the 'date' column to datetime format
    df['date'] = pd.to_datetime(df['date'], dayfirst=True)
    
    # Sort by date and reset index
    df = df.sort_values("date").reset_index(drop=True)
    return df

def add_target_column(df):
    """Add a target column to the DataFrame indicating the outcome of the next game."""
    def add_target(group):
        group["target"] = group["won"].shift(-1)
        return group

    df = df.groupby("team", group_keys=True).apply(add_target)
    df.index = df.index.droplevel()  # Remove the multi-index after grouping
    df["target"] = df["target"].fillna(2).astype(int, errors="ignore")
    return df

def calculate_recent_performance_metrics(row, df, num_recent_games=5):
    """Calculate recent performance metrics for a team based on past games."""
    team = row['team']
    season = row['season']
    current_date = row['date']

    recent_games = df[(df['team'] == team) & 
                      (df['season'] == season) & 
                      (df['date'] < current_date)].tail(num_recent_games)

    average_points_scored = recent_games['total'].mean() if len(recent_games) > 0 else 0.0
    average_points_allowed = recent_games['total_opp'].mean() if len(recent_games) > 0 else 0.0

    shooting_percentage = recent_games['fg'].sum() / recent_games['fga'].sum() if recent_games['fga'].sum() > 0 else 0.0
    three_point_percentage = recent_games['3p'].sum() / recent_games['3pa'].sum() if recent_games['3pa'].sum() > 0 else 0.0
    free_throw_percentage = recent_games['ft'].sum() / recent_games['fta'].sum() if recent_games['fta'].sum() > 0 else 0.0

    total_rebounds = recent_games['orb'].sum() + recent_games['drb'].sum()
    offensive_rebound_rate = recent_games['orb'].sum() / total_rebounds if total_rebounds > 0 else 0.0
    defensive_rebound_rate = recent_games['drb'].sum() / total_rebounds if total_rebounds > 0 else 0.0

    return (average_points_scored, average_points_allowed, shooting_percentage, 
            three_point_percentage, free_throw_percentage, 
            offensive_rebound_rate, defensive_rebound_rate)

def add_recent_performance_metrics(df):
    """Add recent performance metrics as new columns to the DataFrame."""
    metrics = df.apply(lambda row: pd.Series(calculate_recent_performance_metrics(row, df)), axis=1)
    metrics.columns = [
        'avg_points_scored', 'avg_points_allowed', 'shooting_percentage', 
        'three_point_percentage', 'free_throw_percentage', 
        'offensive_rebound_rate', 'defensive_rebound_rate'
    ]
    return pd.concat([df, metrics], axis=1)

def calculate_cumulative_stats(df):
    """Calculate cumulative statistics for each team and add them as new columns."""
    df['point_differential'] = df['total'] - df['total_opp']
    team_season_group = df.groupby(['team', 'season'])

    df['cumulative_point_differential'] = team_season_group['point_differential'].cumsum()
    df['cumulative_wins'] = team_season_group['won'].cumsum()
    df['cumulative_games_played'] = team_season_group.cumcount() + 1
    df['win_percent'] = (df['cumulative_wins'] / df['cumulative_games_played']).fillna(0) * 100
    return df

def calculate_streaks(df):
    """Calculate win and losing streaks for each team."""
    mask_won = df['won'] == 1
    mask_lost = df['won'] == 0

    df['win_streak'] = mask_won.groupby((~mask_won).cumsum()).cumsum().astype(int)
    df['losing_streak'] = mask_lost.groupby((~mask_lost).cumsum()).cumsum().astype(int)
    return df

def update_elo_ratings(df):
    """Calculate and update Elo ratings for teams."""
    elo_ratings = {team: INITIAL_ELO_RATING for team in df['team'].unique()}
    elo_ratings_opp = {team: INITIAL_ELO_RATING for team in df['team_opp'].unique()}

    def expected_win_probability(elo_a, elo_b):
        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    def update_elo(elo_a, elo_b, outcome):
        expected_win = expected_win_probability(elo_a, elo_b)
        return elo_a + K_FACTOR * (outcome - expected_win)

    for index, row in df.iterrows():
        team_a = row['team']
        team_b = row['team_opp']
        outcome = row['won']

        elo_a = elo_ratings[team_a]
        elo_b = elo_ratings_opp[team_b]

        new_elo_a = update_elo(elo_a, elo_b, outcome)
        new_elo_b = update_elo(elo_b, elo_a, 1 - outcome)

        elo_ratings[team_a] = new_elo_a
        elo_ratings_opp[team_b] = new_elo_b

        df.at[index, 'elo_rating'] = new_elo_a
        df.at[index, 'elo_rating_opp'] = new_elo_b

    return df

def calculate_head_to_head_stats(row, df):
    """Calculate head-to-head performance metrics between teams."""
    team = row['team']
    team_opp = row['team_opp']
    season = row['season']

    head_to_head_games = df[((df['team'] == team) & (df['team_opp'] == team_opp) & (df['season'] == season)) |
                            ((df['team'] == team_opp) & (df['team_opp'] == team) & (df['season'] == season))]

    num_wins_team = head_to_head_games[head_to_head_games['team'] == team]['won'].sum()
    total_games_played = head_to_head_games['won'].count()

    win_ratio = num_wins_team / total_games_played if total_games_played > 0 else 0.0
    avg_points_scored = head_to_head_games[head_to_head_games['team'] == team]['total'].mean()
    avg_points_allowed = head_to_head_games[head_to_head_games['team'] == team]['total_opp'].mean()

    return win_ratio, avg_points_scored, avg_points_allowed

def add_head_to_head_stats(df):
    """Add head-to-head statistics to the DataFrame."""
    stats = df.apply(lambda row: pd.Series(calculate_head_to_head_stats(row, df)), axis=1)
    stats.columns = ['head_to_head_win_ratio', 'average_points_scored', 'average_points_allowed']
    return pd.concat([df, stats], axis=1)

def calculate_rest_days(row, df):
    """Calculate the number of rest days for a team between games."""
    team = row['team']
    season = row['season']
    previous_game_date = df[(df['team'] == team) & (df['season'] == season) & 
                            (df['date'] < row['date'])]['date'].max()
    if pd.notnull(previous_game_date):
        return (row['date'] - previous_game_date).days - 1
    return 0

def add_rest_days(df):
    """Add rest days as a new column to the DataFrame."""
    df['rest_days'] = df.apply(lambda row: calculate_rest_days(row, df), axis=1)
    return df

def add_rolling_averages(df):
    """Add rolling averages for selected numeric columns."""
    selected_columns = df.columns[~df.columns.isin(REMOVED_COLUMNS)]
    df_rolling = df[list(selected_columns) + ["won", "team", "season"]]
    numeric_columns = df_rolling.select_dtypes(include='number').columns

    def find_team_averages(team):
        return team[numeric_columns].rolling(4).mean()

    df_rolling = df_rolling.groupby(["team", "season"], group_keys=False).apply(find_team_averages)
    rolling_cols = [f"{col}_4" for col in df_rolling.columns]
    df_rolling.columns = rolling_cols

    df = pd.concat([df, df_rolling], axis=1).dropna()
    return df

def add_next_game_info(df):
    """Add next game information based on the current game."""
    columns_to_shift = [
        ("home", "home_next"),
        ("team_opp", "team_opp_next"),
        ("date", "date_next"),
        ("PER_Combined_opp", "PER_Combined_opp_next"),
        ("elo_rating_opp", "elo_rating_opp_next"),
        ("head_to_head_win_ratio", "head_to_head_win_ratio_next")
    ]

    for col_name, new_col_name in columns_to_shift:
        df[new_col_name] = df.groupby("team")[col_name].shift(-1).fillna(PLACEHOLDER_VALUE)
    return df

def merge_next_game_info(df):
    """Merge next game information with the original DataFrame."""
    selected_cols = [
        "team", "home_next", "team_opp_next", "date_next", 
        "PER_Combined_opp_next", "elo_rating_opp_next", "head_to_head_win_ratio_next"
    ]
    next_stats = df[selected_cols]

    full_stats = df.merge(next_stats, how="left", 
                          left_on=["team", "date_next"], 
                          right_on=["team_opp_next", "date_next"])
    return full_stats

def main():
    # Load and prepare data
    stats_df = load_and_prepare_data(DATA_PATH)
    
    # Feature Engineering
    stats_df = add_target_column(stats_df)
    stats_df = add_recent_performance_metrics(stats_df)
    stats_df = calculate_cumulative_stats(stats_df)
    stats_df = calculate_streaks(stats_df)
    stats_df = update_elo_ratings(stats_df)

    # Ensure head-to-head metrics are calculated before adding next game information
    stats_df = add_head_to_head_stats(stats_df)
    stats_df = add_rest_days(stats_df)
    
    # Rolling averages and next game info
    stats_df = add_rolling_averages(stats_df)
    stats_df = add_next_game_info(stats_df)
    
    # Save without next game features
    stats_df.to_csv(OUTPUT_PATH, index=False)
    
    # Merge and save with next game features
    full_stats = merge_next_game_info(stats_df)
    full_stats.to_csv(NEXT_GAME_OUTPUT_PATH, index=False)
    
    # Display final DataFrame
    print(full_stats)

if __name__ == "__main__":
    main()



"""*****************************Check if placeholder exist in dataframe************************************"""
# # Define the placeholder value you want to check
# placeholder_value = "Not Played"

# # Columns where you expect to find the placeholder value
# next_game_columns = ["home_next_x", "team_opp_next_x", "date_next", "PER_Combined_opp_next_x", "elo_rating_opp_next_x", "head_to_head_win_ratio_next_x", "home_next_y", "team_opp_next_y", "PER_Combined_opp_next_y", "elo_rating_opp_next_y", "head_to_head_win_ratio_next_y"]

# # Check if the placeholder exists in any of the 'next game' columns
# placeholder_found = full_stats[next_game_columns].apply(lambda col: col.eq(placeholder_value).any())

# # Print out the results for each column
# for col, found in placeholder_found.items():
#     if found:
#         print(f"Placeholder '{placeholder_value}' found in column: {col}")
#     else:
#         print(f"No placeholder found in column: {col}")