const COMPETITOR_JOBS_KEY = "rivalsense.activeCompetitorCrawlJobs";
const CRAWL_ALL_JOB_KEY = "rivalsense.activeCrawlAllJob";

function getStorage() {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function getActiveCompetitorCrawlJobs(): Record<string, string> {
  const storage = getStorage();
  if (!storage) return {};
  try {
    const raw = storage.getItem(COMPETITOR_JOBS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function setActiveCompetitorCrawlJob(competitorId: string, jobId: string) {
  const storage = getStorage();
  if (!storage) return;
  const jobs = getActiveCompetitorCrawlJobs();
  jobs[competitorId] = jobId;
  storage.setItem(COMPETITOR_JOBS_KEY, JSON.stringify(jobs));
}

export function clearActiveCompetitorCrawlJob(competitorId: string) {
  const storage = getStorage();
  if (!storage) return;
  const jobs = getActiveCompetitorCrawlJobs();
  delete jobs[competitorId];
  storage.setItem(COMPETITOR_JOBS_KEY, JSON.stringify(jobs));
}

export function getActiveCrawlAllJob() {
  const storage = getStorage();
  if (!storage) return "";
  return storage.getItem(CRAWL_ALL_JOB_KEY) || "";
}

export function setActiveCrawlAllJob(jobId: string) {
  const storage = getStorage();
  if (!storage) return;
  storage.setItem(CRAWL_ALL_JOB_KEY, jobId);
}

export function clearActiveCrawlAllJob() {
  const storage = getStorage();
  if (!storage) return;
  storage.removeItem(CRAWL_ALL_JOB_KEY);
}
