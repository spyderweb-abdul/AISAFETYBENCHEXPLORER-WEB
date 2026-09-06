"""
app/core/celery_app.py

Celery application factory and Beat schedule for Phase 4 scraper jobs
and the Phase 6 citation refresh job.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "aisafetybenchexplorer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.core.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "refresh-all-repo-stats-weekly": {
        "task": "app.core.tasks.refresh_all_repo_stats",
        "schedule": crontab(day_of_week="sunday", hour=3, minute=0),
    },
    "refresh-all-citations-weekly": {
        "task": "app.core.tasks.refresh_all_citation_counts",
        "schedule": crontab(day_of_week="sunday", hour=4, minute=0),
    },
}
