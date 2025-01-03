import pandas as pd
from datetime import datetime
import os

class GameScheduleCleaner:
    def __init__(self, input_file, output_file, stats_file):
        self.input_file = input_file
        self.output_file = output_file
        self.stats_file = stats_file
        self.team_mapping = {
            "New York Knicks": "NYK", "Boston Celtics": "BOS", "Minnesota Timberwolves": "MIN",
            "Los Angeles Lakers": "LAL", "Brooklyn Nets": "BRK", "Atlanta Hawks": "ATL",
            "Indiana Pacers": "IND", "Detroit Pistons": "DET", "Charlotte Hornets": "CHO",
            "Houston Rockets": "HOU", "Phoenix Suns": "PHO", "Los Angeles Clippers": "LAC",
            "Orlando Magic": "ORL", "Miami Heat": "MIA", "Chicago Bulls": "CHI",
            "New Orleans Pelicans": "NOP", "Milwaukee Bucks": "MIL", "Philadelphia 76ers": "PHI",
            "Golden State Warriors": "GSW", "Portland Trail Blazers": "POR", "Cleveland Cavaliers": "CLE",
            "Toronto Raptors": "TOR", "Memphis Grizzlies": "MEM", "Utah Jazz": "UTA",
            "San Antonio Spurs": "SAS", "Dallas Mavericks": "DAL", "Oklahoma City Thunder": "OKC",
            "Denver Nuggets": "DEN", "Washington Wizards": "WAS", "Sacramento Kings": "SAC"
        }

    def transform_player_stats(self) -> None:
        """Transform player stats data into team roster format."""
        print(f"\nTransforming player stats from {self.stats_file}")
        
        # Read the player stats CSV file
        df = pd.read_csv(self.stats_file)
        
        # Keep only Player and Team columns
        roster_df = df[['Player', 'Team']].copy()
        print(f"Initial data shape: {roster_df.shape}")
        
        # Group by Team and collect all players
        team_players = roster_df.groupby('Team')['Player'].apply(list).reset_index()
        print(f"Number of teams: {len(team_players)}")
        
        # Find maximum number of players per team
        max_players = team_players['Player'].apply(len).max()
        print(f"Maximum players per team: {max_players}")
        
        # Create player columns
        for i in range(max_players):
            col_name = f'Player {i+1}'
            team_players[col_name] = team_players['Player'].apply(
                lambda x: x[i] if i < len(x) else None
            )
        
        # Drop the list column
        self.rosters_df = team_players.drop('Player', axis=1)
        print(f"Final roster data shape: {self.rosters_df.shape}")
        
        # Save roster data
        roster_output = os.path.join(os.path.dirname(self.stats_file), 'team_rosters.csv')
        self.rosters_df.to_csv(roster_output, index=False)
        print(f"Saved team rosters to: {roster_output}")

    def load_data(self):
        """Load the scraped data from CSV."""
        self.df = pd.read_csv(self.input_file)
        print("Schedule data loaded successfully.")

    def clean_headers(self):
        """Remove rows that are headers within the data."""
        self.df = self.df[self.df['Date'] != 'Date']
        print("Header rows removed.")

    def filter_columns(self):
        """Retain only specified columns."""
        self.df = self.df[['Date', 'Visitor/Neutral', 'Home/Neutral']]
        print("Unnecessary columns dropped.")

    def replace_team_names(self):
        """Replace full team names with abbreviations."""
        self.df['Visitor/Neutral'] = self.df['Visitor/Neutral'].map(self.team_mapping).fillna(self.df['Visitor/Neutral'])
        self.df['Home/Neutral'] = self.df['Home/Neutral'].map(self.team_mapping).fillna(self.df['Home/Neutral'])
        print("Team names replaced with abbreviations.")

    def rename_columns(self):
        """Rename columns as specified."""
        self.df.rename(columns={
            'Date': 'date_next',
            'Visitor/Neutral': 'team_opp_next',
            'Home/Neutral': 'team_opp_next_rival'
        }, inplace=True)
        print("Columns renamed.")

    def format_and_sort_date(self):
        """Convert the date column to datetime format and sort by date."""
        self.df['date_next'] = pd.to_datetime(self.df['date_next'], errors='coerce')
        self.df.sort_values(by='date_next', inplace=True)
        print("Date column formatted and data sorted by date.")

    def filter_by_date_and_team(self):
        """Filter out past dates and keep only the first occurrence of each team."""
        today = pd.Timestamp(datetime.now().date())
        self.df = self.df[self.df['date_next'] >= today]
        self.df = self.df.drop_duplicates(subset=['team_opp_next_rival'], keep='first')
        print(f"Filtered data to future dates and unique teams.")

    def add_new_columns(self):
        """Add new columns: team_rival, home_next_rival, home_next."""
        self.df['team_rival'] = self.df['team_opp_next']
        self.df['home_next_rival'] = 1
        self.df['home_next'] = 0
        print("New columns added.")

    def merge_with_rosters(self):
        """Merge with team rosters."""
        rosters_columns = [col for col in self.rosters_df.columns if col not in ['Team']]
        self.df = pd.merge(
            self.df,
            self.rosters_df,
            left_on='team_opp_next_rival',
            right_on='Team',
            how='left'
        )
        self.df.drop(columns=['Team'], inplace=True)
        print("Merged with team rosters.")

    def save_data(self):
        """Save the cleaned data to a CSV file."""
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        self.df.to_csv(self.output_file, index=False)
        print(f"Cleaned and merged data saved to: {self.output_file}")

    def run(self):
        """Execute the entire data cleaning and merging process."""
        # First transform player stats into roster format
        self.transform_player_stats()
        
        # Then process schedule data
        self.load_data()
        self.clean_headers()
        self.filter_columns()
        self.replace_team_names()
        self.rename_columns()
        self.format_and_sort_date()
        self.filter_by_date_and_team()
        self.add_new_columns()
        self.merge_with_rosters()
        self.save_data()

# Usage
input_file = "Refresh/data/parsed_csvs/gameSchedules_csv/NBA_2025_games_schedule.csv"
output_file = "Refresh/data/preprocessed_cleaned_csv/NBA_2025_cleaned_schedule.csv"
stats_file = "Refresh/data/parsed_csvs/playerStats_csv/playerStats_2025.csv"

cleaner = GameScheduleCleaner(input_file, output_file, stats_file)
cleaner.run()