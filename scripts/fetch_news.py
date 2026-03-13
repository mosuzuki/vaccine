#!/usr/bin/env python3
import json
import re
import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime
from html import unescape

import feedparser
import requests
import trafilatura
from deep_translator import GoogleTranslator
from rapidfuzz import fuzz


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "config.json"
DATA_DIR = ROOT / "data"
NEWS_PATH = DATA_DIR / "news.json"
CACHE_PATH = DATA_DIR / "translation_cache.json"
TEXT_CACHE_PATH = DATA_DIR / "article_text_cache.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VaccineMonitoringBot/1.0; +https://github.com/)"
}
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "from", "by", "at", "is", "are", "was", "were",
    "be", "been", "this", "that", "these", "those", "it", "its", "as", "will", "can", "may", "into", "about", "after", "before",
    "during", "than", "their", "they", "them", "we", "our", "you", "your", "new", "update", "updates", "said", "say",
    "vaccine", "vaccines", "immunization", "immunisation"
}


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


def split_sentences(text: str):
    text = normalize_space(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [normalize_space(p) for p in parts if len(normalize_space(p)) > 20]


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


def classify_vaccines(text: str, config: dict):
    text_l = (text or "").lower()
    vaccine_keywords = config.get("vaccine_keywords", {})
    vaccines = []
    for vaccine, words in vaccine_keywords.items():
        if any(word.lower() in text_l for word in words):
            vaccines.append(vaccine)
    return vaccines


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
                "region": info["region"],
            })
    if not matches:
        return {"key": "unknown", "name_ja": "不明", "lat": 20.0, "lng": 0.0, "region": "Unknown"}
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


def fetch_article_text(url: str, cache: dict) -> str:
    if not url:
        return ""
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    if key in cache:
        return cache[key]
    text = ""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.ok and resp.text:
            extracted = trafilatura.extract(
                resp.text,
                url=url,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
                output_format="txt",
            )
            text = normalize_space(extracted or "")
    except Exception:
        text = ""
    cache[key] = text
    return text


def summarize_article(title: str, text: str, fallback: str) -> str:
    base_text = text if text and len(text) >= 180 else fallback
    base_text = normalize_space(base_text)
    if not base_text:
        return normalize_space(title)

    sentences = split_sentences(base_text)
    if not sentences:
        return base_text[:160]

    words = re.findall(r"[A-Za-z][A-Za-z0-9\-\.]+", base_text.lower())
    freq = Counter(w for w in words if len(w) > 2 and w not in STOPWORDS)

    scored = []
    for i, sent in enumerate(sentences[:12]):
        sent_words = re.findall(r"[A-Za-z][A-Za-z0-9\-\.]+", sent.lower())
        score = sum(freq.get(w, 0) for w in sent_words)
        if re.search(r"recommend|approve|authorization|schedule|guideline|trial|study|campaign|advisory|committee|policy", sent.lower()):
            score += 6
        if i == 0:
            score += 2
        scored.append((score, i, sent))

    scored.sort(key=lambda x: (-x[0], x[1]))
    best = sorted(scored[:2], key=lambda x: x[1])
    summary = " ".join(s for _, _, s in best)
    summary = normalize_space(summary)
    return summary[:280]


def should_keep_item(item: dict, config: dict) -> bool:
    topics = set(item.get("topics", []))
    if not topics.intersection({"policy", "research", "communication"}):
        return False
    allowed_source_types = set(config.get("pickup_source_types", ["official", "academic"]))
    if item.get("source_type") not in allowed_source_types:
        return False
    text = f"{item.get('title_original','')} {item.get('summary_original','')} {item.get('article_text_original','')}".lower()
    exclude_terms = [t.lower() for t in config.get("exclude_terms", [])]
    if any(term in text for term in exclude_terms):
        return False
    require_groups = config.get("require_keyword_groups", [])
    if require_groups:
        ok = False
        for group in require_groups:
            if all(any(term.lower() in text for term in options) for options in group):
                ok = True
                break
        if not ok:
            return False
    return True


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
        summary_a = (item.get("summary_ai_original") or item.get("summary_ai") or "").lower()
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            other = items[j]
            title_b = (other.get("title_original") or other.get("title") or "").lower()
            url_b = other.get("link", "")
            summary_b = (other.get("summary_ai_original") or other.get("summary_ai") or "").lower()
            title_score = fuzz.token_set_ratio(title_a, title_b)
            summary_score = fuzz.token_set_ratio(summary_a, summary_b)
            same_url = (url_a == url_b and url_a != "")
            if same_url or title_score >= 92 or (title_score >= 80 and summary_score >= 88):
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
        "title": config.get("title", "Vaccine and Immunization Monitoring"),
        "description": config.get("description", ""),
        "generated_at": now_utc.isoformat(),
        "item_count": 0,
        "feed_status": [],
        "items": [],
    }


def main():
    config = load_json(CONFIG_PATH, {})
    cache = load_json(CACHE_PATH, {})
    text_cache = load_json(TEXT_CACHE_PATH, {})
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(days=int(config.get("days_back", 14)))

    feeds = config.get("feeds", [])
    news = build_empty_news(config, now_utc)

    if not feeds:
        save_json(NEWS_PATH, news)
        save_json(CACHE_PATH, cache)
        save_json(TEXT_CACHE_PATH, text_cache)
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

            seen = 0
            kept = 0
            for entry in parsed.entries:
                published = parse_date(entry)
                if published < since:
                    continue
                seen += 1

                title_original = normalize_space(entry.get("title", ""))
                summary_original = extract_summary(entry)
                link = entry.get("link", "")
                article_text_original = fetch_article_text(link, text_cache)
                merged_text = f"{title_original} {summary_original} {article_text_original}"

                topics = classify_topics(merged_text, config)
                vaccines = classify_vaccines(merged_text, config)
                variants = extract_variants(merged_text, config)
                location = detect_country(merged_text, config)
                summary_ai_original = summarize_article(title_original, article_text_original, summary_original)

                item = {
                    "id": make_item_id(link, title_original),
                    "title": translate_text(title_original, cache, config.get("default_language", "ja")),
                    "summary": translate_text(summary_original, cache, config.get("default_language", "ja")),
                    "summary_ai": translate_text(summary_ai_original, cache, config.get("default_language", "ja")),
                    "title_original": title_original,
                    "summary_original": summary_original,
                    "summary_ai_original": summary_ai_original,
                    "article_text_original": article_text_original[:5000],
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
                    "lng": location["lng"],
                }

                if should_keep_item(item, config):
                    all_items.append(item)
                    kept += 1

            feed_status.append({"name": name, "url": url, "status": "ok", "seen": seen, "kept": kept})
        except Exception as exc:
            feed_status.append({"name": name, "url": url, "status": "error", "error": str(exc)})

    all_items.sort(key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
    all_items = dedupe_items(all_items)
    all_items = all_items[: int(config.get("max_items", 200))]

    news = {
        "title": config.get("title", "Vaccine and Immunization Monitoring"),
        "description": config.get("description", ""),
        "generated_at": now_utc.isoformat(),
        "item_count": len(all_items),
        "feed_status": feed_status,
        "items": all_items,
    }

    save_json(NEWS_PATH, news)
    save_json(CACHE_PATH, cache)
    save_json(TEXT_CACHE_PATH, text_cache)
    print(f"Wrote {NEWS_PATH} with {len(all_items)} items")


if __name__ == "__main__":
    main()
