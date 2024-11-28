import os
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

class FeatureEngineer:
    def __init__(self):
        # Configurations
        pd.set_option('display.max_columns', None)
        warnings.filterwarnings('ignore')
        
        # Constants
        self.BASE_DIR = r"C:\Users\User\OneDrive\sandbox\Refresh\data"
        self.DATA_PATH = f"{self.BASE_DIR}/preprocessed_cleaned_csv/fullGame_stats.csv"
        self.PAST_SEASONS_PATH = f"{self.BASE_DIR}/preprocessed_cleaned_csv/fullGame_stats_2024.csv"
        self.OUTPUT_DIR = f"{self.BASE_DIR}/feature_engineered_csv"
        self.OUTPUT_PATH = f"{self.OUTPUT_DIR}/season2date_without_nextGame_features.csv"
        self.ROLLING_OUTPUT_PATH = f"{self.OUTPUT_DIR}/season2date_with_rolling_features.csv"
        self.NEXT_GAME_OUTPUT_PATH = f"{self.OUTPUT_DIR}/season2date_with_nextGame_features.csv"
        
        # Parameters
        self.INITIAL_ELO_RATING = 1500
        self.K_FACTOR = 32
        self.RECENT_GAMES_WINDOW = 5
        self.ROLLING_WINDOW = 5  # Rolling window size
        self.PLACEHOLDER_VALUE = "NotPlayed"
        
        # Columns to exclude from calculations
        self.REMOVED_COLUMNS = [
            "Season", "date", "won", "target", "team", 
            'total', 'home', 'team_opp', 'total_opp', 'home_opp'
        ]

    def ensure_directory_exists(self, file_path):
        """Create directory if it doesn't exist."""
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)

    def load_and_combine_data(self):
        """Load and combine current and historical data."""
        print("Loading data...")
        
        # Load current season data
        current_df = pd.read_csv(self.DATA_PATH)
        current_df['date'] = pd.to_datetime(current_df['date'], dayfirst=True)
        
        # Load historical data if exists
        try:
            historical_df = pd.read_csv(self.PAST_SEASONS_PATH)
            historical_df['date'] = pd.to_datetime(historical_df['date'], dayfirst=True)
            
            # Combine datasets
            combined_df = pd.concat([historical_df, current_df], ignore_index=True)
            print(f"Loaded {len(historical_df)} historical games and {len(current_df)} current season games.")
        except FileNotFoundError:
            print("No historical data found. Using only current season data.")
            combined_df = current_df
        
        # Sort by date and reset index
        combined_df = combined_df.sort_values("date").reset_index(drop=True)
        return combined_df

    def add_target_column(self, df):
        """Add target column indicating next game outcome."""
        def add_target(group):
            group["target"] = group["won"].shift(-1)
            # Add days until next game
            group["days_until_next"] = group["date"].shift(-1) - group["date"]
            group["days_until_next"] = group["days_until_next"].dt.days
            return group

        print("Adding target columns...")
        df = df.groupby("team", group_keys=True).apply(add_target)
        df.index = df.index.droplevel()
        df["target"] = df["target"].fillna(2).astype(int, errors="ignore")
        df["days_until_next"] = df["days_until_next"].fillna(-1)
        return df

    def calculate_recent_performance_metrics(self, row, df):
        """Calculate comprehensive recent performance metrics."""
        team = row['team']
        season = row['Season']
        current_date = row['date']

        # Get recent games
        recent_games = df[
            (df['team'] == team) & 
            (df['Season'] == season) & 
            (df['date'] < current_date)
        ].tail(self.RECENT_GAMES_WINDOW)

        if len(recent_games) == 0:
            return tuple([0.0] * 10)  # Return zeros if no recent games

        # Basic stats
        scoring_stats = {
            'avg_points_scored': recent_games['total'].mean(),
            'avg_points_allowed': recent_games['total_opp'].mean(),
            'point_differential': (recent_games['total'] - recent_games['total_opp']).mean()
        }

        # Shooting percentages
        shooting_stats = {
            'fg_pct': recent_games['fg'].sum() / recent_games['fga'].sum() if recent_games['fga'].sum() > 0 else 0.0,
            'fg3_pct': recent_games['3p'].sum() / recent_games['3pa'].sum() if recent_games['3pa'].sum() > 0 else 0.0,
            'ft_pct': recent_games['ft'].sum() / recent_games['fta'].sum() if recent_games['fta'].sum() > 0 else 0.0
        }

        # Advanced stats
        total_rebounds = recent_games['orb'].sum() + recent_games['drb'].sum()
        advanced_stats = {
            'orb_rate': recent_games['orb'].sum() / total_rebounds if total_rebounds > 0 else 0.0,
            'drb_rate': recent_games['drb'].sum() / total_rebounds if total_rebounds > 0 else 0.0,
            'assist_ratio': recent_games['ast'].mean() / recent_games['total'].mean() if recent_games['total'].mean() > 0 else 0.0,
            'turnover_ratio': recent_games['tov'].mean() / recent_games['total'].mean() if recent_games['total'].mean() > 0 else 0.0
        }

        return tuple(list(scoring_stats.values()) + 
                    list(shooting_stats.values()) + 
                    list(advanced_stats.values()))

    def add_recent_performance_metrics(self, df):
        """Add recent performance metrics as new columns."""
        print("Calculating recent performance metrics...")
        metrics = df.apply(
            lambda row: pd.Series(self.calculate_recent_performance_metrics(row, df)), 
            axis=1
        )
        
        metrics.columns = [
            'avg_points_scored', 'avg_points_allowed', 'point_differential',
            'fg_pct', 'fg3_pct', 'ft_pct',
            'orb_rate', 'drb_rate', 'assist_ratio', 'turnover_ratio'
        ]
        
        return pd.concat([df, metrics], axis=1)

    def calculate_cumulative_stats(self, df):
        """Calculate comprehensive cumulative statistics."""
        print("Calculating cumulative statistics...")
        
        # Create basic stats first
        df['point_differential'] = df['total'] - df['total_opp']
        
        def calculate_team_stats(team_group):
            """Calculate stats for a single team's games."""
            team_group = team_group.sort_values('date')
            
            # Basic cumulative stats
            team_group['cumulative_point_differential'] = team_group['point_differential'].cumsum()
            team_group['cumulative_wins'] = team_group['won'].cumsum()
            team_group['cumulative_games'] = range(1, len(team_group) + 1)
            team_group['win_percentage'] = (team_group['cumulative_wins'] / team_group['cumulative_games']) * 100
            
            # Shooting percentages
            team_group['cumulative_fg%'] = (team_group['fg'].cumsum() / team_group['fga'].cumsum() * 100).fillna(0)
            team_group['cumulative_3p%'] = (team_group['3p'].cumsum() / team_group['3pa'].cumsum() * 100).fillna(0)
            team_group['cumulative_ft%'] = (team_group['ft'].cumsum() / team_group['fta'].cumsum() * 100).fillna(0)
            
            # Advanced cumulative stats
            team_group['cumulative_ast'] = team_group['ast'].expanding().mean()
            team_group['cumulative_tov'] = team_group['tov'].expanding().mean()
            
            # Home/Away stats
            home_games = team_group['home'].cumsum()
            home_wins = (team_group['won'] & team_group['home']).cumsum()
            team_group['home_win_percentage'] = (home_wins / home_games * 100).fillna(0)
            
            return team_group

        # Process each team separately within each season
        grouped = df.groupby(['team', 'Season'])
        result_frames = []
        
        for name, group in grouped:
            result_frames.append(calculate_team_stats(group))
        
        # Combine all processed groups back together
        result = pd.concat(result_frames)
        
        # Sort back to original order
        result = result.sort_index()
        
        # Make sure we have all our original columns plus our new ones
        original_columns = df.columns.tolist()
        stats_columns = [col for col in result.columns if col not in original_columns]
        
        # Update the input dataframe with new statistics
        for col in stats_columns:
            df[col] = result[col]
        
        return df

    def calculate_streaks(self, df):
        """Calculate win and losing streaks for each team."""
        print("Calculating streaks...")
        
        def calculate_team_streaks(team_group):
            """Calculate streaks for a single team's games."""
            # Sort by date within group
            team_group = team_group.sort_values('date')
            
            # Initialize streak columns
            team_group['win_streak'] = 0
            team_group['losing_streak'] = 0
            team_group['home_win_streak'] = 0
            team_group['away_win_streak'] = 0
            
            # Calculate streaks
            current_win_streak = 0
            current_lose_streak = 0
            current_home_win_streak = 0
            current_away_win_streak = 0
            
            for idx in range(len(team_group)):
                won = team_group.iloc[idx]['won']
                is_home = team_group.iloc[idx]['home']
                
                if won:
                    current_win_streak += 1
                    current_lose_streak = 0
                    if is_home:
                        current_home_win_streak += 1
                        current_away_win_streak = 0
                    else:
                        current_away_win_streak += 1
                        current_home_win_streak = 0
                else:
                    current_lose_streak += 1
                    current_win_streak = 0
                    current_home_win_streak = 0
                    current_away_win_streak = 0
                
                team_group.iloc[idx, team_group.columns.get_loc('win_streak')] = current_win_streak
                team_group.iloc[idx, team_group.columns.get_loc('losing_streak')] = current_lose_streak
                team_group.iloc[idx, team_group.columns.get_loc('home_win_streak')] = current_home_win_streak
                team_group.iloc[idx, team_group.columns.get_loc('away_win_streak')] = current_away_win_streak
            
            return team_group
        
        # Process each team separately within each season
        grouped = df.groupby(['team', 'Season'])
        result_frames = []
        
        for name, group in grouped:
            result_frames.append(calculate_team_streaks(group))
        
        # Combine all processed groups back together
        result = pd.concat(result_frames)
        
        # Sort back to original order
        result = result.sort_index()
        
        # Update the input dataframe with new streak columns
        streak_columns = ['win_streak', 'losing_streak', 'home_win_streak', 'away_win_streak']
        for col in streak_columns:
            df[col] = result[col]
        
        return df

    def update_elo_ratings(self, df):
        """Calculate Elo ratings with home court advantage."""
        print("Updating Elo ratings...")
        HOME_ADVANTAGE = 100  # Elo points for home court advantage
        
        elo_ratings = {team: self.INITIAL_ELO_RATING for team in df['team'].unique()}
        
        def expected_win_probability(elo_a, elo_b, home_advantage=0):
            return 1 / (1 + 10 ** ((elo_b - (elo_a + home_advantage)) / 400))
        
        def update_elo(elo_a, elo_b, outcome, k_factor):
            expected_win = expected_win_probability(elo_a, elo_b)
            return elo_a + k_factor * (outcome - expected_win)
        
        for idx, row in df.iterrows():
            team_a = row['team']
            team_b = row['team_opp']
            outcome = row['won']
            
            # Adjust K-factor based on margin of victory
            point_diff = abs(row['total'] - row['total_opp'])
            k_factor = self.K_FACTOR * (1 + 0.1 * (point_diff - 10) / 10 if point_diff > 10 else 1)
            
            elo_a = elo_ratings[team_a]
            elo_b = elo_ratings[team_b]
            
            # Add home court advantage
            home_advantage = HOME_ADVANTAGE if row['home'] else -HOME_ADVANTAGE
            
            new_elo_a = update_elo(elo_a, elo_b, outcome, k_factor)
            new_elo_b = update_elo(elo_b, elo_a, 1 - outcome, k_factor)
            
            elo_ratings[team_a] = new_elo_a
            elo_ratings[team_b] = new_elo_b
            
            df.at[idx, 'elo_rating'] = new_elo_a
            df.at[idx, 'elo_rating_opp'] = new_elo_b
            df.at[idx, 'elo_difference'] = new_elo_a - new_elo_b
        
        return df

    def calculate_head_to_head_stats(self, row, df):
        """Calculate comprehensive head-to-head statistics."""
        team = row['team']
        opponent = row['team_opp']
        season = row['Season']  # Changed from 'season' to 'Season'
        current_date = row['date']

        # Get historical matchups
        historical_matchups = df[
            (((df['team'] == team) & (df['team_opp'] == opponent)) |
            ((df['team'] == opponent) & (df['team_opp'] == team))) &
            (df['date'] < current_date) &
            (df['Season'] == season)  # Changed from 'season' to 'Season'
        ]

        if len(historical_matchups) == 0:
            return tuple([0.0] * 6)

        # Calculate basic stats
        team_games = historical_matchups[historical_matchups['team'] == team]
        wins = team_games['won'].sum()
        total_games = len(historical_matchups)
        
        stats = {
            'h2h_win_ratio': wins / total_games if total_games > 0 else 0.0,
            'h2h_avg_points_scored': team_games['total'].mean() if len(team_games) > 0 else 0.0,
            'h2h_avg_points_allowed': team_games['total_opp'].mean() if len(team_games) > 0 else 0.0,
            'h2h_fg_pct': team_games['fg%'].mean() if len(team_games) > 0 else 0.0,
            'h2h_point_diff': (team_games['total'] - team_games['total_opp']).mean() if len(team_games) > 0 else 0.0,
            'games_played': total_games
        }

        return tuple(stats.values())

    def add_head_to_head_stats(self, df):
        """Add head-to-head statistics."""
        print("Calculating head-to-head statistics...")
        stats = df.apply(lambda row: pd.Series(self.calculate_head_to_head_stats(row, df)), axis=1)
        
        stats.columns = [
            'h2h_win_ratio', 'h2h_avg_points_scored', 'h2h_avg_points_allowed',
            'h2h_fg_pct', 'h2h_point_diff', 'h2h_games_played'
        ]
        
        return pd.concat([df, stats], axis=1)

    def calculate_rest_days(self, row, df):
        """Calculate rest days and schedule difficulty."""
        team = row['team']
        season = row['Season']
        current_date = row['date']
        
        # Get previous game
        previous_games = df[
            (df['team'] == team) & 
            (df['Season'] == season) & 
            (df['date'] < current_date)
        ]
        
        if len(previous_games) == 0:
            return 0, 0, 0
        
        last_game_date = previous_games['date'].max()
        rest_days = (current_date - last_game_date).days - 1
        
        # Calculate games in last 7 days
        games_last_week = len(previous_games[
            previous_games['date'] >= (current_date - pd.Timedelta(days=7))
        ])
        
        # Calculate average rest days in last 5 games
        last_5_games = previous_games.tail(5)
        avg_rest = last_5_games['rest_days'].mean() if 'rest_days' in last_5_games.columns else 0
        
        return rest_days, games_last_week, avg_rest

    def add_rest_days(self, df):
        """Add rest and schedule-related features."""
        print("Calculating rest days and schedule features...")
        stats = df.apply(lambda row: pd.Series(self.calculate_rest_days(row, df)), axis=1)
        
        stats.columns = ['rest_days', 'games_last_week', 'avg_rest_last_5']
        return pd.concat([df, stats], axis=1)
    
    def add_rolling_averages(self, df):
        """Add rolling averages for selected numeric columns."""
        print("Calculating rolling averages...")
        # Exclude the specified columns
        selected_columns = df.columns.difference(self.REMOVED_COLUMNS)
        # numeric_columns = df[selected_columns].select_dtypes(include=['int64', 'float64']).columns
        # Code modified to drop the "unnamed: 0" column here
        numeric_columns = df[selected_columns].select_dtypes(include=['int64', 'float64']).drop(columns=["Unnamed: 0"], errors='ignore').columns

        # Create a DataFrame for rolling averages
        rolling_df = pd.DataFrame()

        # Calculate 5-game rolling averages for each team and season
        for (team, season), group in df.groupby(["team", "Season"]):
            group = group.sort_values("date").copy()
            rolling_averages = group[numeric_columns].rolling(window=self.ROLLING_WINDOW, min_periods=1).mean()
            rolling_averages.columns = [f"{col}_rolling_{self.ROLLING_WINDOW}" for col in numeric_columns]
            
            # Append rolling averages to the main DataFrame
            rolling_df = pd.concat([rolling_df, rolling_averages], axis=0)

        # Concatenate the rolling averages with the original DataFrame
        df = pd.concat([df.reset_index(drop=True), rolling_df.reset_index(drop=True)], axis=1)
        return df
    
    def add_next_game_info(self, df):
        """Add next game information."""
        print("Adding next game information...")
        columns_to_shift = [
            ("home", "home_next"),
            ("team_opp", "team_opp_next"),
            ("date", "date_next"),
            ("PER_Combined_opp", "PER_Combined_opp_next"),
            ("elo_rating_opp", "elo_rating_opp_next"),
            ("h2h_win_ratio", "h2h_win_ratio_next"),
            ("rest_days", "rest_days_next"),
            ("games_last_week", "games_last_week_next")
        ]
        
        # Shift values within each team group
        for col_name, new_col_name in columns_to_shift:
            df[new_col_name] = df.groupby("team")[col_name].shift(-1)

        # Calculate days until next game
        df['days_until_next'] = (df['date_next'] - df['date']).dt.days
        df['days_until_next'] = df['days_until_next'].fillna(-1).astype(int)
        
        return df

    def merge_next_game_info(self, df):
        """Merge next game information back into the original DataFrame."""
        print("Merging next game information...")
        
        # Select columns for merging
        next_game_cols = [
            "team", "date_next", "home_next", "team_opp_next", 
            "PER_Combined_opp_next", "elo_rating_opp_next", 
            "h2h_win_ratio_next", "rest_days_next", "games_last_week_next"
        ]
        
        # Drop duplicates based on team and date_next
        # next_game_info = df[next_game_cols].drop_duplicates(subset=["team", "date_next"], keep="first").dropna(subset=["date_next"])
        next_game_info = df[next_game_cols].drop_duplicates(subset=["team", "date_next"], keep="first")
        
        # Merge next game info with the main DataFrame
        # merged_df = pd.merge(df, next_game_info, on=["team", "date_next"], how="left", suffixes=("", "_merged"))
        merged_df = df.merge(next_game_info, how="left", 
                          left_on=["team", "date_next"], 
                          right_on=["team_opp_next", "date_next"], suffixes=("", "_rival"))
        
        # Fill missing values
        for col in next_game_cols[2:]:
            merged_df[col] = merged_df[col].fillna(self.PLACEHOLDER_VALUE)
        
        return merged_df
    
    def process_data(self):
        """Main processing pipeline."""
        # Load and combine data
        df = self.load_and_combine_data()
        
        # Feature engineering steps
        df = self.add_target_column(df)
        df = self.add_recent_performance_metrics(df)
        df = self.calculate_cumulative_stats(df)
        df = self.calculate_streaks(df)
        df = self.update_elo_ratings(df)
        df = self.add_head_to_head_stats(df)
        df = self.add_rest_days(df)

        # Save results
        self.ensure_directory_exists(self.OUTPUT_PATH)
        df.to_csv(self.OUTPUT_PATH, index=False)
        print(f"Saved results to {self.OUTPUT_PATH}")

        # Add rolling averages
        df = self.add_rolling_averages(df)      
        
        # Save the final DataFrame with rolling averages
        # df.to_csv(self.ROLLING_OUTPUT_PATH, index=False)
        self.ensure_directory_exists(self.ROLLING_OUTPUT_PATH)
        df.to_csv(self.ROLLING_OUTPUT_PATH)
        print(f"Saved processed data with rolling averages to {self.ROLLING_OUTPUT_PATH}")
        
        # Add next game features
        df = self.add_next_game_info(df)
        full_stats = self.merge_next_game_info(df)

        # Move the 'target' column to the end
        target_column = full_stats.pop('target')
        full_stats['target'] = target_column
        
        # Save the final DataFrame
        self.ensure_directory_exists(self.NEXT_GAME_OUTPUT_PATH)
        full_stats.to_csv(self.NEXT_GAME_OUTPUT_PATH, index=False)
        print(f"Saved final results to {self.NEXT_GAME_OUTPUT_PATH}")
        
        return full_stats

def main():
    """Main execution function."""
    try:
        print("Starting feature engineering process...")
        engineer = FeatureEngineer()
        final_df = engineer.process_data()
        print("\nFeature engineering completed successfully!")
    except Exception as e:
        print(f"Error during feature engineering: {str(e)}")
        raise

if __name__ == "__main__":
    main()