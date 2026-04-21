# 运行与运维

## 本地环境

后端：

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
PORT=5001 venv/bin/python3 app.py
```

前端：

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:5001 npm run dev
```

一键启动：

```bash
./start.sh
```

## 环境变量

后端从 `backend/.env` 读取配置。可以从根目录 `.env.example` 复制。

### 必需

本地最小运行不需要必填 API Key。

### 推荐

```text
PORT=5001
FRONTEND_URL=http://localhost:3000
AI_ENGINE=gemini
GEMINI_API_KEY=
TAVILY_API_KEY=
BRAVE_SEARCH_API_KEY=
SERPAPI_API_KEY=
SEARCH_DISCOVERY_ENABLED=true
CHINESE_DISCOVERY_ENABLED=true
```

至少配置一个 Search API Key 可以显著扩大数据覆盖面。

## 数据库

默认数据库路径：

```text
backend/data/rivalsense.db
```

初始化发生在 Flask app 启动时。Schema 位于 `backend/models/database.py`。

备份：

```bash
cp backend/data/rivalsense.db backend/data/rivalsense.db.bak
```

重置本地数据：

```bash
rm backend/data/rivalsense.db backend/data/rivalsense.db-shm backend/data/rivalsense.db-wal
```

重置会清空竞品、抓取记录、报告和简报。

## 验证

后端语法检查：

```bash
cd backend
venv/bin/python3 -m py_compile app.py config.py routes/api.py models/database.py services/*.py
```

前端：

```bash
cd frontend
npm run lint
npm run build
```

健康检查：

```bash
curl -s http://127.0.0.1:5001/api/health
```

## 常见问题

### 前端被切到 3001 后 CORS 报错

`start.sh` 默认固定启动前端在 `3000`，并让前端请求 `http://localhost:5001`。如果你手动运行 `npm run dev`，Next 可能在 `3000` 被占用时自动切到 `3001`。后端已默认允许本地 `3000-3005`，但修改 `FRONTEND_URL` 后需要重启 Flask 才会生效。

### 端口 5001 被占用

使用其他端口：

```bash
cd backend
PORT=5002 venv/bin/python3 app.py
```

前端同步配置：

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:5002 npm run dev
```

### 抓取任务切页后恢复，但刷新后失败

前端只保存 job id。后端 job 在 Flask 进程内存中。如果后端重启，旧 job 会丢失，`GET /api/crawl-jobs/<id>` 会返回 404。生产化需要外部队列和持久化 job store。

### Search API 显示未配置

`GET /api/health` 的 `search_configured` 由以下任一变量决定：

- `BRAVE_SEARCH_API_KEY`
- `TAVILY_API_KEY`
- `SERPAPI_API_KEY`

修改后需要重启后端。

### NLTK 词库或 SSL 问题

当前代码在 macOS 本地为 NLTK 下载做了 SSL 兜底。生产容器建议使用标准 CA：

```bash
pip install certifi
```

并在镜像构建阶段预下载 `vader_lexicon`。

## 清理策略

`.gitignore` 已忽略：

- `.DS_Store`
- `frontend/.next/`
- `frontend/node_modules/`
- `backend/venv/`
- Python `__pycache__/`
- `backend/data/*.db`
- 旧运行导出目录 `reports/`、`data/`

不要提交：

- `backend/.env`
- SQLite 数据库
- 构建缓存
- 本地依赖目录

## 生产化建议

- 数据库：SQLite -> PostgreSQL。
- 后台任务：in-process ThreadPool -> Redis/RQ、Celery、Dramatiq 或云队列。
- 定时调度：APScheduler、cron、Trigger.dev、Inngest 或云 Scheduler。
- 日志：结构化 JSON log，至少包含 job_id、competitor_id、source_type、kept/rejected。
- 抓取合规：按来源设置速率限制、User-Agent、重试和禁止绕过认证。
