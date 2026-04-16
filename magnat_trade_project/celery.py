import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "magnat_trade_project.settings")

app = Celery("magnat_trade")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
