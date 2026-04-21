"""
RivalSense 数据库层 — SQLite 实现
对齐 PRD 数据模型，后续可迁移至 Supabase PostgreSQL
"""
import sqlite3
import os
import json
import uuid
from datetime import datetime, date
from contextlib import contextmanager

from config import Config

DB_PATH = Config.SQLITE_PATH


def _ensure_data_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    """获取数据库连接上下文管理器"""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库 Schema（对齐 PRD 数据设计）"""
    _ensure_data_dir()
    with get_db() as conn:
        conn.executescript("""
            -- 竞品表（PRD US-01/02/03）
            CREATE TABLE IF NOT EXISTS competitors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                website_url TEXT,
                rss_url TEXT,
                g2_url TEXT,
                appstore_url TEXT,
                focus_dimensions TEXT DEFAULT '["功能更新","用户评价","融资动态"]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            -- 抓取记录（PRD §5 抓取模块）
            CREATE TABLE IF NOT EXISTS crawl_records (
                id TEXT PRIMARY KEY,
                competitor_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                title TEXT,
                content TEXT,
                url TEXT,
                published_at TEXT,
                crawled_at TEXT NOT NULL,
                FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE
            );

            -- AI 分析报告（PRD §5.2 输出结构）
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                competitor_id TEXT NOT NULL,
                report_date TEXT NOT NULL,
                summary TEXT,
                user_pain_points TEXT,
                threat_level TEXT CHECK (threat_level IN ('high', 'medium', 'low')),
                threat_reason TEXT,
                opportunity TEXT,
                analytics TEXT,
                raw_ai_response TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE
            );

            -- 每日简报（聚合所有竞品）
            CREATE TABLE IF NOT EXISTS daily_briefs (
                id TEXT PRIMARY KEY,
                brief_date TEXT UNIQUE NOT NULL,
                brief_content TEXT,
                total_signals INTEGER DEFAULT 0,
                high_threats INTEGER DEFAULT 0,
                competitors_covered INTEGER DEFAULT 0,
                recommendations TEXT,
                created_at TEXT NOT NULL
            );
        """)
        _ensure_column(conn, "reports", "analytics", "TEXT")


def _ensure_column(conn, table_name, column_name, column_def):
    """轻量 SQLite 迁移：为已有表补列。"""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row["name"] for row in rows}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def _gen_id(prefix=""):
    """生成带前缀的短 ID"""
    short = uuid.uuid4().hex[:12]
    return f"{prefix}{short}" if prefix else short


def _now():
    return datetime.utcnow().isoformat() + "Z"


def _row_to_dict(row):
    """sqlite3.Row → dict，自动解析 JSON 字段"""
    if row is None:
        return None
    d = dict(row)
    for key in ("focus_dimensions", "user_pain_points", "brief_content",
                "analytics",
                "raw_ai_response", "recommendations"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ── 竞品 CRUD ─────────────────────────────────────────

def create_competitor(name, website_url="", rss_url="", g2_url="",
                      appstore_url="", focus_dimensions=None):
    """创建竞品（PRD US-01）"""
    if focus_dimensions is None:
        focus_dimensions = ["功能更新", "用户评价", "融资动态"]

    comp = {
        "id": _gen_id("comp_"),
        "name": name,
        "website_url": website_url,
        "rss_url": rss_url,
        "g2_url": g2_url,
        "appstore_url": appstore_url,
        "focus_dimensions": json.dumps(focus_dimensions, ensure_ascii=False),
        "created_at": _now(),
        "updated_at": _now(),
    }

    with get_db() as conn:
        conn.execute("""
            INSERT INTO competitors (id, name, website_url, rss_url, g2_url,
                                     appstore_url, focus_dimensions, created_at, updated_at)
            VALUES (:id, :name, :website_url, :rss_url, :g2_url,
                    :appstore_url, :focus_dimensions, :created_at, :updated_at)
        """, comp)

    comp["focus_dimensions"] = focus_dimensions
    return comp


def list_competitors():
    """列出所有竞品"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM competitors ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_competitor(competitor_id):
    """获取单个竞品"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM competitors WHERE id = ?", (competitor_id,)
        ).fetchone()
    return _row_to_dict(row)


def update_competitor(competitor_id, **kwargs):
    """更新竞品信息"""
    allowed = {"name", "website_url", "rss_url", "g2_url",
               "appstore_url", "focus_dimensions"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_competitor(competitor_id)

    if "focus_dimensions" in updates and isinstance(updates["focus_dimensions"], list):
        updates["focus_dimensions"] = json.dumps(updates["focus_dimensions"], ensure_ascii=False)

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = competitor_id

    with get_db() as conn:
        conn.execute(f"UPDATE competitors SET {set_clause} WHERE id = :id", updates)

    return get_competitor(competitor_id)


def delete_competitor(competitor_id):
    """删除竞品及其关联数据"""
    with get_db() as conn:
        conn.execute("DELETE FROM competitors WHERE id = ?", (competitor_id,))
    return True


def count_competitors():
    """统计竞品数量（PRD US-02: 最多 5 个）"""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM competitors").fetchone()
    return row["cnt"] if row else 0


# ── 抓取记录 ─────────────────────────────────────────

def save_crawl_records(competitor_id, records):
    """批量保存抓取记录"""
    now = _now()
    with get_db() as conn:
        for record in records:
            conn.execute("""
                INSERT INTO crawl_records (id, competitor_id, source_type,
                                           title, content, url, published_at, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                _gen_id("crawl_"),
                competitor_id,
                record.get("source_type", "rss"),
                record.get("title", ""),
                record.get("content", ""),
                record.get("url", ""),
                record.get("published_at", ""),
                now,
            ))
    return len(records)


def get_crawl_records(competitor_id, limit=20):
    """获取竞品的最近抓取记录"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM crawl_records
            WHERE competitor_id = ?
            ORDER BY crawled_at DESC
            LIMIT ?
        """, (competitor_id, limit)).fetchall()
    return [_row_to_dict(r) for r in rows]


# ── 报告 ─────────────────────────────────────────────

def save_report(competitor_id, report_data):
    """保存 AI 分析报告（PRD §5.2 结构）"""
    report = {
        "id": _gen_id("rpt_"),
        "competitor_id": competitor_id,
        "report_date": date.today().isoformat(),
        "summary": report_data.get("summary", ""),
        "user_pain_points": json.dumps(
            report_data.get("user_pain_points", []), ensure_ascii=False
        ),
        "threat_level": report_data.get("threat_level", "medium"),
        "threat_reason": report_data.get("threat_reason", ""),
        "opportunity": report_data.get("opportunity", ""),
        "analytics": json.dumps(
            report_data.get("analytics", {}), ensure_ascii=False
        ),
        "raw_ai_response": json.dumps(
            report_data.get("raw_ai_response", {}), ensure_ascii=False
        ),
        "created_at": _now(),
    }

    with get_db() as conn:
        conn.execute("""
            INSERT INTO reports (id, competitor_id, report_date, summary,
                                 user_pain_points, threat_level, threat_reason,
                                 opportunity, analytics, raw_ai_response, created_at)
            VALUES (:id, :competitor_id, :report_date, :summary,
                    :user_pain_points, :threat_level, :threat_reason,
                    :opportunity, :analytics, :raw_ai_response, :created_at)
        """, report)

    return _row_to_dict(
        sqlite3.Row(None, tuple(report.values()))
    ) if False else {
        **report,
        "user_pain_points": report_data.get("user_pain_points", []),
        "analytics": report_data.get("analytics", {}),
    }


def get_latest_report(competitor_id):
    """获取竞品最新报告"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT * FROM reports
            WHERE competitor_id = ?
            ORDER BY report_date DESC, created_at DESC
            LIMIT 1
        """, (competitor_id,)).fetchone()
    return _row_to_dict(row)


def list_reports(competitor_id=None, limit=30):
    """列出报告，可按竞品过滤"""
    with get_db() as conn:
        if competitor_id:
            rows = conn.execute("""
                SELECT r.*, c.name as competitor_name
                FROM reports r JOIN competitors c ON r.competitor_id = c.id
                WHERE r.competitor_id = ?
                ORDER BY r.report_date DESC, r.created_at DESC
                LIMIT ?
            """, (competitor_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.*, c.name as competitor_name
                FROM reports r JOIN competitors c ON r.competitor_id = c.id
                ORDER BY r.report_date DESC, r.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_report(report_id):
    """删除单条报告"""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        return cur.rowcount > 0


# ── 每日简报 ─────────────────────────────────────────

def save_daily_brief(brief_data):
    """保存每日聚合简报"""
    brief = {
        "id": _gen_id("brief_"),
        "brief_date": date.today().isoformat(),
        "brief_content": json.dumps(
            brief_data.get("content", {}), ensure_ascii=False
        ),
        "total_signals": brief_data.get("total_signals", 0),
        "high_threats": brief_data.get("high_threats", 0),
        "competitors_covered": brief_data.get("competitors_covered", 0),
        "recommendations": json.dumps(
            brief_data.get("recommendations", []), ensure_ascii=False
        ),
        "created_at": _now(),
    }

    with get_db() as conn:
        # UPSERT：同一天只保留最新简报
        conn.execute("""
            INSERT INTO daily_briefs (id, brief_date, brief_content, total_signals,
                                      high_threats, competitors_covered, recommendations, created_at)
            VALUES (:id, :brief_date, :brief_content, :total_signals,
                    :high_threats, :competitors_covered, :recommendations, :created_at)
            ON CONFLICT(brief_date) DO UPDATE SET
                brief_content = :brief_content,
                total_signals = :total_signals,
                high_threats = :high_threats,
                competitors_covered = :competitors_covered,
                recommendations = :recommendations,
                created_at = :created_at
        """, brief)

    return brief


def get_latest_brief():
    """获取最新每日简报"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT * FROM daily_briefs ORDER BY brief_date DESC LIMIT 1
        """).fetchone()
    return _row_to_dict(row)


def list_briefs(limit=14):
    """列出历史简报"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM daily_briefs ORDER BY brief_date DESC LIMIT ?
        """, (limit,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_brief(brief_id):
    """删除单条每日简报"""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM daily_briefs WHERE id = ?", (brief_id,))
        return cur.rowcount > 0
