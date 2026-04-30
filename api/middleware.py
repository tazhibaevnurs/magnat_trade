from django.conf import settings
from django.http import JsonResponse


def _is_admin_catalog_gallery_batch_upload(path: str) -> bool:
    p = path.rstrip("/")
    return "/admin/products/product/" in path and p.endswith("gallery-batch-upload")


class RequestBodySizeLimitMiddleware:
    """Limit request body size by surface: API vs regular uploads."""

    API_LIMIT_BYTES = 1 * 1024 * 1024
    UPLOAD_LIMIT_BYTES = 10 * 1024 * 1024

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        content_length_raw = request.META.get("CONTENT_LENGTH") or "0"
        try:
            content_length = int(content_length_raw)
        except (TypeError, ValueError):
            content_length = 0

        is_api = request.path.startswith("/api/") or request.path.startswith("/api/v1/")
        gallery_limit = getattr(settings, "ADMIN_GALLERY_BATCH_UPLOAD_MAX_BYTES", None)
        if gallery_limit and _is_admin_catalog_gallery_batch_upload(request.path):
            limit = gallery_limit
        elif is_api:
            limit = self.API_LIMIT_BYTES
        else:
            limit = self.UPLOAD_LIMIT_BYTES
        if content_length > limit:
            if is_api:
                return JsonResponse(
                    {"detail": f"Request body too large. Limit is {limit // (1024 * 1024)}MB."},
                    status=413,
                )
            return JsonResponse({"detail": "Payload too large."}, status=413)

        return self.get_response(request)
