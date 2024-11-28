import pandas as pd
from datetime import datetime

class GameScheduleCleaner:
    def __init__(self, input_file, output_file, lineup_file):
        self.input_file = input_file
        self.output_file = output_file
        self.lineup_file = lineup_file
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

    def load_data(self):
        """Load the scraped data from CSV."""
        self.df = pd.read_csv(self.input_file)
        self.lineup_df = pd.read_csv(self.lineup_file)
        print("Data loaded successfully.")

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
        # Get today's date
        today = pd.Timestamp(datetime.now().date())

        # Filter out rows where date_next is less than today
        self.df = self.df[self.df['date_next'] >= today]
        print(f"Filtered out rows where 'date_next' is before {today}.")

        # Keep only the first occurrence of each team in 'team_opp_next_rival'
        self.df = self.df.drop_duplicates(subset=['team_opp_next_rival'], keep='first')
        print("Kept only the first occurrence of each team.")

    def add_new_columns(self):
        """Add new columns: team_rival, home_next_rival, home_next."""
        self.df['team_rival'] = self.df['team_opp_next']
        self.df['home_next_rival'] = 1
        self.df['home_next'] = 0
        print("New columns added.")

    def merge_with_last_lineup(self):
        """Merge with the last occurrence of each team from the gameLineup data."""
        # Convert the date column to datetime format
        self.lineup_df['Date'] = pd.to_datetime(self.lineup_df['Date'], errors='coerce')

        # Extract the last occurrence of each team from the lineup DataFrame
        last_lineup_df = self.lineup_df.sort_values(by='Date').groupby('Team').last().reset_index()

        # Drop 'Team' and date columns, keep only the lineup-related columns
        lineup_columns = [col for col in last_lineup_df.columns if col not in ['Team', 'Date']]

        # Merge the cleaned schedule DataFrame with the lineup columns
        self.df = pd.merge(
            self.df,
            last_lineup_df[lineup_columns + ['Team']],
            left_on='team_opp_next_rival',
            right_on='Team',
            how='left'
        )

        # Drop the 'Team' column after the merge
        self.df.drop(columns=['Team'], inplace=True)
        print("Merged with the last occurrence of each team, retaining only the lineup columns.")

    def save_data(self):
        """Save the cleaned data to a CSV file."""
        self.df.to_csv(self.output_file, index=False)
        print(f"Cleaned and merged data saved to: {self.output_file}")

    def run(self):
        """Execute the entire data cleaning and merging process."""
        self.load_data()
        self.clean_headers()
        self.filter_columns()
        self.replace_team_names()
        self.rename_columns()
        self.format_and_sort_date()
        self.filter_by_date_and_team()
        self.add_new_columns()
        self.merge_with_last_lineup()
        self.save_data()

# Usage
input_file = "Refresh/data/parsed_csvs/gameSchedules_csv/NBA_2025_games_schedule.csv"
output_file = "Refresh/data/preprocessed_cleaned_csv/NBA_2025_cleaned_schedule.csv"
lineup_file = "Refresh/data/parsed_csvs/gameLineup_csv/gameLineup_2025.csv"

cleaner = GameScheduleCleaner(input_file, output_file, lineup_file)
cleaner.run()