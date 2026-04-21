"""
RivalSense 智能发现引擎 v4
基于免费结构化 API 的全网嗅探（零 CAPTCHA 风险）：
- Reddit JSON API（评论/吐槽/讨论）
- Hacker News Algolia API（科技新闻/深度讨论）
- 直接站点抓取（Product Hunt, AlternativeTo 等）
"""
import logging
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup
from services.relevance import clean_visible_text

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "RivalSense/1.0 (competitive intelligence bot)",
    "Accept": "text/html,application/json",
}
JINA_READER_BASE = "https://r.jina.ai"


def _is_valid_url(url):
    """过滤无效 URL"""
    if not url or not url.startswith("http"):
        return False
    skip = ["google.com", "bing.com", "duckduckgo.com", "microsoft.com"]
    domain = urlparse(url).netloc.lower()
    return not any(s in domain for s in skip)


# ── Reddit JSON API ──────────────────────────────────────

def _search_reddit(query, limit=15):
    """通过 Reddit 公开 JSON API 搜索帖子"""
    results = []
    try:
        url = f"https://www.reddit.com/search.json"
        params = {
            "q": query,
            "sort": "relevance",
            "limit": limit,
            "t": "all",
            "type": "link",
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if not resp.ok:
            logger.warning(f"Reddit API 返回 {resp.status_code}")
            return results

        children = resp.json().get("data", {}).get("children", [])
        for child in children:
            d = child.get("data", {})
            title = d.get("title", "")
            selftext = d.get("selftext", "")
            permalink = d.get("permalink", "")
            score = d.get("score", 0)
            num_comments = d.get("num_comments", 0)
            subreddit = d.get("subreddit", "")
            post_url = d.get("url", "")
            reddit_url = f"https://www.reddit.com{permalink}" if permalink else post_url

            # 丰富内容：标题 + 自述文本 + 元数据
            content = selftext[:1500] if selftext else ""
            meta = f"[r/{subreddit} | {score} upvotes | {num_comments} comments]"

            results.append({
                "title": title,
                "url": reddit_url,
                "content": f"{meta}\n{content}" if content else meta,
                "snippet": selftext[:200] if selftext else title,
                "source_type": "reddit",
                "score": score,
            })

        # 按 score 排序，优先高赞帖子
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"  Reddit: 获取 {len(results)} 条帖子")

    except Exception as e:
        logger.error(f"Reddit 搜索异常: {e}")

    return results


def _fetch_reddit_comments(permalink, limit=30):
    """获取 Reddit 帖子的评论（高价值用户声音）"""
    comments = []
    try:
        url = f"https://www.reddit.com{permalink}.json?limit={limit}&sort=best"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if not resp.ok:
            return comments

        data = resp.json()
        if len(data) < 2:
            return comments

        comment_listing = data[1].get("data", {}).get("children", [])
        for child in comment_listing:
            if child.get("kind") != "t1":
                continue
            body = child.get("data", {}).get("body", "")
            score = child.get("data", {}).get("score", 0)
            if body and len(body) > 30:
                comments.append({
                    "content": body[:500],
                    "score": score,
                })
        comments.sort(key=lambda x: x.get("score", 0), reverse=True)

    except Exception as e:
        logger.debug(f"Reddit 评论获取失败: {e}")

    return comments[:limit]


# ── Hacker News Algolia API ──────────────────────────────

def _search_hackernews(query, limit=15):
    """通过 HN Algolia API 搜索科技新闻和深度讨论"""
    results = []
    try:
        url = "https://hn.algolia.com/api/v1/search"
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": limit,
        }
        resp = requests.get(url, params=params, timeout=10)
        if not resp.ok:
            logger.warning(f"HN API 返回 {resp.status_code}")
            return results

        hits = resp.json().get("hits", [])
        for hit in hits:
            title = hit.get("title", "")
            article_url = hit.get("url", "")
            points = hit.get("points", 0)
            num_comments = hit.get("num_comments", 0)
            hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

            results.append({
                "title": title,
                "url": article_url if article_url else hn_url,
                "content": f"[HN | {points} points | {num_comments} comments] {title}",
                "snippet": title,
                "source_type": "hackernews",
                "score": points,
            })

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"  HN: 获取 {len(results)} 条科技新闻/讨论")

    except Exception as e:
        logger.error(f"HN 搜索异常: {e}")

    return results


def _search_hackernews_comments(query, limit=20):
    """通过 HN Algolia 搜索评论正文，补充真实开发者吐槽。"""
    results = []
    try:
        url = "https://hn.algolia.com/api/v1/search"
        params = {
            "query": query,
            "tags": "comment",
            "hitsPerPage": limit,
        }
        resp = requests.get(url, params=params, timeout=10)
        if not resp.ok:
            return results

        for hit in resp.json().get("hits", []):
            comment_text = clean_visible_text(hit.get("comment_text", ""), max_len=900)
            story_title = hit.get("story_title", "") or "HN comment"
            if len(comment_text) < 30:
                continue
            hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            results.append({
                "title": f"HN comment: {story_title}",
                "url": hn_url,
                "content": comment_text,
                "snippet": comment_text[:200],
                "source_type": "hackernews_comment",
                "score": hit.get("points", 0) or 0,
            })

        logger.info(f"  HN 评论: 获取 {len(results)} 条")
    except Exception as e:
        logger.debug(f"HN 评论搜索异常: {e}")

    return results


# ── GitHub Issues / StackOverflow ───────────────────────

def _search_github_issues(query, limit=15):
    """搜索 GitHub Issues，适合发现开发者集成问题、bug 与 feature request。"""
    results = []
    try:
        url = "https://api.github.com/search/issues"
        params = {
            "q": f"{query} in:title,body is:issue",
            "sort": "comments",
            "order": "desc",
            "per_page": min(limit, 30),
        }
        headers = {
            **HEADERS,
            "Accept": "application/vnd.github+json",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if not resp.ok:
            logger.debug(f"GitHub Issues API 返回 {resp.status_code}")
            return results

        for item in resp.json().get("items", []):
            body = clean_visible_text(item.get("body", ""), max_len=1200)
            title = item.get("title", "")
            labels = ", ".join(label.get("name", "") for label in item.get("labels", [])[:5])
            comments = item.get("comments", 0) or 0
            content = f"[GitHub issue | {comments} comments | labels: {labels}] {body}"
            if len(title + body) < 35:
                continue
            results.append({
                "title": title,
                "url": item.get("html_url", ""),
                "content": content,
                "snippet": body[:200] or title,
                "source_type": "github_issue",
                "score": comments,
            })

        logger.info(f"  GitHub Issues: 获取 {len(results)} 条")
    except Exception as e:
        logger.debug(f"GitHub Issues 搜索异常: {e}")

    return results


def _search_stackoverflow(query, limit=15):
    """搜索 StackOverflow 问题，补充技术采用和集成故障信号。"""
    results = []
    try:
        url = "https://api.stackexchange.com/2.3/search/advanced"
        params = {
            "site": "stackoverflow",
            "q": query,
            "sort": "relevance",
            "order": "desc",
            "pagesize": min(limit, 30),
            "filter": "withbody",
        }
        resp = requests.get(url, params=params, timeout=12)
        if not resp.ok:
            logger.debug(f"StackOverflow API 返回 {resp.status_code}")
            return results

        for item in resp.json().get("items", []):
            body = clean_visible_text(item.get("body", ""), max_len=1000)
            title = clean_visible_text(item.get("title", ""), max_len=240)
            score = item.get("score", 0) or item.get("view_count", 0) or 0
            if len(title + body) < 35:
                continue
            results.append({
                "title": title,
                "url": item.get("link", ""),
                "content": f"[StackOverflow | score {item.get('score', 0)} | answers {item.get('answer_count', 0)}] {body}",
                "snippet": body[:200] or title,
                "source_type": "stackoverflow",
                "score": score,
            })

        logger.info(f"  StackOverflow: 获取 {len(results)} 条")
    except Exception as e:
        logger.debug(f"StackOverflow 搜索异常: {e}")

    return results


# ── Product Hunt / AlternativeTo 直接抓取 ────────────────

def _scrape_alternativeto(product_name, limit=10):
    """从 AlternativeTo 获取产品评论"""
    results = []
    try:
        slug = product_name.lower().replace(" ", "-")
        url = f"https://alternativeto.net/software/{slug}/reviews/"
        resp = requests.get(url, headers={**HEADERS, "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}, timeout=10)

        if not resp.ok:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        review_blocks = soup.select("div.review-content, div[class*=review], p[class*=comment]")

        for block in review_blocks[:limit]:
            text = block.get_text(strip=True)
            if len(text) > 30:
                results.append({
                    "title": f"{product_name} Review on AlternativeTo",
                    "url": url,
                    "content": text[:500],
                    "snippet": text[:200],
                    "source_type": "alternativeto",
                    "score": 0,
                })

        if results:
            logger.info(f"  AlternativeTo: 获取 {len(results)} 条评论")

    except Exception as e:
        logger.debug(f"AlternativeTo 抓取失败: {e}")

    return results


def _jina_read(url, timeout=18):
    jina_url = f"{JINA_READER_BASE}/{url}"
    try:
        resp = requests.get(
            jina_url,
            headers={**HEADERS, "Accept": "text/plain", "X-Return-Format": "text"},
            timeout=timeout,
        )
        if resp.ok and len(resp.text) > 100:
            return resp.text
    except Exception:
        pass
    return ""


def _discover_review_pages(product_name, website_url="", limit=12):
    """
    Low-cost review page probes. These are best-effort because many review sites
    have inconsistent slugs, so relevance scoring later decides whether to keep.
    """
    results = []
    slug = product_name.lower().replace(" ", "-")
    urls = [
        f"https://www.producthunt.com/products/{slug}/reviews",
        f"https://www.trustradius.com/products/{slug}/reviews",
    ]

    if website_url:
        try:
            domain = urlparse(website_url).netloc.lower().replace("www.", "")
            if domain:
                urls.append(f"https://www.trustpilot.com/review/{domain}")
        except Exception:
            pass

    for url in urls:
        raw = _jina_read(url)
        if not raw:
            continue
        paragraphs = [
            clean_visible_text(p, max_len=700)
            for p in raw.split("\n\n")
            if len(clean_visible_text(p)) > 45
        ]
        for para in paragraphs[:limit]:
            results.append({
                "title": f"Review page feedback: {product_name}",
                "url": url,
                "content": para,
                "snippet": para[:200],
                "source_type": "review_site",
                "score": 0,
            })
        if len(results) >= limit:
            break

    if results:
        logger.info(f"  Review pages: 获取 {len(results)} 条")
    return results[:limit]


# ── 主 API ──────────────────────────────────────────────

class DiscoveryEngine:
    """
    智能发现引擎 v4：基于结构化 API 的零 CAPTCHA 全网嗅探
    """

    @classmethod
    def search_all_channels(cls, competitor_name, max_urls_per_channel=20, website_url=""):
        """
        多渠道并行搜索，返回去重的高质量链接列表
        """
        all_results = []
        reddit_queries = [
            f"{competitor_name} review problems issues",
            f"{competitor_name} bug crash slow",
            f"{competitor_name} expensive pricing alternatives",
            f"{competitor_name} not working feature request",
        ]
        github_queries = [
            f'"{competitor_name}" bug',
            f'"{competitor_name}" "not working"',
            f'"{competitor_name}" "feature request"',
        ]
        stackoverflow_queries = [
            f"{competitor_name} error",
            f"{competitor_name} integration problem",
        ]

        tasks = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            for query in reddit_queries:
                tasks.append(executor.submit(_search_reddit, query, max_urls_per_channel))
            tasks.append(executor.submit(_search_hackernews, competitor_name, max_urls_per_channel))
            tasks.append(executor.submit(_search_hackernews_comments, competitor_name, max_urls_per_channel))
            for query in github_queries:
                tasks.append(executor.submit(_search_github_issues, query, max_urls_per_channel))
            for query in stackoverflow_queries:
                tasks.append(executor.submit(_search_stackoverflow, query, max_urls_per_channel))
            tasks.append(executor.submit(_scrape_alternativeto, competitor_name, 10))
            tasks.append(executor.submit(_discover_review_pages, competitor_name, website_url, 18))

            for future in as_completed(tasks):
                try:
                    all_results.extend(future.result())
                except Exception as e:
                    logger.debug(f"发现子任务失败: {e}")

        reddit_results = [r for r in all_results if r.get("source_type") == "reddit"]

        # ── Reddit 评论深度抓取（高价值声音）──
        top_posts = sorted(reddit_results, key=lambda x: x.get("score", 0), reverse=True)[:6]
        for post in top_posts:
            permalink = post.get("url", "").replace("https://www.reddit.com", "")
            if permalink and "/comments/" in permalink:
                comments = _fetch_reddit_comments(permalink, limit=20)
                for comment in comments:
                    all_results.append({
                        "title": f"Reddit comment on: {post['title'][:50]}",
                        "url": post["url"],
                        "content": comment["content"],
                        "snippet": comment["content"][:200],
                        "source_type": "reddit_comment",
                        "score": comment.get("score", 0),
                    })
                time.sleep(0.5)

        # ── 全局去重 ──
        seen = set()
        unique = []
        for r in all_results:
            # 用 URL + content前50字 做联合去重
            key = r.get("url", "") + r.get("content", "")[:50]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        logger.info(
            f"💡 智能发现引擎为 [{competitor_name}] 找到 {len(unique)} 条独立情报 "
            f"(Reddit {len(reddit_results)}条 + "
            f"Reddit评论 {sum(1 for r in all_results if r.get('source_type')=='reddit_comment')}条 + "
            f"HN {sum(1 for r in all_results if r.get('source_type') in ('hackernews','hackernews_comment'))}条 + "
            f"GitHub {sum(1 for r in all_results if r.get('source_type')=='github_issue')}条 + "
            f"StackOverflow {sum(1 for r in all_results if r.get('source_type')=='stackoverflow')}条 + "
            f"Reviews {sum(1 for r in all_results if r.get('source_type') in ('alternativeto','review_site'))}条)"
        )
        return unique
