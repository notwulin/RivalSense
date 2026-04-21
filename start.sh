#!/bin/bash
# RivalSense 一键启动脚本
# 同时启动 Flask 后端 + Next.js 前端

echo "🚀 RivalSense 启动中..."
echo ""

# 启动 Flask 后端
echo "📡 启动后端 (Flask :5001)..."
cd backend
if [ -d "venv" ]; then
    PORT=5001 venv/bin/python3 app.py &
else
    PORT=5001 python3 app.py &
fi
BACKEND_PID=$!
cd ..

# 等待后端就绪
sleep 2

# 启动 Next.js 前端
echo "🖥️  启动前端 (Next.js :3000)..."
cd frontend && NEXT_PUBLIC_API_URL=http://localhost:5001 npm run dev -- --port 3000 &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ RivalSense 已启动"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:5001"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获中断信号
trap "echo '正在停止...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# 等待子进程
wait
