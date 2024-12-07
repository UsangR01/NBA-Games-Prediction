import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class InjuryRecord:
    """Data class to store injury information for a player"""
    player: str
    team: str
    update_date: str
    description: str

class NBAInjuryScraper:
    """Class to handle scraping and processing of NBA injury data"""
    
    def __init__(self, url: str):
        self.url = url
        
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
    url = "https://www.basketball-reference.com/friv/injuries.cgi"
    scraper = NBAInjuryScraper(url)
    df = scraper.scrape()
    
    if df is not None:
        print(f"Successfully scraped {len(df)} injury records")
        print("\nSample of the data:")
        print(df.head())
        
        # Optional: Save to CSV
        df.to_csv('nba_injuries.csv', index=False)
        print("\nData saved to 'nba_injuries.csv'")

if __name__ == "__main__":
    main()