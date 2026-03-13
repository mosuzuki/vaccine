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
ARCHIVE_PATH = DATA_DIR / "archive.json"
CACHE_PATH = DATA_DIR / "translation_cache.json"
TEXT_CACHE_PATH = DATA_DIR / "article_text_cache.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VaccineImmunizationMonitoringBot/1.0)"}
STOPWORDS = {
    "the","a","an","and","or","to","of","in","on","for","with","from","by","at","is","are","was","were",
    "be","been","this","that","these","those","it","its","as","will","can","may","into","about","after","before",
    "during","than","their","they","them","we","our","you","your","new","update","updates","said","say",
    "vaccine","vaccines","immunization","immunisation"
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
    return normalize_space(unescape(text))


def sanitize_xml(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]", "", text)


def parse_feed(url: str):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    content = sanitize_xml(resp.text)
    return feedparser.parse(content)


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


def split_sentences(text: str):
    text = normalize_space(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [normalize_space(p) for p in parts if len(normalize_space(p)) > 20]


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
    text_l = (text or "").lower()
    out = []
    for topic, words in config.get("topic_keywords", {}).items():
        if any(w.lower() in text_l for w in words):
            out.append(topic)
    return sorted(set(out))


def classify_policy_tags(text: str, config: dict):
    text_l = (text or "").lower()
    out = []
    for tag, words in config.get("policy_tags", {}).items():
        if any(w.lower() in text_l for w in words):
            out.append(tag)
    return sorted(set(out))


def classify_vaccines(text: str, config: dict):
    text_l = (text or "").lower()
    out = []
    for vaccine, words in config.get("vaccine_keywords", {}).items():
        if any(w.lower() in text_l for w in words):
            out.append(vaccine)
    return sorted(set(out))


def extract_variants(text: str, config: dict):
    text_l = (text or "").lower()
    return sorted({p for p in config.get("variant_patterns", []) if p.lower() in text_l})


def detect_country(text: str, config: dict):
    text_l = f" {text.lower()} "
    matches = []
    for key, info in config.get("country_map", {}).items():
        pattern = rf"(?<![a-z]){re.escape(key.lower())}(?![a-z])"
        if re.search(pattern, text_l):
            matches.append({
                "key": key,
                "name_ja": info["name_ja"],
                "lat": info["lat"],
                "lng": info["lng"],
                "region": info["region"],
                "label": info["name_ja"]
            })
    if not matches:
        return {"key": "unknown", "name_ja": "不明", "lat": 20.0, "lng": 0.0, "region": "Unknown", "label": "不明"}
    asia = [m for m in matches if m["region"] == "Asia"]
    return asia[0] if asia else matches[0]


def origin_location(feed: dict, config: dict):
    origin_key = feed.get("origin_key")
    info = config.get("country_map", {}).get(origin_key, {})
    return {
        "key": origin_key or "unknown",
        "name_ja": info.get("name_ja", "不明"),
        "lat": info.get("lat", 20.0),
        "lng": info.get("lng", 0.0),
        "region": info.get("region", "Unknown"),
        "label": feed.get("origin_label") or info.get("name_ja", "不明"),
    }


def fetch_article_text(url: str, cache: dict) -> str:
    if not url:
        return ""
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    if key in cache:
        return cache[key]
    text = ""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        if resp.ok and resp.text:
            extracted = trafilatura.extract(resp.text, url=resp.url, include_comments=False, include_tables=False, favor_precision=True, output_format="txt")
            text = normalize_space(extracted or "")
    except Exception:
        text = ""
    cache[key] = text
    return text


def summarize_article(title: str, article_text: str, fallback: str) -> str:
    base_text = article_text if article_text and len(article_text) >= 180 else fallback
    base_text = normalize_space(base_text)
    if not base_text:
        return normalize_space(title)[:200]
    sentences = split_sentences(base_text)
    if not sentences:
        return base_text[:220]
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-\.]+", base_text.lower())
    freq = Counter(w for w in words if len(w) > 2 and w not in STOPWORDS)
    scored = []
    for i, sent in enumerate(sentences[:14]):
        sent_words = re.findall(r"[A-Za-z][A-Za-z0-9\-\.]+", sent.lower())
        score = sum(freq.get(w, 0) for w in sent_words)
        if re.search(r"recommend|approve|authoriz|schedule|guideline|trial|study|campaign|advisory|committee|policy|confidence|hesitancy|immunogenicity|effectiveness", sent.lower()):
            score += 6
        if i == 0:
            score += 2
        scored.append((score, i, sent))
    picked = sorted(scored[:2], key=lambda x: (x[1])) if len(scored) <= 2 else sorted(sorted(scored, key=lambda x: (-x[0], x[1]))[:2], key=lambda x: x[1])
    summary = normalize_space(" ".join(s for _, _, s in picked))
    return summary[:280]


def should_keep_item(title: str, summary: str, article_text: str, link: str, source_type: str, config: dict) -> bool:
    if source_type not in set(config.get("pickup_source_types", [])):
        return False
    strict = config.get("strict_filters", {})
    title_l = (title or "").lower()
    summary_l = (summary or "").lower()
    article_l = (article_text or "").lower()
    link_l = (link or "").lower()
    combined = f"{title_l} {summary_l} {article_l}".strip()

    for pat in strict.get("exclude_title_patterns", []):
        if pat.lower() in title_l:
            return False
    for pat in strict.get("exclude_url_patterns", []):
        if pat.lower() in link_l:
            return False
    for pat in strict.get("exclude_text_patterns", []):
        if pat.lower() in combined:
            return False
    if any(h.lower() in article_l for h in strict.get("hub_markers", [])):
        return False
    if not any(k.lower() in combined for k in strict.get("require_any_keywords", [])):
        return False
    if not any(k.lower() in combined for k in strict.get("require_topic_keywords", [])):
        return False

    topics = classify_topics(combined, config)
    if not set(topics).intersection({"policy", "research", "communication"}):
        return False

    if source_type in {"academic", "preprint"}:
        return bool(topics)
    if source_type == "official":
        if len(article_l) >= 120:
            return True
        return any(k.lower() in title_l for k in strict.get("require_topic_keywords", []))
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
        sum_a = (item.get("summary_ai_original") or item.get("summary_ai") or item.get("summary_original") or "").lower()
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            other = items[j]
            title_b = (other.get("title_original") or other.get("title") or "").lower()
            url_b = other.get("link", "")
            sum_b = (other.get("summary_ai_original") or other.get("summary_ai") or other.get("summary_original") or "").lower()
            title_score = fuzz.token_set_ratio(title_a, title_b)
            summary_score = fuzz.token_set_ratio(sum_a, sum_b)
            if (url_a and url_a == url_b) or title_score >= 93 or (title_score >= 82 and summary_score >= 90):
                group.append(other)
                used.add(j)
        group.sort(key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
        primary = dict(group[0])
        primary["duplicate_count"] = len(group)
        primary["duplicate_sources"] = sorted({g.get("source", "") for g in group if g.get("source")})
        deduped.append(primary)
    deduped.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return deduped


def merge_archive(existing_items, new_items):
    merged = {item.get("id"): item for item in existing_items if item.get("id")}
    for item in new_items:
        item_id = item.get("id")
        if not item_id:
            continue
        if item_id in merged:
            prev = merged[item_id]
            # keep latest metadata while preserving first_seen
            first_seen = prev.get("first_seen_at") or item.get("published_at")
            prev.update(item)
            prev["first_seen_at"] = first_seen
            prev["last_seen_at"] = datetime.now(timezone.utc).isoformat()
            merged[item_id] = prev
        else:
            item = dict(item)
            item["first_seen_at"] = item.get("published_at")
            item["last_seen_at"] = datetime.now(timezone.utc).isoformat()
            merged[item_id] = item
    items = list(merged.values())
    items = dedupe_items(items)
    items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return items


def main():
    config = load_json(CONFIG_PATH, {})
    cache = load_json(CACHE_PATH, {})
    text_cache = load_json(TEXT_CACHE_PATH, {})
    archive = load_json(ARCHIVE_PATH, {"items": []})
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(days=int(config.get("days_back", 14)))
    current_items = []
    feed_status = []

    for feed in config.get("feeds", []):
        name = feed.get("name", "Unknown")
        url = feed.get("url", "")
        source_type = feed.get("source_type", "unknown")
        source_tier = feed.get("source_tier", "")
        source_priority = int(feed.get("priority", 0))
        src_loc = origin_location(feed, config)
        seen = 0
        kept = 0
        try:
            parsed = parse_feed(url)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise RuntimeError(str(getattr(parsed, "bozo_exception", "Feed parse error")))
            for entry in parsed.entries:
                published = parse_date(entry)
                if published < since:
                    continue
                seen += 1
                title_original = normalize_space(entry.get("title", ""))
                summary_original = extract_summary(entry)
                link = entry.get("link", "")
                article_text_original = fetch_article_text(link, text_cache)
                if not should_keep_item(title_original, summary_original, article_text_original, link, source_type, config):
                    continue
                merged = normalize_space(f"{title_original} {summary_original} {article_text_original}")
                topics = classify_topics(merged, config)
                policy_tags = classify_policy_tags(merged, config)
                vaccines = classify_vaccines(merged, config)
                variants = extract_variants(merged, config)
                target_loc = detect_country(merged, config)
                summary_ai_original = summarize_article(title_original, article_text_original, summary_original)
                item = {
                    "id": make_item_id(link, title_original),
                    "title": translate_text(title_original, cache, config.get("default_language", "ja")),
                    "summary": translate_text(summary_original, cache, config.get("default_language", "ja")),
                    "summary_ai": translate_text(summary_ai_original, cache, config.get("default_language", "ja")),
                    "title_original": title_original,
                    "summary_original": summary_original,
                    "summary_ai_original": summary_ai_original,
                    "article_text_original": article_text_original,
                    "link": link,
                    "source": name,
                    "source_type": source_type,
                    "source_tier": source_tier,
                    "source_priority": source_priority,
                    "published_at": published.isoformat(),
                    "topics": topics,
                    "policy_tags": policy_tags,
                    "vaccines": vaccines,
                    "variants": variants,
                    "target_country": target_loc["name_ja"],
                    "source_location": src_loc,
                    "plot": {"source": src_loc, "target": target_loc},
                    "location": target_loc,
                    "region": target_loc["region"],
                    "country": target_loc["name_ja"],
                    "lat": target_loc["lat"],
                    "lng": target_loc["lng"]
                }
                current_items.append(item)
                kept += 1
            feed_status.append({"name": name, "url": url, "status": "ok", "seen": seen, "kept": kept})
        except Exception as exc:
            feed_status.append({"name": name, "url": url, "status": "error", "error": str(exc)})

    current_items.sort(key=lambda x: (x.get("published_at", ""), x.get("source_priority", 0)), reverse=True)
    current_items = dedupe_items(current_items)
    current_items = current_items[: int(config.get("max_items", 120))]

    archive_items = merge_archive(archive.get("items", []), current_items)

    news = {
        "title": config.get("title", "Vaccine and Immunization Monitoring"),
        "description": config.get("description", ""),
        "generated_at": now_utc.isoformat(),
        "item_count": len(current_items),
        "archive_count": len(archive_items),
        "days_back": int(config.get("days_back", 14)),
        "plot_mode_default": config.get("plot_mode_default", "source"),
        "feed_status": feed_status,
        "items": current_items,
    }
    archive_obj = {
        "title": config.get("title", "Vaccine and Immunization Monitoring"),
        "description": config.get("description", ""),
        "generated_at": now_utc.isoformat(),
        "archive_count": len(archive_items),
        "days_back": int(config.get("days_back", 14)),
        "items": archive_items,
    }
    save_json(NEWS_PATH, news)
    save_json(ARCHIVE_PATH, archive_obj)
    save_json(CACHE_PATH, cache)
    save_json(TEXT_CACHE_PATH, text_cache)
    print(f"Wrote {NEWS_PATH} with {len(current_items)} items")
    print(f"Wrote {ARCHIVE_PATH} with {len(archive_items)} items")


if __name__ == "__main__":
    main()
