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

def classify_by_keywords(text, key_map):
    text_l = (text or "").lower()
    found = []
    for label, words in key_map.items():
        if any(word.lower() in text_l for word in words):
            found.append(label)
    return found

def classify_topics(text, config):
    return classify_by_keywords(text, config.get("topic_keywords", {})) or ["other"]

def classify_policy_tags(text, config):
    return classify_by_keywords(text, config.get("policy_tags", {}))

def classify_vaccines(text, config):
    return classify_by_keywords(text, config.get("vaccine_keywords", {}))

def extract_variants(text, config):
    text_l = (text or "").lower()
    return sorted(set([pat for pat in config.get("variant_patterns", []) if pat.lower() in text_l]))

def country_info_from_key(key, config):
    info = config.get("country_map", {}).get(key.lower())
    if not info:
        return {"key": "unknown", "name_ja": "不明", "lat": 20.0, "lng": 0.0, "region": "Unknown"}
    return {"key": key.lower(), "name_ja": info["name_ja"], "lat": info["lat"], "lng": info["lng"], "region": info["region"]}

def detect_country(text, config):
    text_l = f" {text.lower()} "
    matches = []
    for key, info in config.get("country_map", {}).items():
        pattern = rf"(?<![a-z]){re.escape(key.lower())}(?![a-z])"
        if re.search(pattern, text_l):
            matches.append({"key": key, "name_ja": info["name_ja"], "lat": info["lat"], "lng": info["lng"], "region": info["region"]})
    if not matches:
        return country_info_from_key("unknown", config)
    asia = [m for m in matches if m["region"] == "Asia"]
    return asia[0] if asia else matches[0]

def is_japanese_text(text):
    return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text or ""))

def translate_text(text, cache, target_lang="ja"):
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

def summarize_text(text):
    text = normalize_space(text)
    if not text:
        return ""
    text = text[:700]
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    for s in sentences:
        s = normalize_space(s)
        if len(s) >= 45:
            return s[:220]
    return text[:220]

def make_item_id(link, title):
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()[:16]

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
        group = sorted(group, key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
        primary = dict(group[0])
        primary["duplicate_count"] = len(group)
        primary["duplicate_sources"] = sorted(set(x.get("source", "") for x in group if x.get("source")))
        deduped.append(primary)
    deduped.sort(key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
    return deduped

def build_empty_news(config, now_utc):
    return {"title": config.get("title", "Vaccine and Immunization Monitoring"), "description": config.get("description", ""), "generated_at": now_utc.isoformat(), "item_count": 0, "plot_mode_default": config.get("default_plot_mode", "source"), "feed_status": [], "items": []}

def main():
    config = load_json(CONFIG_PATH, {})
    cache = load_json(CACHE_PATH, {})
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(days=int(config.get("days_back", 30)))
    feeds = config.get("feeds", [])
    if not feeds:
        save_json(NEWS_PATH, build_empty_news(config, now_utc))
        save_json(CACHE_PATH, cache)
        print("No feeds configured. Wrote empty news.json")
        return
    all_items, feed_status = [], []
    for feed in feeds:
        name, url = feed.get("name", "Unknown Feed"), feed.get("url", "")
        source_type, priority, tier = feed.get("source_type", "unknown"), int(feed.get("priority", 0)), feed.get("tier", "")
        origin = country_info_from_key(feed.get("origin_key", "unknown"), config)
        origin_label = feed.get("origin_label", origin["name_ja"])
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
                target_location = detect_country(merged_text, config)
                title_ja = translate_text(title_original, cache, config.get("default_language", "ja"))
                summary_ja = translate_text(summary_original, cache, config.get("default_language", "ja"))
                item = {
                    "id": make_item_id(link, title_original),
                    "title": title_ja,
                    "summary": summary_ja,
                    "title_original": title_original,
                    "summary_original": summary_original,
                    "summary_ai": summarize_text(summary_ja or summary_original),
                    "link": link,
                    "source": name,
                    "source_type": source_type,
                    "source_tier": tier,
                    "source_priority": priority,
                    "published_at": published.isoformat(),
                    "topics": classify_topics(merged_text, config),
                    "policy_tags": classify_policy_tags(merged_text, config),
                    "vaccines": classify_vaccines(merged_text, config),
                    "variants": extract_variants(merged_text, config),
                    "target_location": target_location,
                    "target_country": target_location["name_ja"],
                    "target_region": target_location["region"],
                    "source_location": {"key": origin["key"], "name_ja": origin["name_ja"], "lat": origin["lat"], "lng": origin["lng"], "region": origin["region"], "label": origin_label},
                    "plot": {
                        "source": {"lat": origin["lat"], "lng": origin["lng"], "label": origin_label, "country": origin["name_ja"], "region": origin["region"]},
                        "target": {"lat": target_location["lat"], "lng": target_location["lng"], "label": target_location["name_ja"], "country": target_location["name_ja"], "region": target_location["region"]}
                    }
                }
                all_items.append(item)
                count += 1
            feed_status.append({"name": name, "url": url, "status": "ok", "items": count, "tier": tier})
        except Exception as exc:
            feed_status.append({"name": name, "url": url, "status": "error", "error": str(exc), "tier": tier})
    all_items = dedupe_items(all_items)[: int(config.get("max_items", 250))]
    news = {"title": config.get("title", "Vaccine and Immunization Monitoring"), "description": config.get("description", ""), "generated_at": now_utc.isoformat(), "item_count": len(all_items), "plot_mode_default": config.get("default_plot_mode", "source"), "feed_status": feed_status, "items": all_items}
    save_json(NEWS_PATH, news)
    save_json(CACHE_PATH, cache)
    print(f"Wrote {NEWS_PATH} with {len(all_items)} items")

if __name__ == "__main__":
    main()
