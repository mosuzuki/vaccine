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
    return normalize_space(unescape(text))


def parse_date(entry):
    for raw in [entry.get("published"), entry.get("updated"), entry.get("created")]:
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
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()[:16]


def classify_topics(text: str, config: dict):
    text_l = text.lower()
    topics = []
    for topic, words in config.get("priority_topics", {}).items():
        if any(w.lower() in text_l for w in words):
            topics.append(topic)
    return topics


def classify_vaccines(text: str, config: dict):
    text_l = text.lower()
    found = []
    for vaccine, words in config.get("vaccine_keywords", {}).items():
        if any(w.lower() in text_l for w in words):
            found.append(vaccine)
    return sorted(set(found))


def extract_variants(text: str, config: dict):
    text_l = text.lower()
    return sorted({pat for pat in config.get("variant_patterns", []) if pat.lower() in text_l})


def summarize_line(title: str, summary: str, topics, vaccines):
    if summary:
        first = re.split(r"(?<=[.!?。])\s+", summary)[0]
        first = normalize_space(first)
        if 30 <= len(first) <= 180:
            return first
    bits = []
    if topics:
        bits.append("/".join(topics))
    if vaccines:
        bits.append("・".join(vaccines))
    bits.append(title)
    return normalize_space(" | ".join(bits))[:180]


def is_relevant(text: str, config: dict, source_type: str):
    text_l = text.lower()
    if config.get("require_primary_source", False) and source_type not in config.get("allowed_source_types", ["official", "academic"]):
        return False
    include_terms = config.get("strict_include_any", [])
    if include_terms and not any(term.lower() in text_l for term in include_terms):
        return False
    exclude_terms = config.get("strict_exclude_any", [])
    if any(term.lower() in text_l for term in exclude_terms):
        return False
    topics = classify_topics(text, config)
    if not topics:
        return False
    return True


def detect_country(text: str):
    country_map = {
        "japan": ("日本", 35.6762, 139.6503, "Asia"),
        "china": ("中国", 39.9042, 116.4074, "Asia"),
        "hong kong": ("香港", 22.3193, 114.1694, "Asia"),
        "south korea": ("韓国", 37.5665, 126.9780, "Asia"),
        "republic of korea": ("韓国", 37.5665, 126.9780, "Asia"),
        "taiwan": ("台湾", 25.0330, 121.5654, "Asia"),
        "india": ("インド", 28.6139, 77.2090, "Asia"),
        "united states": ("米国", 38.9072, -77.0369, "North America"),
        "usa": ("米国", 38.9072, -77.0369, "North America"),
        "canada": ("カナダ", 45.4215, -75.6972, "North America"),
        "united kingdom": ("英国", 51.5074, -0.1278, "Europe"),
        "uk": ("英国", 51.5074, -0.1278, "Europe"),
        "france": ("フランス", 48.8566, 2.3522, "Europe"),
        "germany": ("ドイツ", 52.5200, 13.4050, "Europe"),
        "brazil": ("ブラジル", -15.7939, -47.8828, "South America"),
        "australia": ("オーストラリア", -35.2809, 149.1300, "Oceania"),
        "south africa": ("南アフリカ", -25.7479, 28.2293, "Africa")
    }
    text_l = f" {text.lower()} "
    for key, (name, lat, lng, region) in country_map.items():
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", text_l):
            return {"name_ja": name, "lat": lat, "lng": lng, "region": region}
    return {"name_ja": "不明", "lat": 20.0, "lng": 0.0, "region": "Unknown"}


def dedupe_items(items):
    deduped, used = [], set()
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
            if (url_a and url_a == url_b) or fuzz.token_set_ratio(title_a, title_b) >= 92:
                group.append(other)
                used.add(j)
        group.sort(key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
        primary = dict(group[0])
        primary["duplicate_count"] = len(group)
        primary["duplicate_sources"] = sorted({x.get("source", "") for x in group if x.get("source")})
        deduped.append(primary)
    deduped.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return deduped


def main():
    config = load_json(CONFIG_PATH, {})
    cache = load_json(CACHE_PATH, {})
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(days=int(config.get("days_back", 7)))
    feeds = config.get("feeds", [])

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
            kept = 0
            for entry in parsed.entries:
                published = parse_date(entry)
                if published < since:
                    continue
                title_original = normalize_space(entry.get("title", ""))
                summary_original = extract_summary(entry)
                link = entry.get("link", "")
                merged_text = f"{title_original} {summary_original}"
                count += 1
                if not is_relevant(merged_text, config, source_type):
                    continue
                topics = classify_topics(merged_text, config)
                vaccines = classify_vaccines(merged_text, config)
                variants = extract_variants(merged_text, config)
                location = detect_country(merged_text)
                title_ja = translate_text(title_original, cache, config.get("default_language", "ja"))
                summary_ja = translate_text(summary_original, cache, config.get("default_language", "ja"))
                ai_summary = translate_text(summarize_line(title_original, summary_original, topics, vaccines), cache, config.get("default_language", "ja"))
                all_items.append({
                    "id": make_item_id(link, title_original),
                    "title": title_ja,
                    "summary": summary_ja,
                    "summary_ai": ai_summary,
                    "title_original": title_original,
                    "summary_original": summary_original,
                    "link": link,
                    "source": name,
                    "source_type": source_type,
                    "source_priority": priority,
                    "published_at": published.isoformat(),
                    "topics": topics,
                    "vaccines": vaccines,
                    "variants": variants,
                    "location": location,
                    "region": location["region"],
                    "country": location["name_ja"],
                    "lat": location["lat"],
                    "lng": location["lng"]
                })
                kept += 1
            feed_status.append({"name": name, "url": url, "status": "ok", "seen": count, "kept": kept})
        except Exception as exc:
            feed_status.append({"name": name, "url": url, "status": "error", "error": str(exc)})

    all_items.sort(key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
    all_items = dedupe_items(all_items)[: int(config.get("max_items", 120))]

    news = {
        "title": config.get("title", "Vaccine and Immunization Monitoring"),
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
