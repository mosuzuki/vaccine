#!/usr/bin/env python3
import json
import re
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime
from html import unescape

import feedparser
from deep_translator import GoogleTranslator
from rapidfuzz import fuzz


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "config.json"
DATA_DIR = ROOT / "data"
NEWS_PATH = DATA_DIR / "news.json"
CACHE_PATH = DATA_DIR / "translation_cache.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return normalize_space(text)


def parse_date(entry):
    candidates = [
        entry.get("published"),
        entry.get("updated"),
        entry.get("created")
    ]
    for raw in candidates:
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def extract_summary(entry):
    for key in ["summary", "description"]:
        if entry.get(key):
            return strip_html(entry.get(key))
    if entry.get("content"):
        try:
            if isinstance(entry["content"], list) and entry["content"]:
                return strip_html(entry["content"][0].get("value", ""))
        except Exception:
            pass
    return ""


def classify_topics(text: str, config: dict):
    text_l = (text or "").lower()
    topic_keywords = config.get("topic_keywords", {})
    topics = []
    for topic, words in topic_keywords.items():
        if any(word.lower() in text_l for word in words):
            topics.append(topic)
    if not topics:
        topics = ["other"]
    return topics


def extract_variants(text: str, config: dict):
    text_l = (text or "").lower()
    found = []
    for pat in config.get("variant_patterns", []):
        if pat.lower() in text_l:
            found.append(pat)
    return sorted(set(found))


def detect_country(text: str, config: dict):
    text_l = f" {text.lower()} "
    country_map = config.get("country_map", {})
    matches = []
    for key, info in country_map.items():
        pattern = rf"(?<![a-z]){re.escape(key.lower())}(?![a-z])"
        if re.search(pattern, text_l):
            matches.append({
                "key": key,
                "name_ja": info["name_ja"],
                "lat": info["lat"],
                "lng": info["lng"],
                "region": info["region"]
            })
    if not matches:
        return {
            "key": "unknown",
            "name_ja": "不明",
            "lat": 20.0,
            "lng": 0.0,
            "region": "Unknown"
        }
    asia_matches = [m for m in matches if m["region"] == "Asia"]
    if asia_matches:
        return asia_matches[0]
    return matches[0]


def is_japanese_text(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text or ""))


def translate_text(text: str, cache: dict, target_lang: str = "ja") -> str:
    text = normalize_space(text)
    if not text:
        return ""
    if is_japanese_text(text):
        return text

    key = hashlib.sha256(f"{target_lang}:{text}".encode("utf-8")).hexdigest()
    if key in cache:
        return cache[key]

    try:
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
        translated = normalize_space(translated)
        if translated:
            cache[key] = translated
            return translated
    except Exception:
        pass

    cache[key] = text
    return text


def make_item_id(link: str, title: str) -> str:
    base = f"{link}|{title}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:16]


def dedupe_items(items):
    deduped = []
    used = set()

    for i, item in enumerate(items):
        if i in used:
            continue

        group = [item]
        used.add(i)

        title_a = (item.get("title_original") or item.get("title") or "").lower()
        url_a = item.get("link", "")

        for j in range(i + 1, len(items)):
            if j in used:
                continue
            other = items[j]
            title_b = (other.get("title_original") or other.get("title") or "").lower()
            url_b = other.get("link", "")

            title_score = fuzz.token_set_ratio(title_a, title_b)
            same_url = (url_a == url_b and url_a != "")

            if same_url or title_score >= 92:
                group.append(other)
                used.add(j)

        group = sorted(group, key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
        primary = dict(group[0])
        primary["duplicate_count"] = len(group)
        primary["duplicate_sources"] = sorted(set(x.get("source", "") for x in group if x.get("source")))
        deduped.append(primary)

    deduped.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return deduped


def build_empty_news(config, now_utc):
    return {
        "title": config.get("title", "EBS Research Dashboard"),
        "description": config.get("description", ""),
        "generated_at": now_utc.isoformat(),
        "item_count": 0,
        "feed_status": [],
        "items": []
    }


def main():
    config = load_json(CONFIG_PATH, {})
    cache = load_json(CACHE_PATH, {})
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(days=int(config.get("days_back", 30)))

    feeds = config.get("feeds", [])
    news = build_empty_news(config, now_utc)

    if not feeds:
        save_json(NEWS_PATH, news)
        save_json(CACHE_PATH, cache)
        print("No feeds configured. Wrote empty news.json")
        return

    all_items = []
    feed_status = []

    for feed in feeds:
        name = feed.get("name", "Unknown Feed")
        url = feed.get("url", "")
        source_type = feed.get("source_type", "unknown")
        priority = int(feed.get("priority", 0))

        try:
            parsed = feedparser.parse(url)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise RuntimeError(str(getattr(parsed, "bozo_exception", "Feed parse error")))

            count = 0
            for entry in parsed.entries:
                published = parse_date(entry)
                if published < since:
                    continue

                title_original = normalize_space(entry.get("title", ""))
                summary_original = extract_summary(entry)
                link = entry.get("link", "")

                merged_text = f"{title_original} {summary_original}"
                topics = classify_topics(merged_text, config)
                variants = extract_variants(merged_text, config)
                location = detect_country(merged_text, config)

                title_ja = translate_text(title_original, cache, config.get("default_language", "ja"))
                summary_ja = translate_text(summary_original, cache, config.get("default_language", "ja"))

                item = {
                    "id": make_item_id(link, title_original),
                    "title": title_ja,
                    "summary": summary_ja,
                    "title_original": title_original,
                    "summary_original": summary_original,
                    "link": link,
                    "source": name,
                    "source_type": source_type,
                    "source_priority": priority,
                    "published_at": published.isoformat(),
                    "topics": topics,
                    "variants": variants,
                    "location": location,
                    "region": location["region"],
                    "country": location["name_ja"],
                    "lat": location["lat"],
                    "lng": location["lng"]
                }
                all_items.append(item)
                count += 1

            feed_status.append({
                "name": name,
                "url": url,
                "status": "ok",
                "items": count
            })

        except Exception as exc:
            feed_status.append({
                "name": name,
                "url": url,
                "status": "error",
                "error": str(exc)
            })

    all_items.sort(key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
    all_items = dedupe_items(all_items)
    all_items = all_items[: int(config.get("max_items", 200))]

    news = {
        "title": config.get("title", "EBS Research Dashboard"),
        "description": config.get("description", ""),
        "generated_at": now_utc.isoformat(),
        "item_count": len(all_items),
        "feed_status": feed_status,
        "items": all_items
    }

    save_json(NEWS_PATH, news)
    save_json(CACHE_PATH, cache)
    print(f"Wrote {NEWS_PATH} with {len(all_items)} items")


if __name__ == "__main__":
    main()
