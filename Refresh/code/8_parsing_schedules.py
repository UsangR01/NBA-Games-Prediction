import os
from bs4 import BeautifulSoup
import pandas as pd

class GameScheduleScraper:
    def __init__(self, html_dir, output_dir):
        self.html_dir = html_dir
        self.output_dir = output_dir
        self.output_csv = os.path.join(output_dir, "NBA_2025_games_schedule.csv")
        self.output_txt = os.path.join(output_dir, "scraped_games.txt")
        self.all_games = []

        # Ensure the output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def extract_table(self, file_path):
        """Parse HTML file and extract the schedule table."""
        with open(file_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find("table", {"id": "schedule"})
        
        if not table:
            print(f"No table found in {file_path}")
            return None

        headers = [th.text.strip() for th in table.find("thead").find_all("th")]
        rows = []

        for tr in table.find("tbody").find_all("tr"):
            row = [td.text.strip() for td in tr.find_all(["th", "td"])]
            rows.append(row)

        return pd.DataFrame(rows, columns=headers)

    def scrape_all_files(self):
        """Iterate through all HTML files and extract data."""
        for filename in os.listdir(self.html_dir):
            if filename.endswith(".html"):
                file_path = os.path.join(self.html_dir, filename)
                df = self.extract_table(file_path)
                if df is not None:
                    self.all_games.append(df)
                    print(f"Scraped {len(df)} rows from {filename}")

    def save_to_csv(self):
        """Save the concatenated DataFrame to a CSV file."""
        if not self.all_games:
            print("No data to save.")
            return

        final_df = pd.concat(self.all_games, ignore_index=True)
        final_df.to_csv(self.output_csv, index=False)
        print(f"Data saved to: {self.output_csv}")

    def save_scraped_files_list(self):
        """Save the list of parsed HTML files to a text file."""
        with open(self.output_txt, "w") as f:
            for filename in os.listdir(self.html_dir):
                if filename.endswith(".html"):
                    f.write(filename + "\n")
        print(f"Parsed files list saved to: {self.output_txt}")

    def run(self):
        """Main method to run the entire scraping process."""
        self.scrape_all_files()
        self.save_to_csv()
        self.save_scraped_files_list()

# Define paths
HTML_DIR = r"Refresh/data/scrapped_htmls/boxscore_stats/2025/standings"
OUTPUT_DIR = r"Refresh/data/parsed_csvs/gameSchedules_csv"

# Create an instance of the scraper and run it
scraper = GameScheduleScraper(HTML_DIR, OUTPUT_DIR)
scraper.run()