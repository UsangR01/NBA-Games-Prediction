import warnings
warnings.filterwarnings('ignore')
import os
import pandas as pd
from datetime import datetime

class DataPreprocessor:
    def __init__(self, year="2025"):
        self.year = year
        self.base_dir = "Refresh/data"
        self.output_dir = f"{self.base_dir}/preprocessed_cleaned_csv"
        
        # Input paths
        self.gameLineup_path = f"{self.base_dir}/parsed_csvs/gameLineup_csv/gameLineup_{year}.csv"
        self.playerStats_path = f"{self.base_dir}/parsed_csvs/playerStats_csv/playerStats_{year}.csv"
        self.game_stats_path = f"{self.base_dir}/parsed_csvs/scores_csv/nba_games_{year}.csv"
        
        # Output path
        self.output_path = f"{self.output_dir}/fullGame_stats.csv"
        
        # Columns to drop
        self.columns_to_drop = [
            'pts', 'pts_opp', 'gmsc', 'gmsc_opp', 'gmsc_max', 'gmsc_max_opp', 
            '+/-', '+/-_opp', "mp.1", "mp_opp", "mp_opp.1", "mp_max", "mp_max.1", 
            'mp_max_opp', 'mp_max_opp.1', "index_opp", "Team", 'Big5', 
            'Big4', 'Big3', 'Big2', 'Big1', 'Team_opp', 'Big5_opp', 'Big4_opp', 'Big3_opp', 'Big2_opp', 'Big1_opp'
        ]
        
        self.player_columns_to_remove = [
            'Top1', 'Top2', 'Top3', 'Top4', 'Top5',
            'Top1_PER', 'Top2_PER', 'Top3_PER', 'Top4_PER', 'Top5_PER',
            'Top1_opp', 'Top2_opp', 'Top3_opp', 'Top4_opp', 'Top5_opp',
            'Top1_PER_opp', 'Top2_PER_opp', 'Top3_PER_opp', 'Top4_PER_opp', 'Top5_PER_opp'
        ]

    def load_data(self):
        """Load all required datasets"""
        print("Loading data files...")
        self.gameLineup = pd.read_csv(self.gameLineup_path, index_col=0)
        self.playerStats = pd.read_csv(self.playerStats_path)
        self.game_stats = pd.read_csv(self.game_stats_path, index_col=0)
        self.game_stats = self.game_stats.rename(columns={"season": "Season"})
        print("Data loading complete.")

    def prepare_player_stats(self):
        """Prepare player statistics data"""
        print("Preparing player statistics...")
        # Calculate minutes per game
        self.playerStats['MPG'] = round(self.playerStats['MP'] / self.playerStats['G'], 2)
        
        # Select and clean player stats
        self.playerStats_df = self.playerStats[["Player", "Team", "MPG", "PER", "WS/48", "Season"]].copy()
        self.playerStats_df["Player"] = self.playerStats_df["Player"].str.replace("*", "", regex=False)
        
        # Handle multiple team players
        self.playerStats_df = (self.playerStats_df.groupby(["Player", "Season"])
                             .apply(self._handle_multiple_teams)
                             .reset_index(drop=True))
        print("Player statistics preparation complete.")

    def _handle_multiple_teams(self, df):
        """Handle players who played for multiple teams in a season"""
        if df.shape[0] == 1:
            return df
        else:
            row = df[df["Team"] == "TOT"].copy()
            if not row.empty:
                row["Team"] = df.iloc[-1]["Team"]
                return row
            return df.iloc[-1:].copy()

    def identify_top_players(self):
        """Identify top performing players for each team"""
        print("Identifying top players...")
        team_groups = self.playerStats_df.groupby(["Team", "Season"], group_keys=False)
        self.top_five_players = team_groups.apply(self._get_top_five_players)
        
        # Reorder columns
        cols = self.top_five_players.columns.tolist()
        cols.remove('Team')
        cols.remove('Season')
        cols.extend(['Team', 'Season'])
        self.top_five_players = self.top_five_players[cols]
        print("Top players identification complete.")

    def _get_top_five_players(self, group):
        """Get top 5 players based on WS/48 and minutes played"""
        # Filter players by minutes played
        high_minutes = group[group['MPG'] >= 26]
        medium_minutes = group[(group['MPG'] >= 18) & (group['MPG'] < 26)]
        
        # Combine and sort all eligible players
        all_players = pd.concat([
            high_minutes.sort_values("WS/48", ascending=False),
            medium_minutes.sort_values("WS/48", ascending=False),
            group[~group.index.isin(high_minutes.index) & ~group.index.isin(medium_minutes.index)]
            .sort_values("WS/48", ascending=False)
        ])
        
        # Take top 5 players
        top_players = all_players.head(5)
        
        # Create result DataFrame
        result = pd.DataFrame({
            'Team': [group['Team'].iloc[0]],
            'Season': [group['Season'].iloc[0]]
        })
        
        # Add player names and PER values
        for i, (_, player) in enumerate(top_players.iterrows(), 1):
            result[f'Top{i}'] = player['Player']
            result[f'Top{i}_PER'] = player['PER']
        
        return result

    def calculate_big_n_stats(self):
        """Calculate Big-N statistics and PER for each team and their opponents"""
        print("Calculating team statistics...")
        
        # First merge for main team stats
        self.merged_df = self.gameLineup.merge(
            self.top_five_players,
            on=['Team', 'Season'],
            how='left'
        )
        
        # Create team_opp column from the lineup data
        # Get even and odd rows
        even_rows = self.merged_df.iloc[::2].reset_index(drop=True)
        odd_rows = self.merged_df.iloc[1::2].reset_index(drop=True)
        
        # Create team_opp columns
        even_rows['team_opp'] = odd_rows['Team']
        odd_rows['team_opp'] = even_rows['Team']
        
        # Recombine the data
        self.merged_df = pd.concat([even_rows, odd_rows]).sort_index()
        
        # Rename columns for opponent data
        opponent_cols = {
            'Team': 'Team_opp',
            'Top1': 'Top1_opp',
            'Top2': 'Top2_opp',
            'Top3': 'Top3_opp',
            'Top4': 'Top4_opp',
            'Top5': 'Top5_opp',
            'Top1_PER': 'Top1_PER_opp',
            'Top2_PER': 'Top2_PER_opp',
            'Top3_PER': 'Top3_PER_opp',
            'Top4_PER': 'Top4_PER_opp',
            'Top5_PER': 'Top5_PER_opp'
        }
        
        # Merge opponent stats
        self.merged_df = self.merged_df.merge(
            self.top_five_players.rename(columns=opponent_cols),
            left_on=['team_opp', 'Season'],
            right_on=['Team_opp', 'Season'],
            how='left'
        )
        
        # Initialize columns for both teams
        for n in range(1, 6):
            self.merged_df[f'Big{n}'] = 0
            self.merged_df[f'Big{n}_opp'] = 0
        
        self.merged_df['PER_Combined'] = 0
        self.merged_df['PER_Combined_opp'] = 0
        
        # Calculate stats for each row
        print("Processing game statistics...")
        total_rows = len(self.merged_df)
        
        for idx, row in self.merged_df.iterrows():
            if idx % 100 == 0:
                print(f"Processing game {idx}/{total_rows}...")
                
            # Main team calculations
            try:
                top_players = [row[f'Top{i}'] for i in range(1, 6)]
                game_players = [row[f'Player {i}'] for i in range(1, 16) if pd.notna(row[f'Player {i}'])]
                common_players = set(top_players) & set(game_players)
                
                n_common = len(common_players)
                if n_common > 0:
                    self.merged_df.at[idx, f'Big{n_common}'] = 1
                
                per_values = [row[f'Top{i}_PER'] for i in range(1, 6) if row[f'Top{i}'] in common_players]
                self.merged_df.at[idx, 'PER_Combined'] = sum(per_values)
            except Exception as e:
                print(f"Error processing main team at index {idx}: {str(e)}")
                
            # Opponent team calculations
            try:
                top_players_opp = [row[f'Top{i}_opp'] for i in range(1, 6)]
                # Get the opponent's players (next row if even index, previous row if odd index)
                opp_idx = idx + 1 if idx % 2 == 0 else idx - 1
                if 0 <= opp_idx < len(self.merged_df):
                    opp_row = self.merged_df.iloc[opp_idx]
                    game_players_opp = [opp_row[f'Player {i}'] for i in range(1, 16) if pd.notna(opp_row[f'Player {i}'])]
                    common_players_opp = set(top_players_opp) & set(game_players_opp)
                    
                    n_common_opp = len(common_players_opp)
                    if n_common_opp > 0:
                        self.merged_df.at[idx, f'Big{n_common_opp}_opp'] = 1
                    
                    per_values_opp = [row[f'Top{i}_PER_opp'] for i in range(1, 6) if row[f'Top{i}_opp'] in common_players_opp]
                    self.merged_df.at[idx, 'PER_Combined_opp'] = sum(per_values_opp)
            except Exception as e:
                print(f"Error processing opponent team at index {idx}: {str(e)}")
        
        print("Team statistics calculation complete.")

    def prepare_team_stats(self):
        """Prepare team statistics including opponent stats"""
        print("Preparing team statistics...")
        # Select relevant columns including opponent stats
        team_cols = (
            ["Team", "Season"] +
            [f'Top{i}' for i in range(1, 6)] +
            [f'Top{i}_PER' for i in range(1, 6)] +
            [f'Big{i}' for i in range(1, 6)] +
            ['PER_Combined'] +
            [f'Top{i}_opp' for i in range(1, 6)] +
            [f'Top{i}_PER_opp' for i in range(1, 6)] +
            [f'Big{i}_opp' for i in range(1, 6)] +
            ['PER_Combined_opp']
        )
        
        self.Big5_df = self.merged_df[team_cols]
        
        # Create opponent and main stats DataFrames
        self.opp_stats = self.Big5_df.iloc[1::2].reset_index(drop=True)
        self.main_stats = self.Big5_df.iloc[::2].reset_index(drop=True)
        
        # Combine main and opponent stats
        self.Big5_bothTeams = self._combine_team_stats()
        print("Team statistics preparation complete.")

    def _combine_team_stats(self):
        """Combine main and opponent team statistics"""
        combined_rows = []
        max_rows = max(len(self.main_stats), len(self.opp_stats))
        
        for i in range(max_rows):
            if i < len(self.main_stats):
                combined_rows.append(self.main_stats.iloc[i])
            if i < len(self.opp_stats):
                combined_rows.append(self.opp_stats.iloc[i])
        
        combined = pd.concat(combined_rows, axis=1).transpose().reset_index(drop=True)
        return combined.loc[:, ~combined.columns.duplicated()]

    def combine_and_clean_data(self):
        """Combine all data and perform final cleaning"""
        print("Combining and cleaning data...")
        # Combine with game stats
        self.final_df = pd.concat([self.game_stats, self.Big5_bothTeams], axis=1)
        self.final_df = self.final_df.loc[:, ~self.final_df.columns.duplicated()]
        
        # Process dates and sort
        self.final_df['date'] = pd.to_datetime(self.final_df['date'], format='%Y-%m-%d')
        self.final_df = self.final_df.sort_values("date").reset_index(drop=True)
        
        # Drop specified columns
        cols_to_drop = self.columns_to_drop + self.player_columns_to_remove
        self.final_df = self.final_df.drop(columns=cols_to_drop, errors='ignore')
        
        # Handle numeric columns
        self._process_numeric_columns()
        
        # Final cleaning
        self.final_df.dropna(axis=1, inplace=True)
        self.final_df['team'] = self.final_df['team'].replace('CHO', 'CHA')
        self.final_df['team_opp'] = self.final_df['team_opp'].replace('CHO', 'CHA')
        print("Data cleaning complete.")

    def _process_numeric_columns(self):
        """Process numeric columns with proper error handling"""
        temp_df = self.final_df.drop(columns=['team', 'total', 'home', 'team_opp', 'total_opp', 'home_opp', 'date', 'Season', 'won'])
        
        for col in temp_df.columns:
            try:
                if col in ['PER_Combined', 'PER_Combined_opp']:
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce')
                
                if temp_df[col].dtype in ['int64', 'float64']:
                    temp_df[col].fillna(temp_df[col].median(), inplace=True)
            except Exception as e:
                print(f"Error processing column {col}: {str(e)}")
        
        self.final_df = pd.concat([self.final_df[['team', 'total', 'home', 'team_opp', 'total_opp', 'home_opp', 'date', 'Season', 'won']], temp_df], axis=1)

    def save_data(self):
        """Save the processed data to CSV"""
        print("Saving processed data...")
        os.makedirs(self.output_dir, exist_ok=True)
        self.final_df.to_csv(self.output_path)
        print(f"Data saved to {self.output_path}")
        print(f"Final dataset shape: {self.final_df.shape}")

def main():
    print("Starting data preprocessing...")
    preprocessor = DataPreprocessor()
    
    # Execute preprocessing pipeline
    preprocessor.load_data()
    preprocessor.prepare_player_stats()
    preprocessor.identify_top_players()
    preprocessor.calculate_big_n_stats()
    preprocessor.prepare_team_stats()
    preprocessor.combine_and_clean_data()
    preprocessor.save_data()
    print("Data preprocessing complete.")

if __name__ == "__main__":
    main()