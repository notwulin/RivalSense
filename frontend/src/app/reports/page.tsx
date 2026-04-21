"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { Report, Brief } from "@/lib/api";

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

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [briefs, setBriefs] = useState<Brief[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"reports" | "briefs">("reports");
  const [exporting, setExporting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [exportedReportId, setExportedReportId] = useState<string | null>(null);
  const [exportedMdByReport, setExportedMdByReport] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [reportsRes, briefsRes] = await Promise.all([
        api.listReports(),
        api.listBriefs(),
      ]);
      setReports(reportsRes.reports);
      setBriefs(briefsRes.briefs);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchData();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [fetchData]);

  const handleExport = async (report: Report) => {
    setExporting(report.id);
    setError("");
    try {
      const res = await api.exportReport(report.competitor_id);
      setExportedMdByReport((prev) => ({ ...prev, [report.id]: res.markdown }));
      setExportedReportId(report.id);
      await navigator.clipboard.writeText(res.markdown).catch(() => undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出报告失败");
    } finally {
      setExporting(null);
    }
  };

  const handleDeleteReport = async (reportId: string) => {
    if (!confirm("确定要删除这份报告吗？此操作不可恢复。")) return;
    setDeleting(reportId);
    setError("");
    try {
      await api.deleteReport(reportId);
      setReports((prev) => prev.filter((report) => report.id !== reportId));
      setExportedMdByReport((prev) => {
        const next = { ...prev };
        delete next[reportId];
        return next;
      });
      setExportedReportId((current) => (current === reportId ? null : current));
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除报告失败");
    } finally {
      setDeleting(null);
    }
  };

  const handleDeleteBrief = async (briefId: string) => {
    if (!confirm("确定要删除这条每日简报吗？此操作不可恢复。")) return;
    setDeleting(briefId);
    setError("");
    try {
      await api.deleteBrief(briefId);
      setBriefs((prev) => prev.filter((brief) => brief.id !== briefId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除简报失败");
    } finally {
      setDeleting(null);
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
    <div className="space-y-6 min-w-0 max-w-full">
      <header className="min-w-0">
        <p className="section-kicker">Report Center</p>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold m-0">
          报告中心
        </h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          查看历史报告与每日简报（PRD US-07/08/09）
        </p>
      </header>

      {error && (
        <div className="glass-card-strong text-[var(--color-danger)] text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* Tab 切换 */}
      <div className="flex gap-2">
        <button
          onClick={() => { setActiveTab("reports"); setExportedReportId(null); }}
          className={activeTab === "reports" ? "btn-primary" : "btn-secondary"}
        >
          📊 竞品报告（{reports.length}）
        </button>
        <button
          onClick={() => { setActiveTab("briefs"); setExportedReportId(null); }}
          className={activeTab === "briefs" ? "btn-primary" : "btn-secondary"}
        >
          📰 每日简报（{briefs.length}）
        </button>
      </div>

      {/* 竞品报告列表 */}
      {activeTab === "reports" && (
        <div className="space-y-4 min-w-0 max-w-full">
          {reports.length > 0 ? (
            reports.map((report) => (
              <article key={report.id} className="glass-card-strong fade-in min-w-0 max-w-full">
                <div className="flex items-start justify-between gap-3 flex-wrap min-w-0 max-w-full">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3 mb-2 min-w-0 flex-wrap">
                      <h3 className="font-[family-name:var(--font-display)] text-lg font-bold m-0 break-words">
                        {report.competitor_name || "竞品"}
                      </h3>
                      <ThreatBadge level={report.threat_level} />
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {report.report_date}
                      </span>
                    </div>
                    <p className="text-sm text-[var(--color-text-muted)] leading-relaxed mb-2 break-words" style={{ overflowWrap: "anywhere" }}>
                      {report.summary}
                    </p>
                    {report.threat_reason && (
                      <p className="text-xs text-[var(--color-text-muted)] mb-2 break-words" style={{ overflowWrap: "anywhere" }}>
                        ⚡ {report.threat_reason}
                      </p>
                    )}

                    {/* 用户痛点（PRD 差异化核心）*/}
                    {report.user_pain_points && report.user_pain_points.length > 0 && (
                      <div className="mt-3 space-y-1.5">
                        <p className="text-xs font-semibold text-[var(--color-text-muted)]">用户痛点：</p>
                        {report.user_pain_points.map((pp, i) => (
                          <div key={i} className="flex items-start gap-2 text-xs text-[var(--color-text-muted)] min-w-0">
                            <span className="pill-tag text-[10px] shrink-0">{pp.source}</span>
                            <span className="min-w-0 break-words" style={{ overflowWrap: "anywhere" }}>{pp.point}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {report.opportunity && (
                      <p className="text-xs text-[var(--color-safe)] mt-2 break-words" style={{ overflowWrap: "anywhere" }}>
                        💡 {report.opportunity}
                      </p>
                    )}
                  </div>

                  <div className="flex gap-2 shrink-0 flex-wrap justify-end">
                    <button
                      onClick={() => handleExport(report)}
                      disabled={exporting === report.id || deleting === report.id}
                      className="btn-secondary text-sm"
                    >
                      {exporting === report.id ? "导出中..." : "📄 导出 MD"}
                    </button>
                    <button
                      onClick={() => handleDeleteReport(report.id)}
                      disabled={deleting === report.id}
                      className="btn-secondary text-sm text-[var(--color-danger)]"
                    >
                      {deleting === report.id ? "删除中..." : "删除"}
                    </button>
                  </div>
                </div>

                {exportedReportId === report.id && exportedMdByReport[report.id] && (
                  <div className="mt-4 pt-4 border-t border-[rgba(77,41,14,0.08)] fade-in min-w-0 max-w-full">
                    <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                      <h4 className="font-[family-name:var(--font-display)] text-base font-bold m-0 min-w-0 break-words">
                        📋 Markdown 已复制，可在此预览
                      </h4>
                      <button
                        onClick={() => setExportedReportId(null)}
                        className="btn-secondary text-sm"
                      >
                        收起
                      </button>
                    </div>
                    <div
                      className="markdown-preview text-xs bg-white/65 rounded-xl p-4 leading-relaxed max-h-80"
                    >
                      {exportedMdByReport[report.id]}
                    </div>
                  </div>
                )}
              </article>
            ))
          ) : (
            <div className="glass-card text-center py-12">
              <p className="text-[var(--color-text-muted)]">
                暂无报告。请先在竞品管理中添加竞品并触发抓取分析。
              </p>
            </div>
          )}
        </div>
      )}

      {/* 每日简报列表 */}
      {activeTab === "briefs" && (
        <div className="space-y-4">
          {briefs.length > 0 ? (
            briefs.map((brief) => (
              <article key={brief.id} className="glass-card-strong fade-in">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <h3 className="font-[family-name:var(--font-display)] text-lg font-bold m-0">
                    {brief.brief_date}
                  </h3>
                  <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                    <div className="flex gap-3">
                      <span>📊 {brief.total_signals} 信号</span>
                      <span className={brief.high_threats > 0 ? "text-[var(--color-danger)] font-bold" : ""}>
                        ⚠️ {brief.high_threats} 高威胁
                      </span>
                      <span>🏢 {brief.competitors_covered} 竞品</span>
                    </div>
                    <button
                      onClick={() => handleDeleteBrief(brief.id)}
                      disabled={deleting === brief.id}
                      className="btn-secondary text-sm text-[var(--color-danger)]"
                    >
                      {deleting === brief.id ? "删除中..." : "删除"}
                    </button>
                  </div>
                </div>

                <div className="glass-card-strong mb-3">
                  <p className="text-sm font-medium m-0">
                    {brief.brief_content?.headline || "无简报内容"}
                  </p>
                </div>

                {brief.recommendations && brief.recommendations.length > 0 && (
                  <ul className="space-y-1 list-none p-0 m-0">
                    {brief.recommendations.map((rec, i) => (
                      <li key={i} className="text-xs text-[var(--color-text-muted)] leading-relaxed">
                        {rec}
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            ))
          ) : (
            <div className="glass-card text-center py-12">
              <p className="text-[var(--color-text-muted)]">
                暂无简报。请触发一次“抓取全部竞品”来生成每日简报。
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
