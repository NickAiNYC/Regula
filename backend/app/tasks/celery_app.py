"""
Regula Health - Celery Task Queue Configuration
Background processing for EDI files, reports, and notifications
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "regula",
    broker=(
        str(settings.CELERY_BROKER_URL)
        if settings.CELERY_BROKER_URL
        else "redis://localhost:6379/0"
    ),
    backend=(
        str(settings.CELERY_RESULT_BACKEND)
        if settings.CELERY_RESULT_BACKEND
        else "redis://localhost:6379/1"
    ),
    include=["app.tasks.edi_processing", "app.tasks.report_generation"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/New_York",
    enable_utc=True,
    # Performance settings
    task_acks_late=True,  # Acknowledge tasks after completion
    worker_prefetch_multiplier=4,  # Number of tasks to prefetch
    worker_max_tasks_per_child=1000,  # Restart worker after N tasks
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={"master_name": "mymaster"},
    # Priority queues
    task_routes={
        "app.tasks.edi_processing.*": {"queue": "processing"},
        "app.tasks.report_generation.*": {"queue": "reports"},
        "app.tasks.notifications.*": {"queue": "high_priority"},
    },
    # Monitoring
    task_track_started=True,
    task_send_sent_event=True,
)

# Periodic tasks (scheduled jobs)
celery_app.conf.beat_schedule = {
    # Daily rate database sync
    "sync-rate-database": {
        "task": "app.tasks.maintenance.sync_rate_database",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
    },
    # Weekly compliance report
    "generate-weekly-report": {
        "task": "app.tasks.report_generation.generate_weekly_report",
        "schedule": crontab(day_of_week=1, hour=8, minute=0),  # Monday 8 AM
    },
}
