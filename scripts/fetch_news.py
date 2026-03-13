from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import feedparser
import requests
from deep_translator import GoogleTranslator
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "config.json"
OUTPUT_PATH = ROOT / "data" / "news.json"
CACHE_PATH = ROOT / "data" / "translation_cache.json"
USER_AGENT = "ebs-research-dashboard/2.0 (+https://github.com/)"
MAX_ITEMS_PER_FEED = 25
MAX_TOTAL_ITEMS = 250
TRANSLATION_SLEEP_SEC = 0.2


def load_config() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_translation_cache() -> Dict[str, str]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_translation_cache(cache: Dict[str, str]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_space(text)


def parse_datetime(entry: Any) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def normalized_title(title: str) -> str:
    title = strip_html(title).lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return normalize_space(title)


def tokenize(text: str) -> List[str]:
    text = normalized_title(text)
    tokens = [t for t in text.split() if len(t) > 2 and t not in {"the", "and", "for", "with", "from", "that", "this", "into", "after", "about", "your", "their", "new", "news"}]
    return tokens


def short_fingerprint(title: str) -> str:
    tokens = tokenize(title)[:8]
    return " ".join(tokens)


def make_dedup_key(title: str, country: str, primary_classification: str) -> str:
    base = f"{short_fingerprint(title)}|{country}|{primary_classification}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def make_cache_key(text: str) -> str:
    return hashlib.sha1(normalize_space(text).encode("utf-8")).hexdigest()


def infer_topic(text: str, config: Dict[str, Any]) -> str:
    text_l = text.lower()
    scores: List[Tuple[str, int]] = []
    for topic, keywords in config["topic_keywords"].items():
        score = sum(1 for kw in keywords if kw in text_l)
        scores.append((topic, score))
    best_topic, best_score = max(scores, key=lambda x: x[1])
    return best_topic if best_score > 0 else "general"


def infer_event_type(text: str, config: Dict[str, Any]) -> str:
    text_l = text.lower()
    scores: List[Tuple[str, int]] = []
    for event_type, keywords in config["event_type_keywords"].items():
        score = sum(1 for kw in keywords if kw in text_l)
        scores.append((event_type, score))
    best_type, best_score = max(scores, key=lambda x: x[1])
    return best_type if best_score > 0 else "general_update"


def infer_classifications(text: str, config: Dict[str, Any]) -> List[str]:
    text_l = text.lower()
    classifications = []
    for label, keywords in config.get("auto_classification_keywords", {}).items():
        if any(kw in text_l for kw in keywords):
            classifications.append(label)
    return classifications or ["general"]


def infer_country(text: str, feed: Dict[str, Any], config: Dict[str, Any]) -> str:
    text_l = text.lower()
    for country, patterns in config["country_patterns"].items():
        for pat in patterns:
            if pat in text_l:
                return country
    return feed.get("default_country", "Global")


def infer_region(country: str, feed: Dict[str, Any], config: Dict[str, Any]) -> str:
    return config.get("region_by_country", {}).get(country) or feed.get("region") or "Global"


def infer_signal_level(classifications: List[str], topic: str, event_type: str, text: str, is_official: bool) -> str:
    text_l = text.lower()
    if event_type in {"outbreak_report", "safety_update"} or "outbreak" in classifications:
        return "high"
    if topic in {"variant", "supply_access"} or "variant" in classifications:
        return "medium"
    if any(term in text_l for term in ["emergency", "death", "hospital", "hospitalization", "fatal"]):
        return "high"
    return "medium" if is_official else "low"


def summarize(text: str, max_len: int = 280) -> str:
    text = normalize_space(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def fetch_feed(url: str) -> requests.Response:
    return requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})


def choose_better_item(current: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    score_map = {"high": 3, "medium": 2, "low": 1}
    current_score = (
        (2 if current.get("is_official") else 0),
        score_map.get(current.get("signal_level"), 0),
        current.get("published", "")
    )
    candidate_score = (
        (2 if candidate.get("is_official") else 0),
        score_map.get(candidate.get("signal_level"), 0),
        candidate.get("published", "")
    )
    return candidate if candidate_score > current_score else current


def deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    for item in sorted(items, key=lambda x: x["published"], reverse=True):
        matched_index = None
        for idx, existing in enumerate(deduped):
            same_country = existing.get("country") == item.get("country")
            class_overlap = bool(set(existing.get("classifications", [])) & set(item.get("classifications", [])))
            title_similarity = fuzz.token_set_ratio(existing.get("title", ""), item.get("title", ""))
            fp_similarity = fuzz.token_set_ratio(existing.get("title_fingerprint", ""), item.get("title_fingerprint", ""))
            same_link = existing.get("link") == item.get("link")
            if same_link or ((same_country or existing.get("country") == "Global" or item.get("country") == "Global") and (class_overlap or existing.get("topic") == item.get("topic")) and (title_similarity >= 92 or fp_similarity >= 95)):
                matched_index = idx
                break
        if matched_index is None:
            item["duplicate_count"] = 1
            item["merged_sources"] = [item.get("source_name")]
            deduped.append(item)
        else:
            existing = deduped[matched_index]
            chosen = choose_better_item(existing, item)
            chosen["duplicate_count"] = existing.get("duplicate_count", 1) + 1
            merged = list(dict.fromkeys((existing.get("merged_sources") or [existing.get("source_name")]) + [item.get("source_name")]))
            chosen["merged_sources"] = merged
            chosen["dedup_notes"] = f"Merged {chosen['duplicate_count']} similar items"
            deduped[matched_index] = chosen
    return deduped


def build_translator() -> GoogleTranslator | None:
    try:
        return GoogleTranslator(source="auto", target="ja")
    except Exception:
        return None


def translate_text(text: str, translator: GoogleTranslator | None, cache: Dict[str, str]) -> str:
    text = normalize_space(text)
    if not text:
        return ""
    key = make_cache_key(text)
    if key in cache:
        return cache[key]
    translated = text
    if translator is not None:
        try:
            translated = translator.translate(text)
            time.sleep(TRANSLATION_SLEEP_SEC)
        except Exception:
            translated = text
    cache[key] = translated
    return translated


def collect() -> Dict[str, Any]:
    config = load_config()
    cache = load_translation_cache()
    translator = build_translator()
    items: List[Dict[str, Any]] = []
    feed_status: List[Dict[str, Any]] = []

    for feed in config["feeds"]:
        try:
            response = fetch_feed(feed["url"])
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise ValueError(getattr(parsed, "bozo_exception", "Invalid feed"))

            count = 0
            for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
                title = strip_html(getattr(entry, "title", "Untitled"))
                link = getattr(entry, "link", feed["url"])
                summary_raw = strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
                if not title:
                    continue
                text = f"{title} {summary_raw}"
                topic = infer_topic(text, config)
                event_type = infer_event_type(text, config)
                classifications = infer_classifications(text, config)
                primary_classification = next((c for c in ["outbreak", "variant", "vaccine"] if c in classifications), classifications[0])
                country = infer_country(text, feed, config)
                region = infer_region(country, feed, config)
                is_official = feed.get("source_type") == "official"
                signal_level = infer_signal_level(classifications, topic, event_type, text, is_official)
                latlon = config.get("country_centroids", {}).get(country) or config.get("country_centroids", {}).get("Global")
                tags = list(dict.fromkeys([topic, event_type, region, *classifications]))
                dedup_key = make_dedup_key(title, country, primary_classification)
                source_domain = urlparse(link).netloc or urlparse(feed["url"]).netloc
                title_ja = translate_text(title, translator, cache)
                summary_ja = translate_text(summarize(summary_raw or title), translator, cache)
                items.append(
                    {
                        "title": title,
                        "title_ja": title_ja,
                        "link": link,
                        "summary": summarize(summary_raw or title),
                        "summary_ja": summary_ja,
                        "published": parse_datetime(entry),
                        "discovered_at": datetime.now(timezone.utc).isoformat(),
                        "source_name": feed["name"],
                        "source_domain": source_domain,
                        "source_type": feed.get("source_type", "unknown"),
                        "is_official": is_official,
                        "country": country,
                        "region": region,
                        "topic": topic,
                        "event_type": event_type,
                        "classifications": classifications,
                        "primary_classification": primary_classification,
                        "signal_level": signal_level,
                        "is_asia_priority": country in config.get("asia_priority_countries", []),
                        "lat": latlon[0] if latlon else None,
                        "lon": latlon[1] if latlon else None,
                        "tags": tags,
                        "dedup_key": dedup_key,
                        "title_fingerprint": short_fingerprint(title),
                    }
                )
                count += 1
            feed_status.append({"name": feed["name"], "url": feed["url"], "status": "ok", "items": count})
        except Exception as exc:  # noqa: BLE001
            feed_status.append({"name": feed["name"], "url": feed["url"], "status": "error", "error": str(exc)})

    final_items = deduplicate_items(items)
    final_items.sort(key=lambda x: x["published"], reverse=True)
    final_items = final_items[:MAX_TOTAL_ITEMS]
    save_translation_cache(cache)

    return {
        "title": config["title"],
        "description": config["description"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(final_items),
        "feed_status": feed_status,
        "items": final_items,
    }


def main() -> None:
    payload = collect()
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} with {payload['item_count']} items")


if __name__ == "__main__":
    main()
