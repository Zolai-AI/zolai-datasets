#!/usr/bin/env python3
"""Scrape all articles from zomidaily.com using WordPress REST API.

Usage:
    python scrape_zomidaily.py                    # Full scrape (all posts)
    python scrape_zomidaily.py --pages 5          # Scrape first 5 pages only
    python scrape_zomidaily.py --stats            # Show current scrape stats
    python scrape_zomidaily.py --test             # Test on 1 page
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://zomidaily.com/wp-json/wp/v2"
ARTICLES_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "zomidaily" / "articles"
METADATA_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "zomidaily" / "metadata"

PER_PAGE = 100
RATE_LIMIT = 1.0  # seconds between requests
TIMEOUT = 30
HEADERS = {
    "User-Agent": "ZolaiAI/1.0 (Language Preservation; zolai-ai.github.io)"
}


def ensure_dirs() -> None:
    """Create output directories if they don't exist."""
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)


def strip_html(html_content: str) -> str:
    """Remove HTML tags and decode entities."""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n")
    text = unescape(text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_json(url: str) -> Any | None:
    """Fetch JSON from URL with rate limiting and error handling."""
    time.sleep(RATE_LIMIT)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  [ERROR] {url}: {e}", file=sys.stderr)
        return None


def get_total_posts() -> int:
    """Get total number of posts from API headers."""
    url = f"{BASE_URL}/posts?per_page=1&_fields=id"
    time.sleep(RATE_LIMIT)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        total = int(resp.headers.get("X-WP-Total", 0))
        pages = int(resp.headers.get("X-WP-TotalPages", 0))
        print(f"Total posts: {total}, Total pages: {pages}")
        return total
    except requests.RequestException as e:
        print(f"[ERROR] Failed to get total posts: {e}", file=sys.stderr)
        return 0


def get_tags_map() -> dict[int, str]:
    """Fetch all tag IDs → names."""
    tags: dict[int, str] = {}
    page = 1
    while True:
        url = f"{BASE_URL}/tags?per_page=100&_fields=id,name&page={page}"
        data = fetch_json(url)
        if not data:
            break
        for tag in data:
            tags[tag["id"]] = tag["name"]
        if len(data) < 100:
            break
        page += 1
    print(f"Loaded {len(tags)} tags")
    return tags


def scrape_page(page: int, tags_map: dict[int, str]) -> list[dict[str, Any]]:
    """Scrape one page of posts from the REST API."""
    url = (
        f"{BASE_URL}/posts?"
        f"per_page={PER_PAGE}&page={page}"
        f"&_fields=id,date,link,title,content,categories,tags"
    )
    data = fetch_json(url)
    if not data:
        return []

    articles = []
    for post in data:
        article_id = post["id"]
        title = strip_html(post["title"]["rendered"])
        content_html = post["content"]["rendered"]
        content_text = strip_html(content_html)
        post_date = post["date"]
        link = post["link"]

        # Map tag IDs to names
        tag_names = [tags_map.get(tid, str(tid)) for tid in post.get("tags", [])]
        cat_names = [tags_map.get(cid, str(cid)) for cid in post.get("categories", [])]

        article = {
            "id": article_id,
            "title": title,
            "date": post_date,
            "link": link,
            "tags": tag_names,
            "categories": cat_names,
            "content": content_text,
            "word_count": len(content_text.split()),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        articles.append(article)

    return articles


def load_scraped_ids() -> set[int]:
    """Load IDs of already-scraped articles for resume support."""
    ids_file = METADATA_DIR / "scraped_ids.jsonl"
    if not ids_file.exists():
        return set()
    ids = set()
    with open(ids_file) as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(int(line))
    return ids


def save_scraped_id(article_id: int) -> None:
    """Append a scraped article ID for resume tracking."""
    ids_file = METADATA_DIR / "scraped_ids.jsonl"
    with open(ids_file, "a") as f:
        f.write(f"{article_id}\n")


def save_article(article: dict[str, Any]) -> None:
    """Save one article as JSON file."""
    filepath = ARTICLES_DIR / f"{article['id']}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)


def save_metadata(all_articles: list[dict[str, Any]]) -> None:
    """Save metadata summary and article index."""
    # Save full index (without content to keep it small)
    index_file = METADATA_DIR / "all_articles.jsonl"
    with open(index_file, "w", encoding="utf-8") as f:
        for a in all_articles:
            entry = {
                "id": a["id"],
                "title": a["title"],
                "date": a["date"],
                "link": a["link"],
                "tags": a["tags"],
                "categories": a["categories"],
                "word_count": a["word_count"],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Save stats
    total_words = sum(a["word_count"] for a in all_articles)
    tag_counts: dict[str, int] = {}
    for a in all_articles:
        for tag in a["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:30]

    dates = [a["date"] for a in all_articles if a.get("date")]
    stats = {
        "total_articles": len(all_articles),
        "total_words": total_words,
        "avg_words_per_article": round(total_words / max(len(all_articles), 1)),
        "date_range": {
            "earliest": min(dates) if dates else None,
            "latest": max(dates) if dates else None,
        },
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    stats_file = METADATA_DIR / "stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\nMetadata saved to {METADATA_DIR}")
    print(f"  Index: {index_file}")
    print(f"  Stats: {stats_file}")


def run_scrape(max_pages: int | None = None) -> None:
    """Main scrape loop."""
    ensure_dirs()

    print("=" * 60)
    print("ZOMIDAILY.COM SCRAPER (WordPress REST API)")
    print("=" * 60)

    total = get_total_posts()
    if total == 0:
        print("[ERROR] Could not determine total posts.", file=sys.stderr)
        return

    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    if max_pages:
        total_pages = min(total_pages, max_pages)

    print(f"Will scrape {total_pages} pages ({total * min(1, max_pages or 1)}+ posts)")

    # Load tags
    tags_map = get_tags_map()

    # Resume support
    scraped_ids = load_scraped_ids()
    if scraped_ids:
        print(f"Resuming: {len(scraped_ids)} articles already scraped")

    all_articles: list[dict[str, Any]] = []
    failed_pages: list[int] = []

    for page in range(1, total_pages + 1):
        print(f"\n--- Page {page}/{total_pages} ---")
        articles = scrape_page(page, tags_map)

        if not articles:
            print(f"  No articles found on page {page} — stopping.")
            failed_pages.append(page)
            break

        new_count = 0
        skip_count = 0
        for article in articles:
            if article["id"] in scraped_ids:
                skip_count += 1
                continue
            save_article(article)
            save_scraped_id(article["id"])
            all_articles.append(article)
            new_count += 1

        print(
            f"  Page {page}: {len(articles)} articles "
            f"({new_count} new, {skip_count} skipped)"
        )

    # Also load previously scraped articles for metadata
    print("\nLoading all articles for metadata...")
    all_files = sorted(ARTICLES_DIR.glob("*.json"))
    all_loaded: list[dict[str, Any]] = []
    for fp in all_files:
        with open(fp) as f:
            all_loaded.append(json.load(f))

    save_metadata(all_loaded)

    # Summary
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)
    print(f"  Articles scraped this run: {len(all_articles)}")
    print(f"  Total articles on disk:    {len(all_loaded)}")
    print(f"  Failed pages:              {len(failed_pages)}")
    if failed_pages:
        print(f"  Failed page numbers:       {failed_pages}")
    print(f"  Articles dir:              {ARTICLES_DIR}")
    print(f"  Metadata dir:              {METADATA_DIR}")


def show_stats() -> None:
    """Show current scrape statistics."""
    stats_file = METADATA_DIR / "stats.json"
    if not stats_file.exists():
        print("No stats found. Run scrape first.")
        return
    with open(stats_file) as f:
        stats = json.load(f)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape zomidaily.com articles")
    parser.add_argument(
        "--pages", type=int, default=None,
        help="Max pages to scrape (default: all)"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show current scrape statistics"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test mode: scrape just 1 page"
    )
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.test:
        run_scrape(max_pages=1)
    else:
        run_scrape(max_pages=args.pages)


if __name__ == "__main__":
    main()
