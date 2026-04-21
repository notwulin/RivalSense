import type {
  Analytics,
  Brief,
  Competitor,
  CrawlAllResult,
  CrawlJob,
  CrawlResult,
  Report,
} from "./api";

const STATE_KEY = "rivalsense.demo.state";
const JOBS_KEY = "rivalsense.demo.jobs";
const JOB_DURATION_MS = 5200;

type DemoState = {
  competitors: Competitor[];
  reports: Report[];
  briefs: Brief[];
};

type StoredJob = CrawlJob & {
  created_ts: number;
};

type DemoJobs = Record<string, StoredJob>;

function nowIso() {
  return new Date().toISOString();
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function getStorage() {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function makeAnalytics(seed: "intercom" | "zendesk" | "gorgias"): Analytics {
  const variants = {
    intercom: {
      total: 186,
      sources: { reddit_comment: 62, search_result: 44, github_issue: 28, g2_review: 26, rss: 18, cn_media_search: 8 },
      sentiment: { negative: 96, neutral: 61, positive: 29 },
      clusters: [
        {
          cluster_label: "价格与订阅成本",
          count: 34,
          keywords: ["pricing problem", "seat billing", "overpriced", "startup cost"],
          sample_quote: "The pricing looks fine until every teammate and automation rule starts counting toward the bill.",
        },
        {
          cluster_label: "易用性与界面复杂度",
          count: 26,
          keywords: ["confusing inbox", "workflow setup", "admin panel", "routing"],
          sample_quote: "We needed three people to understand why one customer conversation was routed to the wrong team.",
        },
      ],
      signals: [
        {
          type: "product_launch",
          label: "🟢 产品发布",
          trigger_keyword: "AI agent",
          title: "Intercom expands Fin AI workflow coverage for support teams",
          source: "rss",
        },
      ],
    },
    zendesk: {
      total: 154,
      sources: { g2_review: 42, reddit: 34, search_news: 27, stackoverflow: 19, v2ex_search: 18, rss: 14 },
      sentiment: { negative: 73, neutral: 57, positive: 24 },
      clusters: [
        {
          cluster_label: "功能缺口与集成",
          count: 29,
          keywords: ["integration problem", "api limits", "missing export", "automation"],
          sample_quote: "The integration works for standard tickets, but our custom objects keep breaking during sync.",
        },
        {
          cluster_label: "客服与退款",
          count: 18,
          keywords: ["support response", "ticket loop", "refund", "account manager"],
          sample_quote: "Support kept sending us back to documentation even though the issue was clearly account-specific.",
        },
      ],
      signals: [
        {
          type: "pricing_change",
          label: "🟡 定价变动",
          trigger_keyword: "enterprise plan",
          title: "Zendesk highlights enterprise AI suite packaging",
          source: "search_news",
        },
      ],
    },
    gorgias: {
      total: 132,
      sources: { reddit_comment: 38, appstore_review: 31, search_result: 29, g2_review: 22, xiaohongshu_search: 12 },
      sentiment: { negative: 68, neutral: 43, positive: 21 },
      clusters: [
        {
          cluster_label: "性能与响应速度",
          count: 24,
          keywords: ["slow performance", "macro delay", "shopify sync", "latency"],
          sample_quote: "During sale days the Shopify sync delay makes agents answer with outdated order information.",
        },
        {
          cluster_label: "账号与登录",
          count: 15,
          keywords: ["login problem", "permission", "role access", "session"],
          sample_quote: "Agent permissions are hard to reason about and we keep over-granting access to avoid blockers.",
        },
      ],
      signals: [
        {
          type: "product_launch",
          label: "🟢 产品发布",
          trigger_keyword: "automation",
          title: "Gorgias promotes automation features for ecommerce service teams",
          source: "rss",
        },
      ],
    },
  }[seed];

  const total = variants.total;
  const { negative, neutral, positive } = variants.sentiment;
  const sourceDistribution = Object.fromEntries(
    Object.entries(variants.sources).filter((entry): entry is [string, number] => (
      typeof entry[1] === "number"
    ))
  );
  return {
    total_records: total,
    source_distribution: sourceDistribution,
    sentiment_distribution: variants.sentiment,
    sentiment_percentages: {
      negative: Math.round((negative / total) * 1000) / 10,
      neutral: Math.round((neutral / total) * 1000) / 10,
      positive: Math.round((positive / total) * 1000) / 10,
    },
    avg_negative_score: -0.48,
    pain_clusters: variants.clusters,
    business_signals: variants.signals,
    top_negative_quotes: variants.clusters.map((cluster, index) => ({
      content: cluster.sample_quote,
      source: index === 0 ? "reddit_comment" : "g2_review",
      score: index === 0 ? -0.72 : -0.58,
    })),
  };
}

function makeReport(
  competitorId: string,
  competitorName: string,
  seed: "intercom" | "zendesk" | "gorgias",
  overrides: Partial<Report> = {}
): Report {
  const analytics = makeAnalytics(seed);
  const topCluster = analytics.pain_clusters[0];
  return {
    id: `demo_rpt_${competitorId}_${Date.now()}`,
    competitor_id: competitorId,
    competitor_name: competitorName,
    report_date: today(),
    summary: `${competitorName} 的公开反馈集中在「${topCluster.cluster_label}」，同时近期出现 ${analytics.business_signals.length} 条值得跟踪的商业信号。`,
    user_pain_points: analytics.pain_clusters.map((cluster) => ({
      point: `${cluster.cluster_label}：${cluster.keywords.slice(0, 3).join("、")}`,
      source: Object.keys(analytics.source_distribution)[0] || "demo",
      frequency: `${cluster.count} 条`,
    })),
    threat_level: seed === "intercom" ? "high" : seed === "zendesk" ? "medium" : "medium",
    threat_reason: `${competitorName} 在 AI 客服自动化上持续推进，但用户对成本、集成和体验稳定性仍有明显抱怨。`,
    opportunity: `优先强调透明定价、快速集成和低配置成本，可针对 ${topCluster.keywords[0]} 打差异化。`,
    analytics,
    created_at: nowIso(),
    ...overrides,
  };
}

function initialState(): DemoState {
  const competitors: Competitor[] = [
    {
      id: "demo_intercom",
      name: "Intercom",
      website_url: "https://www.intercom.com/blog/",
      rss_url: "",
      g2_url: "https://www.g2.com/products/intercom/reviews",
      appstore_url: "",
      focus_dimensions: ["功能更新", "用户评价", "融资动态"],
      created_at: "2026-04-19T09:00:00Z",
      updated_at: "2026-04-19T09:00:00Z",
    },
    {
      id: "demo_zendesk",
      name: "Zendesk",
      website_url: "https://www.zendesk.com/blog/",
      rss_url: "",
      g2_url: "https://www.g2.com/products/zendesk-support-suite/reviews",
      appstore_url: "",
      focus_dimensions: ["功能更新", "用户评价", "融资动态"],
      created_at: "2026-04-18T09:00:00Z",
      updated_at: "2026-04-18T09:00:00Z",
    },
    {
      id: "demo_gorgias",
      name: "Gorgias",
      website_url: "https://www.gorgias.com/blog",
      rss_url: "",
      g2_url: "https://www.g2.com/products/gorgias/reviews",
      appstore_url: "",
      focus_dimensions: ["功能更新", "用户评价", "融资动态"],
      created_at: "2026-04-17T09:00:00Z",
      updated_at: "2026-04-17T09:00:00Z",
    },
  ];

  const reports = [
    makeReport("demo_intercom", "Intercom", "intercom", { id: "demo_rpt_intercom" }),
    makeReport("demo_zendesk", "Zendesk", "zendesk", { id: "demo_rpt_zendesk" }),
    makeReport("demo_gorgias", "Gorgias", "gorgias", { id: "demo_rpt_gorgias" }),
  ];

  competitors.forEach((competitor) => {
    competitor.latest_report = reports.find((report) => report.competitor_id === competitor.id) || null;
  });

  return {
    competitors,
    reports,
    briefs: [
      {
        id: "demo_brief_today",
        brief_date: today(),
        brief_content: {
          headline: "Intercom 的 AI 自动化推进最积极，但定价和复杂配置正在成为可攻击窗口。",
          competitors: reports.map((report) => ({
            name: report.competitor_name || "竞品",
            threat_level: report.threat_level,
            summary: report.summary,
            threat_reason: report.threat_reason,
            opportunity: report.opportunity,
            pain_points_count: report.user_pain_points.length,
          })),
        },
        total_signals: reports.reduce((sum, report) => sum + (report.analytics?.business_signals.length || 0), 0),
        high_threats: reports.filter((report) => report.threat_level === "high").length,
        competitors_covered: competitors.length,
        recommendations: [
          "将「透明定价 + 快速上线」作为主打信息，直接回应竞品价格复杂的用户痛点。",
          "优先补齐 Shopify、Help Center、Slack 等高频集成模板，减少迁移阻力。",
          "在演示中突出低配置 AI Agent workflow，和 Intercom/Zendesk 的复杂管理台形成对比。",
        ],
      },
    ],
  };
}

function loadState(): DemoState {
  const storage = getStorage();
  if (!storage) return initialState();
  try {
    const raw = storage.getItem(STATE_KEY);
    if (raw) return JSON.parse(raw) as DemoState;
  } catch {
    // fall through
  }
  const seeded = initialState();
  storage.setItem(STATE_KEY, JSON.stringify(seeded));
  return seeded;
}

function saveState(state: DemoState) {
  const storage = getStorage();
  if (storage) storage.setItem(STATE_KEY, JSON.stringify(state));
}

function loadJobs(): DemoJobs {
  const storage = getStorage();
  if (!storage) return {};
  try {
    const raw = storage.getItem(JOBS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveJobs(jobs: DemoJobs) {
  const storage = getStorage();
  if (storage) storage.setItem(JOBS_KEY, JSON.stringify(jobs));
}

function seedForName(name: string): "intercom" | "zendesk" | "gorgias" {
  const lowered = name.toLowerCase();
  if (lowered.includes("zendesk")) return "zendesk";
  if (lowered.includes("gorgias")) return "gorgias";
  return "intercom";
}

function attachLatestReports(state: DemoState) {
  state.competitors.forEach((competitor) => {
    competitor.latest_report =
      state.reports.find((report) => report.competitor_id === competitor.id) || null;
  });
  return state;
}

function buildDashboard(state: DemoState) {
  const hydrated = attachLatestReports(state);
  const competitors = hydrated.competitors
    .map((competitor) => {
      const latest = competitor.latest_report;
      return {
        id: competitor.id,
        name: competitor.name,
        website_url: competitor.website_url,
        threat_level: latest?.threat_level || "low",
        summary: latest?.summary || "Demo 竞品已创建，点击抓取分析可生成模拟报告。",
        threat_reason: latest?.threat_reason || "",
        opportunity: latest?.opportunity || "",
        pain_points_count: latest?.user_pain_points.length || 0,
        last_analyzed: latest?.created_at || "",
      };
    })
    .sort((a, b) => ({ high: 0, medium: 1, low: 2 }[a.threat_level] - { high: 0, medium: 1, low: 2 }[b.threat_level]));

  const brief = hydrated.briefs[0] || null;
  return {
    competitors,
    brief,
    stats: {
      total_competitors: hydrated.competitors.length,
      high_threats: competitors.filter((competitor) => competitor.threat_level === "high").length,
      total_signals: brief?.total_signals || 0,
    },
  };
}

function createStoredJob(kind: CrawlJob["kind"], targetId = "", targetName = ""): StoredJob {
  const created = nowIso();
  return {
    id: `demo_job_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    kind,
    target_id: targetId,
    target_name: targetName,
    status: "queued",
    stage: "queued",
    progress: 0,
    message: "Demo Mode 正在模拟抓取公开情报",
    created_at: created,
    updated_at: created,
    started_at: "",
    completed_at: "",
    result: null,
    error: "",
    created_ts: Date.now(),
  };
}

function finishCompetitorJob(job: StoredJob): CrawlResult {
  const state = loadState();
  const competitor = state.competitors.find((item) => item.id === job.target_id);
  if (!competitor) throw new Error("Demo 竞品不存在");

  const report = makeReport(
    competitor.id,
    competitor.name,
    seedForName(competitor.name),
    { id: `demo_rpt_${competitor.id}_${job.id}` }
  );
  state.reports = [
    report,
    ...state.reports.filter((item) => item.id !== report.id && item.competitor_id !== competitor.id),
  ];
  saveState(attachLatestReports(state));

  return {
    crawled: report.analytics?.total_records || 0,
    errors: [],
    report,
    analytics: report.analytics as Analytics,
  };
}

function finishCrawlAllJob(job: StoredJob): CrawlAllResult {
  const state = loadState();
  const reports = state.competitors.map((competitor) =>
    makeReport(competitor.id, competitor.name, seedForName(competitor.name), {
      id: `demo_rpt_${competitor.id}_${job.id}`,
    })
  );
  state.reports = reports;
  attachLatestReports(state);
  state.briefs = [
    {
      ...initialState().briefs[0],
      id: `demo_brief_${job.id}`,
      brief_date: today(),
      competitors_covered: state.competitors.length,
      high_threats: reports.filter((report) => report.threat_level === "high").length,
      total_signals: reports.reduce((sum, report) => sum + (report.analytics?.business_signals.length || 0), 0),
    },
    ...state.briefs.filter((brief) => brief.id !== "demo_brief_today"),
  ];
  saveState(state);

  return {
    results: reports.map((report) => ({
      competitor: report.competitor_name || "竞品",
      crawled: report.analytics?.total_records || 0,
      threat_level: report.threat_level,
      errors: [],
    })),
    brief: state.briefs[0],
    competitors_processed: state.competitors.length,
  };
}

function hydrateJob(job: StoredJob): CrawlJob {
  const elapsed = Date.now() - job.created_ts;
  const progress = Math.min(100, Math.floor((elapsed / JOB_DURATION_MS) * 100));
  if (progress < 100) {
    return {
      ...job,
      status: progress < 12 ? "queued" : "running",
      stage: progress < 45 ? "crawl" : progress < 78 ? "analyze" : "persist_report",
      progress,
      message:
        progress < 45
          ? "Demo Mode 正在模拟多来源抓取"
          : progress < 78
          ? "Demo Mode 正在模拟 NLP 聚类和去噪"
          : "Demo Mode 正在生成展示报告",
      started_at: job.started_at || job.created_at,
      updated_at: nowIso(),
    };
  }

  if (!job.result) {
    job.result = job.kind === "crawl_all" ? finishCrawlAllJob(job) : finishCompetitorJob(job);
  }
  job.status = "completed";
  job.stage = "completed";
  job.progress = 100;
  job.message = "Demo Mode 模拟抓取完成";
  job.completed_at = job.completed_at || nowIso();
  job.updated_at = nowIso();

  const jobs = loadJobs();
  jobs[job.id] = job;
  saveJobs(jobs);
  return job;
}

export const demoApi = {
  health: async () => ({ status: "ok" }),

  dashboard: async () => buildDashboard(loadState()),

  listCompetitors: async () => {
    const state = attachLatestReports(loadState());
    return { competitors: state.competitors, count: state.competitors.length };
  },

  getCompetitor: async (id: string) => {
    const state = attachLatestReports(loadState());
    const competitor = state.competitors.find((item) => item.id === id);
    if (!competitor) throw new Error("Demo 竞品不存在");
    return { competitor };
  },

  createCompetitor: async (data: Partial<Competitor>) => {
    const state = loadState();
    const name = (data.name || "").trim();
    if (!name) throw new Error("竞品名称不能为空");
    if (state.competitors.length >= 5) throw new Error("Demo Mode 最多展示 5 个竞品");

    const competitor: Competitor = {
      id: `demo_comp_${Date.now()}`,
      name,
      website_url: data.website_url || "",
      rss_url: data.rss_url || "",
      g2_url: data.g2_url || "",
      appstore_url: data.appstore_url || "",
      focus_dimensions: data.focus_dimensions || ["功能更新", "用户评价", "融资动态"],
      created_at: nowIso(),
      updated_at: nowIso(),
      latest_report: null,
    };
    state.competitors = [competitor, ...state.competitors];
    saveState(state);
    return { competitor };
  },

  updateCompetitor: async (id: string, data: Partial<Competitor>) => {
    const state = loadState();
    const competitor = state.competitors.find((item) => item.id === id);
    if (!competitor) throw new Error("Demo 竞品不存在");
    Object.assign(competitor, data, { updated_at: nowIso() });
    saveState(attachLatestReports(state));
    return { competitor };
  },

  deleteCompetitor: async (id: string) => {
    const state = loadState();
    state.competitors = state.competitors.filter((competitor) => competitor.id !== id);
    state.reports = state.reports.filter((report) => report.competitor_id !== id);
    saveState(state);
    return { deleted: true };
  },

  crawlCompetitor: async (id: string) => {
    const state = loadState();
    const competitor = state.competitors.find((item) => item.id === id);
    if (!competitor) throw new Error("Demo 竞品不存在");
    return finishCompetitorJob(createStoredJob("competitor_crawl", competitor.id, competitor.name));
  },

  startCrawlCompetitor: async (id: string) => {
    const state = loadState();
    const competitor = state.competitors.find((item) => item.id === id);
    if (!competitor) throw new Error("Demo 竞品不存在");
    const job = createStoredJob("competitor_crawl", competitor.id, competitor.name);
    const jobs = loadJobs();
    jobs[job.id] = job;
    saveJobs(jobs);
    return { job_id: job.id, job };
  },

  getCrawlJob: async (jobId: string) => {
    const jobs = loadJobs();
    const job = jobs[jobId];
    if (!job) throw new Error("Demo 任务不存在或已过期");
    return { job: hydrateJob(job) };
  },

  crawlAll: async () => finishCrawlAllJob(createStoredJob("crawl_all", "", "Demo competitors")),

  startCrawlAll: async () => {
    const job = createStoredJob("crawl_all", "", "Demo competitors");
    const jobs = loadJobs();
    jobs[job.id] = job;
    saveJobs(jobs);
    return { job_id: job.id, job };
  },

  listReports: async (competitorId?: string) => {
    const state = loadState();
    const reports = competitorId
      ? state.reports.filter((report) => report.competitor_id === competitorId)
      : state.reports;
    return { reports };
  },

  latestReport: async (competitorId: string) => {
    const report = loadState().reports.find((item) => item.competitor_id === competitorId);
    if (!report) throw new Error("暂无 Demo 报告");
    return { report };
  },

  deleteReport: async (reportId: string) => {
    const state = loadState();
    state.reports = state.reports.filter((report) => report.id !== reportId);
    saveState(attachLatestReports(state));
    return { deleted: true, id: reportId };
  },

  exportReport: async (competitorId: string) => {
    const report = loadState().reports.find((item) => item.competitor_id === competitorId);
    if (!report) throw new Error("暂无 Demo 报告");
    return {
      markdown: [
        `# RivalSense Demo 竞品分析报告 · ${report.competitor_name || "竞品"}`,
        "",
        `- 分析日期：${report.report_date}`,
        `- 威胁等级：${report.threat_level}`,
        "",
        "## 摘要",
        report.summary,
        "",
        "## 用户痛点",
        ...report.user_pain_points.map((point) => `- ${point.point}（来源：${point.source}，频率：${point.frequency}）`),
        "",
        "## 产品机会",
        report.opportunity,
      ].join("\n"),
    };
  },

  listBriefs: async () => ({ briefs: loadState().briefs }),

  latestBrief: async () => {
    const brief = loadState().briefs[0];
    if (!brief) throw new Error("暂无 Demo 简报");
    return { brief };
  },

  deleteBrief: async (briefId: string) => {
    const state = loadState();
    state.briefs = state.briefs.filter((brief) => brief.id !== briefId);
    saveState(state);
    return { deleted: true, id: briefId };
  },
};
