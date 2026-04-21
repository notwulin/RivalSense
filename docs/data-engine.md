# 数据引擎

数据引擎的原则是“广召回、强去噪、保留证据”。抓取层尽可能覆盖公开来源，分析层只接收相关且有信号的数据。

## 入口

主入口：

- `services/scraper.py`：显式来源抓取和聚合。
- `services/discovery.py`：开放社区/API 发现。
- `services/search_discovery.py`：可选结构化搜索 API。
- `services/relevance.py`：最终过滤、打分、去重和排序。

`crawl_competitor(competitor)` 会汇总所有来源，最后调用 `filter_and_rank_records(records, competitor_name)`。

## 来源类型

显式来源：

- `rss`：RSS/Atom feed。
- `blog`：官网、博客、新闻页。
- `g2_review`：G2 页面，优先 Firecrawl/Jina Reader。
- `appstore_review`：App Store URL。

开放 API / 社区：

- `reddit`、`reddit_comment`
- `hackernews`、`hackernews_comment`
- `github_issue`
- `stackoverflow`
- `alternativeto`
- `review_site`

结构化 Search API：

- `search_result`
- `search_news`
- `zhihu_search`
- `xiaohongshu_search`
- `weibo_search`
- `bilibili_search`
- `tieba_search`
- `v2ex_search`
- `juejin_search`
- `cn_media_search`

## 结构化 Search API

可选 provider：

- Tavily：`TAVILY_API_KEY`
- Brave Search：`BRAVE_SEARCH_API_KEY`
- SerpAPI：`SERPAPI_API_KEY`

开启条件：

```text
SEARCH_DISCOVERY_ENABLED=true
```

中文平台查询由 `CHINESE_DISCOVERY_ENABLED=true` 控制。当前策略是用搜索 API 发现公开页面，不直接调用平台私有接口，也不绕过登录或反爬。

查询覆盖：

- 英文痛点：review/problems/complaints、bugs/issues、pricing/alternatives、feature request。
- 英文商业信号：outage/security/lawsuit/pricing/funding/launch。
- 中文痛点：吐槽、不好用、问题、bug、替代、价格太贵、体验、评测。
- 中文平台：知乎、小红书、微博、B 站、贴吧、V2EX、掘金、36Kr、IT之家。

## 相关性评分

`score_record(record, competitor_name)` 输出：

- `relevance_score`：产品词在标题、正文和 URL 中的命中。
- `pain_score`：bug、crash、not working、too expensive、缺少、难用等痛点模式。
- `business_score`：funding、launch、price increase、lawsuit、data breach、融资、发布、涨价等商业信号。
- `positive_score`：love、great、recommend、好用等正向噪声。
- `quality_score`：来源质量、内容长度等。
- `priority_score`：综合排序分。
- `signal_intent`：`pain`、`business`、`positive` 或 `discussion`。

## 去噪规则

记录会被丢弃的常见原因：

- 内容太短。
- 高正向、低痛点、低商业信号。
- 非高信任来源且产品相关性不足。
- 既没有痛点，也没有商业信号，且讨论强度不足。
- URL、标题、正文组合重复。

高信任来源包括 RSS、blog、changelog、G2、App Store 和 review site。高信任来源允许较低相关性阈值，但仍会参与后续分析打分。

## 推荐扩展方向

优先级高：

- Reddit subreddit 定向搜索：根据产品赛道配置 subreddit 白名单。
- GitHub repo 定向：产品有开源 SDK 时加入 repo issues/discussions。
- Product Hunt/Trustpilot/Capterra/GetApp/G2 的合规 API 或稳定页面解析。
- 中文 SaaS/开发者社区：V2EX、掘金、知乎问题页、公众号文章搜索结果。

优先级中：

- Twitter/X、LinkedIn、YouTube 评论等社媒来源。需要处理认证、速率限制和合规问题。
- 国内应用商店评论。需要按目标行业单独设计解析器。

不建议：

- 直接抓搜索引擎 HTML SERP。CAPTCHA 风险高，结构不稳定，合规边界差。
- 绕过登录或反爬的私有接口。

## 质量指标

后续每次扩源建议记录：

- 每个来源召回数。
- 去噪后保留率。
- `pain` / `business` / `discussion` 比例。
- Top negative quotes 的人工相关性通过率。
- 聚类关键词中低信息词比例。
