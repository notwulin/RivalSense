"""
Structured search API discovery.

Supported providers are optional and activated by environment variables:
- Tavily: TAVILY_API_KEY
- Brave Search: BRAVE_SEARCH_API_KEY
- SerpAPI: SERPAPI_API_KEY

This module does not scrape search engine result pages directly. It consumes
structured API responses, then lets relevance.py decide what is worth analyzing.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

from config import Config
from services.relevance import clean_visible_text

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 18


CHINESE_PLATFORM_DOMAINS = {
    "zhihu.com": "zhihu_search",
    "xiaohongshu.com": "xiaohongshu_search",
    "xhslink.com": "xiaohongshu_search",
    "weibo.com": "weibo_search",
    "m.weibo.cn": "weibo_search",
    "bilibili.com": "bilibili_search",
    "b23.tv": "bilibili_search",
    "tieba.baidu.com": "tieba_search",
    "v2ex.com": "v2ex_search",
    "juejin.cn": "juejin_search",
    "36kr.com": "cn_media_search",
    "ithome.com": "cn_media_search",
    "sspai.com": "cn_media_search",
    "geekpark.net": "cn_media_search",
    "ifanr.com": "cn_media_search",
}


def _provider_names():
    names = []
    if Config.TAVILY_API_KEY:
        names.append("tavily")
    if Config.BRAVE_SEARCH_API_KEY:
        names.append("brave")
    if Config.SERPAPI_API_KEY:
        names.append("serpapi")
    return names


def _domain(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _source_type_for_url(url, default="search_result"):
    domain = _domain(url)
    for known_domain, source_type in CHINESE_PLATFORM_DOMAINS.items():
        if domain == known_domain or domain.endswith("." + known_domain):
            return source_type
    return default


def _normalize_result(result, provider, query, topic="general"):
    title = clean_visible_text(result.get("title", ""), max_len=240)
    url = result.get("url") or result.get("link") or ""
    snippet = (
        result.get("content")
        or result.get("snippet")
        or result.get("description")
        or result.get("summary")
        or ""
    )
    snippet = clean_visible_text(snippet, max_len=1200)
    if not title and not snippet:
        return None
    if not url.startswith("http"):
        return None

    default_source = "search_news" if topic == "news" else "search_result"
    return {
        "source_type": _source_type_for_url(url, default=default_source),
        "title": title or url,
        "content": snippet or title,
        "snippet": snippet[:240] if snippet else title[:240],
        "url": url,
        "published_at": result.get("published_date") or result.get("date") or "",
        "score": float(result.get("score") or result.get("position") or 0),
        "search_provider": provider,
        "search_query": query,
        "content_length": len(snippet or title),
    }


def _search_tavily(query, max_results=8, topic="general", include_domains=None):
    if not Config.TAVILY_API_KEY:
        return []
    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": min(max_results, 20),
        "topic": topic,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if topic == "general":
        payload["country"] = "china" if _looks_chinese_query(query) else "united states"

    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json=payload,
            headers={
                "Authorization": f"Bearer {Config.TAVILY_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            logger.debug(f"Tavily search failed {resp.status_code}: {query}")
            return []
        return [
            item for item in (
                _normalize_result(result, "tavily", query, topic)
                for result in resp.json().get("results", [])
            )
            if item
        ]
    except Exception as e:
        logger.debug(f"Tavily search exception: {e}")
        return []


def _search_brave(query, max_results=8, topic="general"):
    if not Config.BRAVE_SEARCH_API_KEY:
        return []

    endpoint = "https://api.search.brave.com/res/v1/news/search" if topic == "news" else "https://api.search.brave.com/res/v1/web/search"
    params = {
        "q": query,
        "count": min(max_results, 20),
        "country": "CN" if _looks_chinese_query(query) else "US",
        "search_lang": "zh-cn" if _looks_chinese_query(query) else "en",
    }

    try:
        resp = requests.get(
            endpoint,
            params=params,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": Config.BRAVE_SEARCH_API_KEY,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            logger.debug(f"Brave search failed {resp.status_code}: {query}")
            return []
        data = resp.json()
        raw_results = data.get("results") or data.get("web", {}).get("results", [])
        return [
            item for item in (
                _normalize_result(result, "brave", query, topic)
                for result in raw_results
            )
            if item
        ]
    except Exception as e:
        logger.debug(f"Brave search exception: {e}")
        return []


def _search_serpapi(query, max_results=8, topic="general"):
    if not Config.SERPAPI_API_KEY:
        return []

    params = {
        "engine": "google",
        "q": query,
        "api_key": Config.SERPAPI_API_KEY,
        "num": min(max_results, 10),
        "hl": "zh-cn" if _looks_chinese_query(query) else "en",
        "gl": "cn" if _looks_chinese_query(query) else "us",
    }
    if topic == "news":
        params["tbm"] = "nws"

    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            logger.debug(f"SerpAPI search failed {resp.status_code}: {query}")
            return []
        data = resp.json()
        raw_results = data.get("news_results") if topic == "news" else data.get("organic_results", [])
        raw_results = raw_results or []
        return [
            item for item in (
                _normalize_result(result, "serpapi", query, topic)
                for result in raw_results
            )
            if item
        ]
    except Exception as e:
        logger.debug(f"SerpAPI search exception: {e}")
        return []


def _looks_chinese_query(query):
    return any("\u4e00" <= ch <= "\u9fff" for ch in query)


def _base_queries(competitor_name):
    quoted = f'"{competitor_name}"'
    return [
        (f"{quoted} review problems complaints", "general"),
        (f"{quoted} bugs issues not working", "general"),
        (f"{quoted} pricing expensive alternatives", "general"),
        (f"{quoted} feature request missing", "general"),
        (f"{quoted} outage security lawsuit pricing funding launch", "news"),
    ]


def _chinese_queries(competitor_name):
    quoted = f'"{competitor_name}"'
    pain_terms = ["吐槽", "不好用", "问题", "bug", "替代", "价格 太贵", "体验", "评测"]
    platform_queries = [
        f"site:zhihu.com {quoted} 问题 OR 吐槽 OR 替代",
        f"site:xiaohongshu.com {quoted} 体验 OR 吐槽 OR 评测",
        f"site:weibo.com {quoted} 吐槽 OR 崩溃 OR 问题",
        f"site:bilibili.com {quoted} 评测 OR 吐槽 OR 替代",
        f"site:tieba.baidu.com {quoted} 吐槽 OR 问题",
        f"site:v2ex.com {quoted} 问题 OR 替代 OR bug",
        f"site:juejin.cn {quoted} bug OR 问题 OR 集成",
        f"site:36kr.com OR site:ithome.com {quoted} 融资 OR 发布 OR 涨价 OR 裁员",
    ]
    general_queries = [f"{quoted} {term}" for term in pain_terms]
    return [(query, "general") for query in general_queries + platform_queries]


def build_search_queries(competitor_name, include_chinese=True):
    queries = _base_queries(competitor_name)
    if include_chinese:
        queries.extend(_chinese_queries(competitor_name))

    unique = []
    seen = set()
    for query, topic in queries:
        key = (query, topic)
        if key in seen:
            continue
        seen.add(key)
        unique.append((query, topic))
    return unique[: max(1, Config.SEARCH_MAX_QUERIES)]


class StructuredSearchDiscovery:
    @classmethod
    def search(cls, competitor_name, include_chinese=True):
        if not Config.SEARCH_DISCOVERY_ENABLED:
            return []

        providers = _provider_names()
        if not providers:
            logger.info("结构化 Search API 未配置，跳过 Search discovery")
            return []

        queries = build_search_queries(
            competitor_name,
            include_chinese=include_chinese and Config.CHINESE_DISCOVERY_ENABLED,
        )
        max_results = max(1, Config.SEARCH_RESULTS_PER_QUERY)
        tasks = []
        all_results = []

        with ThreadPoolExecutor(max_workers=min(12, len(providers) * max(len(queries), 1))) as executor:
            for query, topic in queries:
                if "tavily" in providers:
                    tasks.append(executor.submit(_search_tavily, query, max_results, topic))
                if "brave" in providers:
                    tasks.append(executor.submit(_search_brave, query, max_results, topic))
                if "serpapi" in providers:
                    tasks.append(executor.submit(_search_serpapi, query, max_results, topic))

            for future in as_completed(tasks):
                try:
                    all_results.extend(future.result())
                except Exception as e:
                    logger.debug(f"Search discovery task failed: {e}")

        unique = []
        seen = set()
        for item in all_results:
            key = (item.get("url", "").split("?")[0], item.get("title", "")[:120])
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)

        logger.info(
            f"结构化 Search API 为 [{competitor_name}] 补充 {len(unique)} 条结果 "
            f"(providers={','.join(providers)}, queries={len(queries)})"
        )
        return unique
