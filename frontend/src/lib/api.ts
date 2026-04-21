/**
 * RivalSense API 客户端
 * 对接 Flask 后端
 */
import { demoApi } from "./demoApi";

const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:5001");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }

  return res.json();
}

// ── 类型定义 ──

export interface Competitor {
  id: string;
  name: string;
  website_url: string;
  rss_url: string;
  g2_url: string;
  appstore_url: string;
  focus_dimensions: string[];
  created_at: string;
  updated_at: string;
  latest_report?: Report | null;
}

export interface PainPoint {
  point: string;
  source: string;
  frequency: string;
}

export interface Report {
  id: string;
  competitor_id: string;
  competitor_name?: string;
  report_date: string;
  summary: string;
  user_pain_points: PainPoint[];
  threat_level: "high" | "medium" | "low";
  threat_reason: string;
  opportunity: string;
  analytics?: Analytics | null;
  created_at: string;
}

export interface Analytics {
  total_records: number;
  source_distribution: Record<string, number>;
  sentiment_distribution: { negative: number; neutral: number; positive: number };
  sentiment_percentages: { negative: number; neutral: number; positive: number };
  avg_negative_score: number;
  pain_clusters: Array<{
    cluster_label: string;
    count: number;
    keywords: string[];
    sample_quote: string;
  }>;
  business_signals: Array<{
    type: string;
    label: string;
    trigger_keyword: string;
    title: string;
    source: string;
  }>;
  top_negative_quotes: Array<{
    content: string;
    source: string;
    score: number;
  }>;
}

export interface CrawlResult {
  crawled: number;
  errors: string[];
  report: Report;
  analytics: Analytics;
}

export interface CrawlAllResult {
  results: Array<{
    competitor: string;
    crawled: number;
    threat_level: "high" | "medium" | "low";
    errors: string[];
  }>;
  brief: Brief;
  competitors_processed: number;
}

export interface CrawlJob {
  id: string;
  kind: "competitor_crawl" | "crawl_all";
  target_id: string;
  target_name: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  started_at: string;
  completed_at: string;
  result?: CrawlResult | CrawlAllResult | null;
  error?: string;
}

export interface DashboardCompetitor {
  id: string;
  name: string;
  website_url: string;
  threat_level: "high" | "medium" | "low";
  summary: string;
  threat_reason: string;
  opportunity: string;
  pain_points_count: number;
  last_analyzed: string;
}

export interface Brief {
  id: string;
  brief_date: string;
  brief_content: {
    headline: string;
    competitors: Array<{
      name: string;
      threat_level: string;
      summary: string;
      threat_reason: string;
      opportunity: string;
      pain_points_count: number;
    }>;
  };
  total_signals: number;
  high_threats: number;
  competitors_covered: number;
  recommendations: string[];
}

export interface DashboardData {
  competitors: DashboardCompetitor[];
  brief: Brief | null;
  stats: {
    total_competitors: number;
    high_threats: number;
    total_signals: number;
  };
}

// ── API 方法 ──

const realApi = {
  // 健康检查
  health: () => request<{ status: string }>("/api/health"),

  // Dashboard
  dashboard: () => request<DashboardData>("/api/dashboard"),

  // 竞品 CRUD
  listCompetitors: () =>
    request<{ competitors: Competitor[]; count: number }>("/api/competitors"),

  getCompetitor: (id: string) =>
    request<{ competitor: Competitor }>(`/api/competitors/${id}`),

  createCompetitor: (data: Partial<Competitor>) =>
    request<{ competitor: Competitor }>("/api/competitors", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateCompetitor: (id: string, data: Partial<Competitor>) =>
    request<{ competitor: Competitor }>(`/api/competitors/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteCompetitor: (id: string) =>
    request<{ deleted: boolean }>(`/api/competitors/${id}`, {
      method: "DELETE",
    }),

  // 抓取 & 分析
  crawlCompetitor: (id: string) =>
    request<CrawlResult>(`/api/competitors/${id}/crawl`, {
      method: "POST",
    }),

  startCrawlCompetitor: (id: string) =>
    request<{ job_id: string; job: CrawlJob }>(`/api/competitors/${id}/crawl-jobs`, {
      method: "POST",
    }),

  getCrawlJob: (jobId: string) =>
    request<{ job: CrawlJob }>(`/api/crawl-jobs/${jobId}`),

  crawlAll: () =>
    request<CrawlAllResult>("/api/crawl-all", {
      method: "POST",
    }),

  startCrawlAll: () =>
    request<{ job_id: string; job: CrawlJob }>("/api/crawl-all-jobs", {
      method: "POST",
    }),

  // 报告
  listReports: (competitorId?: string) =>
    request<{ reports: Report[] }>(
      `/api/reports${competitorId ? `?competitor_id=${competitorId}` : ""}`
    ),

  latestReport: (competitorId: string) =>
    request<{ report: Report }>(`/api/reports/${competitorId}/latest`),

  deleteReport: (reportId: string) =>
    request<{ deleted: boolean; id: string }>(`/api/reports/${reportId}`, {
      method: "DELETE",
    }),

  exportReport: (competitorId: string) =>
    request<{ markdown: string }>(`/api/reports/${competitorId}/export`, {
      method: "POST",
    }),

  // 简报
  listBriefs: () => request<{ briefs: Brief[] }>("/api/briefs"),
  latestBrief: () => request<{ brief: Brief }>("/api/briefs/latest"),
  deleteBrief: (briefId: string) =>
    request<{ deleted: boolean; id: string }>(`/api/briefs/${briefId}`, {
      method: "DELETE",
    }),
};

export const api = DEMO_MODE ? demoApi : realApi;
