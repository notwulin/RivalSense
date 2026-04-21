"""
RivalSense 数据抓取服务 v2 — 生产级重写
核心升级：
1. Jina Reader API 深度抓取 JS 渲染页（G2 等）
2. RSS 文章全文深度抓取（follow link）
3. 评论情感预标注（过滤正面评价，聚焦真实痛点）
4. 更大抓取量 + 更好的内容清洗
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import re
import logging
import time
from config import Config
from services.relevance import filter_and_rank_records

logger = logging.getLogger(__name__)

USER_AGENT = "RivalSense/2.0 (AI Competitive Intelligence; contact@rivalsense.ai)"
REQUEST_TIMEOUT = 20
JINA_READER_BASE = "https://r.jina.ai"


def _is_valid_url(url):
    """检查 URL 是否有效可抓取"""
    if not url or not url.startswith("http"):
        return False
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return bool(parsed.netloc)
    except Exception:
        return False

# ── 情感关键词库（用于评论预筛选）──────────────────────
NEGATIVE_KEYWORDS = [
    # 英文
    "bug", "crash", "slow", "laggy", "frustrat", "disappoint", "confus",
    "annoying", "terrible", "horrible", "worst", "hate", "broken",
    "missing", "lack", "expensive", "overpriced", "complicated",
    "difficult", "clunky", "unintuitive", "unreliable", "downtime",
    "glitch", "error", "fail", "poor", "bad", "issue", "problem",
    "can't", "cannot", "doesn't work", "not working", "wish",
    "should", "need", "want", "would be nice", "please add",
    "feature request", "deal breaker", "switched to", "moved to",
    "looking for alternative", "cancel", "unsubscribe",
    # 中文
    "卡顿", "崩溃", "闪退", "难用", "复杂", "贵", "慢", "差",
    "失望", "问题", "故障", "缺少", "不好", "垃圾", "坑",
    "bug", "不稳定", "不方便", "退款", "取消订阅",
]

POSITIVE_KEYWORDS = [
    "amazing", "love", "awesome", "great", "wonderful", "excellent",
    "perfect", "best", "fantastic", "incredible", "recommend",
    "easy to use", "intuitive", "powerful", "beautiful", "elegant",
    "太好了", "好用", "推荐", "优秀", "完美", "棒",
]


def _classify_sentiment(text):
    """
    对评论文本进行情感粗分类
    返回: 'negative' | 'mixed' | 'positive' | 'neutral'
    """
    if not text:
        return "neutral"
    text_lower = text.lower()

    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)

    if neg_count >= 2 or (neg_count >= 1 and pos_count == 0):
        return "negative"
    elif neg_count >= 1 and pos_count >= 1:
        return "mixed"
    elif pos_count >= 2:
        return "positive"
    return "neutral"


def _safe_get(url, headers=None, timeout=None):
    """带超时和错误处理的 HTTP GET"""
    default_headers = {"User-Agent": USER_AGENT}
    if headers:
        default_headers.update(headers)
    try:
        resp = requests.get(
            url, headers=default_headers,
            timeout=timeout or REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.warning(f"抓取失败 {url}: {e}")
        return None


def _clean_text(text, max_len=800):
    """清洗文本：去 HTML、合并空白、截断"""
    if not text:
        return ""
    # 去 HTML
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
    # 合并多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 去 emoji 和特殊字符（保留中日韩字符）
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+', '', text)
    return text[:max_len]


# ── Jina Reader — 任意 URL 深度抓取（处理 JS 渲染）──────

def _firecrawl_read(url, timeout=45):
    """
    通过 Firecrawl API 进行深度抓取
    专治 Cloudflare 高级反爬（如 G2等）
    """
    if not Config.FIRECRAWL_API_KEY:
        return None
        
    logger.info(f"🔥 使用 Firecrawl 抓取高防页面: {url}")
    headers = {
        "Authorization": f"Bearer {Config.FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "formats": ["markdown"],
        "waitFor": 3000
    }
    
    try:
        # 兼容 v1 和 v0(v2) API 地址，这里使用标准 v1 endpoints
        api_url = "https://api.firecrawl.dev/v1/scrape"
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        if resp.ok:
            data = resp.json()
            # Firecrawl v1 结构: data -> markdown
            md = data.get("data", {}).get("markdown", "")
            if len(md) > 100:
                return md
        logger.warning(f"Firecrawl 返回异常 {url} | 状态码: {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"Firecrawl 抓取失败 {url}: {e}")
        return None

def _jina_read(url, timeout=25):
    """
    通过 Jina Reader API 获取任意网页的清洁 Markdown 文本
    免费、无需 API Key、自动处理 JS 渲染
    """
    jina_url = f"{JINA_READER_BASE}/{url}"
    headers = {
        "Accept": "text/plain",
        "X-Return-Format": "text",
    }
    try:
        resp = requests.get(jina_url, headers=headers, timeout=timeout)
        if resp.ok and len(resp.text) > 100:
            return resp.text
        logger.warning(f"Jina Reader 返回内容不足 {url}: {len(resp.text)} chars")
        return None
    except Exception as e:
        logger.warning(f"Jina Reader 失败 {url}: {e}")
        return None


def _fetch_article_content(url):
    """
    深度抓取单篇文章的全文内容
    优先 Jina Reader，回退 BeautifulSoup
    """
    # 优先用 Jina（处理 JS 渲染）
    content = _jina_read(url, timeout=15)
    if content and len(content) > 200:
        # 截取前 1500 字作为文章摘要（节省 token)
        return _clean_text(content, max_len=1500)

    # 回退到 BeautifulSoup
    resp = _safe_get(url)
    if not resp:
        return ""

    try:
        soup = BeautifulSoup(resp.text, "lxml")

        # 移除噪音元素
        for tag in soup.select("nav, footer, header, aside, script, style, [class*='sidebar'], [class*='nav'], [class*='footer'], [class*='cookie']"):
            tag.decompose()

        # 提取正文
        article = soup.select_one("article, main, [role='main'], .post-content, .article-content, .entry-content")
        if article:
            text = article.get_text(separator=" ", strip=True)
        else:
            # 回退：提取所有 <p> 标签
            paragraphs = soup.select("p")
            text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

        return _clean_text(text, max_len=1500)
    except Exception as e:
        logger.warning(f"文章内容提取失败 {url}: {e}")
        return ""


# ── RSS / Atom 抓取（加深度全文）──────────────────────

def fetch_rss(rss_url, limit=20, deep_scrape=True):
    """
    使用 feedparser 解析 RSS/Atom feed
    deep_scrape=True 时，自动 follow 链接抓取文章全文
    """
    if not rss_url:
        return []

    try:
        feed = feedparser.parse(rss_url, agent=USER_AGENT)

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS 解析警告 {rss_url}: {feed.bozo_exception}")
            return []

        entries = []
        for entry in feed.entries[:limit]:
            published = ""
            for attr in ("published_parsed", "updated_parsed"):
                parsed = getattr(entry, attr, None)
                if parsed:
                    try:
                        published = datetime(*parsed[:6]).isoformat() + "Z"
                        break
                    except (ValueError, TypeError):
                        published = entry.get("published", entry.get("updated", ""))

            # 基础摘要
            summary = _clean_text(
                entry.get("summary", entry.get("description", entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")),
                max_len=600
            )

            title = entry.get("title", "").strip()
            link = entry.get("link", "")

            # 深度抓取文章全文
            full_content = ""
            if deep_scrape and link and len(summary) < 200:
                full_content = _fetch_article_content(link)
                time.sleep(0.3)  # 礼貌延迟

            entries.append({
                "source_type": "rss",
                "title": title,
                "content": full_content if full_content else summary,
                "url": link,
                "published_at": published,
                "content_length": len(full_content or summary),
            })

        logger.info(f"RSS 抓取成功 {rss_url}: {len(entries)} 条 (深度抓取: {deep_scrape})")
        return entries

    except Exception as e:
        logger.error(f"RSS 抓取异常 {rss_url}: {e}")
        return []


# ── 博客/网页抓取 ──────────────────────────────────────

def fetch_blog(blog_url, limit=10):
    """
    抓取博客首页文章列表 + 逐篇深度抓取
    """
    if not blog_url:
        return []

    # 优先用 Jina 抓取博客首页
    page_text = _jina_read(blog_url)
    if not page_text:
        resp = _safe_get(blog_url)
        if not resp:
            return []
        page_text = resp.text

    try:
        soup = BeautifulSoup(page_text if "<html" in page_text.lower()[:100] else f"<html><body>{page_text}</body></html>", "lxml")
        entries = []

        # 提取文章链接
        article_links = []
        for selector in ["article a[href]", ".post a[href]", "h2 a[href]", "h3 a[href]", ".blog-post a[href]", '[class*="post"] a[href]', '[class*="article"] a[href]']:
            found = soup.select(selector)
            if found:
                for a in found:
                    href = a.get("href", "")
                    title = a.get_text(strip=True)
                    if href and title and len(title) > 5 and href not in [l[0] for l in article_links]:
                        article_links.append((urljoin(blog_url, href), title))
                if len(article_links) >= limit:
                    break

        # 去重
        seen_urls = set()
        unique_links = []
        for url, title in article_links:
            if url not in seen_urls and not url.endswith(('#', '/', blog_url)):
                seen_urls.add(url)
                unique_links.append((url, title))

        # 深度抓取每篇文章
        for url, title in unique_links[:limit]:
            content = _fetch_article_content(url)
            if content and len(content) > 50:
                entries.append({
                    "source_type": "blog",
                    "title": title,
                    "content": content,
                    "url": url,
                    "published_at": "",
                    "content_length": len(content),
                })
                time.sleep(0.3)

        logger.info(f"博客抓取成功 {blog_url}: {len(entries)} 条")
        return entries

    except Exception as e:
        logger.error(f"博客抓取异常 {blog_url}: {e}")
        return []


# ── G2 评论抓取（Jina Reader 深度抓取）──────────────────

def fetch_g2_reviews(g2_url, limit=20):
    """
    通过 Firecrawl / Jina Reader 抓取 G2 评论页（G2 是 JS 渲染且有强反爬）
    自动分类情感，过滤正面评价，聚焦真实用户痛点
    """
    if not g2_url:
        return []

    # 确保 URL 指向评论页
    if "/reviews" not in g2_url:
        g2_url = g2_url.rstrip("/") + "/reviews"

    raw_text = None
    
    # 策略 1：优先尝试 Firecrawl (穿透 Cloudflare)
    if Config.FIRECRAWL_API_KEY:
        raw_text = _firecrawl_read(g2_url)
        
    # 策略 2：如果没有 Firecrawl 或抓取失败，降级到 Jina Reader
    if not raw_text or len(raw_text) < 200:
        if Config.FIRECRAWL_API_KEY:
            logger.warning(f"Firecrawl G2 抓取未获取足够内容，尝试降级到 Jina Reader: {g2_url}")
        else:
            logger.info("未配置 FIRECRAWL_API_KEY，使用 Jina Reader 尝试抓取 G2（可能被拦截）")
        raw_text = _jina_read(g2_url, timeout=30)
        
    # 策略 3：如果依然失败，使用 requests 回退（大概率会 403）
    if not raw_text or len(raw_text) < 200:
        logger.warning(f"G2 高级抓取均未返回足够内容，尝试基础抓取 {g2_url}")
        return _fetch_g2_fallback(g2_url, limit)

    entries = []

    # 从 Jina 返回的 Markdown 文本中提取评论块
    # G2 评论通常包含 "What do you like best", "What do you dislike" 等结构
    review_patterns = [
        # "What do you dislike" 部分是痛点金矿
        r"(?:What do you dislike|What I dislike|Cons|缺点|不满意)[^:：]*[：:]\s*(.+?)(?=What|Review|Pros|优点|满意|\n\n|\Z)",
        # "Problems" 或 "Issues"
        r"(?:Problem|Issue|Complaint)[^:：]*[：:]\s*(.+?)(?=What|Review|\n\n|\Z)",
    ]

    for pattern in review_patterns:
        matches = re.findall(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        for match in matches[:limit]:
            cleaned = _clean_text(match, max_len=400)
            if len(cleaned) > 20:
                sentiment = _classify_sentiment(cleaned)
                entries.append({
                    "source_type": "g2_review",
                    "title": "G2 用户痛点",
                    "content": cleaned,
                    "url": g2_url,
                    "published_at": "",
                    "sentiment": sentiment,
                    "content_length": len(cleaned),
                })

    # 如果结构化提取不足，回退到逐段落扫描
    if len(entries) < 3:
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 40]
        for para in paragraphs:
            cleaned = _clean_text(para, max_len=400)
            sentiment = _classify_sentiment(cleaned)
            # 只保留负面或中性评论（过滤正面！）
            if sentiment in ("negative", "mixed") and len(cleaned) > 30:
                entries.append({
                    "source_type": "g2_review",
                    "title": "G2 用户反馈",
                    "content": cleaned,
                    "url": g2_url,
                    "published_at": "",
                    "sentiment": sentiment,
                    "content_length": len(cleaned),
                })
                if len(entries) >= limit:
                    break

    # 按痛点优先排序：negative > mixed > neutral
    sentiment_order = {"negative": 0, "mixed": 1, "neutral": 2, "positive": 3}
    entries.sort(key=lambda x: sentiment_order.get(x.get("sentiment", "neutral"), 3))

    logger.info(f"G2 评论抓取成功 {g2_url}: {len(entries)} 条（已过滤正面评价）")
    return entries[:limit]


def _fetch_g2_fallback(g2_url, limit):
    """G2 BeautifulSoup 回退方案"""
    resp = _safe_get(g2_url)
    if not resp:
        return []

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        entries = []

        # 尝试多种选择器
        for selector in ['[itemprop="reviewBody"]', '.review-content', '[class*="review-body"]', '.peerInsight']:
            elements = soup.select(selector)
            if elements:
                for el in elements[:limit]:
                    text = _clean_text(el.get_text(), max_len=400)
                    sentiment = _classify_sentiment(text)
                    if sentiment in ("negative", "mixed") and len(text) > 30:
                        entries.append({
                            "source_type": "g2_review",
                            "title": "G2 用户反馈",
                            "content": text,
                            "url": g2_url,
                            "published_at": "",
                            "sentiment": sentiment,
                        })
                break

        return entries
    except Exception as e:
        logger.error(f"G2 回退抓取异常 {g2_url}: {e}")
        return []


# ── AppStore 评论抓取（增强版）──────────────────────────

def fetch_appstore_reviews(appstore_url, limit=20):
    """
    从 AppStore RSS feed 获取评论，自动分类情感
    """
    if not appstore_url:
        return []

    app_id_match = re.search(r'/id(\d+)', appstore_url)
    if not app_id_match:
        # 尝试 Jina 抓取
        return _fetch_reviews_via_jina(appstore_url, "appstore_review", limit)

    app_id = app_id_match.group(1)

    # 尝试多个国家/地区的 RSS
    entries = []
    for country in ["cn", "us"]:
        rss_url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
        resp = _safe_get(rss_url)
        if not resp:
            continue

        try:
            data = resp.json()
            feed_entries = data.get("feed", {}).get("entry", [])

            for entry in feed_entries[:limit]:
                if not isinstance(entry, dict) or "content" not in entry:
                    continue

                title = entry.get("title", {}).get("label", "AppStore 评论")
                content = entry.get("content", {}).get("label", "")
                rating = entry.get("im:rating", {}).get("label", "")
                author = entry.get("author", {}).get("name", {}).get("label", "")

                cleaned = _clean_text(content, max_len=500)
                if not cleaned or len(cleaned) < 15:
                    continue

                sentiment = _classify_sentiment(cleaned)

                # 低分（1-3星）= 高价值痛点
                rating_int = int(rating) if rating and rating.isdigit() else 0
                is_low_rating = rating_int > 0 and rating_int <= 3

                # 核心过滤：只保留真实痛点
                # 1-3 星评论全部保留（低分 = 明确不满）
                # 4-5 星评论仅在情感明确为 negative 时保留（mixed 不够）
                if is_low_rating:
                    # 低分评论直接收录
                    pass
                elif sentiment == "negative":
                    # 高分但明确包含负面抱怨，保留
                    pass
                else:
                    # 4-5星且正面/混合/中性 → 不是痛点，跳过
                    continue

                entries.append({
                    "source_type": "appstore_review",
                    "title": title,
                    "content": f"[{rating}星] {cleaned}" if rating else cleaned,
                    "url": appstore_url,
                    "published_at": "",
                    "sentiment": sentiment if is_low_rating else sentiment,
                    "rating": rating,
                    "is_pain_point": True,
                    "author": author,
                })

        except Exception as e:
            logger.error(f"AppStore RSS 解析异常 ({country}): {e}")

    # 痛点优先排序
    entries.sort(key=lambda x: (
        0 if x.get("is_pain_point") else 1,
        0 if x.get("sentiment") == "negative" else 1,
    ))

    logger.info(f"AppStore 评论抓取成功: {len(entries)} 条")
    return entries[:limit]


def _fetch_reviews_via_jina(url, source_type, limit):
    """通用 Jina Reader 评论抓取"""
    raw_text = _jina_read(url)
    if not raw_text:
        return []

    entries = []
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 30]

    for para in paragraphs[:limit * 2]:
        cleaned = _clean_text(para, max_len=400)
        sentiment = _classify_sentiment(cleaned)
        if sentiment in ("negative", "mixed") and len(cleaned) > 30:
            entries.append({
                "source_type": source_type,
                "title": f"{source_type.replace('_', ' ').title()} 反馈",
                "content": cleaned,
                "url": url,
                "published_at": "",
                "sentiment": sentiment,
            })

    return entries[:limit]


# ── 产品更新日志抓取 ──────────────────────────────────

def fetch_changelog(competitor_name, website_url):
    """
    智能发现并抓取产品更新日志 / Release Notes
    这是判断竞品"核心动作"的最高质量数据源
    """
    if not website_url:
        return []

    # 常见 changelog 路径
    base = website_url.rstrip("/")
    changelog_paths = [
        "/changelog", "/blog/changelog", "/release-notes",
        "/updates", "/whats-new", "/blog/updates",
        "/blog/product-updates", "/product-updates",
    ]

    for path in changelog_paths:
        url = base + path
        content = _jina_read(url, timeout=15)
        if content and len(content) > 300:
            entries = []
            # 按更新条目拆分
            sections = re.split(r'\n(?=#{1,3}\s|\d{4}[-/])', content)
            for section in sections[:10]:
                cleaned = _clean_text(section, max_len=800)
                if len(cleaned) > 50:
                    # 提取日期
                    date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', section)
                    entries.append({
                        "source_type": "changelog",
                        "title": cleaned[:80].split('\n')[0],
                        "content": cleaned,
                        "url": url,
                        "published_at": date_match.group(1) if date_match else "",
                        "content_length": len(cleaned),
                    })

            if entries:
                logger.info(f"Changelog 抓取成功 {url}: {len(entries)} 条")
                return entries

        time.sleep(0.3)

    return []


# ── 统一抓取入口 ──────────────────────────────────────

def crawl_competitor(competitor):
    """
    对单个竞品执行全量抓取（v2 增强版）
    数据源优先级：Changelog > RSS > 博客 > G2评论 > AppStore评论
    返回 (records_list, errors_list)
    """
    all_records = []
    errors = []
    name = competitor.get("name", "未知")

    logger.info(f"════ 开始抓取竞品 [{name}] ════")

    # 1. 产品更新日志（最高价值数据源）
    if competitor.get("website_url"):
        try:
            records = fetch_changelog(name, competitor["website_url"])
            all_records.extend(records)
            logger.info(f"  Changelog: {len(records)} 条")
        except Exception as e:
            errors.append(f"Changelog 抓取失败: {e}")

    # 2. RSS 抓取（深度全文）
    if competitor.get("rss_url"):
        try:
            records = fetch_rss(competitor["rss_url"], limit=50, deep_scrape=True)
            all_records.extend(records)
            logger.info(f"  RSS: {len(records)} 条")
        except Exception as e:
            errors.append(f"RSS 抓取失败: {e}")

    # 3. 博客抓取
    if competitor.get("website_url"):
        try:
            records = fetch_blog(competitor["website_url"], limit=50)
            all_records.extend(records)
            logger.info(f"  博客: {len(records)} 条")
        except Exception as e:
            errors.append(f"博客抓取失败: {e}")

    # 4. G2 评论（已内置情感过滤）
    if competitor.get("g2_url"):
        try:
            records = fetch_g2_reviews(competitor["g2_url"], limit=50)
            all_records.extend(records)
            logger.info(f"  G2 评论: {len(records)} 条")
        except Exception as e:
            errors.append(f"G2 评论抓取失败: {e}")

    # 5. AppStore 评论
    if competitor.get("appstore_url"):
        try:
            records = fetch_appstore_reviews(competitor["appstore_url"], limit=100)
            all_records.extend(records)
            logger.info(f"  AppStore: {len(records)} 条")
        except Exception as e:
            errors.append(f"AppStore 评论抓取失败: {e}")

    # 6. 智能发现引擎 v4 (Reddit + HN + AlternativeTo)
    try:
        from services.discovery import DiscoveryEngine
        import concurrent.futures

        discovered_items = DiscoveryEngine.search_all_channels(
            name,
            max_urls_per_channel=20,
            website_url=competitor.get("website_url", ""),
        )
        if discovered_items:
            logger.info(f"  智能发现引擎: 获取了 {len(discovered_items)} 条原始情报")
            discovery_count = 0

            for item in discovered_items:
                content = item.get("content", "")
                snippet = item.get("snippet", "")
                source_type = item.get("source_type", "discovery")

                # Reddit/评论类数据已自带内容，直接入库
                if source_type in (
                    "reddit",
                    "reddit_comment",
                    "hackernews_comment",
                    "github_issue",
                    "stackoverflow",
                    "alternativeto",
                    "review_site",
                ) and content and len(content) > 20:
                    all_records.append({
                        "source_type": source_type,
                        "title": item.get("title", ""),
                        "content": content[:2000],
                        "url": item.get("url", ""),
                        "published_at": "",
                        "sentiment": "neutral",
                        "content_length": len(content),
                    })
                    discovery_count += 1

                # HN 文章类链接需要深度抓取原文
                elif source_type == "hackernews":
                    url = item.get("url", "")
                    if url and _is_valid_url(url):
                        try:
                            article_content = _fetch_article_content(url)
                            if article_content and len(article_content) > 100:
                                all_records.append({
                                    "source_type": "hackernews",
                                    "title": item.get("title", ""),
                                    "content": article_content[:2000],
                                    "url": url,
                                    "published_at": "",
                                    "sentiment": "neutral",
                                    "content_length": len(article_content),
                                })
                                discovery_count += 1
                        except Exception:
                            pass
                    # 即使原文抓取失败，也用标题入库（作为商业信号检测素材）
                    if not any(r.get("url") == url for r in all_records):
                        all_records.append({
                            "source_type": "hackernews",
                            "title": item.get("title", ""),
                            "content": content or snippet or item.get("title", ""),
                            "url": item.get("url", ""),
                            "published_at": "",
                            "sentiment": "neutral",
                            "content_length": len(content or snippet or ""),
                        })
                        discovery_count += 1

                # 其他来源用 snippet 兜底
                elif snippet and len(snippet) > 20:
                    all_records.append({
                        "source_type": source_type,
                        "title": item.get("title", ""),
                        "content": snippet,
                        "url": item.get("url", ""),
                        "published_at": "",
                        "sentiment": "neutral",
                        "content_length": len(snippet),
                    })
                    discovery_count += 1

            logger.info(f"  智能发现成功入库: {discovery_count} 条全网数据")

    except Exception as e:
        logger.error(f"智能发现引擎执行异常: {e}")
        errors.append(f"智能发现引擎错误: {e}")

    # 7. 结构化 Search API 补充（Tavily / Brave / SerpAPI）
    try:
        from services.search_discovery import StructuredSearchDiscovery

        search_items = StructuredSearchDiscovery.search(
            name,
            include_chinese=True,
        )
        if search_items:
            all_records.extend(search_items)
            logger.info(f"  结构化 Search API: 补充 {len(search_items)} 条候选数据")
    except Exception as e:
        logger.error(f"结构化 Search API 执行异常: {e}")
        errors.append(f"结构化 Search API 错误: {e}")

    # 8. 统一相关性过滤、去重和排序
    try:
        raw_count = len(all_records)
        all_records, filter_stats = filter_and_rank_records(all_records, name, max_records=700)
        logger.info(
            f"  相关性过滤: 原始 {raw_count} 条 → 保留 {filter_stats['kept']} 条 "
            f"| 剔除 {filter_stats['rejected']} 条噪声"
        )
    except Exception as e:
        logger.error(f"相关性过滤异常，保留原始数据继续分析: {e}")
        errors.append(f"相关性过滤失败: {e}")

    # 统计
    total_chars = sum(r.get("content_length", len(r.get("content", ""))) for r in all_records)
    neg_reviews = sum(
        1 for r in all_records
        if r.get("sentiment") in ("negative", "mixed") or r.get("signal_intent") == "pain"
    )

    logger.info(
        f"════ 竞品 [{name}] 抓取完成 ════\n"
        f"  总记录: {len(all_records)} 条 | 总字符: {total_chars:,}\n"
        f"  负面/混合评论: {neg_reviews} 条 | 错误: {len(errors)} 个"
    )

    return all_records, errors
