# RivalSense · AI 竞品雷达

RivalSense 是一个本地优先的 AI 竞品情报系统：持续抓取公开信号，做相关性过滤与去噪，结合本地 NLP 与可选大模型摘要，输出可追踪的竞品报告和每日简报。

## 在线演示

- Demo URL: https://rival-sense.vercel.app/
- 演示模式：`NEXT_PUBLIC_DEMO_MODE=true`
- 说明：Demo Mode 使用内置样例数据和模拟抓取进度，不依赖后端/API Key，适合面试或作品集稳定展示。

## 你会看到什么

- `Dashboard`：竞品总览、威胁等级、最新简报、统计卡片
- `竞品管理`：新增/编辑/删除竞品，触发单竞品抓取，查看分析面板
- `报告中心`：历史报告与每日简报，支持 Markdown 导出与删除

## 核心能力

- 竞品管理：MVP 阶段最多 5 个竞品
- 异步抓取：单竞品与全量抓取均走后台 job，可轮询进度并支持前端切页恢复
- 数据发现：RSS、官网/博客、开发者社区、评论站点与结构化搜索 API
- 中文发现：覆盖知乎、小红书、微博、B 站、贴吧、V2EX、掘金、36Kr、IT 之家等公开页面发现
- 去噪与排序：相关性评分、去重、信号过滤
- 本地分析：VADER、SnowNLP、jieba、TF-IDF、KMeans
- 报告输出：竞品报告 + 每日简报 + Markdown 导出

## 技术栈

- Frontend: Next.js 16, React 19, Tailwind CSS 4
- Backend: Flask, SQLite (WAL), Flask-CORS
- NLP: nltk, SnowNLP, jieba, scikit-learn, pandas, numpy
- AI 摘要（可选）: Gemini / DeepSeek（未配置时自动本地兜底）

## 快速开始

以下命令均在项目根目录执行。

### 路径 A：只跑前端演示（最快）

```bash
cd frontend
npm install
NEXT_PUBLIC_DEMO_MODE=true npm run dev
```

打开 http://localhost:3000

### 路径 B：完整本地全栈（推荐技术演示）

1. 安装依赖

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install
```

2. 配置环境变量

```bash
cp .env.example backend/.env
```

3. 一键启动

```bash
./start.sh
```

默认地址：

- 前端：http://localhost:3000
- 后端：http://localhost:5001
- 健康检查：http://localhost:5001/api/health

## 环境变量（最小集）

主要配置见 `.env.example`，常用项：

- `NEXT_PUBLIC_DEMO_MODE`：`true` 时前端使用内置 Demo 数据
- `NEXT_PUBLIC_API_URL`：前端请求后端的地址（默认 `http://localhost:5001`）
- `PORT`：后端端口（默认 `5001`）
- `FRONTEND_URL`：CORS 白名单
- `AI_ENGINE`：`gemini` 或 `deepseek`
- `GEMINI_API_KEY` / `DEEPSEEK_API_KEY`：可选，大模型摘要
- `TAVILY_API_KEY` / `BRAVE_SEARCH_API_KEY` / `SERPAPI_API_KEY`：可选，结构化搜索发现

## API 快速索引

默认 Base URL：`http://localhost:5001/api`

- `GET /health`
- `GET /competitors` / `POST /competitors`
- `POST /competitors/<id>/crawl-jobs`
- `POST /crawl-all-jobs`
- `GET /crawl-jobs/<job_id>`
- `GET /dashboard`
- `GET /reports` / `POST /reports/<competitor_id>/export`
- `GET /briefs`

完整接口见 [docs/api.md](docs/api.md)。

## 部署

- 作品集主入口：Vercel + Demo Mode（推荐）
- 技术补充：Render Free 部署 Flask 后端（可选）

详细步骤见 [docs/deployment.md](docs/deployment.md)。

## 项目结构

```text
.
├── backend/                 # Flask API、SQLite、抓取与分析管线
│   ├── app.py
│   ├── config.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── data/
├── frontend/                # Next.js 前端
│   ├── src/app/
│   └── src/lib/
├── docs/                    # 架构、API、部署与引擎文档
├── .env.example
├── start.sh
└── render.yaml
```

## 文档导航

- [系统架构](docs/architecture.md)
- [API 参考](docs/api.md)
- [部署指南](docs/deployment.md)
- [数据引擎](docs/data-engine.md)
- [分析引擎](docs/analysis-engine.md)
- [运行与运维](docs/operations.md)

## 当前限制

- 后台 job 当前存于 Flask 进程内存，后端重启后历史 `job_id` 失效
- SQLite 适合本地与 MVP 单进程场景，多实例建议迁移 PostgreSQL
- 免费平台部署真实抓取时存在冷启动、出站与存储限制

## License

本项目采用 [MIT License](LICENSE)。
