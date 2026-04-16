"""Одноразовый запрос categoryProductList и вывод хвоста ответа (без полного Django)."""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import httpx  # noqa: E402


def main() -> None:
    base = (os.getenv("ONEC_API_BASE_URL") or "").rstrip("/")
    if not base:
        base = "https://77.235.19.234:4443/bereke_test/hs"
        print("ONEC_API_BASE_URL пуст, используем:", base, file=sys.stderr)
    path = "/categories_products/categoryProductList"
    url = f"{base}{path}"

    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "X-Source": os.getenv("ONEC_API_SOURCE", "website"),
    }
    auth_raw = (os.getenv("ONEC_API_BASIC_AUTH") or "").strip()
    if auth_raw:
        headers["Authorization"] = auth_raw if auth_raw.startswith("Basic ") else f"Basic {auth_raw}"
    else:
        u = (os.getenv("ONEC_API_BASIC_USER") or "").strip()
        p = (os.getenv("ONEC_API_BASIC_PASSWORD") or "").strip()
        if u or p:
            b64 = base64.b64encode(f"{u}:{p}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {b64}"

    token = (os.getenv("ONEC_API_TOKEN") or "").strip()
    if token and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"

    verify = os.getenv("ONEC_VERIFY_SSL", "true").lower() in ("1", "true", "yes")
    timeout = float(os.getenv("ONEC_API_TIMEOUT", "120"))

    print("GET", url, file=sys.stderr)
    with httpx.Client(timeout=timeout, verify=verify) as client:
        r = client.get(url, headers=headers)

    print("HTTP", r.status_code, file=sys.stderr)
    text = r.text
    if not text.strip():
        print("(пустое тело)")
        return

    pretty = text
    try:
        data = r.json()
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        pass

    n = len(pretty)
    tail_n = 12000
    print("chars:", n, file=sys.stderr)
    print("--- tail ---")
    print(pretty[-tail_n:] if n > tail_n else pretty)


if __name__ == "__main__":
    main()
