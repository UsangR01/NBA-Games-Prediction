import requests
from bs4 import BeautifulSoup
import pdfplumber
import csv
import os
import re

class NBAInjuryReportScraper:
    nba_teams = [
        "Brooklyn Nets", "Philadelphia 76ers", "Boston Celtics", "Washington Wizards",
        "Golden State Warriors", "New Orleans Pelicans", "Atlanta Hawks", "Chicago Bulls",
        "Indiana Pacers", "Milwaukee Bucks", "Portland Trail Blazers", "Houston Rockets",
        "Dallas Mavericks", "Denver Nuggets", "Sacramento Kings", "LA Clippers",
        "New York Knicks", "Utah Jazz", "Detroit Pistons", "Orlando Magic", "Charlotte Hornets",
        "Memphis Grizzlies", "San Antonio Spurs", "Los Angeles Lakers",
        "Cleveland Cavaliers", "Toronto Raptors", "Miami Heat", "Minnesota Timberwolves",
        "Phoenix Suns", "Oklahoma City Thunder"
    ]
    
    def __init__(self, main_url):
        self.main_url = main_url
        self.pdf_url = None
        self.pdf_path = "latest_nba_injury_report.pdf"
        self.csv_path = "nba_injury_report.csv"

    def get_latest_report_url(self):
        """Fetch the latest injury report URL from the NBA website."""
        response = requests.get(self.main_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            update_section = soup.find("div", class_="col-xs-12 post-injury")
            if update_section:
                links = update_section.find_all("a")
                if links:
                    self.pdf_url = links[-1]['href']
                    print(f"Latest Report URL: {self.pdf_url}")
                    return True
        print("Failed to fetch the latest injury report URL.")
        return False

    def download_pdf(self):
        """Download the injury report PDF from the fetched URL."""
        if not self.pdf_url:
            print("No PDF URL to download.")
            return False
        response = requests.get(self.pdf_url)
        if response.status_code == 200:
            with open(self.pdf_path, "wb") as file:
                file.write(response.content)
            print(f"Downloaded injury report as '{self.pdf_path}'")
            return True
        print("Failed to download the injury report.")
        return False

    def clean_line(self, line):
        """Clean a line of text."""
        line = re.sub(r'Page \d+ of \d+', '', line)
        line = re.sub(r'Injury Report:.*?PM', '', line)
        return ' '.join(line.split()).strip()

    def _get_team_from_matchup(self, matchup, first_team=True):
        """Get full team name from matchup code."""
        try:
            team_code = matchup.split('@')[0] if first_team else matchup.split('@')[1]
            return next((team for team in self.nba_teams if team.split()[-1][:3] == team_code), None)
        except:
            return None

    def parse_player_line(self, line):
        """Parse a line containing player information."""
        # Try to match player info with team name included
        team_player_match = re.search(r'([A-Za-z\s]+)\s+([A-Za-z\s\',\.-]+)\s+(Out|Questionable|Probable|Available|Doubtful)\s*(.*)', line)
        if team_player_match:
            potential_team = team_player_match.group(1).strip()
            player = team_player_match.group(2).strip()
            status = team_player_match.group(3).strip()
            reason = team_player_match.group(4).strip()
        else:
            # Try to match just player info
            player_match = re.search(r'([A-Za-z\s\',\.-]+)\s+(Out|Questionable|Probable|Available|Doubtful)\s*(.*)', line)
            if player_match:
                potential_team = None
                player = player_match.group(1).strip()
                status = player_match.group(2).strip()
                reason = player_match.group(3).strip()
            else:
                return None, None, None, None
        
        return potential_team, player, status, reason

    def parse_pdf_to_csv(self):
        """Parse the downloaded PDF and save the data as a CSV."""
        with pdfplumber.open(self.pdf_path) as pdf:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["Game Date", "Game Time", "Matchup", "Team", "Player Name", "Current Status", "Reason"])
                
                current_game_info = None
                current_team = None
                header_found = False
                entries_buffer = []

                for page in pdf.pages:
                    text = page.extract_text()
                    lines = text.split('\n')
                    
                    for line in lines:
                        line = self.clean_line(line)
                        if not line or "NOT YET SUBMITTED" in line:
                            continue

                        if not header_found:
                            if "GameDate" in line and "GameTime" in line:
                                header_found = True
                            continue

                        # Match game info and team name
                        game_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}\(ET\))\s+([A-Z]{3}@[A-Z]{3})\s+([A-Za-z\s]+)', line)
                        if game_match:
                            self._write_buffered_entries(writer, entries_buffer)
                            entries_buffer = []
                            
                            current_game_info = game_match.groups()[:3]
                            team_name = game_match.group(4).strip()
                            current_team = next((team for team in self.nba_teams 
                                               if team.replace(" ", "").lower() in team_name.replace(" ", "").lower()), 
                                               self._get_team_from_matchup(current_game_info[2], True))
                            continue

                        # Match player info
                        potential_team, player, status, reason = self.parse_player_line(line)
                        if player and status:
                            # Check if we found a new team
                            if potential_team:
                                new_team = next((team for team in self.nba_teams 
                                               if team.replace(" ", "").lower() in potential_team.replace(" ", "").lower()),
                                               None)
                                if new_team:
                                    self._write_buffered_entries(writer, entries_buffer)
                                    entries_buffer = []
                                    current_team = new_team

                            entries_buffer.append({
                                'game_info': current_game_info,
                                'team': current_team,
                                'player': player.strip(),
                                'status': status.strip(),
                                'reason': [reason.strip()] if reason.strip() else []
                            })
                        elif entries_buffer:  # Continuation of reason
                            entries_buffer[-1]['reason'].append(line.strip())

                # Write remaining entries
                self._write_buffered_entries(writer, entries_buffer)

    def _write_buffered_entries(self, writer, entries):
        """Write buffered entries to CSV."""
        for entry in entries:
            if not entry['game_info'] or not entry['player']:
                continue
                
            reason = ' '.join(entry['reason']).strip()
            reason = re.sub(r'([A-Z][a-z]+,\s*[A-Z][a-z]+\s+(Out|Questionable|Probable|Available|Doubtful))', '', reason)
            reason = re.sub(r'\s+', ' ', reason).strip()
            
            # Clean up player name
            player_name = entry['player']
            player_name = re.sub(r'^.*?(?=[A-Z][a-z]+,)', '', player_name)
            player_name = re.sub(r'[A-Z]{3}@[A-Z]{3}\s*', '', player_name)
            
            writer.writerow([
                entry['game_info'][0],  # Game Date
                entry['game_info'][1],  # Game Time
                entry['game_info'][2],  # Matchup
                entry['team'],
                player_name.strip(),
                entry['status'],
                reason
            ])

    def run(self):
        """Main function to run the scraping and parsing process."""
        if self.get_latest_report_url() and self.download_pdf():
            self.parse_pdf_to_csv()
            print(f"Successfully created CSV file at {self.csv_path}")

# Instantiate and run the scraper
if __name__ == "__main__":
    scraper = NBAInjuryReportScraper(main_url="https://official.nba.com/nba-injury-report-2024-25-season/")
    scraper.run()