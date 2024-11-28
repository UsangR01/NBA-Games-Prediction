import pandas as pd

class GameScheduleCleaner:
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
        self.team_mapping = {
            "New York Knicks": "NYK", "Boston Celtics": "BOS", "Minnesota Timberwolves": "MIN",
            "Los Angeles Lakers": "LAL", "Brooklyn Nets": "BRK", "Atlanta Hawks": "ATL",
            "Indiana Pacers": "IND", "Detroit Pistons": "DET", "Charlotte Hornets": "CHA",
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

    def add_new_columns(self):
        """Add new columns: team_rival, home_next_rival, home_next."""
        self.df['team_rival'] = self.df['team_opp_next']
        self.df['home_next_rival'] = 1
        self.df['home_next'] = 0
        print("New columns added.")

    def format_date(self):
        """Convert the date column to datetime format."""
        self.df['date_next'] = pd.to_datetime(self.df['date_next'], errors='coerce')
        print("Date column formatted.")

    def sort_by_date(self):
        """Sort the DataFrame by the date column."""
        self.df.sort_values(by='date_next', inplace=True)
        print("Data sorted by date.")

    def drop_duplicates(self):
        """Keep only the first occurrence of each team in the home_next_rival column."""
        self.df.drop_duplicates(subset=['team_opp_next_rival'], keep='first', inplace=True)
        print("Duplicates removed based on home_next_rival column.")

    def save_data(self):
        """Save the cleaned data to a CSV file."""
        self.df.to_csv(self.output_file, index=False)
        print(f"Cleaned data saved to: {self.output_file}")

    def run(self):
        """Execute the entire data cleaning process."""
        self.load_data()
        self.clean_headers()
        self.filter_columns()
        self.replace_team_names()
        self.rename_columns()
        self.format_date()
        self.add_new_columns()
        self.drop_duplicates()
        self.sort_by_date()
        self.save_data()

# Usage
input_file = "Refresh/data/parsed_csvs/gameSchedules_csv/NBA_2025_games_schedule.csv"
output_file = "Refresh/data/preprocessed_cleaned_csv/NBA_2025_schedule.csv"

cleaner = GameScheduleCleaner(input_file, output_file)
cleaner.run()