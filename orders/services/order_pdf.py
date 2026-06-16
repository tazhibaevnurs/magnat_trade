"""Генерация PDF для заказов (один заказ или сводный файл)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from orders.models import Order

_FONT_REGISTERED = False
_FONT_NAME = "Helvetica"


def _ensure_pdf_font() -> str:
    global _FONT_REGISTERED, _FONT_NAME
    if _FONT_REGISTERED:
        return _FONT_NAME
    try:
        font_candidates = [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        ]
        for f in font_candidates:
            if f.exists():
                pdfmetrics.registerFont(TTFont("OrderFont", str(f)))
                _FONT_NAME = "OrderFont"
                break
    except Exception:
        pass
    _FONT_REGISTERED = True
    return _FONT_NAME


def _draw_order_on_canvas(c: canvas.Canvas, order: Order, *, page_break_before: bool = False) -> None:
    font_name = _ensure_pdf_font()
    width, height = A4
    margin = 34
    if page_break_before:
        c.showPage()
    y = height - margin
    content_width = width - (margin * 2)

    primary = colors.HexColor("#ef4444")
    primary_dark = colors.HexColor("#dc2626")
    text_main = colors.HexColor("#111827")
    text_muted = colors.HexColor("#6b7280")
    border = colors.HexColor("#e5e7eb")
    soft_bg = colors.HexColor("#f8fafc")

    def new_page():
        nonlocal y
        c.showPage()
        y = height - margin

    def ensure_space(space_needed: float):
        nonlocal y
        if y - space_needed < margin:
            new_page()

    def draw_wrapped_text(
        text: str,
        x: float,
        y_top: float,
        max_width: float,
        size: int = 11,
        color=colors.black,
        leading: float = 14,
    ) -> float:
        c.setFont(font_name, size)
        c.setFillColor(color)
        lines = simpleSplit((text or "-").strip(), font_name, size, max_width)
        cur_y = y_top
        for line in lines:
            c.drawString(x, cur_y, line)
            cur_y -= leading
        return cur_y

    c.setFillColor(primary)
    c.roundRect(margin, y - 40, content_width, 42, 10, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(font_name, 16)
    c.drawString(margin + 14, y - 24, "Береке Канц")
    c.setFont(font_name, 11)
    c.drawRightString(margin + content_width - 14, y - 22, "Подтверждение заказа")
    y -= 58

    c.setFillColor(text_main)
    c.setFont(font_name, 24)
    c.drawString(margin, y, "Спасибо за заказ!")
    y -= 26
    c.setFillColor(text_muted)
    c.setFont(font_name, 11)
    c.drawString(margin, y, "Мы получили вашу заявку и уже передали ее в обработку.")
    y -= 24

    ensure_space(78)
    c.setFillColor(soft_bg)
    c.setStrokeColor(border)
    c.roundRect(margin, y - 64, content_width, 62, 10, fill=1, stroke=1)
    c.setFillColor(text_main)
    c.setFont(font_name, 11)
    c.drawString(margin + 12, y - 20, f"Номер заказа: {order.id}")
    c.drawString(margin + 12, y - 38, f"Дата оформления: {order.created_at.strftime('%d.%m.%Y %H:%M')}")
    c.setFillColor(primary_dark)
    c.setFont(font_name, 12)
    c.drawRightString(margin + content_width - 12, y - 29, f"Итого: {order.total_amount} сом")
    y -= 84

    c.setFillColor(text_main)
    c.setFont(font_name, 14)
    c.drawString(margin, y, "Состав заказа")
    y -= 14

    for item in order.items.all():
        item_name = (item.name_snapshot or str(item.product_id or "")).strip() or "Товар"
        if item.special_instructions:
            item_name = f"{item_name} (отметка: {item.special_instructions})"
        qty_text = f"x {item.quantity}"
        price_text = f"{item.line_total} сом"

        wrapped_name = simpleSplit(item_name, font_name, 11, content_width - 210)
        row_height = max(30, 18 + (len(wrapped_name) - 1) * 13)
        ensure_space(row_height + 8)

        c.setFillColor(colors.white)
        c.setStrokeColor(border)
        c.roundRect(margin, y - row_height, content_width, row_height, 6, fill=1, stroke=1)
        c.setFillColor(text_main)
        c.setFont(font_name, 11)

        name_y = y - 17
        for line in wrapped_name:
            c.drawString(margin + 10, name_y, line)
            name_y -= 13

        c.setFillColor(text_muted)
        c.setFont(font_name, 10)
        c.drawString(margin + content_width - 154, y - 17, qty_text)
        c.setFillColor(primary_dark)
        c.setFont(font_name, 11)
        c.drawRightString(margin + content_width - 10, y - 17, price_text)
        y -= row_height + 8

    y -= 8

    ensure_space(150)
    c.setFillColor(text_main)
    c.setFont(font_name, 14)
    c.drawString(margin, y, "Доставка и контакты")
    y -= 12

    c.setFillColor(soft_bg)
    c.setStrokeColor(border)
    c.roundRect(margin, y - 130, content_width, 126, 10, fill=1, stroke=1)

    x_left = margin + 12
    x_right = margin + (content_width / 2) + 8
    base_y = y - 20
    account_email = ""
    if order.user_id and getattr(order.user, "email", ""):
        account_email = order.user.email
    left_items = [
        f"Способ доставки: {order.delivery_method_label}",
        f"Стоимость доставки: {order.shipping_fee} сом",
        f"Клиент: {order.delivery_full_name or '-'}",
    ]
    right_items = [
        f"Телефон: {order.delivery_phone or '-'}",
        f"Email: {order.delivery_email or account_email or '-'}",
    ]

    c.setFont(font_name, 10)
    c.setFillColor(text_main)
    cur_left = base_y
    for text in left_items:
        c.drawString(x_left, cur_left, text[:80])
        cur_left -= 16

    cur_right = base_y
    for text in right_items:
        c.drawString(x_right, cur_right, text[:80])
        cur_right -= 16

    address_bottom_y = draw_wrapped_text(
        f"Адрес: {order.delivery_address or '-'}",
        x_left,
        y - 74,
        content_width - 24,
        size=10,
        color=text_main,
        leading=14,
    )
    if order.customer_comment:
        draw_wrapped_text(
            f"Комментарий: {order.customer_comment}",
            x_left,
            address_bottom_y - 4,
            content_width - 24,
            size=10,
            color=text_muted,
            leading=13,
        )
    y = y - 142

    ensure_space(90)
    c.setFillColor(colors.white)
    c.setStrokeColor(border)
    c.roundRect(margin, y - 72, content_width, 70, 10, fill=1, stroke=1)
    c.setFillColor(text_main)
    c.setFont(font_name, 11)
    c.drawString(margin + 12, y - 22, f"Сумма товаров: {order.goods_subtotal} сом")
    c.drawString(margin + 12, y - 42, f"Доставка: {order.shipping_fee} сом")
    c.setFillColor(primary)
    c.setFont(font_name, 14)
    c.drawRightString(margin + content_width - 12, y - 33, f"Итого: {order.total_amount} сом")

    c.setFillColor(text_muted)
    c.setFont(font_name, 9)
    c.drawString(margin, margin - 8, "Спасибо, что выбрали Береке Канц")


def build_order_pdf(order: Order) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _draw_order_on_canvas(c, order, page_break_before=False)
    c.save()
    return buf.getvalue()


def build_orders_pdf(orders: Iterable[Order]) -> bytes:
    orders_list = list(orders)
    if not orders_list:
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        font_name = _ensure_pdf_font()
        c.setFont(font_name, 14)
        c.drawString(40, 800, "Заказы отсутствуют.")
        c.save()
        return buf.getvalue()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for index, order in enumerate(orders_list):
        _draw_order_on_canvas(c, order, page_break_before=index > 0)
    c.save()
    return buf.getvalue()
