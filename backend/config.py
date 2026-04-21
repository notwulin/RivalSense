"""
RivalSense 配置管理
环境变量统一在此加载，API Key 服务端存储，不暴露前端（PRD §6 安全性要求）
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """应用配置"""
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "rivalsense-dev-key")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    # 数据库
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///rivalsense.db")
    SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "rivalsense.db"
    ))

    # AI 模型配置（PRD 附录 B：gemini、deepseek 等）
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_API_URL = os.getenv(
        "GEMINI_API_URL",
        f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}:generateContent"
    )

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")

    # 默认 AI 引擎: gemini | deepseek
    AI_ENGINE = os.getenv("AI_ENGINE", "gemini")

    # 数据抓取
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
    JINA_API_KEY = os.getenv("JINA_API_KEY", "")
    BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
    SEARCH_DISCOVERY_ENABLED = os.getenv("SEARCH_DISCOVERY_ENABLED", "true").lower() == "true"
    CHINESE_DISCOVERY_ENABLED = os.getenv("CHINESE_DISCOVERY_ENABLED", "true").lower() == "true"
    SEARCH_MAX_QUERIES = int(os.getenv("SEARCH_MAX_QUERIES", "18"))
    SEARCH_RESULTS_PER_QUERY = int(os.getenv("SEARCH_RESULTS_PER_QUERY", "8"))

    # 抓取限制
    MAX_COMPETITORS = 5  # PRD US-02: MVP 限制最多 5 个竞品
    CRAWL_INTERVAL_HOURS = 24  # 每日抓取
    CRAWL_TIME = "08:30"  # 每日定时抓取时间

    # 后端端口（避免 macOS AirPlay 占用 5000）
    PORT = int(os.getenv("PORT", 5001))

    # 前端 URL（CORS）
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
