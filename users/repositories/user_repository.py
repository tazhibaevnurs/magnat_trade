from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


def _scalar_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value).strip()


class UserRepository:
    @staticmethod
    def upsert_by_external_id(data: dict[str, Any]) -> tuple[object, bool]:
        """
        Поиск только по external_id (код контрагента из 1С).
        Если email нет в данных 1С — подставляется технический адрес.
        """
        ext_raw = data.get("external_id") or data.get("id")
        if not ext_raw:
            raise ValueError("external_id or id is required")
        ext = str(ext_raw).strip()
        email = _scalar_str(data.get("email")).lower()
        if not email:
            email = f"onec-{ext}@imported.local"
        raw_name = (data.get("name") or "").strip()
        parts = raw_name.split(None, 1)
        first = parts[0][:150] if parts else ""
        last = parts[1][:150] if len(parts) > 1 else ""
        phone_raw = _scalar_str(data.get("phone"))
        _ut = data.get("user_type") or data.get("price_type") or "retail"
        if _ut not in ("retail", "wholesale", "manager"):
            _ut = "retail"
        defaults = {
            "first_name": first,
            "last_name": last,
            "phone": phone_raw[:32],
            "user_type": _ut,
            "entity_type": data.get("entity_type", "individual"),
            "is_active": data.get("is_active", True),
            "email": email,
        }
        with transaction.atomic():
            user = User.objects.filter(external_id=ext).first()
            if user:
                if email and User.objects.filter(email=email).exclude(pk=user.pk).exists():
                    # Email уже у другого пользователя (розница, другой контрагент) —
                    # не затираем уникальный ключ, оставляем текущий email этой записи.
                    defaults = {**defaults, "email": user.email}
                for key, value in defaults.items():
                    setattr(user, key, value)
                user.save()
                return user, False

            other = User.objects.filter(email=email).exclude(external_id=ext).first()
            if other:
                # Один email в 1С у нескольких контрагентов — обновляем существующую запись
                for key, value in defaults.items():
                    setattr(other, key, value)
                other.external_id = ext
                other.save()
                return other, False

            user = User.objects.create_user(
                email=email,
                password=None,
                external_id=ext,
                first_name=defaults["first_name"],
                last_name=defaults["last_name"],
                phone=defaults["phone"],
                user_type=defaults["user_type"],
                entity_type=defaults["entity_type"],
                is_active=defaults["is_active"],
            )
            return user, True
