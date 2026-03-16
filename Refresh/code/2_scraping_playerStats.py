import warnings
warnings.filterwarnings("ignore")

import os
import time
import random
import asyncio
import argparse
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


# ---------------------------------------------------------------------------
# Season detection
# ---------------------------------------------------------------------------
def get_current_season():
    """Basketball-reference season label: Jan-Jun -> same year, Jul-Dec -> year+1."""
    now = datetime.now()
    return now.year if now.month <= 6 else now.year + 1


_current = get_current_season()
SEASONS = sorted({_current - 1, _current})

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR  = "Refresh/data/scrapped_htmls"
STATS_DIR = os.path.join(DATA_DIR, "playerStats")
SCRAPED_STATS_FILE = os.path.join(STATS_DIR, "scraped_player_stats.txt")

os.makedirs(STATS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Tracking helpers
# ---------------------------------------------------------------------------
def load_scraped_stats():
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
    with open(SCRAPED_STATS_FILE, "a") as f:
        f.write(f"{season},{time.time()}\n")

scraped_stats = load_scraped_stats()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
async def get_html(url, min_sleep=5, max_sleep=10, retries=3):
    for i in range(1, retries + 1):
        time.sleep(random.uniform(min_sleep, max_sleep))
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=60000)
                print(f"Accessing: {url}")
                html = await page.content()
                await browser.close()
                return html
        except PlaywrightTimeout:
            print(f"Timeout error on {url} (Attempt {i}/{retries})")
            if i == retries:
                return None
        except Exception as e:
            print(f"Error accessing {url}: {str(e)}")
            if i == retries:
                return None
    return None


# ---------------------------------------------------------------------------
# Scraping logic
# ---------------------------------------------------------------------------
def should_update_stats(season, force=False):
    if force:
        return True
    if str(season) not in scraped_stats:
        return True
    age = time.time() - scraped_stats[str(season)]
    # Current season: refresh every 6 hours; past seasons: every 30 days
    if season == _current:
        return age > 6 * 3600
    return age > 30 * 24 * 3600


async def scrape_player_stats(season, force=False):
    if not should_update_stats(season, force):
        print(f"Skipping season {season} — recently updated")
        return False

    url = f"https://www.basketball-reference.com/leagues/NBA_{season}_advanced.html"
    html = await get_html(url)
    if not html:
        print(f"Failed to fetch stats for season {season}")
        return False

    save_path = os.path.join(STATS_DIR, f"{season}_player_stats.html")
    if os.path.exists(save_path):
        with open(save_path, "r", encoding="utf-8") as f:
            if f.read() == html:
                print(f"No changes for season {season}")
                scraped_stats[str(season)] = time.time()
                return False

    with open(save_path, "w+", encoding="utf-8") as f:
        f.write(html)
    print(f"Updated player stats for season {season}")
    scraped_stats[str(season)] = time.time()
    save_scraped_stat(season)
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def run_once():
    print(f"\nScraping player stats for seasons: {SEASONS}")
    for season in SEASONS:
        await scrape_player_stats(season, force=False)
    print("\nSingle-pass player stats scrape complete.")


async def run_continuous():
    while True:
        print("\nChecking for player stats updates...")
        updates_found = any([
            await scrape_player_stats(season) for season in SEASONS
        ])
        wait = 300 if updates_found else 3600
        print(f"Waiting {wait // 60} minutes...")
        await asyncio.sleep(wait)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single scraping pass and exit (default: continuous loop)."
    )
    args = parser.parse_args()

    if args.once:
        await run_once()
    else:
        await run_continuous()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
