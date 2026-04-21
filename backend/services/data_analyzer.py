"""
RivalSense Data Analyzer v2
Python 驱动的本地 NLP 分析管线，零 API 调用、零 Token 消耗。
1. 双语情感打分 (SnowNLP + VADER)
2. 痛点关键词提取与聚类 (TF-IDF + KMeans)
3. 统计摘要聚合
"""
import logging
import os
import ssl
import re
from collections import Counter

import pandas as pd
import numpy as np
import jieba
import snownlp
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.cluster import KMeans
from services.relevance import LOW_INFORMATION_TOKENS, clean_visible_text, score_record

logger = logging.getLogger(__name__)

# ── NLTK 初始化（自动修复 SSL 证书问题）──────────────────
import nltk

# 修复 macOS 常见的 SSL 证书问题
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

from nltk.sentiment.vader import SentimentIntensityAnalyzer
vader_analyzer = SentimentIntensityAnalyzer()


CUSTOM_STOPWORDS = {
    "app", "apps", "product", "service", "company", "review", "reviews",
    "reddit", "comment", "comments", "thread", "post", "posts", "hn",
    "github", "issue", "issues", "stackoverflow", "stack", "overflow",
    "user", "users", "people", "thing", "things", "way", "time", "day",
    "work", "works", "working", "worked", "make", "makes", "made",
    "use", "used", "using", "try", "tried", "trying", "know", "think",
    "want", "wanted", "getting", "going", "actually", "probably",
    "maybe", "pretty", "quite", "also", "even", "much", "many",
    "still", "anyone", "someone", "everyone", "anything", "something",
    "one", "two", "get", "got", "gets", "like", "just", "really",
    "they", "them", "their", "there", "here", "me", "my", "mine",
    "you", "your", "yours", "we", "our", "ours", "he", "she", "it",
    "pavel", "durov", "apple", "google", "microsoft",
    "的", "了", "和", "是", "就", "都", "而", "及", "与", "在", "我",
    "也", "有", "很", "会", "但", "这", "个", "它", "被", "将", "对",
    "没", "来", "去", "要", "一个", "这个", "那个", "用户", "产品",
}


PROBLEM_PHRASES = {
    r"doesn['’]?t work|do not work|not working|won['’]?t work": "not_working",
    r"can['’]?t login|cannot login|log in|sign in": "login_problem",
    r"feature request": "feature_request",
    r"missing feature|missing features": "missing_feature",
    r"too expensive|overpriced|price increase": "pricing_problem",
    r"customer support|support team": "customer_support",
    r"hard to use|difficult to use": "hard_to_use",
    r"data breach|security incident": "security_incident",
    r"slow performance|very slow": "slow_performance",
}


PAIN_CATEGORY_RULES = [
    ("稳定性与故障", {"bug", "crash", "error", "broken", "not_working", "fail", "downtime"}),
    ("性能与响应速度", {"slow", "laggy", "slow_performance", "latency", "performance"}),
    ("价格与订阅成本", {"expensive", "overpriced", "pricing", "pricing_problem", "subscription", "refund"}),
    ("功能缺口与集成", {"missing", "missing_feature", "feature_request", "integration", "api", "export", "import"}),
    ("易用性与界面复杂度", {"confusing", "clunky", "unintuitive", "hard_to_use", "complex", "ui", "ux"}),
    ("账号与登录", {"login", "login_problem", "account", "auth", "authentication", "password"}),
    ("客服与退款", {"support", "customer_support", "refund", "ticket", "response"}),
    ("隐私与安全", {"privacy", "security", "security_incident", "breach", "encrypted", "encryption"}),
]


# ── 工具函数 ──────────────────────────────────────────

def detect_language(text):
    """简单根据中文字符比例判断语言"""
    if not text:
        return "en"
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return "zh" if (chinese_chars / max(len(text), 1)) > 0.1 else "en"


def analyze_sentiment(text):
    """
    计算文本情感分数，范围 [-1.0, 1.0]
    """
    if not text or len(text) < 5:
        return 0.0
    lang = detect_language(text)
    if lang == "zh":
        try:
            s_obj = snownlp.SnowNLP(text)
            return (s_obj.sentiments - 0.5) * 2
        except Exception:
            return 0.0
    else:
        scores = vader_analyzer.polarity_scores(text)
        return scores.get("compound", 0.0)


def _competitor_stopwords(competitor_name):
    words = set()
    for token in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", (competitor_name or "").lower()):
        words.add(token)
    return words


def _normalize_problem_phrases(text):
    text = clean_visible_text(text).lower()
    text = text.replace("can't", "cannot").replace("won't", "will not")
    for pattern, replacement in PROBLEM_PHRASES.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _prepare_keyword_doc(text, stopwords):
    text = _normalize_problem_phrases(text)
    if detect_language(text) == "zh":
        words = jieba.lcut(text)
    else:
        words = re.findall(r"[a-zA-Z_]{2,}|[\u4e00-\u9fff]{2,}", text)

    filtered = []
    for word in words:
        word = word.lower().strip("_")
        if len(word) < 2 or word in stopwords:
            continue
        if word.isdigit():
            continue
        filtered.append(word)
    return " ".join(filtered)


def _is_quality_term(term, stopwords):
    term = term.lower().replace("_", " ").strip()
    if len(term) < 3:
        return False
    parts = [p for p in term.split() if p]
    if not parts:
        return False
    if all(part in stopwords or part in LOW_INFORMATION_TOKENS for part in parts):
        return False
    if any(part.isdigit() for part in parts):
        return False
    return True


def _dedupe_terms(terms, stopwords, limit=6):
    cleaned = []
    for term in terms:
        normalized = term.lower().replace("_", " ").strip()
        if not _is_quality_term(normalized, stopwords):
            continue
        if any(normalized == existing or normalized in existing for existing in cleaned):
            continue
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _label_cluster(keywords):
    keyword_set = {kw.replace(" ", "_") for kw in keywords}
    keyword_set.update(part for kw in keywords for part in kw.split())

    for label, triggers in PAIN_CATEGORY_RULES:
        if keyword_set & triggers:
            return label

    if keywords:
        return f"围绕 {keywords[0]} 的集中抱怨"
    return "未命名痛点"


def _source_breakdown(records):
    counter = Counter(r.get("source_type", "unknown") for r in records)
    return dict(counter.most_common(5))


def _pain_candidate_records(records, competitor_name):
    candidates = []
    for record in records:
        scores = {
            "pain_score": record.get("pain_score"),
            "business_score": record.get("business_score"),
            "positive_score": record.get("positive_score"),
        }
        if scores["pain_score"] is None:
            scores.update(score_record(record, competitor_name))

        pain_score = float(scores.get("pain_score") or 0)
        business_score = float(scores.get("business_score") or 0)
        positive_score = float(scores.get("positive_score") or 0)
        source = record.get("source_type", "unknown")
        sentiment = record.get("sentiment", "neutral")

        is_feedback_source = source in {
            "g2_review", "appstore_review", "review_site", "alternativeto",
            "reddit_comment", "reddit", "github_issue", "stackoverflow",
            "hackernews_comment", "search_result", "search_news",
            "zhihu_search", "xiaohongshu_search", "weibo_search",
            "bilibili_search", "tieba_search", "v2ex_search",
            "juejin_search", "cn_media_search",
        }
        has_pain_signal = pain_score >= 1.5 or (is_feedback_source and pain_score >= 1)
        is_negative = sentiment == "negative" or record.get("sentiment_score", 0) < -0.15
        business_only = business_score > pain_score and pain_score < 2

        if has_pain_signal and not business_only and positive_score < 3:
            candidates.append({**record, **scores})
        elif is_feedback_source and is_negative and pain_score >= 1 and not business_only:
            candidates.append({**record, **scores})

    return candidates


def _simple_phrase_cluster(records, stopwords):
    docs = [
        _prepare_keyword_doc((r.get("title", "") + " " + r.get("content", "")), stopwords)
        for r in records
    ]
    words = []
    for doc in docs:
        words.extend(doc.split())
    common = [
        word for word, _ in Counter(words).most_common(12)
        if _is_quality_term(word, stopwords)
    ]
    keywords = _dedupe_terms(common, stopwords, limit=5)
    if not keywords:
        return []
    best = sorted(records, key=lambda r: float(r.get("pain_score", 0)), reverse=True)[0]
    return [{
        "cluster_label": _label_cluster(keywords),
        "count": len(records),
        "keywords": keywords,
        "sample_quote": clean_visible_text(best.get("content", ""), max_len=180),
        "source_breakdown": _source_breakdown(records),
    }]


def extract_pain_points_clusters(records, n_clusters=5, competitor_name=""):
    """
    对负面评论进行 TF-IDF 关键词提取 + KMeans 主题聚类
    """
    candidates = _pain_candidate_records(records, competitor_name)
    if not candidates:
        return []

    stopwords = set(ENGLISH_STOP_WORDS) | CUSTOM_STOPWORDS | LOW_INFORMATION_TOKENS
    stopwords |= _competitor_stopwords(competitor_name)

    if len(candidates) < 3:
        return _simple_phrase_cluster(candidates, stopwords)

    processed_docs = []
    for record in candidates:
        text = record.get("title", "") + " " + record.get("content", "")
        processed_docs.append(_prepare_keyword_doc(text, stopwords))

    valid_indices = [i for i, doc in enumerate(processed_docs) if doc.strip()]
    valid_docs = [processed_docs[i] for i in valid_indices]
    original_records = [candidates[i] for i in valid_indices]

    if len(valid_docs) < 3:
        return _simple_phrase_cluster(original_records, stopwords)

    try:
        vectorizer = TfidfVectorizer(
            max_df=0.72,
            min_df=1,
            max_features=260,
            ngram_range=(1, 3),
            token_pattern=r"(?u)\b[a-zA-Z_\u4e00-\u9fff][a-zA-Z_\u4e00-\u9fff]{1,}\b",
        )
        tfidf_matrix = vectorizer.fit_transform(valid_docs)
    except ValueError:
        return []

    feature_names = vectorizer.get_feature_names_out()
    actual_clusters = min(n_clusters, max(1, len(valid_docs) // 2), len(valid_docs))
    if actual_clusters <= 1:
        return _simple_phrase_cluster(original_records, stopwords)

    kmeans = KMeans(n_clusters=actual_clusters, random_state=42, n_init=10)
    kmeans.fit(tfidf_matrix)

    clusters_info = []
    for i in range(actual_clusters):
        cluster_indices = np.where(kmeans.labels_ == i)[0]
        if len(cluster_indices) == 0:
            continue

        cluster_center = kmeans.cluster_centers_[i]
        top_keyword_indices = cluster_center.argsort()[-18:][::-1]
        raw_keywords = [feature_names[idx] for idx in top_keyword_indices]
        top_keywords = _dedupe_terms(raw_keywords, stopwords, limit=6)
        if not top_keywords:
            continue

        sample_records = [original_records[idx] for idx in cluster_indices]
        sample_records.sort(
            key=lambda r: (float(r.get("pain_score", 0)), len(r.get("content", ""))),
            reverse=True,
        )
        sample = clean_visible_text(sample_records[0].get("content", ""), max_len=180)

        clusters_info.append({
            "cluster_label": _label_cluster(top_keywords),
            "count": int(len(cluster_indices)),
            "keywords": top_keywords,
            "sample_quote": sample,
            "source_breakdown": _source_breakdown(sample_records),
        })

    return sorted(clusters_info, key=lambda x: x["count"], reverse=True)


def identify_business_signals(records):
    """
    通过关键词直接扫描重大商业信号
    """
    SIGNALS = {
        "fundraising": ["funding", "raised $", "raised 1", "raised 2", "raised 3", "raised 4", "raised 5", "raised 6", "raised 7", "raised 8", "raised 9", "series", "融资", "估值", "千万", "billion"],
        "pricing_change": ["price increase", "涨价", "new plan", "enterprise plan", "subscription plan", "定价调整"],
        "product_launch": ["launch", "release", "发布", "上线", "new feature", "introducing", "announcing"],
        "talent_move": ["hiring", "layoff", "裁员", "招聘", "fired"],
        "legal_regulatory": ["lawsuit", "regulatory", "regulator", "arrest", "ban", "blocked", "诉讼", "监管", "被捕", "封禁"],
        "security_incident": ["data breach", "security incident", "leak", "outage", "宕机", "泄露", "安全事故"],
    }
    SIGNAL_LABELS = {
        "fundraising": "🔴 融资动态",
        "pricing_change": "🟡 定价变动",
        "product_launch": "🟢 产品发布",
        "talent_move": "🟠 人才变动",
        "legal_regulatory": "🟣 法务监管",
        "security_incident": "🔵 安全事故",
    }

    signals_found = []
    for record in records:
        text = (record.get("title", "") + " " + record.get("content", "")).lower()
        if not text:
            continue
        for signal_type, keywords in SIGNALS.items():
            for kw in keywords:
                if kw in text:
                    if not any(s["type"] == signal_type for s in signals_found):
                        signals_found.append({
                            "type": signal_type,
                            "label": SIGNAL_LABELS.get(signal_type, signal_type),
                            "trigger_keyword": kw,
                            "title": record.get("title", text[:60]),
                            "source": record.get("source_type", "unknown")
                        })
                    break
    return signals_found


# ── 主处理入口 ──────────────────────────────────────────

def process_and_summarize(competitor_name, crawled_data):
    """
    主数据处理流，返回:
    1. statistical_summary: 供给 LLM 的高度浓缩纯文本事实
    2. analytics: 结构化 JSON，供前端可视化面板渲染
    """
    if not crawled_data:
        empty_analytics = {
            "total_records": 0,
            "source_distribution": {},
            "sentiment_distribution": {"negative": 0, "neutral": 0, "positive": 0},
            "avg_negative_score": 0,
            "pain_clusters": [],
            "business_signals": [],
            "top_negative_quotes": [],
        }
        return "数据不足，无法生成统计摘要。", empty_analytics

    # 1. 情感打分
    for record in crawled_data:
        if "sentiment_score" not in record:
            text = (record.get("title", "") + " " + record.get("content", ""))
            score = analyze_sentiment(text)
            record["sentiment_score"] = score
            if score < -0.15:
                record["sentiment"] = "negative"
            elif score > 0.15:
                record["sentiment"] = "positive"
            else:
                record["sentiment"] = "neutral"
        elif record.get("sentiment") == "mixed":
            record["sentiment"] = "negative"

        scores = score_record(record, competitor_name)
        for key, value in scores.items():
            record.setdefault(key, value)

    # 2. 基本统计
    total = len(crawled_data)
    source_counter = Counter(r.get("source_type", "unknown") for r in crawled_data)
    source_stats = dict(source_counter)

    sentiment_counter = Counter(r.get("sentiment", "neutral") for r in crawled_data)
    neg_count = sentiment_counter.get("negative", 0)
    neu_count = sentiment_counter.get("neutral", 0)
    pos_count = sentiment_counter.get("positive", 0)

    neg_pct = (neg_count / max(total, 1)) * 100
    neu_pct = (neu_count / max(total, 1)) * 100
    pos_pct = (pos_count / max(total, 1)) * 100

    neg_scores = [r["sentiment_score"] for r in crawled_data if r.get("sentiment") == "negative"]
    avg_neg_score = sum(neg_scores) / max(len(neg_scores), 1) if neg_scores else 0.0

    # 3. 痛点聚类
    clusters = extract_pain_points_clusters(crawled_data, competitor_name=competitor_name)

    # 4. 商业信号
    signals = identify_business_signals(crawled_data)

    # 5. 最具代表性的负面原话 (Top 5)
    neg_records_sorted = sorted(
        [
            r for r in crawled_data
            if r.get("signal_intent") == "pain"
            or (r.get("sentiment") == "negative" and r.get("pain_score", 0) >= 1)
        ],
        key=lambda x: (x.get("sentiment_score", 0), -x.get("pain_score", 0))
    )
    top_negative_quotes = []
    for r in neg_records_sorted[:5]:
        top_negative_quotes.append({
            "content": clean_visible_text(r.get("content", ""), max_len=180),
            "source": r.get("source_type", "unknown"),
            "score": round(r.get("sentiment_score", 0), 2),
            "pain_score": round(r.get("pain_score", 0), 1),
        })

    # 6. 生成纯文本统计摘要（给 LLM 的浓缩弹药）
    source_str = " | ".join([f"{k}: {v}条" for k, v in source_stats.items()])
    summary_lines = [
        f"=== {competitor_name} 数据统计摘要 (总记录: {total} 条) ===",
        f"来源分布: {source_str}",
        f"情感分布: 负面 {neg_pct:.1f}% ({neg_count}条) | 中性 {neu_pct:.1f}% | 正面 {pos_pct:.1f}%",
        f"平均负面得分: {avg_neg_score:.2f} (越接近 -1.0 抱怨越强烈)",
        "",
    ]

    if clusters:
        summary_lines.append("Top 痛点主题聚类:")
        for i, c in enumerate(clusters[:5], 1):
            kws = ", ".join(c["keywords"][:4])
            summary_lines.append(f"  #{i} {c['cluster_label']} | 影响 {c['count']} 人 | 核心短语: {kws}")
            summary_lines.append(f"     代表原话: \"{c['sample_quote'][:100]}\"")
    else:
        summary_lines.append("痛点分析: 收集的负面数据较少，未形成明显聚类。")

    summary_lines.append("")
    if signals:
        summary_lines.append("探测到的重要商业信号:")
        for s in signals:
            summary_lines.append(f"  - {s['label']}: {s['title'][:60]}")
    else:
        summary_lines.append("商业动态: 近期无重大投融资或涨价动态。")

    text_summary = "\n".join(summary_lines)

    # 7. 结构化 JSON（供前端渲染）
    analytics = {
        "total_records": total,
        "source_distribution": source_stats,
        "sentiment_distribution": {
            "negative": neg_count,
            "neutral": neu_count,
            "positive": pos_count,
        },
        "sentiment_percentages": {
            "negative": round(neg_pct, 1),
            "neutral": round(neu_pct, 1),
            "positive": round(pos_pct, 1),
        },
        "avg_negative_score": round(avg_neg_score, 2),
        "pain_clusters": clusters,
        "business_signals": signals,
        "top_negative_quotes": top_negative_quotes,
    }

    logger.info(
        f"[{competitor_name}] Python NLP 分析完成: "
        f"{total}条数据, 负面{neg_count}条, {len(clusters)}个痛点簇, {len(signals)}个商业信号"
    )

    return text_summary, analytics
