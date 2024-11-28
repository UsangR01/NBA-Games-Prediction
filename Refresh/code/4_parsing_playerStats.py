import warnings
import pandas as pd
import os
from bs4 import BeautifulSoup
from datetime import datetime

# Ignore warnings
warnings.filterwarnings('ignore')

# Constants
BASE_DIR = "Refresh/data/parsed_csvs/playerStats_csv"
PARSED_FILES_LOG = f"{BASE_DIR}/parsed_files.txt"
PLAYER_STATS_DIR = "Refresh/data/scrapped_htmls/playerStats"
PLAYER_STATS_CSV_FILE = f"{BASE_DIR}/playerStats_2025.csv"

def ensure_directory_exists(directory):
    """Ensure the directory exists, if not, create it."""
    os.makedirs(directory, exist_ok=True)

def load_parsed_files():
    """Load parsed files with timestamps from the log."""
    parsed_files = {}
    if os.path.exists(PARSED_FILES_LOG):
        with open(PARSED_FILES_LOG, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    file_name, timestamp = parts
                    parsed_files[file_name] = float(timestamp)
    return parsed_files

def save_parsed_file(file_name):
    """Save a parsed file with timestamp to the log."""
    current_time = datetime.now().timestamp()
    ensure_directory_exists(os.path.dirname(PARSED_FILES_LOG))
    with open(PARSED_FILES_LOG, "a") as f:
        f.write(f"{file_name},{current_time}\n")

def should_parse_file(file_name, file_path, parsed_files):
    """Determine if a file should be parsed based on modification time."""
    if not os.path.exists(file_path):
        return False
    
    current_mtime = os.path.getmtime(file_path)
    
    # If file hasn't been parsed before or has been modified
    if file_name not in parsed_files:
        return True
    
    return current_mtime > parsed_files[file_name]

def remove_header_rows(soup):
    """Remove header rows from the soup object."""
    rows_to_remove = [row.get("data-row") for row in soup.select("tr.thead") if row.get("data-row")]
    for row in soup.select("tr"):
        if row.get("data-row") in rows_to_remove:
            row.decompose()

def extract_table_data(soup, table_id):
    """Extract table data from the soup object."""
    table = soup.find("table", id=table_id)
    if not table:
        return []

    return [
        [cell.text.strip() for cell in row.find_all(["th", "td"])]
        for row in table.find_all("tr")
        if row.find_all(["th", "td"])
    ]

def create_dataframe(table_data, season_year):
    """Create a DataFrame from table data and add the season year."""
    if not table_data or len(table_data) < 2:
        return None
    
    df = pd.DataFrame(table_data[1:], columns=table_data[0]).dropna(axis=1, how='all')
    df['Season'] = season_year
    df['Parsed_Date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return df

def parse_player_stats_files():
    """Parse player statistics HTML files and save to CSV."""
    parsed_files = load_parsed_files()
    new_data_frames = []
    files_processed = 0

    for file_name in os.listdir(PLAYER_STATS_DIR):
        if not file_name.endswith('.html'):
            continue

        file_path = os.path.join(PLAYER_STATS_DIR, file_name)

        if not should_parse_file(file_name, file_path, parsed_files):
            print(f"Skipping {file_name} - no updates needed")
            continue

        try:
            with open(file_path, encoding='utf-8') as f:
                html = f.read()

            soup = BeautifulSoup(html, "html.parser")
            remove_header_rows(soup)

            table_data = extract_table_data(soup, 'advanced_stats')

            if not table_data:
                print(f"No data found in {file_name}, skipping...")
                continue

            season_year = file_name.split("_")[0][:4]
            df = create_dataframe(table_data, season_year)

            if df is not None:
                new_data_frames.append(df)
                save_parsed_file(file_name)
                files_processed += 1

                if files_processed % 5 == 0:
                    print(f"Processed {files_processed} files...")

        except Exception as e:
            print(f"Error processing {file_name}: {str(e)}")
            continue

    if new_data_frames:
        print("\nSaving extracted data to CSV...")
        try:
            # Combine all new data
            new_data = pd.concat(new_data_frames, ignore_index=True)
            new_data.to_csv(PLAYER_STATS_CSV_FILE, index=False)
            print(f"\nSuccessfully processed {files_processed} files:")
            print(f"- {len(new_data)} new or updated player records saved to CSV")
        except Exception as e:
            print(f"Error saving data to CSV: {str(e)}")
    else:
        print("No new data to process")

def main():
    """Main function to execute the script."""
    ensure_directory_exists(BASE_DIR)
    parse_player_stats_files()

if __name__ == "__main__":
    main()