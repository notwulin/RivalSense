# 免费作品集部署

本项目的公网展示目标是“面试官打开即能看到完整产品体验”。推荐主展示站使用 Vercel Hobby 免费计划 + Demo Mode，不依赖 Flask 后端、数据库或 API Key。

## 推荐方案：Vercel Demo Mode

适用场景：

- 作品集展示
- 面试官预览
- 不希望后端冷启动影响首屏
- 不希望配置真实抓取 API Key

### 1. 推送到 GitHub

确保仓库中包含：

- `frontend/`
- `backend/`
- `docs/`
- `README.md`
- `render.yaml`

不要提交：

- `backend/.env`
- `backend/data/*.db`
- `frontend/node_modules/`
- `frontend/.next/`

### 2. 在 Vercel 导入项目

1. 打开 Vercel Dashboard。
2. Import Git Repository。
3. 选择 RivalSense 仓库。
4. Root Directory 选择 `frontend`。
5. Framework Preset 使用 Next.js。
6. Build Command 使用 `npm run build`。
7. Output Directory 保持默认。

### 3. 设置环境变量

在 Vercel Project Settings -> Environment Variables 添加：

```text
NEXT_PUBLIC_DEMO_MODE=true
```

不要设置 `NEXT_PUBLIC_API_URL`。Demo Mode 会使用浏览器内置样例数据，不请求后端。

### 4. 部署验收

部署成功后检查：

- `/` Dashboard 有 3 个示例竞品和每日简报。
- `/competitors` 能查看竞品、展开分析面板、点击“抓取分析”并看到模拟进度。
- `/reports` 有历史报告和每日简报，支持导出 Markdown、删除。
- 顶部显示 Demo Mode 提示，避免误导面试官。

## 可选方案：Render Free 后端

如果想向面试官展示真实 Flask API，可额外部署后端到 Render Free。

重要限制：

- Free Web Service 15 分钟无流量会休眠，下一次访问可能需要约 1 分钟冷启动。
- Free Web Service 本地文件系统是临时的，SQLite 数据在重启、重部署或休眠后不可靠。
- 真实抓取会访问外部网络，免费平台可能因出站流量或抓取频率受限。

因此 Render 后端只建议作为“技术补充演示”，不要作为主作品集入口。

### Render 设置

本仓库已提供 `render.yaml`。也可以手动创建 Web Service：

- Runtime：Python
- Root Directory：`backend`
- Build Command：`pip install -r requirements.txt`
- Start Command：`gunicorn --bind 0.0.0.0:$PORT "app:create_app()"`
- Instance Type：Free

环境变量：

```text
PORT=10000
FLASK_DEBUG=false
FRONTEND_URL=https://your-vercel-domain.vercel.app,http://localhost:3000
GEMINI_API_KEY=
TAVILY_API_KEY=
BRAVE_SEARCH_API_KEY=
SERPAPI_API_KEY=
```

### 让 Vercel 连接 Render 后端

在 Vercel 设置：

```text
NEXT_PUBLIC_DEMO_MODE=false
NEXT_PUBLIC_API_URL=https://your-render-service.onrender.com
```

重新部署前端即可使用真实后端。

## 推荐展示方式

面试作品集建议：

- README 顶部放 Vercel Demo URL。
- 简历中放 Vercel Demo URL + GitHub URL。
- 面试讲解时说明：公网展示为 Demo Mode，完整真实抓取/分析链路可本地运行，也可接 Render 后端。

这样既保证打开稳定，也能体现完整全栈架构。
