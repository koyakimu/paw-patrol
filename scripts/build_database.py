#!/usr/bin/env python3
"""Build the unified PAW Patrol episode database from raw data sources.

Reads data/raw/*.json and produces:
  - data/broadcasts.json  (TV Tokyo broadcast list with rebroadcast flags)
  - data/segments.json    (Canadian episodes with Japan mapping)
  - data/seasons.json     (Season metadata for all sources)
"""

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_raw(filename):
    path = os.path.join(RAW_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_output(filename, data):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {path}")


# ── Step 1: Detect rebroadcasts ──────────────────────────────────────────────

def detect_rebroadcasts(broadcasts):
    """Flag rebroadcasts by detecting duplicate titles.

    When the same title appears multiple times, the first occurrence is the
    original and subsequent ones are rebroadcasts.
    """
    title_first = {}  # title -> first broadcast number
    for b in broadcasts:
        t = b["title"]
        if t not in title_first:
            title_first[t] = b["number"]

    for b in broadcasts:
        first_num = title_first[b["title"]]
        if b["number"] == first_num:
            b["is_rebroadcast"] = False
            b["rebroadcast_of"] = None
        else:
            b["is_rebroadcast"] = True
            b["rebroadcast_of"] = first_num

    return broadcasts


# ── Step 2: Build broadcasts.json ────────────────────────────────────────────

def build_broadcasts(tv_raw):
    broadcasts = []
    for b in tv_raw["broadcasts"]:
        entry = {
            "number": b["number"],
            "air_date": b.get("air_date"),
            "title": b["title"],
            "synopsis": b.get("synopsis"),
            "is_rebroadcast": b.get("is_rebroadcast", False),
            "rebroadcast_of": b.get("rebroadcast_of"),
            "segment_titles": b.get("segment_titles"),
            "canada_ids": [],  # filled in mapping step
        }
        broadcasts.append(entry)
    return broadcasts


# ── Step 3: Build segments.json ──────────────────────────────────────────────

def build_segments(canada_raw):
    segments = []
    for season in canada_raw["seasons"]:
        for ep in season["episodes"]:
            seg = {
                "id": f"S{season['season']:02d}E{ep['episode_number']:02d}",
                "canada": {
                    "season": season["season"],
                    "episode": ep["episode_number"],
                    "title": ep["name"],
                    "air_date": ep.get("air_date"),
                    "runtime": ep.get("runtime"),
                    "summary": ep.get("summary"),
                    "tvmaze_id": ep.get("tvmaze_id"),
                },
                "japan": {
                    "broadcast_number": None,
                    "title": None,
                    "unext_season": None,
                    "unext_episode": None,
                },
            }
            segments.append(seg)
    return segments


# ── Step 4: Build seasons.json ───────────────────────────────────────────────

def build_seasons(canada_raw, tv_broadcasts, unext_raw):
    canada_seasons = []
    for season in canada_raw["seasons"]:
        eps = season["episodes"]
        canada_seasons.append({
            "season": season["season"],
            "episode_count": season["episode_count"],
            "first_air_date": eps[0].get("air_date") if eps else None,
            "last_air_date": eps[-1].get("air_date") if eps else None,
        })

    # Detect TV Tokyo season boundaries from broadcast numbers and dates
    # Seasons 1-3 are known: 1-26, 27-52, 53-78. Season 4+ is 79 onward.
    tvtokyo_seasons = [
        {"season": 1, "broadcast_range": [1, 26]},
        {"season": 2, "broadcast_range": [27, 52]},
        {"season": 3, "broadcast_range": [53, 78]},
        {"season": 4, "broadcast_range": [79, None]},  # None = ongoing
    ]
    # Fill in last broadcast number for season 4
    max_num = max(b["number"] for b in tv_broadcasts)
    tvtokyo_seasons[-1]["broadcast_range"][1] = max_num

    # Fill air dates from actual data
    for ts in tvtokyo_seasons:
        start, end = ts["broadcast_range"]
        start_b = next((b for b in tv_broadcasts if b["number"] == start), None)
        end_b = next((b for b in tv_broadcasts if b["number"] == end), None)
        ts["first_air_date"] = start_b["air_date"] if start_b else None
        ts["last_air_date"] = end_b["air_date"] if end_b else None

    # U-NEXT seasons (from raw data if available)
    unext_seasons = []
    if unext_raw and unext_raw.get("seasons"):
        for s in unext_raw["seasons"]:
            unext_seasons.append({
                "season": s.get("season"),
                "season_name": s.get("season_name"),
                "episode_count": len(s.get("episodes", [])),
            })

    return {
        "canada": canada_seasons,
        "tvtokyo": tvtokyo_seasons,
        "unext": unext_seasons,
    }


# ── Step 5: Map TV Tokyo broadcasts to Canadian segments ─────────────────────

def normalize_ja(text):
    """Normalize Japanese text for matching."""
    # Remove quotes, spaces, punctuation
    text = re.sub(r'[「」『』\s　・！？!?\u3000]', '', text)
    # Normalize some common variations
    text = text.replace('パウパトロール', 'パウパトロール')
    return text.lower()


def map_broadcasts_to_segments(broadcasts, segments, unext_raw):
    """Map TV Tokyo broadcasts to Canadian segments.

    Key insight: One TV Tokyo broadcast (30 min) typically contains two
    Canadian segments (11 min each). TV Tokyo broadcasts with segment_titles
    (split by 「」) map to two consecutive Canadian segments. Single-title
    broadcasts (specials) map to one segment.

    Strategy: sequential mapping where each original broadcast consumes
    1 or 2 Canadian segments depending on whether it has segment_titles.
    """
    originals = [b for b in broadcasts if not b["is_rebroadcast"]]
    print(f"  Original broadcasts: {len(originals)}")
    print(f"  Canadian segments: {len(segments)}")

    seg_idx = 0  # cursor into segments list
    mapped_broadcasts = 0
    mapped_segments = 0

    for b in originals:
        if seg_idx >= len(segments):
            break

        seg_titles = b.get("segment_titles")
        if seg_titles and len(seg_titles) >= 2:
            # Two-segment broadcast: map to two consecutive Canadian segments
            for st in seg_titles:
                if seg_idx >= len(segments):
                    break
                segments[seg_idx]["japan"]["broadcast_number"] = b["number"]
                segments[seg_idx]["japan"]["title"] = st
                b["canada_ids"].append(segments[seg_idx]["id"])
                seg_idx += 1
                mapped_segments += 1
        else:
            # Single-segment broadcast (special episode or single title)
            title = b["title"].strip("「」")
            segments[seg_idx]["japan"]["broadcast_number"] = b["number"]
            segments[seg_idx]["japan"]["title"] = title
            b["canada_ids"].append(segments[seg_idx]["id"])
            seg_idx += 1
            mapped_segments += 1

        mapped_broadcasts += 1

    # Also map rebroadcasts to the same segments as their originals
    for b in broadcasts:
        if b["is_rebroadcast"] and b["rebroadcast_of"]:
            orig = next((ob for ob in broadcasts if ob["number"] == b["rebroadcast_of"]), None)
            if orig:
                b["canada_ids"] = list(orig["canada_ids"])

    print(f"  Mapped: {mapped_broadcasts} broadcasts, {mapped_segments} segments")
    unmapped_segments = sum(1 for s in segments if s["japan"]["broadcast_number"] is None)
    print(f"  Unmapped segments: {unmapped_segments} (not yet broadcast in Japan)")

    return broadcasts, segments


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Building unified PAW Patrol database...")

    # Load raw data
    print("\nLoading raw data...")
    canada_raw = load_raw("canada.json")
    tv_raw = load_raw("tvtokyo.json")
    try:
        unext_raw = load_raw("unext.json")
    except FileNotFoundError:
        unext_raw = None

    print(f"  Canada (TVmaze): {canada_raw['total_episodes']} episodes")
    print(f"  TV Tokyo: {tv_raw['total_broadcasts']} broadcasts")
    if unext_raw:
        print(f"  U-NEXT: {unext_raw['total_episodes']} episodes")

    # Step 1: Detect rebroadcasts
    print("\nStep 1: Detecting rebroadcasts...")
    detect_rebroadcasts(tv_raw["broadcasts"])
    rebroadcast_count = sum(1 for b in tv_raw["broadcasts"] if b.get("is_rebroadcast"))
    print(f"  Rebroadcasts found: {rebroadcast_count}")

    # Step 2: Build broadcasts
    print("\nStep 2: Building broadcasts...")
    broadcasts = build_broadcasts(tv_raw)

    # Step 3: Build segments
    print("\nStep 3: Building segments...")
    segments = build_segments(canada_raw)
    print(f"  Segments: {len(segments)}")

    # Step 4: Map broadcasts to segments
    print("\nStep 4: Mapping broadcasts to segments...")
    broadcasts, segments = map_broadcasts_to_segments(broadcasts, segments, unext_raw)

    # Step 5: Build seasons
    print("\nStep 5: Building seasons...")
    seasons = build_seasons(canada_raw, broadcasts, unext_raw)

    # Save outputs
    print("\nSaving outputs...")
    save_output("broadcasts.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(broadcasts),
        "rebroadcasts": rebroadcast_count,
        "unique": len(broadcasts) - rebroadcast_count,
        "broadcasts": broadcasts,
    })
    save_output("segments.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(segments),
        "mapped_to_japan": sum(1 for s in segments if s["japan"]["broadcast_number"] is not None),
        "segments": segments,
    })
    save_output("seasons.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seasons": seasons,
    })

    print(f"\nDone!")
    print(f"  broadcasts.json: {len(broadcasts)} entries ({rebroadcast_count} rebroadcasts)")
    print(f"  segments.json: {len(segments)} entries")
    print(f"  seasons.json: {len(seasons['canada'])} CA / {len(seasons['tvtokyo'])} JP seasons")


if __name__ == "__main__":
    main()
