from .celery import app as celery_app

# Для CLI: celery -A magnat_trade_project worker|beat
app = celery_app

__all__ = ("celery_app", "app")
