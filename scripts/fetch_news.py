#!/usr/bin/env python3
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus

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
    candidates = [entry.get("published"), entry.get("updated"), entry.get("created")]
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


def google_news_rss_url(query: str):
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"


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


def classify_topics(text: str, config: dict):
    text_l = (text or "").lower()
    topics = []
    for topic, words in config.get("topic_keywords", {}).items():
        if any(word.lower() in text_l for word in words):
            topics.append(topic)
    return topics or ["other"]


def classify_policy(text: str, config: dict):
    text_l = (text or "").lower()
    found = []
    for label, words in config.get("policy_categories", {}).items():
        if any(word.lower() in text_l for word in words):
            found.append(label)
    return found or ["その他"]


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
        return {"key": "unknown", "name_ja": "不明", "lat": 20.0, "lng": 0.0, "region": "Unknown"}
    asia = [m for m in matches if m["region"] == "Asia"]
    return asia[0] if asia else matches[0]


def get_source_location(key: str, config: dict):
    src = config.get("source_location_map", {}).get(key)
    if not src:
        return {"name_ja": "不明", "lat": 20.0, "lng": 0.0, "country": "不明", "region": "Unknown"}
    return src


def make_item_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()[:16]


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
            same_url = url_a and url_a == url_b
            if same_url or title_score >= 92:
                group.append(other)
                used.add(j)
        group = sorted(group, key=lambda x: (x.get("published_at", ""), x.get("tier", 9) * -1), reverse=True)
        primary = dict(group[0])
        primary["duplicate_count"] = len(group)
        primary["duplicate_sources"] = sorted(set(x.get("source", "") for x in group if x.get("source")))
        deduped.append(primary)
    deduped.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return deduped


def parse_feed(url: str):
    parsed = feedparser.parse(url)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(str(getattr(parsed, "bozo_exception", "Feed parse error")))
    return parsed.entries


def process_entries(entries, name, source_type, tier, source_location_key, config, cache, since):
    items = []
    for entry in entries:
        published = parse_date(entry)
        if published < since:
            continue
        title_original = normalize_space(entry.get("title", ""))
        summary_original = extract_summary(entry)
        link = entry.get("link", "")
        merged = f"{title_original} {summary_original}"
        topics = classify_topics(merged, config)
        policy_tags = classify_policy(merged, config)
        variants = extract_variants(merged, config)
        target_location = detect_country(merged, config)
        source_location = get_source_location(source_location_key, config)
        title_ja = translate_text(title_original, cache, config.get("default_language", "ja"))
        summary_ja = translate_text(summary_original, cache, config.get("default_language", "ja"))
        items.append({
            "id": make_item_id(link, title_original),
            "title": title_ja,
            "summary": summary_ja,
            "title_original": title_original,
            "summary_original": summary_original,
            "link": link,
            "source": name,
            "source_type": source_type,
            "tier": tier,
            "published_at": published.isoformat(),
            "topics": topics,
            "policy_tags": policy_tags,
            "variants": variants,
            "target_location": target_location,
            "source_location": source_location,
            "plot_location": source_location,
            "region": source_location["region"],
            "country": source_location["country"],
            "lat": source_location["lat"],
            "lng": source_location["lng"]
        })
    return items


def main():
    config = load_json(CONFIG_PATH, {})
    cache = load_json(CACHE_PATH, {})
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=int(config.get("days_back", 21)))

    all_items = []
    feed_status = []

    for feed in config.get("official_feeds", []):
        try:
            entries = parse_feed(feed["url"])
            items = process_entries(entries, feed["name"], feed["source_type"], feed["tier"], feed["source_location_key"], config, cache, since)
            all_items.extend(items)
            feed_status.append({"name": feed["name"], "url": feed["url"], "status": "ok", "items": len(items), "tier": feed["tier"]})
        except Exception as exc:
            feed_status.append({"name": feed["name"], "url": feed["url"], "status": "error", "error": str(exc), "tier": feed["tier"]})

    for group_name in ["media_queries", "academic_queries"]:
        for query in config.get(group_name, []):
            rss_url = google_news_rss_url(query["query"])
            try:
                entries = parse_feed(rss_url)
                items = process_entries(entries, query["name"], query["source_type"], query["tier"], query["source_location_key"], config, cache, since)
                all_items.extend(items)
                feed_status.append({"name": query["name"], "url": rss_url, "status": "ok", "items": len(items), "tier": query["tier"]})
            except Exception as exc:
                feed_status.append({"name": query["name"], "url": rss_url, "status": "error", "error": str(exc), "tier": query["tier"]})

    all_items = [x for x in all_items if not (x["source_type"] == "media" and x["topics"] == ["other"])]
    all_items.sort(key=lambda x: (x.get("published_at", ""), -x.get("tier", 9)), reverse=True)
    all_items = dedupe_items(all_items)[: int(config.get("max_items", 300))]

    news = {
        "title": config.get("title", "Global Vaccine Policy Monitor"),
        "description": config.get("description", ""),
        "generated_at": now.isoformat(),
        "item_count": len(all_items),
        "feed_status": feed_status,
        "items": all_items,
        "map_default_mode": config.get("map_default_mode", "source")
    }
    save_json(NEWS_PATH, news)
    save_json(CACHE_PATH, cache)
    print(f"Wrote {NEWS_PATH} with {len(all_items)} items")


if __name__ == "__main__":
    main()
