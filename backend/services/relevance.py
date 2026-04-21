"""
Record relevance scoring and denoising for RivalSense.

The scraper should recall broadly, but the analyzer should only see records that
are plausibly about the tracked product and useful for pain or business signals.
"""
import math
import re
from copy import deepcopy
from urllib.parse import urlparse

from bs4 import BeautifulSoup


HIGH_TRUST_SOURCES = {
    "rss",
    "blog",
    "changelog",
    "g2_review",
    "appstore_review",
    "review_site",
}

CONVERSATION_SOURCES = {
    "reddit",
    "reddit_comment",
    "hackernews",
    "hackernews_comment",
    "github_issue",
    "stackoverflow",
    "alternativeto",
    "review_site",
    "search_result",
    "search_news",
    "zhihu_search",
    "xiaohongshu_search",
    "weibo_search",
    "bilibili_search",
    "tieba_search",
    "v2ex_search",
    "juejin_search",
    "cn_media_search",
}

PAIN_PATTERNS = [
    r"\bbug(s)?\b", r"\bcrash(es|ed|ing)?\b", r"\berror(s)?\b",
    r"\bfail(s|ed|ing)?\b", r"\bbroken\b", r"\bnot working\b",
    r"\bdoesn['’]?t work\b", r"\bcan['’]?t\b", r"\bcannot\b",
    r"\bslow\b", r"\blag(gy|s|ging)?\b", r"\bdowntime\b",
    r"\bunreliable\b", r"\bconfusing\b", r"\bclunky\b",
    r"\bunintuitive\b", r"\bmissing\b", r"\black(s|ing)?\b",
    r"\bexpensive\b", r"\boverpriced\b", r"\bprice increase\b",
    r"\brefund\b", r"\bcancel(led|ing)?\b", r"\bunsubscribe\b",
    r"\bfeature request\b", r"\bplease add\b", r"\bwish\b",
    r"\bshould\b", r"\bneed(s|ed)?\b", r"\balternative\b",
    r"\bswitched to\b", r"\bmigrat(ed|ing)?\b",
    "卡顿", "崩溃", "闪退", "难用", "复杂", "太贵", "贵",
    "慢", "问题", "故障", "缺少", "不稳定", "退款", "取消订阅",
]

BUSINESS_PATTERNS = [
    r"\bfunding\b", r"\braised\s+(\$|\d)", r"\bseries [a-z]\b",
    r"\bacquir(ed|es|ing|ition)\b", r"\bmerger\b", r"\bipo\b",
    r"\bvaluation\b", r"\blaunch(ed|es|ing)?\b", r"\brelease(d|s)?\b",
    r"\bannounc(ed|es|ing)\b", r"\bprice increase\b", r"\bnew plan\b",
    r"\benterprise\b", r"\bhiring\b", r"\blayoff(s)?\b",
    r"\boutage\b", r"\bdata breach\b", r"\bsecurity incident\b",
    r"\blawsuit\b", r"\bregulator(y|s)?\b",
    "融资", "估值", "收购", "并购", "上市", "发布", "上线",
    "定价", "涨价", "企业版", "裁员", "招聘", "宕机", "泄露",
]

POSITIVE_PATTERNS = [
    r"\bamazing\b", r"\blove\b", r"\bawesome\b", r"\bgreat\b",
    r"\bwonderful\b", r"\bexcellent\b", r"\bperfect\b", r"\bbest\b",
    r"\bfantastic\b", r"\bincredible\b", r"\brecommend\b",
    "好用", "推荐", "优秀", "完美", "很棒", "太好了", "没什么问题", "没有问题",
]

LOW_INFORMATION_TOKENS = {
    "the", "and", "for", "you", "your", "they", "them", "their", "this",
    "that", "with", "from", "have", "has", "had", "was", "were", "are",
    "one", "get", "got", "just", "like", "still", "anyone", "really",
}

SOURCE_QUALITY = {
    "g2_review": 5,
    "appstore_review": 5,
    "review_site": 4,
    "reddit_comment": 4,
    "reddit": 3,
    "github_issue": 4,
    "stackoverflow": 4,
    "hackernews_comment": 3,
    "hackernews": 2,
    "alternativeto": 3,
    "search_result": 2,
    "search_news": 3,
    "zhihu_search": 4,
    "xiaohongshu_search": 4,
    "weibo_search": 3,
    "bilibili_search": 3,
    "tieba_search": 3,
    "v2ex_search": 4,
    "juejin_search": 3,
    "cn_media_search": 3,
    "changelog": 5,
    "rss": 4,
    "blog": 3,
}


def clean_visible_text(text, max_len=None):
    if not text:
        return ""
    text = BeautifulSoup(str(text), "html.parser").get_text(separator=" ", strip=True)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[[^\]]{1,80}\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_len:
        return text[:max_len]
    return text


def _slugify(value):
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def product_terms(competitor_name):
    name = clean_visible_text(competitor_name).lower()
    raw_parts = re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", name)
    terms = {name, _slugify(name)}
    terms.update(part for part in raw_parts if part not in LOW_INFORMATION_TOKENS)
    terms = {term for term in terms if term and len(term) >= 2}
    return terms


def _pattern_score(text, patterns, strong_weight=2.0, weak_weight=1.0):
    score = 0.0
    matched = []
    for pattern in patterns:
        if pattern.startswith("\\") or pattern.startswith("r"):
            found = re.search(pattern, text, re.IGNORECASE)
        else:
            found = pattern.lower() in text
        if found:
            weight = strong_weight if len(pattern) > 10 or " " in pattern else weak_weight
            score += weight
            matched.append(pattern.replace("\\b", "").replace("\\", ""))
    return score, matched[:8]


def score_record(record, competitor_name):
    title = clean_visible_text(record.get("title", ""), max_len=500)
    content = clean_visible_text(record.get("content", ""), max_len=4000)
    url = record.get("url", "") or ""
    source = record.get("source_type", "unknown")
    text = f"{title} {content}".lower()
    url_text = url.lower()

    terms = product_terms(competitor_name)
    trusted = source in HIGH_TRUST_SOURCES

    relevance = 0.0
    matched_terms = []
    for term in terms:
        if not term:
            continue
        if term in text:
            relevance += 4.0 if " " in term or "-" in term else 2.0
            matched_terms.append(term)
        if term and term in url_text:
            relevance += 1.5

    if trusted:
        relevance += 2.0
    if source in CONVERSATION_SOURCES:
        relevance += 0.5
    if record.get("score"):
        relevance += min(2.0, math.log1p(max(float(record.get("score", 0)), 0)) / 3)

    pain_score, pain_terms = _pattern_score(text, PAIN_PATTERNS, strong_weight=2.0)
    business_score, business_terms = _pattern_score(text, BUSINESS_PATTERNS, strong_weight=1.7)
    positive_score, positive_terms = _pattern_score(text, POSITIVE_PATTERNS, strong_weight=1.5)
    quality_score = float(SOURCE_QUALITY.get(source, 1))

    rating = str(record.get("rating", "") or "")
    if rating.isdigit():
        rating_value = int(rating)
        if rating_value <= 3:
            pain_score += 2.0
        elif rating_value >= 4:
            positive_score += 2.0

    content_len = len(content)
    if content_len >= 120:
        quality_score += 0.5
    if content_len > 1800:
        quality_score += 0.5

    if pain_score >= 2:
        intent = "pain"
    elif business_score >= 1.7:
        intent = "business"
    elif positive_score >= 2 and pain_score == 0:
        intent = "positive"
    else:
        intent = "discussion"

    priority_score = (
        relevance * 1.4
        + pain_score * 2.0
        + business_score * 1.1
        + quality_score
        - positive_score * 0.8
    )

    return {
        "relevance_score": round(relevance, 2),
        "pain_score": round(pain_score, 2),
        "business_score": round(business_score, 2),
        "positive_score": round(positive_score, 2),
        "quality_score": round(quality_score, 2),
        "priority_score": round(priority_score, 2),
        "signal_intent": intent,
        "matched_terms": sorted(set(matched_terms))[:8],
        "pain_terms": pain_terms,
        "business_terms": business_terms,
        "positive_terms": positive_terms,
    }


def should_keep_record(record, competitor_name):
    source = record.get("source_type", "unknown")
    title = clean_visible_text(record.get("title", ""))
    content = clean_visible_text(record.get("content", ""))
    text_len = len(content)
    scores = score_record(record, competitor_name)

    if text_len < 25 and len(title) < 12:
        return False, "too_short", scores

    if scores["positive_score"] >= 3 and scores["pain_score"] < 1 and scores["business_score"] < 1:
        return False, "mostly_positive", scores
    if scores["positive_score"] >= scores["pain_score"] and scores["pain_score"] <= 1 and scores["business_score"] < 1:
        return False, "weak_positive_or_neutral", scores

    if source in HIGH_TRUST_SOURCES:
        return True, "", scores

    if scores["relevance_score"] < 2.5:
        return False, "low_relevance", scores

    if scores["pain_score"] >= 1 or scores["business_score"] >= 1:
        return True, "", scores

    if source in CONVERSATION_SOURCES and scores["relevance_score"] >= 5:
        return True, "", scores

    return False, "low_signal", scores


def dedupe_records(records):
    seen = set()
    unique = []
    for record in records:
        url = (record.get("url") or "").split("?")[0].rstrip("/")
        title = clean_visible_text(record.get("title", "")).lower()[:120]
        content = clean_visible_text(record.get("content", "")).lower()[:180]
        key = (url, title, content)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def filter_and_rank_records(records, competitor_name, max_records=700):
    kept = []
    rejected = 0

    for record in dedupe_records(records):
        ok, reason, scores = should_keep_record(record, competitor_name)
        if not ok:
            rejected += 1
            continue

        enriched = deepcopy(record)
        enriched.update(scores)
        enriched["content"] = clean_visible_text(enriched.get("content", ""), max_len=3000)
        enriched["title"] = clean_visible_text(enriched.get("title", ""), max_len=300)
        if reason:
            enriched["noise_reason"] = reason
        kept.append(enriched)

    kept.sort(key=lambda item: item.get("priority_score", 0), reverse=True)
    return kept[:max_records], {
        "kept": len(kept[:max_records]),
        "rejected": rejected,
        "deduped_total": len(kept) + rejected,
    }
