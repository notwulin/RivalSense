"""
RivalSense AI 洞察分析服务 v3
架构升级：Python NLP 做 80% 重活，LLM 只做 20% 点睛
"""
import json
import requests
import logging
from datetime import date as date_cls
from config import Config
from services.data_analyzer import process_and_summarize

logger = logging.getLogger(__name__)

# ── System Prompt v5（纯点睛版，基于统计提要）──────────────────────────

SYSTEM_PROMPT = """你是一名顶级商业战略顾问。
我方提供了一份通过严密自然语言处理挖掘的【竞品数据统计与事实摘要】。
你的任务是：基于这些统计事实，撰写一份极度精炼、一针见血的高管执行摘要 (Executive Summary)。

## 规则
1. 你的分析必须 100% 忠于我提供的统计数据，绝不能捏造痛点或商业动态。
2. 威胁等级界定：
   - high：有强烈的负面舆情(负面>40%)，或有重大商业动作（融资/收购/核心改版）。
   - medium：常规迭代伴随中等强度的吐槽(负面20-40%)。
   - low：无波澜(负面<20%)。
3. 把最重要的聚类痛点作为反击机会。
4. 输出必须是精简、专业、客观的语气，使用中文。

## 输出格式
严格 JSON，严禁 Markdown 块或其他字符：
{
    "competitor": "竞品名称",
    "date": "YYYY-MM-DD",
    "threat_level": "high|medium|low",
    "threat_reason": "核心评级依据，1-2句话",
    "summary": "竞品现状执行摘要，综合其商业信号与情感趋势，约100字",
    "user_pain_points": [
        {"point": "转述最高频核心痛点簇(中文)", "source": "全网统计", "frequency": "high|medium|low"}
    ],
    "opportunity": "我方战略反击切入点，1-2句话"
}"""


def _build_analysis_prompt(competitor_name, crawled_data):
    """
    通过 data_analyzer 生成 ~500 字的统计摘要喂给大模型。
    返回 (prompt_text, analytics_dict)
    """
    text_summary, analytics = process_and_summarize(competitor_name, crawled_data)

    logger.info(f"[{competitor_name}] Python 本地统计摘要已生成（{len(text_summary)} 字符），移交 LLM 点睛...")

    prompt = (
        f"请阅读以下关于竞品「{competitor_name}」的统计摘要，并按 JSON 格式生成商业洞察：\n\n"
        f"{text_summary}\n"
    )
    return prompt, analytics


# ── Gemini API 调用 ──────────────────────────────────

def _call_gemini(prompt_text):
    """调用 Gemini API 进行分析"""
    if not Config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未配置")

    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "generationConfig": {
            "temperature": 0.15,
            "responseMimeType": "application/json",
        },
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt_text}]
        }]
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": Config.GEMINI_API_KEY,
    }

    resp = requests.post(
        Config.GEMINI_API_URL,
        json=payload,
        headers=headers,
        timeout=45,
    )

    if not resp.ok:
        raise RuntimeError(f"Gemini API 错误 HTTP {resp.status_code}: {resp.text[:300]}")

    result = resp.json()
    content = ""
    candidates = result.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts)

    return content


# ── DeepSeek API 调用 ──────────────────────────────────

def _call_deepseek(prompt_text):
    """调用 DeepSeek API 进行分析"""
    if not Config.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY 未配置")

    payload = {
        "model": Config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
    }

    resp = requests.post(
        Config.DEEPSEEK_API_URL,
        json=payload,
        headers=headers,
        timeout=45,
    )

    if not resp.ok:
        raise RuntimeError(f"DeepSeek API 错误 HTTP {resp.status_code}: {resp.text[:300]}")

    result = resp.json()
    return result.get("choices", [{}])[0].get("message", {}).get("content", "{}")


# ── 本地规则回退 ──────────────────────────────────────

def _fallback_analysis(competitor_name, crawled_data):
    """当 LLM 不可用时的本地规则分析"""
    text_summary, analytics = process_and_summarize(competitor_name, crawled_data)

    # 基于统计数据推断威胁等级
    neg_pct = analytics.get("sentiment_percentages", {}).get("negative", 0)
    signals = analytics.get("business_signals", [])

    threat_level = "low"
    if neg_pct > 40 or any(s["type"] == "fundraising" for s in signals):
        threat_level = "high"
    elif neg_pct > 20 or signals:
        threat_level = "medium"

    # 从聚类中提取痛点
    pain_points = []
    for cluster in analytics.get("pain_clusters", [])[:4]:
        label = cluster.get("cluster_label") or "未命名痛点"
        keywords = "、".join(cluster.get("keywords", [])[:3])
        pain_points.append({
            "point": f"{label}（{keywords}，影响 {cluster['count']} 人）",
            "source": "NLP聚类",
            "frequency": "high" if cluster["count"] > 5 else "medium"
        })

    top_cluster = analytics.get("pain_clusters", [{}])[0] if analytics.get("pain_clusters") else {}
    top_label = top_cluster.get("cluster_label", "待定")

    return {
        "competitor": competitor_name,
        "date": date_cls.today().isoformat(),
        "summary": f"基于 {analytics['total_records']} 条数据的本地 NLP 分析：负面评价占 {neg_pct:.0f}%。",
        "user_pain_points": pain_points,
        "threat_level": threat_level,
        "threat_reason": f"负面舆情占比 {neg_pct:.0f}%，{'检测到商业信号' if signals else '无重大商业动态'}。",
        "opportunity": f"围绕「{top_label}」建立更清晰的差异化方案，并用可验证证据对外表达。",
        "analysis_mode": "fallback_nlp",
        "analytics": analytics,
    }


# ── 痛点质量校验 ──────────────────────────────────────

def _validate_pain_points(pain_points):
    """后处理：校验痛点质量，过滤误判"""
    positive_signals = [
        "amazing", "love", "great", "awesome", "wonderful",
        "best", "excellent", "perfect", "fantastic", "incredible",
        "太好了", "好用", "推荐", "优秀", "完美", "棒",
        "i love", "so good", "really good", "highly recommend",
    ]

    validated = []
    for pp in pain_points:
        if not isinstance(pp, dict):
            continue
        text = pp.get("point", "").lower()
        if any(signal in text for signal in positive_signals):
            continue
        if len(pp.get("point", "")) < 5:
            continue
        validated.append(pp)

    return validated


# ── 统一分析入口 ──────────────────────────────────────

def analyze_competitor(competitor_name, crawled_data):
    """
    对竞品进行 AI 洞察分析（v3 混合架构）
    流程：Python NLP 统计 → LLM 点睛 → 合并输出
    """
    if not crawled_data:
        return _fallback_analysis(competitor_name, [])

    # Step 1: Python 本地分析 + 生成 prompt
    prompt_text, analytics = _build_analysis_prompt(competitor_name, crawled_data)

    # Step 2: 尝试调用 LLM
    engine = Config.AI_ENGINE.lower()
    raw_content = None

    try:
        if engine == "deepseek" and Config.DEEPSEEK_API_KEY:
            logger.info(f"使用 DeepSeek 分析 [{competitor_name}]")
            raw_content = _call_deepseek(prompt_text)
        elif Config.GEMINI_API_KEY:
            logger.info(f"使用 Gemini 分析 [{competitor_name}]")
            raw_content = _call_gemini(prompt_text)
        else:
            logger.warning("无可用 AI 引擎，使用本地 NLP 回退")
            return _fallback_analysis(competitor_name, crawled_data)

    except Exception as e:
        logger.error(f"AI 分析失败 [{competitor_name}]: {e}")
        result = _fallback_analysis(competitor_name, crawled_data)
        result["error"] = str(e)
        return result

    # Step 3: 解析 LLM 返回的 JSON
    try:
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        result = json.loads(cleaned)
        result["analysis_mode"] = engine

        # 必要字段兜底
        result.setdefault("competitor", competitor_name)
        result.setdefault("threat_level", "medium")
        result.setdefault("user_pain_points", [])
        result.setdefault("summary", "")
        result.setdefault("threat_reason", "")
        result.setdefault("opportunity", "")

        # 痛点质量校验
        if result["user_pain_points"]:
            result["user_pain_points"] = _validate_pain_points(result["user_pain_points"])

        # 关键：将 Python 分析的结构化数据附加到结果中（供前端展示）
        result["analytics"] = analytics

        logger.info(
            f"AI 分析完成 [{competitor_name}]: "
            f"威胁={result['threat_level']}, "
            f"痛点={len(result['user_pain_points'])}条, "
            f"数据量={analytics['total_records']}条"
        )

        return result

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"AI 输出解析失败 [{competitor_name}]: {e}")
        result = _fallback_analysis(competitor_name, crawled_data)
        result["raw_ai_response"] = raw_content
        return result


# ── 每日简报聚合 ──────────────────────────────────────

def build_daily_brief(competitor_reports):
    """
    将所有竞品的分析报告聚合为每日简报
    """
    if not competitor_reports:
        return {
            "content": {"competitors": [], "headline": "今日无竞品分析数据"},
            "total_signals": 0,
            "high_threats": 0,
            "competitors_covered": 0,
            "recommendations": ["请先添加竞品并配置数据源"],
        }

    high_threats = [r for r in competitor_reports if r.get("threat_level") == "high"]
    medium_threats = [r for r in competitor_reports if r.get("threat_level") == "medium"]
    total_pain_points = sum(len(r.get("user_pain_points", [])) for r in competitor_reports)

    recommendations = []
    if high_threats:
        names = "、".join(r.get("competitor", "未知") for r in high_threats[:3])
        recommendations.append(f"⚠️ 高威胁竞品（{names}）需要立即关注。")
    for r in high_threats[:2]:
        if r.get("opportunity"):
            recommendations.append(f"💡 {r['competitor']}：{r['opportunity']}")
    if total_pain_points > 0:
        recommendations.append(f"📊 本日共发现 {total_pain_points} 条竞品用户痛点信号。")
    if not recommendations:
        recommendations.append("✅ 今日竞品动态平稳，可聚焦自身产品迭代。")

    headline = ""
    if high_threats:
        headline = f"{len(high_threats)} 个高威胁信号需要立即关注"
    elif medium_threats:
        headline = f"{len(medium_threats)} 个竞品有中等威胁动态"
    else:
        headline = "今日竞品动态整体平稳"

    return {
        "content": {
            "date": date_cls.today().isoformat(),
            "headline": headline,
            "competitors": [
                {
                    "name": r.get("competitor", ""),
                    "threat_level": r.get("threat_level", "low"),
                    "summary": r.get("summary", ""),
                    "threat_reason": r.get("threat_reason", ""),
                    "opportunity": r.get("opportunity", ""),
                    "pain_points_count": len(r.get("user_pain_points", [])),
                }
                for r in competitor_reports
            ],
        },
        "total_signals": len(competitor_reports),
        "high_threats": len(high_threats),
        "competitors_covered": len(competitor_reports),
        "recommendations": recommendations,
    }
