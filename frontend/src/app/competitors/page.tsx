"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { Competitor, Analytics, CrawlJob, CrawlResult } from "@/lib/api";
import {
  clearActiveCompetitorCrawlJob,
  getActiveCompetitorCrawlJobs,
  setActiveCompetitorCrawlJob,
} from "@/lib/crawlJobStore";

const CRAWL_POLL_INTERVAL_MS = 1500;
const CRAWL_TIMEOUT_MS = 10 * 60 * 1000;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* ── 可视化小组件 ────────────────────────────────────── */

function SentimentDonut({ analytics }: { analytics: Analytics }) {
  const { negative, neutral, positive } = analytics.sentiment_distribution;
  const total = negative + neutral + positive || 1;
  const negPct = (negative / total) * 100;
  const neuPct = (neutral / total) * 100;
  const posPct = (positive / total) * 100;

  // CSS conic-gradient donut
  const gradient = `conic-gradient(
    #ef4444 0% ${negPct}%,
    #a3a3a3 ${negPct}% ${negPct + neuPct}%,
    #22c55e ${negPct + neuPct}% 100%
  )`;

  return (
    <div className="flex items-center gap-4">
      <div
        style={{
          background: gradient,
          width: 80,
          height: 80,
          borderRadius: "50%",
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 16,
            background: "rgba(255,255,255,0.9)",
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          {total}条
        </div>
      </div>
      <div className="space-y-1 text-xs">
        <div className="flex items-center gap-2">
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444", display: "inline-block" }} />
          负面 {negative}条 ({negPct.toFixed(0)}%)
        </div>
        <div className="flex items-center gap-2">
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#a3a3a3", display: "inline-block" }} />
          中性 {neutral}条 ({neuPct.toFixed(0)}%)
        </div>
        <div className="flex items-center gap-2">
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#22c55e", display: "inline-block" }} />
          正面 {positive}条 ({posPct.toFixed(0)}%)
        </div>
      </div>
    </div>
  );
}

function SourceBars({ analytics }: { analytics: Analytics }) {
  const sources = analytics.source_distribution;
  const entries = Object.entries(sources).sort((a, b) => b[1] - a[1]);
  const maxVal = entries[0]?.[1] || 1;
  const colors = ["#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ef4444", "#06b6d4"];

  return (
    <div className="space-y-2">
      {entries.map(([source, count], i) => (
        <div key={source} className="flex items-center gap-2 text-xs">
          <span className="w-24 text-right text-[var(--color-text-muted)] truncate">{source}</span>
          <div className="flex-1 h-5 bg-white/40 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(count / maxVal) * 100}%`,
                background: colors[i % colors.length],
                minWidth: 24,
              }}
            />
          </div>
          <span className="w-8 font-bold">{count}</span>
        </div>
      ))}
    </div>
  );
}

function PainClusters({ analytics }: { analytics: Analytics }) {
  if (!analytics.pain_clusters || analytics.pain_clusters.length === 0) {
    return <p className="text-xs text-[var(--color-text-muted)]">数据量不足，未形成明显痛点聚类。</p>;
  }

  return (
    <div className="space-y-3">
      {analytics.pain_clusters.map((cluster, i) => (
        <div key={i} className="p-3 rounded-xl bg-white/50 border border-[rgba(77,41,14,0.08)]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-sm font-bold">#{i + 1} 痛点簇</span>
            <span className="pill-tag text-[10px]">影响 {cluster.count} 人</span>
          </div>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {cluster.keywords.map((kw) => (
              <span key={kw} className="px-2 py-0.5 text-[10px] rounded-full bg-red-100 text-red-700 font-medium">
                {kw}
              </span>
            ))}
          </div>
          <p className="text-[11px] text-[var(--color-text-muted)] italic leading-relaxed">
            &ldquo;{cluster.sample_quote}&rdquo;
          </p>
        </div>
      ))}
    </div>
  );
}

function BusinessSignals({ analytics }: { analytics: Analytics }) {
  if (!analytics.business_signals || analytics.business_signals.length === 0) {
    return <p className="text-xs text-[var(--color-text-muted)]">近期无重大商业信号。</p>;
  }

  return (
    <div className="space-y-2">
      {analytics.business_signals.map((signal, i) => (
        <div key={i} className="flex items-start gap-2 text-xs p-2 rounded-lg bg-white/50">
          <span className="text-base">{signal.label.slice(0, 2)}</span>
          <div>
            <span className="font-semibold">{signal.label.slice(2)}</span>
            <p className="text-[var(--color-text-muted)] mt-0.5">{signal.title}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function TopNegativeQuotes({ analytics }: { analytics: Analytics }) {
  if (!analytics.top_negative_quotes || analytics.top_negative_quotes.length === 0) return null;

  return (
    <div className="space-y-2">
      {analytics.top_negative_quotes.map((q, i) => (
        <div key={i} className="flex items-start gap-2 text-[11px] p-2 rounded-lg bg-red-50/60 border border-red-100">
          <span className="font-bold text-red-500 shrink-0">{q.score}</span>
          <p className="text-[var(--color-text-muted)] leading-relaxed">{q.content}</p>
          <span className="pill-tag text-[9px] shrink-0">{q.source}</span>
        </div>
      ))}
    </div>
  );
}

/* ── 分析结果面板（核心展示） ─────────────────────────── */

function AnalyticsPanel({ analytics }: { analytics: Analytics }) {
  return (
    <div className="mt-4 pt-4 border-t border-[rgba(77,41,14,0.08)] space-y-5 fade-in">
      {/* 数据概览条 */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="px-3 py-1.5 rounded-xl bg-blue-50/80 text-xs font-bold text-blue-700">
          📊 共抓取 {analytics.total_records} 条数据
        </div>
        <div className="px-3 py-1.5 rounded-xl bg-red-50/80 text-xs font-bold text-red-600">
          负面占比 {analytics.sentiment_percentages?.negative?.toFixed(0) || 0}%
        </div>
        <div className="px-3 py-1.5 rounded-xl bg-amber-50/80 text-xs font-bold text-amber-700">
          痛点簇 {analytics.pain_clusters?.length || 0} 个
        </div>
        <div className="px-3 py-1.5 rounded-xl bg-purple-50/80 text-xs font-bold text-purple-700">
          商业信号 {analytics.business_signals?.length || 0} 个
        </div>
      </div>

      {/* 双列布局 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 左列：情感分布 */}
        <div className="glass-card-strong">
          <h4 className="text-sm font-bold mb-3">📈 情感分布</h4>
          <SentimentDonut analytics={analytics} />
        </div>

        {/* 右列：数据来源 */}
        <div className="glass-card-strong">
          <h4 className="text-sm font-bold mb-3">🌐 数据来源分布</h4>
          <SourceBars analytics={analytics} />
        </div>
      </div>

      {/* 痛点聚类 */}
      <div className="glass-card-strong">
        <h4 className="text-sm font-bold mb-3">🔥 AI 痛点主题聚类 (TF-IDF + KMeans)</h4>
        <PainClusters analytics={analytics} />
      </div>

      {/* 双列：商业信号 + 最烈吐槽 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card-strong">
          <h4 className="text-sm font-bold mb-3">📡 商业信号雷达</h4>
          <BusinessSignals analytics={analytics} />
        </div>
        <div className="glass-card-strong">
          <h4 className="text-sm font-bold mb-3">💢 最强负面原话 Top 5</h4>
          <TopNegativeQuotes analytics={analytics} />
        </div>
      </div>
    </div>
  );
}

/* ── 主页面 ──────────────────────────────────────────── */

export default function CompetitorsPage() {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [crawlingId, setCrawlingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  // 存储每个竞品的 analytics 数据
  const [analyticsMap, setAnalyticsMap] = useState<Record<string, Analytics>>({});
  const [crawlJobs, setCrawlJobs] = useState<Record<string, CrawlJob>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const pollingJobIds = useRef<Set<string>>(new Set());

  const [form, setForm] = useState({
    name: "",
    website_url: "",
    rss_url: "",
    g2_url: "",
    appstore_url: "",
  });

  const fetchCompetitors = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.listCompetitors();
      setCompetitors(res.competitors);
      const persistedAnalytics = res.competitors.reduce<Record<string, Analytics>>((acc, comp) => {
        if (comp.latest_report?.analytics) {
          acc[comp.id] = comp.latest_report.analytics;
        }
        return acc;
      }, {});
      setAnalyticsMap(persistedAnalytics);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchCompetitors();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [fetchCompetitors]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;

    setSaving(true);
    setError("");
    try {
      await api.createCompetitor(form);
      setForm({ name: "", website_url: "", rss_url: "", g2_url: "", appstore_url: "" });
      setShowForm(false);
      await fetchCompetitors();
    } catch (e) {
      setError(e instanceof Error ? e.message : "添加失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定要删除这个竞品吗？相关报告也会被删除。")) return;
    try {
      await api.deleteCompetitor(id);
      await fetchCompetitors();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const pollCrawlJob = useCallback(async (jobId: string, competitorId: string) => {
    const deadline = Date.now() + CRAWL_TIMEOUT_MS;

    while (Date.now() < deadline) {
      const { job } = await api.getCrawlJob(jobId);
      setCrawlJobs((prev) => ({ ...prev, [competitorId]: job }));

      if (job.status === "completed") return job;
      if (job.status === "failed") {
        throw new Error(job.error || "抓取任务失败");
      }

      await sleep(CRAWL_POLL_INTERVAL_MS);
    }

    throw new Error("抓取任务超时，请稍后刷新查看结果");
  }, []);

  const finishCrawlJob = useCallback(async (job: CrawlJob, competitorId: string, shouldExpand: boolean) => {
    clearActiveCompetitorCrawlJob(competitorId);
    setCrawlingId((current) => (current === competitorId ? null : current));

    const result = job.result as CrawlResult | null | undefined;
    if (result?.analytics) {
      setAnalyticsMap((prev) => ({ ...prev, [competitorId]: result.analytics }));
      if (shouldExpand) setExpandedId(competitorId);
    }

    await fetchCompetitors();
  }, [fetchCompetitors]);

  const resumeCrawlJob = useCallback(async (competitorId: string, jobId: string) => {
    if (pollingJobIds.current.has(jobId)) return;
    pollingJobIds.current.add(jobId);
    setCrawlingId((current) => current || competitorId);

    try {
      const { job } = await api.getCrawlJob(jobId);
      setCrawlJobs((prev) => ({ ...prev, [competitorId]: job }));

      if (job.status === "completed") {
        await finishCrawlJob(job, competitorId, false);
        return;
      }
      if (job.status === "failed") {
        clearActiveCompetitorCrawlJob(competitorId);
        throw new Error(job.error || "抓取任务失败");
      }

      const finalJob = await pollCrawlJob(jobId, competitorId);
      await finishCrawlJob(finalJob, competitorId, false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复抓取任务失败");
      clearActiveCompetitorCrawlJob(competitorId);
      setCrawlingId((current) => (current === competitorId ? null : current));
    } finally {
      pollingJobIds.current.delete(jobId);
    }
  }, [finishCrawlJob, pollCrawlJob]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const activeJobs = getActiveCompetitorCrawlJobs();
      for (const [competitorId, jobId] of Object.entries(activeJobs)) {
        void resumeCrawlJob(competitorId, jobId);
      }
    }, 0);

    return () => window.clearTimeout(timer);
  }, [resumeCrawlJob]);

  const handleCrawl = async (id: string) => {
    setCrawlingId(id);
    setError("");
    try {
      const started = await api.startCrawlCompetitor(id);
      setActiveCompetitorCrawlJob(id, started.job_id);
      setCrawlJobs((prev) => ({ ...prev, [id]: started.job }));

      const finalJob = await pollCrawlJob(started.job_id, id);
      if (!finalJob.result || !("analytics" in finalJob.result)) {
        throw new Error("抓取任务完成但未返回分析结果");
      }

      await finishCrawlJob(finalJob, id, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "抓取失败");
      clearActiveCompetitorCrawlJob(id);
    } finally {
      setCrawlingId(null);
    }
  };

  const threatLabel = (level?: string) => {
    if (level === "high") return <span className="threat-badge threat-high">高威胁</span>;
    if (level === "medium") return <span className="threat-badge threat-medium">中威胁</span>;
    return <span className="threat-badge threat-low">低威胁</span>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] gap-3">
        <span className="pulse-loader" />
        <span className="pulse-loader" style={{ animationDelay: "0.2s" }} />
        <span className="pulse-loader" style={{ animationDelay: "0.4s" }} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 页头 */}
      <header className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="section-kicker">Competitor Intelligence</p>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold m-0">
            竞品管理
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            输入竞品名称即可自动全网嗅探（Reddit/HN/AlternativeTo/AppStore）+ Python NLP 统计分析
          </p>
        </div>
        {competitors.length < 5 && (
          <button onClick={() => setShowForm(!showForm)} className="btn-primary">
            {showForm ? "取消" : "➕ 添加竞品"}
          </button>
        )}
      </header>

      {error && (
        <div className="glass-card-strong text-[var(--color-danger)] text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* 添加表单 */}
      {showForm && (
        <form onSubmit={handleSubmit} className="glass-card fade-in space-y-4">
          <h3 className="font-[family-name:var(--font-display)] text-lg font-bold m-0">
            添加新竞品
          </h3>
          <p className="text-xs text-[var(--color-text-muted)] -mt-2">
            💡 只需填写竞品名称，系统将自动搜索全网相关讨论和评价。其他 URL 为可选项。
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1.5">竞品名称 *</label>
              <input
                type="text"
                className="input-field"
                placeholder="例：Telegram"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">官网 / 博客 URL（可选）</label>
              <input
                type="url"
                className="input-field"
                placeholder="https://telegram.org/blog"
                value={form.website_url}
                onChange={(e) => setForm({ ...form, website_url: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">RSS Feed URL（可选）</label>
              <input
                type="url"
                className="input-field"
                placeholder="https://..."
                value={form.rss_url}
                onChange={(e) => setForm({ ...form, rss_url: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">G2 评论页 URL（可选）</label>
              <input
                type="url"
                className="input-field"
                placeholder="https://www.g2.com/products/.../reviews"
                value={form.g2_url}
                onChange={(e) => setForm({ ...form, g2_url: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">AppStore URL（可选）</label>
              <input
                type="url"
                className="input-field"
                placeholder="https://apps.apple.com/app/id..."
                value={form.appstore_url}
                onChange={(e) => setForm({ ...form, appstore_url: e.target.value })}
              />
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? "保存中..." : "保存竞品"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">
              取消
            </button>
          </div>
        </form>
      )}

      {/* 竞品列表 */}
      {competitors.length > 0 ? (
        <div className="grid gap-4">
          {competitors.map((comp) => {
            const job = crawlJobs[comp.id];
            const jobActive = job?.status === "queued" || job?.status === "running";

            return (
            <article key={comp.id} className="glass-card fade-in">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="font-[family-name:var(--font-display)] text-xl font-bold m-0 truncate">
                      {comp.name}
                    </h3>
                    {comp.latest_report && threatLabel(comp.latest_report.threat_level)}
                  </div>
                  {comp.website_url && (
                    <p className="text-xs text-[var(--color-text-muted)] truncate mb-2">
                      🌐 {comp.website_url}
                    </p>
                  )}
                  {comp.latest_report ? (
                    <div className="space-y-2 mt-3">
                      <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">
                        📋 {comp.latest_report.summary}
                      </p>
                      {comp.latest_report.threat_reason && (
                        <p className="text-xs px-3 py-2 rounded-xl bg-white/50 text-[var(--color-text-muted)]">
                          ⚡ {comp.latest_report.threat_reason}
                        </p>
                      )}
                      {comp.latest_report.user_pain_points && comp.latest_report.user_pain_points.length > 0 && (
                        <div className="mt-2 space-y-1">
                          <p className="text-xs font-semibold text-[var(--color-text-muted)]">用户痛点：</p>
                          {comp.latest_report.user_pain_points.map((pp, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs text-[var(--color-text-muted)]">
                              <span className="pill-tag text-[10px] shrink-0">{pp.source}</span>
                              <span>{pp.point}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {comp.latest_report.opportunity && (
                        <p className="text-xs text-[var(--color-safe)]">
                          💡 机会：{comp.latest_report.opportunity}
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--color-text-muted)] mt-2">
                      尚未分析，点击右侧&quot;抓取分析&quot;开始
                    </p>
                  )}
                </div>

                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => handleCrawl(comp.id)}
                    disabled={crawlingId === comp.id || jobActive}
                    className="btn-primary text-sm"
                  >
                    {crawlingId === comp.id || jobActive ? (
                      <>
                        <span className="pulse-loader" style={{ background: "white" }} />
                        {job?.progress ? `分析中 ${job.progress}%` : "启动中..."}
                      </>
                    ) : (
                      "🔍 抓取分析"
                    )}
                  </button>
                  {(analyticsMap[comp.id] || comp.latest_report?.analytics) && (
                    <button
                      onClick={() => setExpandedId(expandedId === comp.id ? null : comp.id)}
                      className="btn-secondary text-sm"
                    >
                      {expandedId === comp.id ? "收起面板" : "📊 查看数据"}
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(comp.id)}
                    className="btn-secondary text-sm text-[var(--color-danger)]"
                  >
                    删除
                  </button>
                </div>
              </div>

              {/* 数据源标签 */}
              <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-[rgba(77,41,14,0.06)]">
                <span className="pill-tag text-[11px]">🧠 智能发现引擎</span>
                {comp.rss_url && <span className="pill-tag text-[11px]">📡 RSS</span>}
                {comp.website_url && <span className="pill-tag text-[11px]">🌐 博客</span>}
                {comp.g2_url && <span className="pill-tag text-[11px]">⭐ G2</span>}
                {comp.appstore_url && <span className="pill-tag text-[11px]">📱 AppStore</span>}
              </div>

              {jobActive && (
                <div className="mt-3 rounded-xl bg-white/55 p-3 border border-[rgba(77,41,14,0.08)]">
                  <div className="flex items-center justify-between gap-3 text-xs text-[var(--color-text-muted)] mb-2">
                    <span className="truncate">{job.message || "后台任务执行中"}</span>
                    <span className="font-bold text-[var(--color-text-primary)]">{job.progress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/70 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[var(--color-brand-brown)] transition-all duration-500"
                      style={{ width: `${Math.max(job.progress, 3)}%` }}
                    />
                  </div>
                </div>
              )}

              {job?.status === "failed" && (
                <div className="mt-3 rounded-xl bg-red-50/70 p-3 border border-red-100 text-xs text-[var(--color-danger)]">
                  {job.error || "后台抓取任务失败"}
                </div>
              )}

              {/* ✨ 数据可视化面板 */}
              {expandedId === comp.id && (analyticsMap[comp.id] || comp.latest_report?.analytics) && (
                <AnalyticsPanel analytics={(analyticsMap[comp.id] || comp.latest_report?.analytics) as Analytics} />
              )}
            </article>
            );
          })}
        </div>
      ) : (
        <div className="glass-card text-center py-16">
          <p className="text-4xl mb-4">🔭</p>
          <h3 className="font-[family-name:var(--font-display)] text-xl font-bold mb-2">
            开始追踪你的竞品
          </h3>
          <p className="text-[var(--color-text-muted)] mb-6">
            只需输入竞品名称，AI 将自动全网搜索、抓取分析并生成威胁洞察与数据面板。
          </p>
          <button onClick={() => setShowForm(true)} className="btn-primary">
            ➕ 添加第一个竞品
          </button>
        </div>
      )}
    </div>
  );
}
