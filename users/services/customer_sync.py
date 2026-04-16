from __future__ import annotations

from typing import Any

from django.db import transaction

from users.repositories import UserRepository


class CustomerSyncService:
    @staticmethod
    def sync_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
        created = 0
        updated = 0
        with transaction.atomic():
            for raw in items:
                _, was_created = UserRepository.upsert_by_external_id(raw)
                if was_created:
                    created += 1
                else:
                    updated += 1
        return {"created": created, "updated": updated, "total": len(items)}
