"""
RivalSense Flask 应用入口
PRD 附录 B：后端 Python Flask
"""
import os
import sys
import logging

# 确保 backend 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_cors import CORS
from config import Config
from models.database import init_db
from routes.api import api

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rivalsense")


def create_app():
    """Flask 应用工厂"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # CORS：允许 Next.js / Vercel 前端访问（PRD §6 安全性）
    allowed_origins = [
        origin.strip()
        for origin in (Config.FRONTEND_URL or "").split(",")
        if origin.strip()
    ]
    for port in range(3000, 3006):
        allowed_origins.append(f"http://localhost:{port}")
        allowed_origins.append(f"http://127.0.0.1:{port}")
    CORS(app, origins=sorted(set(allowed_origins)), supports_credentials=True)

    # 注册 API 蓝图
    app.register_blueprint(api)

    # 初始化数据库
    with app.app_context():
        init_db()
        logger.info("✅ 数据库初始化完成")

    # 根路由
    @app.route("/")
    def index():
        return {
            "name": "RivalSense API",
            "version": "1.0.0",
            "docs": "PRD v1.0",
            "endpoints": {
                "health": "/api/health",
                "competitors": "/api/competitors",
                "dashboard": "/api/dashboard",
                "crawl_all": "/api/crawl-all",
                "reports": "/api/reports",
                "briefs": "/api/briefs",
            }
        }

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5001))
    logger.info(f"🚀 RivalSense API 启动于 http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
