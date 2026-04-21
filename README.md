# RivalSense · AI 竞品雷达

**本地优先的 AI 竞品情报系统：全网公开信号发现 -> 智能去噪 -> 本地 NLP 统计 -> AI 摘要合成**

[![Vercel Deployment](https://img.shields.io/badge/Frontend-Vercel-black?style=flat-square&logo=vercel)](https://rival-sense.vercel.app/)
[![Backend-Flask](https://img.shields.io/badge/Backend-Flask-lightgrey?style=flat-square&logo=flask)](https://github.com/notwulin/RivalSense)
[![License-MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

---
> [!TIP]
> **🚀 在线作品集演示 (Live Demo)**  
> **URL**: [https://rival-sense.vercel.app/](https://rival-sense.vercel.app/)  
> **演示模式**: `NEXT_PUBLIC_DEMO_MODE=true`  
> 该模式下前端将直接展示内置的 Mock 采样数据与模拟进度，无需启动后端服务，适合快速查看交互效果。
---

## 💎 产品全景(Quick Look)

- **智能看板**：竞品状态总览、威胁等级实时预警、最新分析简报及核心数据统计卡片。
- **竞品管理**：新增/编辑/删除竞品；触发单点异步抓取，深度查看分析面板。
- **报告中心**：管理历史竞品报告与每日全量简报，支持一键导出 Markdown 或清理旧数据。

## 🌟 核心能力(Key Capabilities)
### 1. 深度信号捕获
- **异步抓取**：单竞品与全量抓取均走后台 job，可轮询进度并支持前端切页恢复
- **维度发现引擎**：覆盖 RSS、官网/博客、GitHub Issues开发者社区、Reddit评论站点、结构化搜索API等主流技术与社交平台。

### 2. 智能处理闭环
- **去噪与语义打分**：基于相关性算法自动过滤无效信息，提取高价值商业信号。
- **本地 NLP 预处理**：集成 VADER/SnowNLP 情感分析、jieba 分词、TF-IDF 索引及 KMeans 聚类。
- **报告闭环**：每日自动/手动合成简报，本地统计压缩极大降低了大模型 Token 消耗。

## 🛠️ 技术栈

| 领域 | 技术方案 |
| :--- | :--- |
| **Frontend** | Next.js 16, React 19, Tailwind CSS 4 |
| **Backend** | Flask, SQLite (WAL Mode), Flask-CORS |
| **NLP/Analysis** | nltk, SnowNLP, jieba, scikit-learn, pandas, numpy |
| **AI Summary** | Gemini / DeepSeek (未配置时自动本地兜底) |

## ⚡ 快速开始

以下命令均在项目根目录执行。

### 路径 A：纯前端演示（最快）
```bash
cd frontend
npm install
NEXT_PUBLIC_DEMO_MODE=true npm run dev
```
访问：`http://localhost:3000`

### 路径 B：全栈本地运行
1. **环境准备**：
```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install
```

2. **配置环境变量**

```bash
cp .env.example backend/.env
```

3. **一键启动**

```bash
./start.sh
```

默认地址：

- 前端：http://localhost:3000
- 后端：http://localhost:5001
- 健康检查：http://localhost:5001/api/health

## 🔑 环境变量（最小集）

主要配置见 `.env.example`，常用项：

- `NEXT_PUBLIC_DEMO_MODE`：`true` 时前端使用内置 Demo 数据
- `NEXT_PUBLIC_API_URL`：前端请求后端的地址（默认 `http://localhost:5001`）
- `PORT`：后端端口（默认 `5001`）
- `FRONTEND_URL`：CORS 白名单
- `AI_ENGINE`：`gemini` 或 `deepseek`
- `GEMINI_API_KEY` / `DEEPSEEK_API_KEY`：可选，大模型摘要
- `TAVILY_API_KEY` / `BRAVE_SEARCH_API_KEY` / `SERPAPI_API_KEY`：可选，结构化搜索发现

## 🔍 API 快速索引

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

## 🛳️ 部署

- 作品集主入口：Vercel + Demo Mode（推荐）
- 技术补充：Render Free 部署 Flask 后端（可选）

详细步骤见 [docs/deployment.md](docs/deployment.md)。

## 📂 项目结构

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

## 🛳️ 文档导航

- [系统架构](docs/architecture.md) | [API 参考](docs/api.md) | [部署指南](docs/deployment.md)
- [数据引擎](docs/data-engine.md) | [分析引擎](docs/analysis-engine.md) | [运维手册](docs/operations.md)

## ⚠️ 当前限制

- 后台 job 当前存于 Flask 进程内存，后端重启后历史 `job_id` 失效
- SQLite 适合本地与 MVP 单进程场景，多实例建议迁移 PostgreSQL

---

本项目采用 [MIT License](LICENSE)。
