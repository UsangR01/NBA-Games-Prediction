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
# Scrape the previous complete season AND the current one
SEASONS = sorted({_current - 1, _current})

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = "Refresh/data/scrapped_htmls/boxscore_stats"

for _s in SEASONS:
    os.makedirs(os.path.join(DATA_DIR, str(_s), "standings"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, str(_s), "scores"), exist_ok=True)


def standings_dir(season):
    return os.path.join(DATA_DIR, str(season), "standings")

def scores_dir(season):
    return os.path.join(DATA_DIR, str(season), "scores")

def scraped_games_file(season):
    return os.path.join(DATA_DIR, str(season), "scraped_games.txt")


# ---------------------------------------------------------------------------
# Tracking helpers
# ---------------------------------------------------------------------------
def load_scraped_games(season):
    path = scraped_games_file(season)
    if os.path.exists(path):
        with open(path, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_scraped_game(url, season):
    with open(scraped_games_file(season), "a") as f:
        f.write(f"{url}\n")

scraped_games = {s: load_scraped_games(s) for s in SEASONS}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
async def get_html(url, selector, min_sleep=5, max_sleep=10, retries=3):
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
                html = await page.inner_html(selector)
                await browser.close()
                return html
        except PlaywrightTimeout:
            print(f"Timeout error on {url} (Attempt {i}/{retries})")
            if i == retries:
                print(f"Failed to fetch {url} after {retries} attempts")
                return None
    return None


# ---------------------------------------------------------------------------
# Scraping logic
# ---------------------------------------------------------------------------
async def scrape_season(season):
    """Fetch monthly standings/schedule pages for a season."""
    url = f"https://www.basketball-reference.com/leagues/NBA_{season}_games.html"
    html = await get_html(url, "#content .filter")
    if not html:
        print(f"Failed to fetch season page for {season}")
        return False

    soup = BeautifulSoup(html, "html.parser")
    standings_pages = [
        f"https://www.basketball-reference.com{l['href']}"
        for l in soup.find_all("a")
    ]

    scraped_count = 0
    sdir = standings_dir(season)
    for page_url in standings_pages:
        save_path = os.path.join(sdir, page_url.split("/")[-1])
        should_scrape = not os.path.exists(save_path) or (
            "games-" in page_url.split("/")[-1] and
            time.time() - os.path.getmtime(save_path) > 86400  # 24 hours
        )
        if should_scrape:
            html = await get_html(page_url, "#all_schedule")
            if html:
                with open(save_path, "w+") as f:
                    f.write(html)
                print(f"Scraped standings: {page_url}")
                scraped_count += 1
            else:
                print(f"Failed to scrape: {page_url}")
        else:
            print(f"Skipping (recent): {page_url}")

    return scraped_count > 0


async def scrape_all_games():
    """Scrape individual box score pages for all seasons."""
    new_games_found = False

    for season in SEASONS:
        sdir = standings_dir(season)
        sc_dir = scores_dir(season)

        if not os.path.exists(sdir):
            print(f"No standings directory for season {season}, skipping.")
            continue

        for filename in os.listdir(sdir):
            filepath = os.path.join(sdir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                html = f.read()

            soup = BeautifulSoup(html, "html.parser")
            hrefs = [l.get("href") for l in soup.find_all("a")]
            box_scores = [
                f"https://www.basketball-reference.com{l}"
                for l in hrefs if l and "boxscore" in l and ".html" in l
            ]

            for url in box_scores:
                save_path = os.path.join(sc_dir, url.split("/")[-1])
                if url not in scraped_games[season] and not os.path.exists(save_path):
                    html = await get_html(url, "#content")
                    if html:
                        with open(save_path, "w+", encoding="utf-8") as f:
                            f.write(html)
                        print(f"Scraped game: {url}")
                        scraped_games[season].add(url)
                        save_scraped_game(url, season)
                        new_games_found = True
                    else:
                        print(f"Failed to scrape: {url}")
                else:
                    print(f"Skipping (exists): {url}")

    return new_games_found


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def run_once():
    """Single pass: update standings then scrape any missing game HTML."""
    print(f"\nScraping seasons: {SEASONS}")
    for season in SEASONS:
        print(f"\n-- Fetching standings for {season} --")
        await scrape_season(season)
    print("\n-- Scraping missing box scores --")
    await scrape_all_games()
    print("\nSingle-pass scrape complete.")


async def run_continuous():
    """Continuous mode: loop indefinitely checking for new games."""
    while True:
        print("\nChecking for new games...")
        new_standings = False
        for season in SEASONS:
            if await scrape_season(season):
                new_standings = True
        new_games = await scrape_all_games()

        if not new_standings and not new_games:
            print("No new content. Waiting 1 hour...")
            await asyncio.sleep(3600)
        else:
            print("New content found. Waiting 5 minutes...")
            await asyncio.sleep(300)


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
