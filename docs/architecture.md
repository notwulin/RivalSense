# 系统架构

RivalSense 当前采用前后端分离架构：Next.js 负责产品界面与轮询，Flask 负责 API、抓取任务、SQLite 持久化和分析流水线。

## 组件视图

```text
Browser
  |
  | HTTP / polling
  v
Next.js frontend
  |
  | NEXT_PUBLIC_API_URL
  v
Flask API
  |
  +-- routes/api.py                # REST API
  +-- services/jobs.py             # 进程内后台 job
  +-- services/crawl_runner.py     # crawl -> persist -> analyze -> report
  +-- services/scraper.py          # 显式 URL/RSS/网页抓取
  +-- services/discovery.py        # 开放社区/API 发现
  +-- services/search_discovery.py # 结构化 Search API 发现
  +-- services/relevance.py        # 相关性评分、去重、去噪
  +-- services/data_analyzer.py    # 本地 NLP 统计
  +-- services/ai_analyzer.py      # AI 摘要与本地兜底
  v
SQLite database
```

## 主要数据流

1. 用户在前端添加竞品。
2. 前端调用 `POST /api/competitors/<id>/crawl-jobs` 或 `POST /api/crawl-all-jobs`。
3. 后端创建内存 job，立即返回 `job_id`。
4. 前端保存 active `job_id` 到 `localStorage`，并轮询 `GET /api/crawl-jobs/<job_id>`。
5. 后台任务执行 `run_competitor_crawl_pipeline`：
   - 广泛召回公开数据
   - 相关性评分、去重、去噪
   - 保存 `crawl_records`
   - 本地 NLP 生成 analytics
   - AI 或本地兜底生成报告
   - 保存 `reports`
6. 前端收到 completed job 后刷新竞品、Dashboard 或报告中心。

## 前端恢复机制

长抓取期间用户切换页面时，React 页面组件会卸载。为避免用户重新点击抓取：

- `frontend/src/lib/crawlJobStore.ts` 保存 active job id。
- Dashboard 保存全量抓取 job：`rivalsense.activeCrawlAllJob`。
- 竞品页保存单竞品抓取 job map：`rivalsense.activeCompetitorCrawlJobs`。
- 页面重新挂载后读取 localStorage，调用 `GET /api/crawl-jobs/<job_id>` 继续轮询。

注意：这只解决前端切页恢复。后端 job 仍在进程内存中，后端进程重启后 job 会丢失。

## 后端任务模型

`services/jobs.py` 使用 `ThreadPoolExecutor(max_workers=2)`：

- `queued`：任务已登记，等待执行。
- `running`：正在执行，持续更新 `stage`、`progress`、`message`。
- `completed`：任务完成，`result` 内含抓取结果、报告和 analytics。
- `failed`：任务失败，`error` 内含错误信息。

任务保留 24 小时，最多保留 100 个。多进程或云部署时需要迁移到 Redis/RQ、Celery、Dramatiq 或托管队列。

## 数据模型

SQLite 表：

- `competitors`：竞品基础信息和关注维度。
- `crawl_records`：抓取后的原始/清洗记录。
- `reports`：单竞品分析报告，包含 `analytics` JSON。
- `daily_briefs`：全量竞品聚合简报。

SQLite 使用 WAL，并启用外键级联删除。删除竞品会删除关联 crawl records 和 reports。

## 部署边界

本地和单进程 MVP：

- Flask + SQLite + in-process job 足够。
- 前端可使用 Next.js dev 或 build/start。

生产化前需要处理：

- SQLite 迁移到 PostgreSQL。
- job manager 迁移到外部队列。
- 抓取限速、重试、代理与目标站 robots 合规策略。
- API Key Secret 管理。
- 日志、任务审计和失败重跑。
