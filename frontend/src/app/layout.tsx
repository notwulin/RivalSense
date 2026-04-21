import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "RivalSense · AI 竞品雷达",
  description: "输入你的产品方向，自动持续追踪竞品动态，生成结构化简报与威胁等级判断。",
};

const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        {/* 导航栏 */}
        <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-[rgba(255,250,244,0.72)] border-b border-[rgba(77,41,14,0.08)]">
          <div className="max-w-[1280px] mx-auto px-6 h-14 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 no-underline">
              <span className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--color-text-primary)]">
                RivalSense
              </span>
              <span className="pill-tag text-[11px]">AI 竞品雷达</span>
              {demoMode && <span className="pill-tag text-[11px]">Demo Mode</span>}
            </Link>
            <div className="flex items-center gap-1">
              <Link href="/" className="px-3 py-1.5 rounded-xl text-sm text-[var(--color-text-muted)] hover:bg-white/50 transition-colors no-underline">
                Dashboard
              </Link>
              <Link href="/competitors" className="px-3 py-1.5 rounded-xl text-sm text-[var(--color-text-muted)] hover:bg-white/50 transition-colors no-underline">
                竞品管理
              </Link>
              <Link href="/reports" className="px-3 py-1.5 rounded-xl text-sm text-[var(--color-text-muted)] hover:bg-white/50 transition-colors no-underline">
                报告中心
              </Link>
            </div>
          </div>
        </nav>

        {demoMode && (
          <div className="fixed top-14 left-0 right-0 z-40 bg-amber-100/90 border-b border-amber-200 text-amber-900 text-xs">
            <div className="max-w-[1280px] mx-auto px-6 py-2">
              Demo Mode：当前公网作品集预览使用内置样例数据与模拟抓取进度，不依赖后端服务或真实 API Key。
            </div>
          </div>
        )}

        {/* 主内容 */}
        <main className={`w-full min-w-0 max-w-[1280px] mx-auto overflow-x-hidden px-6 ${demoMode ? "pt-28" : "pt-20"} pb-12`}>
          {children}
        </main>
      </body>
    </html>
  );
}
