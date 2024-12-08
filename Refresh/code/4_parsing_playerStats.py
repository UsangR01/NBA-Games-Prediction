# Import statements
import warnings
import pandas as pd
import os
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Ignore warnings
warnings.filterwarnings('ignore')

@dataclass
class FileMetadata:
    """Data class to store file metadata"""
    name: str
    path: str
    modification_time: float

class FileTracker:
    """Class to track parsed files and their timestamps"""
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.parsed_files: Dict[str, float] = {}
        self._load_parsed_files()

    def _load_parsed_files(self) -> None:
        """Load previously parsed files from log"""
        if os.path.exists(self.log_file_path):
            with open(self.log_file_path, "r") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        self.parsed_files[parts[0]] = float(parts[1])

    def save_parsed_file(self, file_name: str) -> None:
        """Record a newly parsed file"""
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
        current_time = datetime.now().timestamp()
        with open(self.log_file_path, "a") as f:
            f.write(f"{file_name},{current_time}\n")
        self.parsed_files[file_name] = current_time

    def should_parse_file(self, metadata: FileMetadata) -> bool:
        """Determine if a file needs parsing based on modification time"""
        if not os.path.exists(metadata.path):
            return False
        return (metadata.name not in self.parsed_files or 
                metadata.modification_time > self.parsed_files[metadata.name])

class HTMLParser(ABC):
    """Abstract base class for HTML parsing"""
    @abstractmethod
    def parse(self, html_content: str) -> List[List[str]]:
        pass

class PlayerStatsParser(HTMLParser):
    """Parser specifically for basketball player statistics"""
    def __init__(self, table_id: str = "advanced"):
        self.table_id = table_id

    def _remove_header_rows(self, soup: BeautifulSoup) -> None:
        """Remove duplicate header rows from the table"""
        rows_to_remove = [row.get("data-row") for row in soup.select("tr.thead") 
                         if row.get("data-row")]
        for row in soup.select("tr"):
            if row.get("data-row") in rows_to_remove:
                row.decompose()

    def _clean_cell_text(self, cell) -> str:
        """Clean text content from a table cell"""
        # Remove any hidden elements
        for hidden in cell.find_all(class_="sr_share"):
            hidden.decompose()
        return cell.get_text(strip=True)

    def parse(self, html_content: str) -> List[List[str]]:
        """Parse HTML content and extract table data"""
        soup = BeautifulSoup(html_content, "html.parser")
        self._remove_header_rows(soup)
        
        table = soup.find("table", id=self.table_id)
        if not table:
            print(f"Table with id '{self.table_id}' not found")
            return []

        data = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
                
            row_data = [self._clean_cell_text(cell) for cell in cells]
            if any(row_data):
                data.append(row_data)
        
        return data

class DataFrameBuilder:
    """Class to build and manage DataFrames"""
    @staticmethod
    def create_dataframe(table_data: List[List[str]], season_year: str) -> Optional[pd.DataFrame]:
        """Create DataFrame from parsed table data"""
        if not table_data or len(table_data) < 2:
            print(f"Insufficient data rows found: {len(table_data) if table_data else 0}")
            return None
        
        df = pd.DataFrame(table_data[1:], columns=table_data[0])
        df = df.dropna(axis=1, how='all')
        
        # Add metadata
        df['Season'] = season_year
        df['Parsed_Date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
        return df

class PlayerStatsProcessor:
    """Main class to process player statistics files"""
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = input_dir
        self.output_dir = os.path.join(output_dir, "playerStats_csv")
        self.file_tracker = FileTracker(os.path.join(self.output_dir, "parsed_files.txt"))
        self.parser = PlayerStatsParser()
        self.new_data_frames: List[pd.DataFrame] = []
        self.files_processed = 0

    def _get_season_year(self, file_name: str) -> str:
        """Extract season year from filename"""
        return file_name.split("_")[0][:4]

    def process_file(self, file_metadata: FileMetadata) -> None:
        """Process a single file"""
        try:
            with open(file_metadata.path, encoding='utf-8') as f:
                html_content = f.read()

            table_data = self.parser.parse(html_content)
            if not table_data:
                print(f"No data found in {file_metadata.name}, skipping...")
                return

            season_year = self._get_season_year(file_metadata.name)
            df = DataFrameBuilder.create_dataframe(table_data, season_year)

            if df is not None:
                self.new_data_frames.append(df)
                self.file_tracker.save_parsed_file(file_metadata.name)
                self.files_processed += 1
                print(f"Successfully processed {file_metadata.name}")

        except Exception as e:
            print(f"Error processing {file_metadata.name}: {str(e)}")

    def save_results(self) -> None:
        """Save processed data to CSV"""
        if not self.new_data_frames:
            print("No new data to process")
            return

        try:
            output_file = os.path.join(self.output_dir, "playerStats_2025.csv")
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            combined_data = pd.concat(self.new_data_frames, ignore_index=True)
            combined_data.to_csv(output_file, index=False)
            
            print(f"\nSuccessfully processed {self.files_processed} files:")
            print(f"- {len(combined_data)} new or updated player records saved to CSV")
        except Exception as e:
            print(f"Error saving data to CSV: {str(e)}")

    def process_all_files(self) -> None:
        """Process all HTML files in the input directory"""
        for file_name in os.listdir(self.input_dir):
            if not file_name.endswith('.html'):
                continue

            file_metadata = FileMetadata(
                name=file_name,
                path=os.path.join(self.input_dir, file_name),
                modification_time=os.path.getmtime(os.path.join(self.input_dir, file_name))
            )

            if not self.file_tracker.should_parse_file(file_metadata):
                print(f"Skipping {file_name} - no updates needed")
                continue

            print(f"\nProcessing {file_name}...")
            self.process_file(file_metadata)

        self.save_results()

def main():
    """Main function to execute the script"""
    BASE_DIR = "Refresh/data"
    processor = PlayerStatsProcessor(
        input_dir=f"{BASE_DIR}/scrapped_htmls/playerStats",
        output_dir=f"{BASE_DIR}/parsed_csvs"
    )
    processor.process_all_files()

if __name__ == "__main__":
    main()