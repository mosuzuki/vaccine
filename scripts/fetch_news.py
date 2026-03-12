
import json, re, hashlib, html, sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "data" / "news.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (GitHub Actions Vaccine Dashboard)"}

COUNTRY_PATTERNS = {
    "Japan": [r"\bjapan\b", r"\bjapanese\b", r"\btokyo\b", r"\bosaka\b"],
    "China": [r"\bchina\b", r"\bchinese\b", r"\bbeijing\b", r"\bshanghai\b"],
    "Hong Kong": [r"\bhong kong\b"],
    "South Korea": [r"\bsouth korea\b", r"\bkorea\b", r"\bseoul\b"],
    "Taiwan": [r"\btaiwan\b"],
    "India": [r"\bindia\b", r"\bindian\b"],
    "Thailand": [r"\bthailand\b", r"\bthai\b"],
    "Philippines": [r"\bphilippines\b", r"\bphilippine\b", r"\bmanila\b"],
    "United States": [r"\bunited states\b", r"\bu\.s\.\b", r"\busa\b", r"\bcdc\b", r"\bfda\b"],
    "United Kingdom": [r"\buk\b", r"\bunited kingdom\b", r"\bengland\b", r"\bscotland\b", r"\bnhs\b", r"\bmhra\b", r"\bukhsa\b"],
    "European Union": [r"\beuropean union\b", r"\beu\b", r"\bema\b", r"\becdc\b"],
    "Global": [r"\bwho\b", r"\bunicef\b", r"\bgavi\b", r"\bglobal\b", r"\bworldwide\b"]
}

TOPIC_RULES = {
    "Policy / Recommendation": [r"recommend", r"committee", r"schedule", r"program", r"programme", r"guidance", r"advis", r"coverage", r"uptake", r"campaign"],
    "Regulatory / Approval": [r"approv", r"authori[sz]", r"indication", r"label", r"prequal", r"ep(ar|a)r", r"new medicine"],
    "Safety": [r"safety", r"adverse", r"side effect", r"signal", r"warning", r"recall", r"medwatch", r"vaers"],
    "Product / R&D": [r"trial", r"study", r"candidate", r"phase", r"research", r"effectiveness", r"new vaccine", r"new immuni[sz]ation"],
    "Outbreak response": [r"outbreak", r"response vaccination", r"mass vaccination", r"ring vaccination", r"measles", r"polio", r"cholera", r"yellow fever", r"mpox", r"ebola"]
}

KEYWORDS = []
for vals in CONFIG["keyword_groups"].values():
    KEYWORDS.extend(vals)
KEYWORDS = sorted(set(KEYWORDS), key=len, reverse=True)

def norm_space(s:str)->str:
    return re.sub(r"\s+", " ", (s or "").strip())

def clean_text(s:str)->str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("\xa0", " ")
    return norm_space(s)

def normalize_url(url:str)->str:
    if not url:
        return ""
    url = html.unescape(url).strip()
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "url" in qs and "news.google.com" in parsed.netloc:
        url = unquote(qs["url"][0])
        parsed = urlparse(url)
    # strip common tracking params
    base_query = []
    for k, vals in sorted(parse_qs(parsed.query).items()):
        if k.lower().startswith(("utm_", "ga_", "fbclid", "gclid", "ocid")):
            continue
        if k.lower() in {"output", "rss"}:
            continue
        for v in vals:
            base_query.append(f"{k}={v}")
    query = "&".join(base_query)
    clean = parsed._replace(query=query, fragment="")
    return clean.geturl()

def published_iso(entry):
    candidates = [entry.get("published"), entry.get("updated")]
    structs = [entry.get("published_parsed"), entry.get("updated_parsed")]
    for s in candidates:
        if s:
            try:
                return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    for st in structs:
        if st:
            try:
                dt = datetime(*st[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return None

def score_item(text:str)->int:
    t = text.lower()
    score = 0
    for kw in KEYWORDS:
        if kw.lower() in t:
            score += 2 if len(kw) > 7 else 1
    if "vaccine" in t or "vaccin" in t or "immuni" in t:
        score += 2
    return score

def detect_country(text:str)->str:
    t = text.lower()
    for country, patterns in COUNTRY_PATTERNS.items():
        for p in patterns:
            if re.search(p, t):
                return country
    return "Global"

def country_to_region(country:str)->str:
    mapping = {
        "Japan":"Asia", "China":"Asia", "Hong Kong":"Asia", "South Korea":"Asia", "Taiwan":"Asia",
        "India":"Asia","Thailand":"Asia","Philippines":"Asia",
        "United States":"North America","United Kingdom":"Europe","European Union":"Europe",
        "Global":"Global"
    }
    return mapping.get(country, "Global")

def detect_topics(text:str):
    t = text.lower()
    topics = []
    for topic, pats in TOPIC_RULES.items():
        if any(re.search(p, t) for p in pats):
            topics.append(topic)
    if not topics:
        topics = ["General vaccine news"]
    return topics

def keyword_hits(text:str):
    t = text.lower()
    hits = [kw for kw in KEYWORDS if kw.lower() in t]
    return hits[:8]

def is_relevant(text:str)->bool:
    t = text.lower()
    if ("vaccine" in t or "vaccin" in t or "immuni" in t or "nirsevimab" in t or "beyfortus" in t):
        return True
    return score_item(t) >= 2

def fallback_summary(entry):
    txt = clean_text(entry.get("summary") or entry.get("description") or "")
    if txt:
        return txt[:320]
    return ""

def fetch_feed(feed):
    url = feed["url"]
    parsed = feedparser.parse(url, request_headers=HEADERS)
    items = []
    if getattr(parsed, "bozo", 0) and not getattr(parsed, "entries", None):
        # fallback to requests for servers that dislike feedparser
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
    for entry in parsed.entries[:CONFIG["max_items_per_feed"]]:
        title = clean_text(entry.get("title", ""))
        summary = fallback_summary(entry)
        link = normalize_url(entry.get("link", ""))
        body = f"{title} {summary}"
        if not title or not link:
            continue
        if not is_relevant(body):
            continue
        items.append({
            "title": title,
            "summary": summary,
            "url": link,
            "published_at": published_iso(entry),
            "source_name": feed["name"],
            "source_type": feed.get("source_type", "official"),
            "source_home": feed.get("source_home", ""),
            "seed_region": feed.get("region", "Global"),
            "seed_country": feed.get("country", "Global"),
            "score": score_item(body),
        })
    return items

def make_id(url, title):
    base = normalize_url(url) + "||" + norm_space(title).lower()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:14]

def dedupe(items):
    seen = {}
    for item in items:
        key = normalize_url(item["url"])
        title_key = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()
        combined = key or title_key
        if combined in seen:
            old = seen[combined]
            if item.get("score", 0) > old.get("score", 0):
                seen[combined] = item
        else:
            seen[combined] = item
    # fuzzy title dedupe
    out = []
    seen_titles = set()
    for item in sorted(seen.values(), key=lambda x: (x.get("published_at") or "", x.get("score",0)), reverse=True):
        tkey = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()
        short = " ".join(tkey.split()[:12])
        if short in seen_titles:
            continue
        seen_titles.add(short)
        out.append(item)
    return out

def enrich(items):
    enriched = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=CONFIG["lookback_days"])
    for item in items:
        text = f'{item["title"]} {item.get("summary","")}'
        country = detect_country(text)
        region = country_to_region(country)
        if country == "Global" and item.get("seed_country") not in {"Global","EU","Asia"}:
            country = item["seed_country"]
        if region == "Global" and item.get("seed_region") not in {"Global"}:
            region = item["seed_region"]
        pub = item.get("published_at")
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z","+00:00"))
                if dt < cutoff:
                    continue
            except Exception:
                pass
        item["id"] = make_id(item["url"], item["title"])
        item["country"] = country
        item["region"] = region
        item["topics"] = detect_topics(text)
        item["keyword_hits"] = keyword_hits(text)
        enriched.append(item)
    return enriched

def build_meta(items):
    now = datetime.now(timezone.utc)
    last7 = now - timedelta(days=7)
    last30 = now - timedelta(days=30)
    stats = {"total": len(items), "last7": 0, "last30": 0, "by_region": {}, "by_topic": {}, "by_source": {}}
    for it in items:
        pub = it.get("published_at")
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z","+00:00"))
                if dt >= last7:
                    stats["last7"] += 1
                if dt >= last30:
                    stats["last30"] += 1
            except Exception:
                pass
        stats["by_region"][it["region"]] = stats["by_region"].get(it["region"], 0) + 1
        for tp in it["topics"]:
            stats["by_topic"][tp] = stats["by_topic"].get(tp, 0) + 1
        stats["by_source"][it["source_name"]] = stats["by_source"].get(it["source_name"], 0) + 1
    return stats

def main():
    all_items = []
    errors = []
    for feed in CONFIG["feeds"]:
        try:
            all_items.extend(fetch_feed(feed))
        except Exception as e:
            errors.append({"feed": feed["name"], "url": feed["url"], "error": str(e)})
    all_items = dedupe(all_items)
    all_items = enrich(all_items)
    def sort_key(x):
        return (x.get("published_at") or "", x.get("score", 0))
    all_items = sorted(all_items, key=sort_key, reverse=True)[:CONFIG["max_total_items"]]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "Vaccine & Immunization News Dashboard",
        "description": "Auto-updated vaccine and immunization news dashboard for GitHub Pages.",
        "stats": build_meta(all_items),
        "errors": errors,
        "items": all_items,
        "sources": CONFIG["feeds"],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(all_items)} items to {OUTPUT}")
    if errors:
        print(f"Warnings: {len(errors)} feeds had errors", file=sys.stderr)

if __name__ == "__main__":
    main()
