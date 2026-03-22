#!/usr/bin/env python3
"""Fetch PAW Patrol episode data from TVmaze API (no API key required)."""

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

TVMAZE_SHOW_ID = 894  # PAW Patrol
BASE_URL = "https://api.tvmaze.com"


def fetch_json(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    # Fetch show details
    print("Fetching show details from TVmaze...")
    show = fetch_json(f"{BASE_URL}/shows/{TVMAZE_SHOW_ID}")

    print(f"  Show: {show['name']}")
    print(f"  Status: {show['status']}")
    print(f"  Premiered: {show['premiered']}")

    time.sleep(0.5)

    # Fetch all episodes
    print("Fetching all episodes...")
    episodes_raw = fetch_json(f"{BASE_URL}/shows/{TVMAZE_SHOW_ID}/episodes")

    # Group by season
    by_season = defaultdict(list)
    for ep in episodes_raw:
        by_season[ep["season"]].append({
            "episode_number": ep["number"],
            "name": ep["name"],
            "type": ep.get("type"),
            "air_date": ep.get("airdate"),
            "air_time": ep.get("airtime"),
            "airstamp": ep.get("airstamp"),
            "runtime": ep.get("runtime"),
            "rating_average": ep.get("rating", {}).get("average"),
            "image": ep.get("image"),
            "summary": ep.get("summary"),
            "tvmaze_id": ep["id"],
            "tvmaze_url": ep.get("url"),
        })

    seasons = []
    for season_num in sorted(by_season.keys()):
        eps = by_season[season_num]
        print(f"  Season {season_num}: {len(eps)} episodes")
        seasons.append({
            "season": season_num,
            "episode_count": len(eps),
            "episodes": eps,
        })

    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "tvmaze",
        "tvmaze_id": TVMAZE_SHOW_ID,
        "show_name": show.get("name"),
        "show_url": show.get("url"),
        "show_overview": show.get("summary"),
        "show_premiered": show.get("premiered"),
        "show_ended": show.get("ended"),
        "show_status": show.get("status"),
        "show_network": show.get("network", {}).get("name"),
        "show_network_country": show.get("network", {}).get("country", {}).get("name"),
        "show_language": show.get("language"),
        "show_genres": show.get("genres"),
        "show_image": show.get("image"),
        "total_seasons": len(seasons),
        "total_episodes": sum(s["episode_count"] for s in seasons),
        "seasons": seasons,
    }

    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "canada.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {result['total_seasons']} seasons, {result['total_episodes']} episodes")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
