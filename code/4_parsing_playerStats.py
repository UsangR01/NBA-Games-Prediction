import warnings
import pandas as pd
import os
from bs4 import BeautifulSoup

# Ignore warnings
warnings.filterwarnings('ignore')

# Constants
PARSED_FILES_LOG = "data/parsed_csvs/playerStats_csv/parsed_files.txt"
PLAYER_STATS_DIR = "data/scrapped_htmls/playerStats"
OUTPUT_DIR = "data/parsed_csvs/playerStats_csv"
COMBINED_OUTPUT_DIR = "data/parsed_csvs/playerStats_csv/combined_playerStats"
COMBINED_CSV_FILE = f"{COMBINED_OUTPUT_DIR}/playerStats_running.csv"

def load_parsed_files(log_file):
    """Load parsed files from the log."""
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_parsed_file(log_file, file_name):
    """Save a parsed file to the log."""
    with open(log_file, "a") as f:
        f.write(f"{file_name}\n")

def parse_player_stats_files(player_stats_dir, output_dir, parsed_files_log):
    """Parse player statistics HTML files and save them as CSV."""
    parsed_files = load_parsed_files(parsed_files_log)
    player_stats_files = os.listdir(player_stats_dir)

    for file_name in player_stats_files:
        file_path = os.path.join(player_stats_dir, file_name)
        
        if file_name in parsed_files:
            print(f"Skipping {file_name} as it has already been parsed.")
            continue

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

        output_file_name = file_name.replace(".html", ".csv")
        output_file_path = os.path.join(output_dir, output_file_name)
        os.makedirs(output_dir, exist_ok=True)

        df.to_csv(output_file_path, index=False)

        save_parsed_file(parsed_files_log, file_name)

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
    df = pd.DataFrame(table_data[1:], columns=table_data[0]).dropna(axis=1, how='all')
    df['Season Year'] = season_year
    return df

def combine_csv_files(input_dir, output_file):
    """Combine CSV files from a directory into a single CSV file."""
    csv_files = [file for file in os.listdir(input_dir) if file.endswith(".csv")]
    if not csv_files:
        print("No CSV files found to combine.")
        return

    combined_data = pd.concat(
        (pd.read_csv(os.path.join(input_dir, file)).dropna(axis=1, how='all') for file in csv_files),
        ignore_index=True
    )

    combined_data.to_csv(output_file, index=False)
    print(f"Combined CSV saved to {output_file}")

def main():
    """Main function to execute the script."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    parse_player_stats_files(PLAYER_STATS_DIR, OUTPUT_DIR, PARSED_FILES_LOG)

    os.makedirs(COMBINED_OUTPUT_DIR, exist_ok=True)
    combine_csv_files(OUTPUT_DIR, COMBINED_CSV_FILE)

if __name__ == "__main__":
    main()
