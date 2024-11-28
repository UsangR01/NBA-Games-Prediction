import warnings
warnings.filterwarnings("ignore")

import os
import time
import random
import asyncio
from datetime import datetime, timedelta

SEASONS = [2025]

# Define the directory paths
DATA_DIR = "Refresh/data/scrapped_htmls"
STATS_DIR = os.path.join(DATA_DIR, "playerStats")

# Create the directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATS_DIR, exist_ok=True)

# File to store the list of scraped player stats
SCRAPED_STATS_FILE = os.path.join(DATA_DIR, "playerStats/scraped_player_stats.txt")

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

def load_scraped_stats():
    """Load previously scraped stats with timestamps"""
    stats_info = {}
    if os.path.exists(SCRAPED_STATS_FILE):
        with open(SCRAPED_STATS_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    season, timestamp = parts
                    stats_info[season] = float(timestamp)
    return stats_info

def save_scraped_stat(season):
    """Save scraped stat with timestamp"""
    current_time = time.time()
    with open(SCRAPED_STATS_FILE, "a") as f:
        f.write(f"{season},{current_time}\n")

# Initialize scraped stats dictionary
scraped_stats = load_scraped_stats()

async def get_html(url, min_sleep=5, max_sleep=10, retries=3):
    """Enhanced HTML fetching with better error handling"""
    for i in range(1, retries + 1):
        sleep_duration = random.uniform(min_sleep, max_sleep)
        time.sleep(sleep_duration)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(url)
                print(f"Accessing: {url}")
                html = await page.content()
                await browser.close()
                return html
        except PlaywrightTimeout:
            print(f"Timeout error on {url} (Attempt {i}/{retries})")
            if i == retries:
                print(f"Failed to fetch {url} after {retries} attempts")
                return None
        except Exception as e:
            print(f"Error accessing {url}: {str(e)}")
            if i == retries:
                return None
    return None

def should_update_stats(season):
    """Determine if stats for a season should be updated"""
    current_time = time.time()
    
    # If season hasn't been scraped before
    if str(season) not in scraped_stats:
        return True
    
    last_update = scraped_stats[str(season)]
    time_since_update = current_time - last_update
    
    # Current season: update every 6 hours
    if season == max(SEASONS):
        return time_since_update > (6 * 3600)  # 6 hours in seconds
    
    # Past seasons: update every 30 days
    return time_since_update > (30 * 24 * 3600)  # 30 days in seconds

async def scrape_player_stats(season):
    """Scrape player stats with smart updating"""
    if not should_update_stats(season):
        print(f"Skipping season {season} - recently updated")
        return False

    url = f"https://www.basketball-reference.com/leagues/NBA_{season}_advanced.html"
    html = await get_html(url)
    
    if not html:
        print(f"Failed to fetch stats for season {season}")
        return False

    save_path = os.path.join(STATS_DIR, f"{season}_player_stats.html")
    
    # Check if content has changed
    if os.path.exists(save_path):
        with open(save_path, "r", encoding='utf-8') as f:
            existing_content = f.read()
        if existing_content == html:
            print(f"No changes in stats for season {season}")
            scraped_stats[str(season)] = time.time()
            return False

    # Save new content
    with open(save_path, "w+", encoding='utf-8') as f:
        f.write(html)
        print(f"Updated player stats for season {season}")
    
    # Update tracking
    scraped_stats[str(season)] = time.time()
    save_scraped_stat(season)
    return True

async def main():
    """Main function for continuous monitoring"""
    while True:
        print("\nChecking for player stats updates...")
        updates_found = False
        
        for season in SEASONS:
            updated = await scrape_player_stats(season)
            if updated:
                updates_found = True
        
        if updates_found:
            print("Found updates. Waiting 5 minutes before next check...")
            await asyncio.sleep(300)  # 5 minutes
        else:
            print("No updates needed. Waiting 1 hour before next check...")
            await asyncio.sleep(3600)  # 1 hour

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()