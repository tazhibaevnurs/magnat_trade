from __future__ import annotations

import html
import logging
import threading

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def _telegram_notifications_enabled() -> bool:
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = (getattr(settings, "TELEGRAM_GROUP_CHAT_ID", "") or "").strip()
    enabled = bool(getattr(settings, "TELEGRAM_NOTIFICATIONS_ENABLED", False))
    return enabled and bool(token) and bool(chat_id)


def _send_telegram_message(text: str) -> bool:
    if not _telegram_notifications_enabled():
        return False

    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = (getattr(settings, "TELEGRAM_GROUP_CHAT_ID", "") or "").strip()
    timeout = float(getattr(settings, "TELEGRAM_HTTP_TIMEOUT", 3.0))
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:3900],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            logger.warning("Telegram notify failed: HTTP %s %s", resp.status_code, resp.text[:300])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram notify exception: %s", exc)
        return False


def _dispatch_message(text: str) -> bool:
    async_mode = bool(getattr(settings, "TELEGRAM_ASYNC_SEND", True))
    if not async_mode:
        return _send_telegram_message(text)
    threading.Thread(
        target=_send_telegram_message,
        args=(text,),
        daemon=True,
        name="telegram-notify",
    ).start()
    return True


def notify_order_created(order) -> bool:
    lines = list(order.items.all()[:12])
    items_preview = "\n".join(
        f"• {html.escape(line.name_snapshot or line.product_id)} × {line.quantity} = {line.line_total}"
        for line in lines
    )
    if order.items.count() > len(lines):
        items_preview += "\n• …"

    customer = html.escape(order.delivery_full_name or "-")
    phone = html.escape(getattr(order, "delivery_phone", "") or "-")
    email = html.escape(order.delivery_email or "-")
    delivery = html.escape(str(getattr(order, "delivery_method_label", "-")))
    address = html.escape(order.delivery_address or "-")
    comment = html.escape(getattr(order, "customer_comment", "") or "Без комментария")
    order_id = html.escape(str(order.id))

    text = (
        "🛍️ <b>Новая заявка с сайта</b>\n"
        "Спасибо! Поступил новый заказ.\n\n"
        f"🧾 <b>Номер заказа:</b> <code>{order_id}</code>\n\n"
        "👤 <b>Клиент</b>\n"
        f"• Имя: {customer}\n"
        f"• Телефон: {phone}\n"
        f"• Email: {email}\n\n"
        "🚚 <b>Доставка</b>\n"
        f"• Способ: {delivery}\n"
        f"• Адрес: {address}\n\n"
        "💰 <b>Оплата</b>\n"
        f"• Сумма товаров: {order.goods_subtotal}\n"
        f"• Доставка: {order.shipping_fee}\n"
        f"• Итого к оплате: <b>{order.total_amount}</b>\n\n"
        f"💬 <b>Комментарий:</b> {comment}\n\n"
        f"📦 <b>Состав заказа:</b>\n{items_preview}"
    )
    return _dispatch_message(text)


def notify_feedback_created(*, name: str, email: str, category: str, subject: str, message: str) -> bool:
    text = (
        "Новая заявка (обратная связь)\n"
        f"Имя: {name}\n"
        f"Email: {email}\n"
        f"Категория: {category}\n"
        f"Тема: {subject}\n"
        f"Сообщение:\n{message}"
    )
    return _dispatch_message(text)


def notify_wholesale_request_created(*, email: str, comment: str) -> bool:
    text = (
        "Новая заявка на оптовый доступ\n"
        f"Пользователь: {email}\n"
        f"Комментарий: {comment or '-'}"
    )
    return _dispatch_message(text)
