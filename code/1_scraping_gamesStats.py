import warnings
warnings.filterwarnings("ignore")

import os
import time
import random
import asyncio

# SEASONS = list(range(2014, 2024))
SEASONS = [2025]

# Define the directory paths
DATA_DIR = "data/scrapped_htmls/boxscore_stats"
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

# Maintain a set of scraped games
scraped_games = load_scraped_games()

async def get_html(url, selector, min_sleep=5, max_sleep=10, retries=3):
    # Function to retrieve HTML content from a URL using Playwright
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
                html = await page.inner_html(selector)
        except PlaywrightTimeout:
            print(f"Timeout error on {url}")
            continue
        else:
            break
    return html

async def scrape_season(season):
    # Function to scrape season standings
    url = f"https://www.basketball-reference.com/leagues/NBA_{season}_games.html"
    html = await get_html(url, "#content .filter")

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a")
    standings_pages = [f"https://www.basketball-reference.com{l['href']}" for l in links]

    for url in standings_pages:
        save_path = os.path.join(STANDINGS_DIR, url.split("/")[-1])
        # Skip if the game URL is in the set or file already exists
        if os.path.exists(save_path):
            print(f"Skipping {url} as it has already been scraped.")
            continue

        html = await get_html(url, "#all_schedule")
        with open(save_path, "w+") as f:
            f.write(html)
            print(f"Scraped {url}")

async def scrape_game(standings_file):
    # Function to scrape individual game details
    with open(standings_file, 'r') as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a")
    hrefs = [l.get('href') for l in links]
    box_scores = [f"https://www.basketball-reference.com{l}" for l in hrefs if l and "boxscore" in l and '.html' in l]

    for url in box_scores:
        save_path = os.path.join(SCORES_DIR, url.split("/")[-1])
        # Skip if the game URL is in the set or file already exists
        if url in scraped_games or os.path.exists(save_path):
            print(f"Skipping {url} as it has already been scraped.")
            continue

        html = await get_html(url, "#content")
        if not html:
            continue
        with open(save_path, "w+", encoding='utf-8') as f:
            f.write(html)
            print(f"Scraped {url}")
        # Add the scraped game URL to the set and save to the file
        scraped_games.add(url)
        save_scraped_game(url)

async def scrape_all_games():
    # Function to scrape all games in a season
    standings_files = os.listdir(STANDINGS_DIR)
    for season in SEASONS:
        files = [s for s in standings_files if str(season) in s]

        for f in files:
            filepath = os.path.join(STANDINGS_DIR, f)
            # Read the local file directly
            with open(filepath, "r", encoding="utf-8") as f:
                html = f.read()

            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a")
            hrefs = [l.get('href') for l in links]
            box_scores = [f"https://www.basketball-reference.com{l}" for l in hrefs if l and "boxscore" in l and '.html' in l]

            for url in box_scores:
                save_path = os.path.join(SCORES_DIR, url.split("/")[-1])
                # Skip if the game URL is in the set or file already exists
                if url in scraped_games or os.path.exists(save_path):
                    print(f"Skipping {url} as it has already been scraped.")
                    continue

                html = await get_html(url, "#content")
                if not html:
                    continue
                with open(save_path, "w+", encoding='utf-8') as f:
                    f.write(html)
                    print(f"Scraped {url}")
                # Add the scraped game URL to the set and save to the file
                scraped_games.add(url)
                save_scraped_game(url)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(scrape_season(SEASONS[0]))  # Assuming SEASONS is a list containing only one season
    loop.run_until_complete(scrape_all_games())
    loop.close()
