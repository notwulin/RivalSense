# RivalSense Frontend

Next.js App Router 前端，用于竞品管理、抓取进度展示、Dashboard、报告中心和分析面板。

## 运行

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:5001 npm run dev
```

访问 `http://localhost:3000`。

作品集 Demo Mode：

```bash
NEXT_PUBLIC_DEMO_MODE=true npm run dev
```

Demo Mode 会使用内置样例数据和模拟抓取进度，不需要 Flask 后端。

## 关键文件

- `src/app/page.tsx`：Dashboard 与全量抓取入口
- `src/app/competitors/page.tsx`：竞品 CRUD、单竞品抓取、分析面板
- `src/app/reports/page.tsx`：报告中心、报告/简报删除
- `src/lib/api.ts`：Flask API client 与前端类型定义
- `src/lib/crawlJobStore.ts`：浏览器本地保存 active crawl job，用于切页后恢复轮询

更多系统说明见根目录 `README.md` 和 `docs/`。
