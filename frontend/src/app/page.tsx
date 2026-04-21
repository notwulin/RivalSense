"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CrawlJob, DashboardData, DashboardCompetitor } from "@/lib/api";
import {
  clearActiveCrawlAllJob,
  getActiveCrawlAllJob,
  setActiveCrawlAllJob,
} from "@/lib/crawlJobStore";

const CRAWL_POLL_INTERVAL_MS = 1500;
const CRAWL_TIMEOUT_MS = 15 * 60 * 1000;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ThreatBadge({ level }: { level: string }) {
  const cls =
    level === "high"
      ? "threat-badge threat-high"
      : level === "medium"
      ? "threat-badge threat-medium"
      : "threat-badge threat-low";
  const label = level === "high" ? "高威胁" : level === "medium" ? "中威胁" : "低威胁";
  return <span className={cls}>{label}</span>;
}

function CompetitorCard({ comp }: { comp: DashboardCompetitor }) {
  return (
    <article className="glass-card-strong fade-in flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-[family-name:var(--font-display)] text-xl font-bold m-0 truncate">
            {comp.name}
          </h3>
          {comp.website_url && (
            <p className="text-xs text-[var(--color-text-muted)] mt-1 truncate">
              {comp.website_url}
            </p>
          )}
        </div>
        <ThreatBadge level={comp.threat_level} />
      </div>

      <p className="text-sm text-[var(--color-text-muted)] leading-relaxed line-clamp-3">
        {comp.summary}
      </p>

      {comp.threat_reason && (
        <div className="text-xs px-3 py-2 rounded-xl bg-white/50 text-[var(--color-text-muted)]">
          💡 {comp.threat_reason}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)] pt-1">
        <span>{comp.pain_points_count} 个用户痛点</span>
        {comp.last_analyzed && (
          <span>分析于 {new Date(comp.last_analyzed).toLocaleDateString("zh-CN")}</span>
        )}
      </div>
    </article>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [crawlJob, setCrawlJob] = useState<CrawlJob | null>(null);
  const [error, setError] = useState("");
  const pollingJobId = useRef("");

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const result = await api.dashboard();
      setData(result);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchDashboard();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [fetchDashboard]);

  const pollCrawlJob = useCallback(async (jobId: string) => {
    const deadline = Date.now() + CRAWL_TIMEOUT_MS;

    while (Date.now() < deadline) {
      const { job } = await api.getCrawlJob(jobId);
      setCrawlJob(job);

      if (job.status === "completed") return job;
      if (job.status === "failed") {
        throw new Error(job.error || "全量抓取任务失败");
      }

      await sleep(CRAWL_POLL_INTERVAL_MS);
    }

    throw new Error("全量抓取任务超时，请稍后刷新查看结果");
  }, []);

  const finishCrawlAllJob = useCallback(async () => {
    clearActiveCrawlAllJob();
    setCrawling(false);
    await fetchDashboard();
  }, [fetchDashboard]);

  const resumeCrawlAllJob = useCallback(async (jobId: string) => {
    if (pollingJobId.current === jobId) return;
    pollingJobId.current = jobId;
    setCrawling(true);

    try {
      const { job } = await api.getCrawlJob(jobId);
      setCrawlJob(job);

      if (job.status === "completed") {
        await finishCrawlAllJob();
        return;
      }
      if (job.status === "failed") {
        throw new Error(job.error || "全量抓取任务失败");
      }

      await pollCrawlJob(jobId);
      await finishCrawlAllJob();
    } catch (e) {
      clearActiveCrawlAllJob();
      setError(e instanceof Error ? e.message : "恢复全量抓取任务失败");
      setCrawling(false);
    } finally {
      pollingJobId.current = "";
    }
  }, [finishCrawlAllJob, pollCrawlJob]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const jobId = getActiveCrawlAllJob();
      if (jobId) void resumeCrawlAllJob(jobId);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [resumeCrawlAllJob]);

  const handleCrawlAll = async () => {
    setCrawling(true);
    setError("");
    try {
      const started = await api.startCrawlAll();
      setActiveCrawlAllJob(started.job_id);
      setCrawlJob(started.job);
      await pollCrawlJob(started.job_id);
      await finishCrawlAllJob();
    } catch (e) {
      clearActiveCrawlAllJob();
      setError(e instanceof Error ? e.message : "抓取失败");
    } finally {
      setCrawling(false);
    }
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
      {/* Hero 区域 */}
      <header className="glass-card flex flex-col lg:flex-row gap-6">
        <div className="flex-1 min-w-0">
          <p className="section-kicker">AI 竞品雷达</p>
          <h1 className="font-[family-name:var(--font-display)] text-5xl lg:text-7xl font-bold leading-[0.95] m-0">
            RivalSense
          </h1>
          <p className="text-lg text-[var(--color-text-muted)] mt-4 mb-6 max-w-xl leading-relaxed">
            自动追踪竞品动态、用户评价与融资信息，生成结构化简报与威胁等级判断。
          </p>

          <div className="flex items-center gap-3 flex-wrap">
            <button onClick={handleCrawlAll} disabled={crawling} className="btn-primary">
              {crawling ? (
                <>
                  <span className="pulse-loader" style={{ background: "white" }} />
                  抓取分析中...
                </>
              ) : (
                "🔄 立即抓取全部竞品"
              )}
            </button>
            <Link href="/competitors" className="btn-secondary no-underline">
              ➕ 添加竞品
            </Link>
          </div>

          {error && (
            <p className="mt-3 text-sm text-[var(--color-danger)]">{error}</p>
          )}

          {crawling && crawlJob && (
            <div className="mt-4 max-w-xl rounded-xl bg-white/55 p-3 border border-[rgba(77,41,14,0.08)]">
              <div className="flex items-center justify-between gap-3 text-xs text-[var(--color-text-muted)] mb-2">
                <span className="truncate">{crawlJob.message || "后台任务执行中"}</span>
                <span className="font-bold text-[var(--color-text-primary)]">{crawlJob.progress}%</span>
              </div>
              <div className="h-2 rounded-full bg-white/70 overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--color-brand-brown)] transition-all duration-500"
                  style={{ width: `${Math.max(crawlJob.progress, 3)}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2 mt-5">
            <span className="pill-tag">发布日志</span>
            <span className="pill-tag">融资动态</span>
            <span className="pill-tag">用户评价</span>
            <span className="pill-tag">威胁分级</span>
          </div>
        </div>

        {/* 统计面板 */}
        <div className="grid gap-4 w-full lg:w-72 shrink-0">
          <div className="stat-card">
            <span className="stat-label">竞品覆盖数</span>
            <span className="stat-value">{data?.stats.total_competitors ?? 0}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">高威胁事件</span>
            <span className="stat-value text-[var(--color-danger)]">
              {data?.stats.high_threats ?? 0}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">今日信号</span>
            <span className="stat-value">{data?.stats.total_signals ?? 0}</span>
          </div>
        </div>
      </header>

      {/* 今日简报 */}
      {data?.brief && (
        <section className="glass-card">
          <p className="section-kicker">Daily Brief</p>
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-bold m-0 mb-4">
            今日简报
          </h2>
          <div className="glass-card-strong mb-4">
            <p className="text-base font-medium m-0">
              {data.brief.brief_content?.headline || "暂无简报"}
            </p>
          </div>
          {data.brief.recommendations && data.brief.recommendations.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-[var(--color-text-muted)]">行动建议</h3>
              <ul className="space-y-1.5 list-none p-0 m-0">
                {data.brief.recommendations.map((rec, i) => (
                  <li key={i} className="text-sm leading-relaxed text-[var(--color-text-muted)]">
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* 竞品威胁总览（PRD §7: Dashboard 首页 — 竞品威胁总览卡片）*/}
      <section>
        <p className="section-kicker">Threat Overview</p>
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-bold m-0 mb-4">
          竞品威胁总览
        </h2>

        {data?.competitors && data.competitors.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.competitors.map((comp) => (
              <CompetitorCard key={comp.id} comp={comp} />
            ))}
          </div>
        ) : (
          <div className="glass-card-strong text-center py-12">
            <p className="text-[var(--color-text-muted)] text-lg mb-4">
              还没有添加竞品
            </p>
            <a href="/competitors" className="btn-primary no-underline">
              ➕ 添加你的第一个竞品
            </a>
          </div>
        )}
      </section>
    </div>
  );
}
