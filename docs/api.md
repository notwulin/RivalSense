# API 参考

默认后端地址：`http://localhost:5001`。所有业务接口都以 `/api` 开头。

## Health

### `GET /api/health`

返回服务状态、AI 配置状态和 Search API 配置状态。

```json
{
  "status": "ok",
  "service": "RivalSense API",
  "ai_engine": "gemini",
  "ai_configured": false,
  "search_configured": false
}
```

## Competitors

### `GET /api/competitors`

列出竞品，并附加最新报告。

### `POST /api/competitors`

创建竞品。MVP 阶段最多 5 个。

```json
{
  "name": "Intercom",
  "website_url": "https://www.intercom.com/blog/",
  "rss_url": "",
  "g2_url": "",
  "appstore_url": ""
}
```

### `GET /api/competitors/<competitor_id>`

获取竞品详情、最新报告和最近 10 条抓取记录。

### `PUT /api/competitors/<competitor_id>`

更新竞品字段：`name`、`website_url`、`rss_url`、`g2_url`、`appstore_url`、`focus_dimensions`。

### `DELETE /api/competitors/<competitor_id>`

删除竞品。SQLite 外键会级联删除关联抓取记录和报告。

## Crawl Jobs

### `POST /api/competitors/<competitor_id>/crawl-jobs`

异步启动单个竞品抓取分析任务。

响应：

```json
{
  "job_id": "job_xxx",
  "job": {
    "id": "job_xxx",
    "kind": "competitor_crawl",
    "status": "queued",
    "progress": 0
  }
}
```

### `POST /api/crawl-all-jobs`

异步启动所有竞品抓取分析，并生成每日简报。

### `GET /api/crawl-jobs/<job_id>`

查询任务状态。

关键字段：

- `status`：`queued`、`running`、`completed`、`failed`
- `stage`：当前阶段，例如 `crawl`、`analyze`、`persist_report`
- `progress`：0-100
- `message`：可展示给用户的进度说明
- `result`：完成后返回 crawl/report/analytics 或 brief
- `error`：失败原因

### `GET /api/crawl-jobs?limit=20`

列出最近任务。

## Legacy Sync Crawl

### `POST /api/competitors/<competitor_id>/crawl`

同步执行单个竞品抓取分析。保留用于兼容，不建议前端使用。

### `POST /api/crawl-all`

同步执行所有竞品抓取分析。保留用于兼容，不建议前端使用。

## Dashboard

### `GET /api/dashboard`

返回首页竞品卡片、最新简报和统计数字。

## Reports

### `GET /api/reports?competitor_id=<id>&limit=30`

列出历史报告。`competitor_id` 可选。

### `GET /api/reports/<competitor_id>/latest`

获取某个竞品最新报告。旧报告如果缺少 `analytics`，后端会基于最近抓取记录即时重算。

### `DELETE /api/reports/<report_id>`

删除单条历史报告。

### `POST /api/reports/<competitor_id>/export`

导出该竞品最新报告为 Markdown。

## Briefs

### `GET /api/briefs`

列出每日简报，默认最近 14 条。

### `GET /api/briefs/latest`

获取最新每日简报。

### `DELETE /api/briefs/<brief_id>`

删除单条每日简报。

## 错误格式

大多数错误返回：

```json
{
  "error": "错误说明"
}
```

前端 `src/lib/api.ts` 会把 `error` 转成 `Error.message`。
