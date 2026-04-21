"""
In-process background job manager for long crawl requests.

This is intentionally small and dependency-free for the MVP. For multi-process
production deployments, move this contract to Redis/RQ, Celery, or a managed
queue while keeping the API shape stable.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import logging
import threading
import time
import uuid

from models.database import get_competitor, list_competitors
from services.crawl_runner import (
    run_all_crawls_pipeline,
    run_competitor_crawl_pipeline,
)

logger = logging.getLogger(__name__)

MAX_WORKERS = 2
MAX_JOBS = 100
JOB_RETENTION_SECONDS = 24 * 60 * 60

_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="crawl-job")
_jobs = {}
_lock = threading.Lock()


def _now():
    return datetime.utcnow().isoformat() + "Z"


def _gen_job_id():
    return "job_" + uuid.uuid4().hex[:12]


@dataclass
class CrawlJob:
    id: str
    kind: str
    target_id: str = ""
    target_name: str = ""
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    message: str = "等待调度"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    started_at: str = ""
    completed_at: str = ""
    result: object = None
    error: str = ""
    created_ts: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


def _prune_jobs():
    cutoff = time.time() - JOB_RETENTION_SECONDS
    with _lock:
        stale_ids = [
            job_id
            for job_id, job in _jobs.items()
            if job.created_ts < cutoff and job.status in ("completed", "failed")
        ]
        for job_id in stale_ids:
            _jobs.pop(job_id, None)

        if len(_jobs) <= MAX_JOBS:
            return

        completed = sorted(
            (
                (job.created_ts, job_id)
                for job_id, job in _jobs.items()
                if job.status in ("completed", "failed")
            ),
            key=lambda item: item[0],
        )
        for _, job_id in completed[: max(0, len(_jobs) - MAX_JOBS)]:
            _jobs.pop(job_id, None)


def _register_job(job):
    _prune_jobs()
    with _lock:
        _jobs[job.id] = job
    return job


def _update_job(job_id, **updates):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = _now()
        return job.to_dict()


def _progress_updater(job_id):
    def update(stage, progress, message):
        _update_job(
            job_id,
            status="running",
            stage=stage,
            progress=max(0, min(100, int(progress))),
            message=message,
        )

    return update


def _run_guarded(job_id, runner):
    _update_job(
        job_id,
        status="running",
        stage="starting",
        progress=1,
        message="任务已开始",
        started_at=_now(),
    )
    try:
        result = runner(_progress_updater(job_id))
        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message="任务完成",
            completed_at=_now(),
            result=result,
            error="",
        )
    except Exception as exc:
        logger.exception("后台抓取任务失败: %s", job_id)
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            progress=100,
            message="任务失败",
            completed_at=_now(),
            error=str(exc),
        )


def submit_competitor_crawl_job(competitor):
    job = CrawlJob(
        id=_gen_job_id(),
        kind="competitor_crawl",
        target_id=competitor["id"],
        target_name=competitor.get("name", ""),
    )
    _register_job(job)

    def runner(progress_callback):
        latest_competitor = get_competitor(competitor["id"])
        if not latest_competitor:
            raise ValueError("竞品不存在")
        return run_competitor_crawl_pipeline(latest_competitor, progress_callback)

    _executor.submit(_run_guarded, job.id, runner)
    return job.to_dict()


def submit_crawl_all_job():
    competitors = list_competitors()
    if not competitors:
        raise ValueError("请先添加竞品")

    job = CrawlJob(
        id=_gen_job_id(),
        kind="crawl_all",
        target_name=f"{len(competitors)} competitors",
    )
    _register_job(job)
    _executor.submit(_run_guarded, job.id, run_all_crawls_pipeline)
    return job.to_dict()


def get_job(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return job.to_dict() if job else None


def list_jobs(limit=20):
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda job: job.created_ts, reverse=True)
        return [job.to_dict() for job in jobs[:limit]]
