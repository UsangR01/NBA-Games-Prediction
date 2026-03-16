import warnings
import pandas as pd
import os
from bs4 import BeautifulSoup, Comment
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

# Ignore warnings
warnings.filterwarnings('ignore')

@dataclass
class FileMetadata:
    """Data class to store file metadata"""
    name: str
    path: str
    modification_time: float

class PlayerStatsProcessor:
    """Main class to process player statistics files"""
    def __init__(self, input_dir: str, output_dir: str, force_process: bool = True):
        self.input_dir = input_dir
        self.base_output_dir = output_dir
        self.stats_output_dir = os.path.join(output_dir, "playerStats_csv")
        self.squad_output_dir = os.path.join(output_dir, "nbaInjuries_csv")
        self.parsed_files_log = os.path.join(self.stats_output_dir, "parsed_files.txt")
        self.parsed_files: Dict[str, float] = {}
        self.force_process = force_process
        self._ensure_directories()
        self._load_parsed_files()

    def _ensure_directories(self) -> None:
        """Create necessary output directories"""
        os.makedirs(self.stats_output_dir, exist_ok=True)
        os.makedirs(self.squad_output_dir, exist_ok=True)

    def _load_parsed_files(self) -> None:
        """Load previously parsed files from log"""
        if os.path.exists(self.parsed_files_log) and not self.force_process:
            with open(self.parsed_files_log, "r") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        self.parsed_files[parts[0]] = float(parts[1])

    def _save_parsed_file(self, file_name: str) -> None:
        """Record a newly parsed file"""
        current_time = datetime.now().timestamp()
        with open(self.parsed_files_log, "w" if self.force_process else "a") as f:
            f.write(f"{file_name},{current_time}\n")
        self.parsed_files[file_name] = current_time

    def _should_parse_file(self, metadata: FileMetadata) -> bool:
        """Determine if a file needs parsing based on modification time"""
        if not os.path.exists(metadata.path):
            return False
        if self.force_process:
            return True
        return (metadata.name not in self.parsed_files or 
                metadata.modification_time > self.parsed_files[metadata.name])

    def _parse_html_table(self, html_content: str) -> List[List[str]]:
        """Parse HTML content and extract table data"""
        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find("table", id="advanced")
        if not table:
            # Basketball-reference wraps tables inside HTML comments
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", id="advanced")
                if table:
                    break
        if not table:
            print("Table with id 'advanced' not found")
            return []

        data = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
                
            # Clean each cell's text
            row_data = []
            for cell in cells:
                # Remove any hidden elements
                for hidden in cell.find_all(class_="sr_share"):
                    hidden.decompose()
                row_data.append(cell.get_text(strip=True))
                
            if any(row_data):
                data.append(row_data)
        
        return data

    def _create_dataframe(self, table_data: List[List[str]], season_year: str) -> Optional[pd.DataFrame]:
        """Create DataFrame from table data"""
        if not table_data or len(table_data) < 2:
            print(f"Insufficient data rows found: {len(table_data) if table_data else 0}")
            return None
        
        df = pd.DataFrame(table_data[1:], columns=table_data[0])
        df = df.dropna(axis=1, how='all')
        df['Season'] = season_year
        df['Parsed_Date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
        return df

    def _process_team_squads(self, df: pd.DataFrame, max_players: int = 25) -> pd.DataFrame:
        """
        Create team squad data in wide format.
        
        Args:
            df (pd.DataFrame): Player statistics DataFrame
            max_players (int): Maximum number of players to include per team
            
        Returns:
            pd.DataFrame: Processed DataFrame with teams and their players
        """
        # Keep only Player and Team columns
        squad_df = df[['Player', 'Team']].copy()
        print(f"\nFound {len(squad_df)} players in total")
        
        # Group by team and aggregate players into lists
        team_players = squad_df.groupby('Team')['Player'].agg(list).reset_index()
        print(f"Processing {len(team_players)} teams")
        
        # Create columns for each player position (p1, p2, etc.)
        for i in range(max_players):
            col_name = f'p{i+1}'
            team_players[col_name] = team_players['Player'].apply(
                lambda x: x[i] if len(x) > i else None
            )
        
        # Drop the list column
        final_df = team_players.drop('Player', axis=1)
        
        # Remove the 'League Average' row if it exists
        final_df = final_df[~final_df['p1'].str.contains('League Average', na=False)]
        
        print(f"Created team squad data with shape {final_df.shape}")
        return final_df

    def process_file(self, file_metadata: FileMetadata) -> Optional[pd.DataFrame]:
        """Process a single file"""
        try:
            with open(file_metadata.path, encoding='utf-8') as f:
                html_content = f.read()

            print(f"Parsing HTML content from {file_metadata.name}...")
            table_data = self._parse_html_table(html_content)
            if not table_data:
                print(f"No data found in {file_metadata.name}, skipping...")
                return None

            season_year = file_metadata.name.split("_")[0][:4]
            df = self._create_dataframe(table_data, season_year)
            
            if df is not None:
                self._save_parsed_file(file_metadata.name)
                print(f"Successfully processed {file_metadata.name}")
            
            return df

        except Exception as e:
            print(f"Error processing {file_metadata.name}: {str(e)}")
            return None

    def process_all_files(self) -> None:
        """Process all HTML files in the input directory"""
        all_data_frames = []
        
        for file_name in os.listdir(self.input_dir):
            if not file_name.endswith('.html'):
                continue

            file_metadata = FileMetadata(
                name=file_name,
                path=os.path.join(self.input_dir, file_name),
                modification_time=os.path.getmtime(os.path.join(self.input_dir, file_name))
            )

            if not self._should_parse_file(file_metadata):
                print(f"Skipping {file_name} - no updates needed")
                continue

            print(f"\nProcessing {file_name}...")
            df = self.process_file(file_metadata)
            if df is not None:
                all_data_frames.append(df)

        if all_data_frames:
            # Combine all data frames
            combined_data = pd.concat(all_data_frames, ignore_index=True)
            
            # Save player stats
            stats_output = os.path.join(self.stats_output_dir, "playerStats_2025.csv")
            combined_data.to_csv(stats_output, index=False)
            print(f"\nPlayer stats saved to {stats_output}")
            
            # Process and save team squads
            squad_data = self._process_team_squads(combined_data)
            squad_output = os.path.join(self.squad_output_dir, "completeTeamSquad.csv")
            squad_data.to_csv(squad_output, index=False)
            print(f"Team squad data saved to {squad_output}")
        else:
            print("No new data to process")

def main():
    """Main function to execute the script"""
    BASE_DIR = "Refresh/data"
    processor = PlayerStatsProcessor(
        input_dir=f"{BASE_DIR}/scrapped_htmls/playerStats",
        output_dir=f"{BASE_DIR}/parsed_csvs",
        force_process=True  # Added force_process parameter
    )
    processor.process_all_files()

if __name__ == "__main__":
    main()