"""
RivalSense API 路由
对齐 PRD 信息架构：竞品管理 / Dashboard / 报告
"""
from flask import Blueprint, request, jsonify
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import (
    create_competitor, list_competitors, get_competitor,
    update_competitor, delete_competitor, count_competitors,
    get_crawl_records,
    get_latest_report, list_reports, delete_report,
    get_latest_brief, list_briefs, delete_brief,
)
from services.crawl_runner import run_all_crawls_pipeline, run_competitor_crawl_pipeline
from services.data_analyzer import process_and_summarize
from services.jobs import (
    get_job,
    list_jobs,
    submit_crawl_all_job,
    submit_competitor_crawl_job,
)
from config import Config

api = Blueprint("api", __name__, url_prefix="/api")


def _attach_analytics_if_missing(report, competitor_id, competitor_name=""):
    """
    旧报告没有 analytics 字段时，用最近抓取记录即时重算，避免前端面板丢失。
    新报告会直接从 reports.analytics 读取。
    """
    if not report:
        return report
    if report.get("analytics"):
        return report

    records = get_crawl_records(competitor_id, limit=700)
    if not records:
        report["analytics"] = None
        return report

    try:
        _, analytics = process_and_summarize(competitor_name or "竞品", records)
        report["analytics"] = analytics
    except Exception:
        report["analytics"] = None
    return report


# ── 健康检查 ──────────────────────────────────────────

@api.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "RivalSense API",
        "ai_engine": Config.AI_ENGINE,
        "ai_configured": bool(Config.GEMINI_API_KEY or Config.DEEPSEEK_API_KEY),
        "search_configured": bool(
            Config.BRAVE_SEARCH_API_KEY or Config.TAVILY_API_KEY or Config.SERPAPI_API_KEY
        ),
    })


# ── 竞品管理 CRUD（PRD P0: 核心入口）──────────────────

@api.route("/competitors", methods=["GET"])
def list_competitors_route():
    """列出所有竞品"""
    competitors = list_competitors()
    # 为每个竞品附加最新报告
    for comp in competitors:
        latest = get_latest_report(comp["id"])
        comp["latest_report"] = _attach_analytics_if_missing(latest, comp["id"], comp.get("name", ""))
    return jsonify({"competitors": competitors, "count": len(competitors)})


@api.route("/competitors", methods=["POST"])
def create_competitor_route():
    """
    添加竞品（PRD US-01）
    MVP 限制最多 5 个（PRD US-02）
    """
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "竞品名称不能为空"}), 400

    if count_competitors() >= Config.MAX_COMPETITORS:
        return jsonify({
            "error": f"MVP 阶段最多支持 {Config.MAX_COMPETITORS} 个竞品（PRD US-02）"
        }), 400

    comp = create_competitor(
        name=name,
        website_url=(data.get("website_url") or "").strip(),
        rss_url=(data.get("rss_url") or "").strip(),
        g2_url=(data.get("g2_url") or "").strip(),
        appstore_url=(data.get("appstore_url") or "").strip(),
        focus_dimensions=data.get("focus_dimensions"),
    )

    return jsonify({"competitor": comp}), 201


@api.route("/competitors/<competitor_id>", methods=["GET"])
def get_competitor_route(competitor_id):
    """获取竞品详情"""
    comp = get_competitor(competitor_id)
    if not comp:
        return jsonify({"error": "竞品不存在"}), 404
    comp["latest_report"] = get_latest_report(competitor_id)
    comp["latest_report"] = _attach_analytics_if_missing(
        comp["latest_report"], competitor_id, comp.get("name", "")
    )
    comp["crawl_records"] = get_crawl_records(competitor_id, limit=10)
    return jsonify({"competitor": comp})


@api.route("/competitors/<competitor_id>", methods=["PUT"])
def update_competitor_route(competitor_id):
    """更新竞品信息（PRD US-03: 设置关注维度）"""
    comp = get_competitor(competitor_id)
    if not comp:
        return jsonify({"error": "竞品不存在"}), 404

    data = request.get_json(force=True)
    updated = update_competitor(competitor_id, **data)
    return jsonify({"competitor": updated})


@api.route("/competitors/<competitor_id>", methods=["DELETE"])
def delete_competitor_route(competitor_id):
    """删除竞品"""
    comp = get_competitor(competitor_id)
    if not comp:
        return jsonify({"error": "竞品不存在"}), 404

    delete_competitor(competitor_id)
    return jsonify({"deleted": True, "id": competitor_id})


# ── 抓取 & 分析（PRD P0: 核心链路）──────────────────

@api.route("/competitors/<competitor_id>/crawl", methods=["POST"])
def crawl_competitor_route(competitor_id):
    """
    对单个竞品执行抓取 + AI 分析
    PRD 核心流程：抓取 → AI 分析 → 更新报告
    验收标准：AI 分析单竞品 < 30 秒（PRD §6）
    """
    comp = get_competitor(competitor_id)
    if not comp:
        return jsonify({"error": "竞品不存在"}), 404

    return jsonify(run_competitor_crawl_pipeline(comp))


@api.route("/competitors/<competitor_id>/crawl-jobs", methods=["POST"])
def create_competitor_crawl_job_route(competitor_id):
    """
    异步启动单个竞品抓取任务，返回 job_id 供前端轮询进度。
    """
    comp = get_competitor(competitor_id)
    if not comp:
        return jsonify({"error": "竞品不存在"}), 404

    job = submit_competitor_crawl_job(comp)
    return jsonify({"job_id": job["id"], "job": job}), 202


@api.route("/crawl-jobs/<job_id>", methods=["GET"])
def get_crawl_job_route(job_id):
    """获取抓取任务状态"""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "任务不存在或已过期"}), 404
    return jsonify({"job": job})


@api.route("/crawl-jobs", methods=["GET"])
def list_crawl_jobs_route():
    """列出最近抓取任务"""
    limit = int(request.args.get("limit", 20))
    return jsonify({"jobs": list_jobs(limit=limit)})


@api.route("/crawl-all", methods=["POST"])
def crawl_all_route():
    """
    对所有竞品执行抓取 + 分析，并生成每日简报
    PRD US-04: 每天早上 9:00 收到竞品简报
    """
    if not list_competitors():
        return jsonify({"error": "请先添加竞品"}), 400

    return jsonify(run_all_crawls_pipeline())


@api.route("/crawl-all-jobs", methods=["POST"])
def create_crawl_all_job_route():
    """
    异步启动全量竞品抓取任务。
    """
    try:
        job = submit_crawl_all_job()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"job_id": job["id"], "job": job}), 202


# ── Dashboard 数据（PRD P0: 基础消费入口）──────────────

@api.route("/dashboard")
def dashboard():
    """
    Dashboard 首页数据聚合
    PRD §7: Dashboard（首页）— 竞品威胁总览卡片
    性能目标：首屏 < 3 秒
    """
    competitors = list_competitors()
    latest_brief = get_latest_brief()

    # 为每个竞品附加最新报告
    competitor_cards = []
    for comp in competitors:
        latest = get_latest_report(comp["id"])
        competitor_cards.append({
            "id": comp["id"],
            "name": comp["name"],
            "website_url": comp.get("website_url", ""),
            "threat_level": latest.get("threat_level", "low") if latest else "low",
            "summary": latest.get("summary", "尚未分析") if latest else "尚未分析",
            "threat_reason": latest.get("threat_reason", "") if latest else "",
            "opportunity": latest.get("opportunity", "") if latest else "",
            "pain_points_count": len(latest.get("user_pain_points", [])) if latest else 0,
            "last_analyzed": latest.get("created_at", "") if latest else "",
        })

    # 按威胁等级排序（高 > 中 > 低）
    threat_order = {"high": 0, "medium": 1, "low": 2}
    competitor_cards.sort(key=lambda x: threat_order.get(x["threat_level"], 3))

    return jsonify({
        "competitors": competitor_cards,
        "brief": latest_brief,
        "stats": {
            "total_competitors": len(competitors),
            "high_threats": sum(1 for c in competitor_cards if c["threat_level"] == "high"),
            "total_signals": latest_brief.get("total_signals", 0) if latest_brief else 0,
        },
    })


# ── 报告（PRD P1: 历史报告回溯）──────────────────────

@api.route("/reports")
def list_reports_route():
    """报告列表"""
    competitor_id = request.args.get("competitor_id")
    limit = int(request.args.get("limit", 30))
    reports = list_reports(competitor_id=competitor_id, limit=limit)
    return jsonify({"reports": reports})


@api.route("/reports/<competitor_id>/latest")
def latest_report_route(competitor_id):
    """获取竞品最新报告"""
    report = get_latest_report(competitor_id)
    if not report:
        return jsonify({"error": "暂无报告"}), 404
    comp = get_competitor(competitor_id)
    report = _attach_analytics_if_missing(report, competitor_id, comp.get("name", "") if comp else "")
    return jsonify({"report": report})


@api.route("/reports/<report_id>", methods=["DELETE"])
def delete_report_route(report_id):
    """删除单条历史报告"""
    deleted = delete_report(report_id)
    if not deleted:
        return jsonify({"error": "报告不存在"}), 404
    return jsonify({"deleted": True, "id": report_id})


# ── 每日简报 ──────────────────────────────────────────

@api.route("/briefs")
def list_briefs_route():
    """简报列表"""
    limit = int(request.args.get("limit", 14))
    briefs = list_briefs(limit=limit)
    return jsonify({"briefs": briefs})


@api.route("/briefs/latest")
def latest_brief_route():
    """最新简报"""
    brief = get_latest_brief()
    if not brief:
        return jsonify({"error": "暂无简报，请先触发一次全量抓取"}), 404
    return jsonify({"brief": brief})


@api.route("/briefs/<brief_id>", methods=["DELETE"])
def delete_brief_route(brief_id):
    """删除单条每日简报"""
    deleted = delete_brief(brief_id)
    if not deleted:
        return jsonify({"error": "简报不存在"}), 404
    return jsonify({"deleted": True, "id": brief_id})


# ── 报告导出（PRD P1）──────────────────────────────────

@api.route("/reports/<competitor_id>/export", methods=["POST"])
def export_report_route(competitor_id):
    """导出报告为 Markdown（PRD US-09）"""
    report = get_latest_report(competitor_id)
    if not report:
        return jsonify({"error": "暂无报告"}), 404

    comp = get_competitor(competitor_id)
    comp_name = comp["name"] if comp else "未知竞品"

    md_lines = [
        f"# RivalSense 竞品分析报告 · {comp_name}",
        "",
        f"- 分析日期：{report.get('report_date', '')}",
        f"- 威胁等级：**{report.get('threat_level', 'N/A')}**",
        "",
        "## 核心动作摘要",
        report.get("summary", "暂无摘要"),
        "",
        "## 威胁分析",
        report.get("threat_reason", "暂无分析"),
        "",
        "## 用户痛点",
    ]

    pain_points = report.get("user_pain_points", [])
    if isinstance(pain_points, list):
        for pp in pain_points:
            if isinstance(pp, dict):
                md_lines.append(
                    f"- {pp.get('point', '')}（来源：{pp.get('source', '未知')}，"
                    f"频率：{pp.get('frequency', 'N/A')}）"
                )
    else:
        md_lines.append("暂无痛点数据")

    md_lines.extend([
        "",
        "## 产品机会",
        report.get("opportunity", "暂无机会分析"),
        "",
        "---",
        "*由 RivalSense AI 竞品雷达生成*",
    ])

    return jsonify({
        "markdown": "\n".join(md_lines),
        "competitor": comp_name,
        "report_date": report.get("report_date", ""),
    })
