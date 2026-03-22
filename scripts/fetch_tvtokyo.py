#!/usr/bin/env python3
"""Fetch PAW Patrol episode data from TV Tokyo website."""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.tv-tokyo.co.jp/anime/pawpatrol/episodes/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; paw-patrol-episode-db/1.0)"
}


def fetch_page(page_num):
    """Fetch a single page of episodes. Returns None if page doesn't exist."""
    if page_num == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}index_{page_num}.html"

    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_page(html):
    """Parse episodes from a page's HTML."""
    soup = BeautifulSoup(html, "lxml")
    episodes = []

    for box in soup.find_all("div", class_="articlebox"):
        ep = {}

        # Title: div.atitle contains "第292話「...」"
        atitle = box.find("div", class_="atitle")
        if not atitle:
            continue
        title_text = atitle.get_text(strip=True)
        ep["raw_title"] = title_text

        # Extract episode number
        m = re.match(r"第(\d+)話(.+)", title_text)
        if m:
            ep["number"] = int(m.group(1))
            ep["title"] = m.group(2).strip()
        else:
            continue

        # Air date: div.adate > p contains "2026.3.27 放送"
        adate = box.find("div", class_="adate")
        if adate:
            date_text = adate.get_text(strip=True)
            dm = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", date_text)
            if dm:
                ep["air_date"] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"

        # Synopsis: div.atxt > p
        atxt = box.find("div", class_="atxt")
        if atxt:
            # Get all text, preserving structure for multi-segment episodes
            segments = []
            for p in atxt.find_all("p"):
                # Check for individual segment titles (span.onairttl)
                seg_titles = p.find_all("span", class_="onairttl")
                if seg_titles:
                    # Multi-segment episode
                    text = p.get_text(separator="\n", strip=True)
                    segments.append(text)
                else:
                    text = p.get_text(strip=True)
                    if text:
                        segments.append(text)
            ep["synopsis"] = "\n".join(segments) if segments else None

            # Extract individual segment titles if present
            seg_title_spans = atxt.find_all("span", class_="onairttl")
            if seg_title_spans:
                ep["segment_titles"] = [s.get_text(strip=True).strip("「」") for s in seg_title_spans]

        # URL from Twitter share button
        twitter_link = box.find("a", class_="twitter-share-button")
        if twitter_link and twitter_link.get("data-url"):
            ep["url"] = twitter_link["data-url"]

        episodes.append(ep)

    return episodes


def main():
    all_broadcasts = []
    page_num = 1

    print("Fetching TV Tokyo PAW Patrol episodes...")

    while True:
        print(f"  Page {page_num}...", end=" ", flush=True)
        html = fetch_page(page_num)
        if html is None:
            print("not found, stopping.")
            break

        episodes = parse_page(html)
        print(f"{len(episodes)} episodes")

        if not episodes:
            print("  No episodes found, stopping.")
            break

        all_broadcasts.extend(episodes)
        page_num += 1
        time.sleep(1.5)

    # Sort by episode number (ascending)
    all_broadcasts.sort(key=lambda e: e.get("number", 0))

    # Deduplicate by episode number
    seen = set()
    unique = []
    for ep in all_broadcasts:
        num = ep.get("number")
        if num not in seen:
            seen.add(num)
            unique.append(ep)
    all_broadcasts = unique

    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "tv-tokyo.co.jp",
        "total_pages": page_num - 1,
        "total_broadcasts": len(all_broadcasts),
        "broadcasts": all_broadcasts,
    }

    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "tvtokyo.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {result['total_pages']} pages, {result['total_broadcasts']} broadcasts")
    print(f"  Range: #{all_broadcasts[0]['number']} - #{all_broadcasts[-1]['number']}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
