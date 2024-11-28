import warnings
warnings.filterwarnings("ignore")

import os
import time
import random

# SEASONS = list(range(2014, 2025))  # Update the seasons range
SEASONS = [2025]

# Define the directory paths
DATA_DIR = "data/scrapped_htmls"
STATS_DIR = os.path.join(DATA_DIR, "playerStats")

# Create the directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATS_DIR, exist_ok=True)

# File to store the list of scraped player stats
SCRAPED_STATS_FILE = os.path.join(DATA_DIR, "playerStats/scraped_player_stats.txt")

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Load the list of scraped seasons from a file
def load_scraped_seasons():
    if os.path.exists(SCRAPED_STATS_FILE):
        with open(SCRAPED_STATS_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

# Save the scraped season to a file
def save_scraped_season(season):
    with open(SCRAPED_STATS_FILE, "a") as f:
        f.write(f"{season}\n")

# Maintain a set of scraped seasons
scraped_seasons = load_scraped_seasons()

async def get_html(url, min_sleep=5, max_sleep=10, retries=3):
    html = None
    for i in range(1, retries + 1):
        sleep_duration = random.uniform(min_sleep, max_sleep)
        time.sleep(sleep_duration)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(url)
                print(await page.title())
                html = await page.content()
        except PlaywrightTimeout:
            print(f"Timeout error on {url}")
            continue
        else:
            break
    return html

async def scrape_player_stats(season):
    url = f"https://www.basketball-reference.com/leagues/NBA_{season}_advanced.html"

    # Skip if the season has already been scraped
    if str(season) in scraped_seasons:
        print(f"Skipping season {season} as it has already been scraped.")
        return

    html = await get_html(url)

    save_path = os.path.join(STATS_DIR, f"{season}_player_stats.html")
    with open(save_path, "w+", encoding='utf-8') as f:
        f.write(html)
        print(f"Scraped player stats for season {season}")

    # Mark this season as scraped
    scraped_seasons.add(str(season))
    save_scraped_season(season)

import asyncio
import nest_asyncio

nest_asyncio.apply()

async def scrape_seasons():
    for season in SEASONS:
        await scrape_player_stats(season)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(scrape_seasons())
    loop.close()
