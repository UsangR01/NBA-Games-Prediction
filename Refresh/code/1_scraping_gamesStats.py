import warnings
warnings.filterwarnings("ignore")

import os
import time
import random
import asyncio

SEASONS = [2025]

# Define the directory paths
DATA_DIR = "Refresh/data/scrapped_htmls/boxscore_stats"
STANDINGS_DIR = os.path.join(DATA_DIR, "2025/standings")
SCORES_DIR = os.path.join(DATA_DIR, "2025/scores")

# File to store the list of scraped games
SCRAPED_GAMES_FILE = os.path.join(DATA_DIR, "2025/scraped_games.txt")

# Create the directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STANDINGS_DIR, exist_ok=True)
os.makedirs(SCORES_DIR, exist_ok=True)

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Load the list of scraped games from a file
def load_scraped_games():
    if os.path.exists(SCRAPED_GAMES_FILE):
        with open(SCRAPED_GAMES_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

# Save the list of scraped games to a file
def save_scraped_game(url):
    with open(SCRAPED_GAMES_FILE, "a") as f:
        f.write(f"{url}\n")

# Initialize scraped games set
scraped_games = load_scraped_games()

async def get_html(url, selector, min_sleep=5, max_sleep=10, retries=3):
    html = None
    for i in range(1, retries + 1):
        sleep_duration = random.uniform(min_sleep, max_sleep)
        time.sleep(sleep_duration)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(url)
                print(f"Accessing: {url}")
                html = await page.inner_html(selector)
                await browser.close()
                return html  # Return immediately after successful fetch
        except PlaywrightTimeout:
            print(f"Timeout error on {url} (Attempt {i}/{retries})")
            if i == retries:
                print(f"Failed to fetch {url} after {retries} attempts")
                return None
    return html

async def scrape_season(season):
    url = f"https://www.basketball-reference.com/leagues/NBA_{season}_games.html"
    html = await get_html(url, "#content .filter")
    if not html:
        print(f"Failed to fetch season page for {season}")
        return False

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a")
    standings_pages = [f"https://www.basketball-reference.com{l['href']}" for l in links]
    
    scraped_count = 0
    for url in standings_pages:
        save_path = os.path.join(STANDINGS_DIR, url.split("/")[-1])
        
        # Check if we need to update existing file (e.g., for ongoing month)
        should_scrape = not os.path.exists(save_path) or (
            "games-" in url.split("/")[-1] and 
            time.time() - os.path.getmtime(save_path) > 86400  # 24 hours
        )
        
        if should_scrape:
            html = await get_html(url, "#all_schedule")
            if html:
                with open(save_path, "w+") as f:
                    f.write(html)
                print(f"Scraped {url}")
                scraped_count += 1
            else:
                print(f"Failed to scrape {url}")
        else:
            print(f"Skipping {url} as it has already been scraped recently.")
    
    return scraped_count > 0

async def scrape_all_games():
    standings_files = os.listdir(STANDINGS_DIR)
    new_games_found = False
    
    for season in SEASONS:
        files = [s for s in standings_files if str(season) in s]
        
        for filename in files:
            filepath = os.path.join(STANDINGS_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                html = f.read()

            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a")
            hrefs = [l.get('href') for l in links]
            box_scores = [f"https://www.basketball-reference.com{l}" 
                         for l in hrefs if l and "boxscore" in l and '.html' in l]

            for url in box_scores:
                save_path = os.path.join(SCORES_DIR, url.split("/")[-1])
                
                # Check if this is a new game or needs updating
                if url not in scraped_games and not os.path.exists(save_path):
                    html = await get_html(url, "#content")
                    if html:
                        with open(save_path, "w+", encoding='utf-8') as f:
                            f.write(html)
                        print(f"Scraped new game: {url}")
                        scraped_games.add(url)
                        save_scraped_game(url)
                        new_games_found = True
                    else:
                        print(f"Failed to scrape {url}")
                else:
                    print(f"Skipping {url} - already scraped")
    
    return new_games_found

async def main():
    while True:
        print("\nChecking for new games...")
        # First check if we need to update the standings
        new_standings = await scrape_season(SEASONS[0])
        
        # Then check for new games
        new_games = await scrape_all_games()
        
        if not new_standings and not new_games:
            print("No new content found. Waiting before next check...")
            await asyncio.sleep(3600)  # Wait an hour before checking again
        else:
            print("Found new content. Continuing to check for more...")
            await asyncio.sleep(300)  # Wait 5 minutes before checking again

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()