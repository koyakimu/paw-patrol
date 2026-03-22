#!/usr/bin/env python3
"""Fetch PAW Patrol episode data from U-NEXT using Playwright."""

import json
import os
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

TITLE_URL = "https://video.unext.jp/title/SID0041925"
TITLE_CODE = "SID0041925"


def main():
    print("Fetching U-NEXT PAW Patrol episodes...")
    print("  Starting headless browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
        )
        page = context.new_page()

        print(f"  Navigating to {TITLE_URL}...")
        page.goto(TITLE_URL, wait_until="domcontentloaded", timeout=60000)
        # Wait for SPA content to render
        page.wait_for_timeout(8000)

        # Close any modal dialogs (login prompts, etc.)
        print("  Closing any modal dialogs...")
        for close_sel in ['button[aria-label="close"]', 'button:has-text("×")', '[class*="close"]', '[class*="Close"]']:
            try:
                close_btn = page.query_selector(close_sel)
                if close_btn and close_btn.is_visible():
                    close_btn.click()
                    page.wait_for_timeout(1000)
                    print(f"    Closed modal via {close_sel}")
                    break
            except Exception:
                pass
        # Also try pressing Escape
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
        except Exception:
            pass

        seasons_data = []

        # First, let's see what's on the page
        print("  Analyzing page structure...")

        # Try to get all episode cards visible on the page
        episodes_on_page = extract_episodes(page)

        if episodes_on_page:
            print(f"  Found {len(episodes_on_page)} episodes on initial page")
            seasons_data.append({
                "season": 1,
                "season_name": "Default",
                "episodes": episodes_on_page,
            })

        # Try iterating seasons via URL parameters instead of clicking
        print("  Trying season URLs...")
        for season_num in range(1, 20):
            season_url = f"{TITLE_URL}?season={season_num}"
            try:
                page.goto(season_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)

                # Close modal again if it appears
                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                except Exception:
                    pass

                eps = extract_episodes(page)
                if not eps:
                    # No more seasons
                    if season_num > 1:
                        print(f"    Season {season_num}: no episodes, stopping")
                        break
                    continue

                print(f"    Season {season_num}: {len(eps)} episodes")

                # Check if this is the same as a previous season (some sites ignore the param)
                if seasons_data and eps == seasons_data[-1].get("episodes"):
                    print(f"    Season {season_num}: same as previous, stopping")
                    break

                # Try to detect actual season name from page
                season_name = f"シーズン{season_num}"
                try:
                    season_label = page.query_selector('[class*="season"] [class*="selected"], [class*="Season"] [class*="active"]')
                    if season_label:
                        season_name = season_label.inner_text().strip()
                except Exception:
                    pass

                seasons_data.append({
                    "season": season_num,
                    "season_name": season_name,
                    "episodes": eps,
                })

            except Exception as e:
                print(f"    Season {season_num}: error - {e}")
                if season_num > 2:
                    break

        # If URL-based approach didn't work better, try scrolling on main page
        if not seasons_data or (len(seasons_data) == 1 and seasons_data[0]["season_name"] == "Default"):
            print("  Trying scroll-based approach on main page...")
            page.goto(TITLE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            except Exception:
                pass

            for _ in range(10):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)

            all_eps = extract_episodes(page)
            if all_eps:
                print(f"  Found {len(all_eps)} episodes after scrolling")
                seasons_data = [{
                    "season": 1,
                    "season_name": "All",
                    "episodes": all_eps,
                }]

        # Also capture the page HTML for debugging
        page_title = page.title()
        page_url = page.url

        # Take a screenshot for debugging
        screenshot_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "unext_debug.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"  Debug screenshot saved to: {screenshot_path}")

        browser.close()

    total_episodes = sum(len(s["episodes"]) for s in seasons_data)

    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "video.unext.jp",
        "title_code": TITLE_CODE,
        "page_title": page_title,
        "page_url": page_url,
        "total_seasons": len(seasons_data),
        "total_episodes": total_episodes,
        "seasons": seasons_data,
    }

    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "unext.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(seasons_data)} seasons, {total_episodes} episodes")
    print(f"Output: {output_path}")

    if total_episodes == 0:
        print("\nWARNING: No episodes were extracted. This may be because:")
        print("  - U-NEXT requires login to view episode lists")
        print("  - The page structure has changed")
        print("  - Check the debug screenshot for more details")


def extract_episodes(page):
    """Extract episode information from the current page state."""
    episodes = []

    # Try various selectors for episode cards
    selectors = [
        '[data-testid="episode-card"]',
        '[class*="episode"]',
        '[class*="Episode"]',
        'a[href*="/episode/"]',
        '[data-ucn*="episode"]',
    ]

    for selector in selectors:
        elements = page.query_selector_all(selector)
        if elements:
            for el in elements:
                ep = extract_episode_info(el, page)
                if ep:
                    episodes.append(ep)
            if episodes:
                break

    # Deduplicate by title or episode code
    seen = set()
    unique = []
    for ep in episodes:
        key = ep.get("episode_code") or ep.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(ep)

    return unique


def extract_episode_info(element, page):
    """Extract episode info from a single element."""
    ep = {}

    try:
        # Get text content
        text = element.inner_text().strip()
        if not text:
            return None

        ep["raw_text"] = text[:200]

        # Try to get href for episode code
        href = element.get_attribute("href")
        if href and "/episode/" in href:
            parts = href.split("/")
            ep["episode_code"] = parts[-1] if parts else None
            ep["url"] = f"https://video.unext.jp{href}" if href.startswith("/") else href

        # Try to extract title and episode number from text
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Episode number pattern: "#1" or "第1話"
            import re
            m = re.match(r"#(\d+)", line)
            if m:
                ep["episode"] = int(m.group(1))
            m = re.match(r"第(\d+)話", line)
            if m:
                ep["episode"] = int(m.group(1))

        # Title is usually the longest meaningful line
        meaningful = [l.strip() for l in lines if l.strip() and len(l.strip()) > 2]
        if meaningful:
            ep["title"] = meaningful[0]

        # Try to get thumbnail
        img = element.query_selector("img")
        if img:
            ep["thumbnail_url"] = img.get_attribute("src")

    except Exception:
        return None

    return ep if ep.get("title") or ep.get("episode_code") else None


if __name__ == "__main__":
    main()
