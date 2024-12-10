import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import os

@dataclass
class InjuryRecord:
    """Data class to store injury information for a player"""
    player: str
    team: str
    update_date: str
    description: str

class NBAInjuryScraper:
    """Class to handle scraping and processing of NBA injury data"""
    
    def __init__(self, url: str, output_dir: str):
        self.url = url
        self.output_dir = output_dir
        self._ensure_output_directory()
        
    def _ensure_output_directory(self) -> None:
        """Creates the output directory if it doesn't exist"""
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _fetch_page(self) -> Optional[str]:
        """
        Fetches the HTML content from the URL
        
        Returns:
            str: HTML content if successful, None otherwise
        """
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return None
            
    def _parse_html(self, html_content: str) -> BeautifulSoup:
        """
        Parses HTML content using BeautifulSoup
        
        Args:
            html_content (str): Raw HTML content
            
        Returns:
            BeautifulSoup: Parsed HTML object
        """
        return BeautifulSoup(html_content, 'html.parser')
        
    def _extract_table_data(self, soup: BeautifulSoup) -> List[InjuryRecord]:
        """
        Extracts injury data from the parsed HTML
        
        Args:
            soup (BeautifulSoup): Parsed HTML object
            
        Returns:
            List[InjuryRecord]: List of injury records
        """
        injuries = []
        table = soup.find('table', id='injuries')
        
        if not table:
            return injuries
            
        for row in table.find_all('tr', {'class': lambda x: x != 'thead'}):
            if not row.find('th'):  # Skip header rows
                continue
                
            cols = row.find_all(['th', 'td'])
            if len(cols) >= 4:
                player = cols[0].text.strip()
                team = cols[1].text.strip()
                update_date = cols[2].text.strip()
                description = cols[3].text.strip()
                
                injuries.append(InjuryRecord(
                    player=player,
                    team=team,
                    update_date=update_date,
                    description=description
                ))
                
        return injuries
        
    def _convert_to_dataframe(self, injuries: List[InjuryRecord]) -> pd.DataFrame:
        """
        Converts list of injury records to pandas DataFrame
        
        Args:
            injuries (List[InjuryRecord]): List of injury records
            
        Returns:
            pd.DataFrame: DataFrame containing injury data
        """
        return pd.DataFrame([vars(injury) for injury in injuries])

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process the DataFrame to clean and transform data
        
        Args:
            df (pd.DataFrame): Raw DataFrame
            
        Returns:
            pd.DataFrame: Processed DataFrame
        """
        # Remove duplicate header row if exists
        df = df[df['player'] != 'Player']
        
        # Split Description into Status and Description
        def split_description(text: str) -> Tuple[str, str]:
            parts = text.split(' (', 1)
            if len(parts) == 2:
                status = parts[0].strip()
                description = f"({parts[1]}"
            else:
                status = text
                description = ""
            return status, description
        
        # Apply the split function
        status_desc = df['description'].apply(split_description)
        df['Status'] = status_desc.apply(lambda x: x[0])
        df['Description'] = status_desc.apply(lambda x: x[1])
        
        # Reorder columns
        return df[['player', 'team', 'update_date', 'Status', 'Description']]

    def process_injured_players(self, df: pd.DataFrame, max_players: int = 10) -> pd.DataFrame:
        """
        Process injury data to create a wide format table of injured players by team.
        
        Args:
            df (pd.DataFrame): Raw injury data DataFrame
            max_players (int): Maximum number of players to include per team
            
        Returns:
            pd.DataFrame: Processed DataFrame with teams and their injured players
        """
        # 1. Filter for 'Out' status only
        out_players = df[df['Status'].str.contains('Out', case=False)].copy()
        
        # 2. Keep only player and team columns
        out_players = out_players[['player', 'team']].copy()
        
        # 3. Group by team and aggregate players into lists
        team_players = out_players.groupby('team')['player'].agg(list).reset_index()
        
        # 4. Create columns for each player position (p1, p2, etc.)
        for i in range(max_players):
            col_name = f'p{i+1}'
            team_players[col_name] = team_players['player'].apply(
                lambda x: x[i] if len(x) > i else None
            )
        
        # 5. Drop the list column and keep only team and player columns
        final_df = team_players.drop('player', axis=1)
        
        return final_df

    def save_to_csv(self, df: pd.DataFrame, filename: str) -> None:
        """
        Saves the DataFrame to csv in the specified output directory
        
        Args:
            df (pd.DataFrame): DataFrame to save
            filename (str): Name of the output file
        """
        output_path = os.path.join(self.output_dir, filename)
        df.to_csv(output_path, index=False)
        print(f"\nData saved to '{output_path}'")

    def scrape(self) -> Optional[pd.DataFrame]:
        """
        Main method to scrape NBA injury data
        
        Returns:
            Optional[pd.DataFrame]: DataFrame with injury data if successful, None otherwise
        """
        html_content = self._fetch_page()
        if not html_content:
            return None
            
        soup = self._parse_html(html_content)
        injuries = self._extract_table_data(soup)
        
        if not injuries:
            print("No injury data found")
            return None
            
        df = self._convert_to_dataframe(injuries)
        return self._process_dataframe(df)

def main():
    """Main function to demonstrate scraper usage"""
    # Define base directory and create full path for output
    base_dir = "Refresh/data/parsed_csvs/nbaInjuries_csv"
    
    url = "https://www.basketball-reference.com/friv/injuries.cgi"
    scraper = NBAInjuryScraper(url, output_dir=base_dir)
    
    # Scrape and process initial data
    df = scraper.scrape()
    
    if df is not None:
        print(f"Successfully scraped {len(df)} injury records")
        print("\nSample of the raw data:")
        print(df.head())
        
        # Save raw data
        scraper.save_to_csv(df, 'nba_injuries.csv')
        
        # Process data to get injured players by team
        processed_df = scraper.process_injured_players(df)
        print("\nSample of the processed data:")
        print(processed_df.head())
        
        # Save processed data
        scraper.save_to_csv(processed_df, 'nba_injuries_processed.csv')

if __name__ == "__main__":
    main()