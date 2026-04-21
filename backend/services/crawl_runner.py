"""
Reusable crawl execution pipeline.

Keeps the synchronous API routes and background jobs on the same behavior path.
"""
import logging

from models.database import (
    list_competitors,
    save_crawl_records,
    save_report,
    save_daily_brief,
)
from services.scraper import crawl_competitor
from services.ai_analyzer import analyze_competitor, build_daily_brief

logger = logging.getLogger(__name__)


def _emit(progress_callback, stage, progress, message):
    if progress_callback:
        progress_callback(stage=stage, progress=progress, message=message)


def run_competitor_crawl_pipeline(competitor, progress_callback=None):
    """
    Execute crawl -> persist records -> analyze -> persist report.
    Returns the JSON-ready payload used by the API.
    """
    competitor_id = competitor["id"]
    competitor_name = competitor.get("name", "未知")

    _emit(progress_callback, "crawl", 10, f"开始抓取 {competitor_name} 的公开情报")
    records, errors = crawl_competitor(competitor)

    _emit(progress_callback, "persist_records", 55, f"保存 {len(records)} 条抓取记录")
    saved_count = save_crawl_records(competitor_id, records) if records else 0

    _emit(progress_callback, "analyze", 72, "本地 NLP 聚类与商业信号识别中")
    report_data = analyze_competitor(competitor_name, records)

    _emit(progress_callback, "persist_report", 92, "保存分析报告")
    save_report(competitor_id, report_data)

    payload = {
        "competitor_id": competitor_id,
        "crawled": saved_count,
        "errors": errors,
        "report": report_data,
        "analytics": report_data.get("analytics", {}),
    }

    _emit(progress_callback, "completed", 100, "抓取分析完成")
    logger.info(
        "竞品 [%s] 抓取分析完成: crawled=%s errors=%s",
        competitor_name,
        saved_count,
        len(errors),
    )
    return payload


def run_all_crawls_pipeline(progress_callback=None):
    """
    Execute crawl + analysis for all competitors and build the daily brief.
    """
    competitors = list_competitors()
    if not competitors:
        raise ValueError("请先添加竞品")

    all_reports = []
    results = []
    total = len(competitors)

    for index, comp in enumerate(competitors, start=1):
        base_progress = int(((index - 1) / total) * 88)
        _emit(
            progress_callback,
            "crawl_competitor",
            max(5, base_progress),
            f"处理第 {index}/{total} 个竞品：{comp.get('name', '未知')}",
        )

        records, errors = crawl_competitor(comp)
        saved_count = save_crawl_records(comp["id"], records) if records else 0
        report_data = analyze_competitor(comp["name"], records)
        save_report(comp["id"], report_data)

        all_reports.append(report_data)
        results.append({
            "competitor": comp["name"],
            "crawled": saved_count,
            "threat_level": report_data.get("threat_level", "low"),
            "errors": errors,
        })

        _emit(
            progress_callback,
            "crawl_competitor",
            int((index / total) * 88),
            f"{comp.get('name', '未知')} 已完成，累计 {index}/{total}",
        )

    _emit(progress_callback, "daily_brief", 94, "生成每日异动简报")
    brief_data = build_daily_brief(all_reports)
    save_daily_brief(brief_data)

    payload = {
        "results": results,
        "brief": brief_data,
        "competitors_processed": total,
    }
    _emit(progress_callback, "completed", 100, "全部竞品抓取分析完成")
    return payload
