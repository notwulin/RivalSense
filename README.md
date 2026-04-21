# RivalSense

RivalSense 是一个本地优先的 AI 竞品情报系统。它把公开数据抓取、来源相关性评分、去噪、NLP 聚类、情感分析和 AI 摘要合成串成一条可运行链路，目标是低成本持续追踪竞品动态、用户痛点和商业信号。

当前版本已经从早期 Node 原型切换为 Flask + SQLite + Next.js 架构。

## 作品集预览

Vercel 部署前端，并开启 Demo Mode：

```text
NEXT_PUBLIC_DEMO_MODE=true
```

Demo Mode 使用内置样例数据和模拟抓取进度，不依赖后端冷启动、数据库或 API Key，适合稳定预览。真实 Flask 后端仍可本地运行，也可选部署到 Render 做技术补充演示。


## 核心能力

- 竞品管理：添加、更新、删除最多 5 个 MVP 阶段竞品。
- 异步抓取：单个竞品和全量竞品抓取均使用后台 job，前端可轮询进度并在切页后恢复。
- 数据引擎：RSS、官网/博客、G2/App Store URL、Reddit、Hacker News、GitHub Issues、StackOverflow、AlternativeTo、Review pages、结构化搜索 API。
- 中文发现：通过结构化搜索 API 覆盖知乎、小红书、微博、B 站、贴吧、V2EX、掘金、36Kr、IT之家等平台的可发现页面。
- 相关性与去噪：按产品词、来源质量、痛点信号、商业信号、正向噪声和内容质量打分排序。
- 本地 NLP：VADER、SnowNLP、jieba、TF-IDF、KMeans，用本地统计压缩大模型输入。
- 报告中心：历史报告和每日简报列表，支持删除报告、删除简报和导出最新报告 Markdown。
- 可视化面板：情感分布、来源分布、痛点聚类、商业信号和负面原话 Top 5。

## 技术栈

- Frontend：Next.js 16 App Router、React 19、Tailwind CSS 4
- Backend：Python 3、Flask、Flask-CORS、SQLite WAL
- NLP：nltk、SnowNLP、jieba、scikit-learn、pandas、numpy
- AI 摘要：Gemini 或 DeepSeek等自行配置；未配置时走本地兜底
- Discovery：Reddit JSON API、HN Algolia、GitHub Search API、StackExchange API、Jina Reader、Firecrawl、Tavily、Brave Search、SerpAPI

## 目录结构

```text
.
├── backend/                 # Flask API、SQLite、抓取与分析管线
│   ├── app.py
│   ├── config.py
│   ├── data/                # 本地 SQLite 数据库目录
│   ├── models/              # 数据库访问层
│   ├── routes/              # API 路由
│   └── services/            # 抓取、发现、评分、NLP、AI、后台任务
├── frontend/                # Next.js 前端
│   ├── src/app/
│   └── src/lib/api.ts
├── docs/                    # 技术文档
├── .env.example             # 环境变量模板
├── start.sh                 # 本地一键启动脚本
├── prd_rivalsense.html      # 原始 PRD
└── project_handoff.md       # 项目接力上下文
```

## 快速启动

以下命令都从项目根目录执行。

1. 准备后端环境：

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
```

2. 准备前端环境：

```bash
npm --prefix frontend install
```

3. 配置环境变量：

```bash
cp .env.example backend/.env
```

最小可运行配置可以不填任何 API Key；系统会跳过付费搜索和大模型，使用开放 API 与本地分析兜底。推荐至少配置一个结构化搜索 API Key 以扩大数据覆盖面。

4. 启动：

```bash
./start.sh
```

默认地址：

- 前端：http://localhost:3000
- 后端：http://localhost:5001
- 健康检查：http://localhost:5001/api/health

也可以分开启动：

```bash
cd backend
PORT=5001 venv/bin/python3 app.py
```

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:5001 npm run dev
```

## 常用命令

```bash
# 后端语法检查
cd backend
venv/bin/python3 -m py_compile app.py config.py routes/api.py models/database.py services/*.py

# 前端 lint
cd frontend
npm run lint

# 前端生产构建
cd frontend
npm run build
```

## 环境变量

主要变量见 `.env.example`。常用项：

- `PORT`：Flask 后端端口，默认 `5001`
- `FRONTEND_URL`：CORS 允许的前端地址，默认 `http://localhost:3000`
- `AI_ENGINE`：`gemini` 或 `deepseek`
- `GEMINI_API_KEY` / `DEEPSEEK_API_KEY`：AI 摘要可选配置
- `FIRECRAWL_API_KEY`：高防页面深度抓取可选配置
- `TAVILY_API_KEY` / `BRAVE_SEARCH_API_KEY` / `SERPAPI_API_KEY`：结构化搜索发现可选配置
- `SEARCH_DISCOVERY_ENABLED`：是否启用结构化搜索，默认 `true`
- `CHINESE_DISCOVERY_ENABLED`：是否启用中文平台发现查询，默认 `true`

## 文档

- [系统架构](docs/architecture.md)
- [API 参考](docs/api.md)
- [数据引擎](docs/data-engine.md)
- [分析引擎](docs/analysis-engine.md)
- [运行与运维](docs/operations.md)

## 当前限制

- 后台 job 目前保存在 Flask 进程内存中。前端可跨页面恢复轮询，但后端进程重启后旧 `job_id` 会失效。
- SQLite 适合本地和 MVP 单进程场景；多实例部署需要迁移到 PostgreSQL，并把 job manager 迁移到 Redis/RQ、Celery 或托管队列。
- 中文平台多依赖搜索 API 发现公开页面，不直接绕过平台登录、反爬或私有 API。
- 本地 NLP 聚类依赖抓取数据质量；低相关语料会被去噪层尽量过滤，但仍需要持续补充垂直来源和评估样本。
