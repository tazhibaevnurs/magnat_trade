import logging
import socket
from urllib.parse import urlparse

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _celery_broker_reachable() -> bool:
    broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
    if not broker_url:
        return False

    parsed = urlparse(broker_url)
    if parsed.scheme != "redis":
        return True

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def queue_export_order_to_onec(order_id: str, request_id: str | None = None) -> str | None:
    """
    Безопасно поставить выгрузку заказа в очередь Celery.
    Не выбрасывает исключения наружу, чтобы не ломать checkout при временной
    недоступности брокера/результат-бэкенда.
    """
    if not _celery_broker_reachable():
        logger.warning("Celery broker is unavailable. Skip queueing order export %s", order_id)
        return None

    try:
        task = export_order_to_onec.apply_async(
            args=(str(order_id),),
            kwargs={"request_id": request_id},
            ignore_result=True,
        )
        return getattr(task, "id", None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to queue export_order_to_onec for order %s: %s", order_id, exc)
        return None


@shared_task(bind=True, max_retries=5, default_retry_delay=60, ignore_result=True)
def export_order_to_onec(self, order_id: str, request_id: str | None = None) -> dict:
    from orders.services.order_export import OrderExportService
    from integrations.clients.onec import OneCAPIError

    try:
        return OrderExportService.export_to_onec(order_id, request_id=request_id)
    except OneCAPIError as exc:
        from orders.models import Order
        import uuid

        try:
            o = Order.objects.get(id=uuid.UUID(str(order_id)))
            o.last_export_error = str(exc)[:2000]
            o.save(update_fields=["last_export_error", "updated_at"])
        except Exception:  # noqa: BLE001
            pass
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def pull_counterparties_from_onec(self) -> dict:
    """Фоновая загрузка контрагентов из 1С (counterpartyList) в локальную БД."""
    from integrations.clients.onec import OneCAPIError, OneCClient
    from users.services import CustomerSyncService

    try:
        client = OneCClient()
        items = client.fetch_counterparty_list()
        return CustomerSyncService.sync_batch(items)
    except OneCAPIError as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def sync_products_from_onec(self) -> dict:
    """
    Периодическая синхронизация номенклатуры: GET productList; при пустом кэше — ещё categoryProductList.

    Расписание Celery Beat: каждые ``ONEC_BEAT_PRODUCT_SYNC_MINUTES`` (по умолчанию 5).
    """
    from integrations.clients.onec import OneCAPIError
    from integrations.services.onec_full_sync import run_product_list_sync_only

    if not getattr(settings, "ONEC_BEAT_SYNC_ENABLED", True):
        return {"skipped": True, "reason": "ONEC_BEAT_SYNC_ENABLED=false"}

    try:
        return run_product_list_sync_only()
    except OneCAPIError as exc:
        logger.warning("sync_products_from_onec failed: %s", exc)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=2, default_retry_delay=180)
def sync_all_from_onec(self) -> dict:
    """
    Полная синхронизация с 1С: GET categoryProductList, productList, counterpartyList (опционально).

    Расписание Beat: каждые ``ONEC_BEAT_FULL_SYNC_MINUTES`` (по умолчанию 60), отдельно от
    частого обновления цен через ``sync_products_from_onec``.
    """
    from integrations.clients.onec import OneCAPIError
    from integrations.services.onec_full_sync import run_full_onec_sync

    if not getattr(settings, "ONEC_BEAT_SYNC_ENABLED", True):
        return {"skipped": True, "reason": "ONEC_BEAT_SYNC_ENABLED=false"}

    skip_cust = getattr(settings, "ONEC_BEAT_SKIP_CUSTOMERS", False)
    try:
        return run_full_onec_sync(skip_customers=skip_cust)
    except OneCAPIError as exc:
        logger.warning("sync_all_from_onec failed: %s", exc)
        raise self.retry(exc=exc) from exc
