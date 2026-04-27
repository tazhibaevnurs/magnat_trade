import json
from dataclasses import dataclass, asdict
from typing import List

from playwright.sync_api import Browser, Playwright, TimeoutError, sync_playwright


BASE_URL = "http://127.0.0.1:8000"
PAGES_TO_CHECK = ["/", "/shop", "/about-us", "/contact-us", "/cart"]


@dataclass
class CheckResult:
    mode: str
    check: str
    target: str
    status: str
    details: str = ""


def collect_internal_links(page) -> List[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]",
        """(anchors) => anchors
            .map((a) => a.getAttribute('href') || '')
            .filter((href) =>
                href.startsWith('/') &&
                !href.startsWith('//') &&
                !href.startsWith('/static/')
            )""",
    )
    return sorted(set(hrefs))


def run_link_checks(browser: Browser, mode: str, mobile: bool) -> List[CheckResult]:
    context = browser.new_context(
        viewport={"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900},
        is_mobile=mobile,
        has_touch=mobile,
    )
    page = context.new_page()
    results: List[CheckResult] = []

    try:
        for route in PAGES_TO_CHECK:
            response = page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded")
            code = response.status if response else 0
            status = "pass" if code and code < 400 else "fail"
            results.append(CheckResult(mode, "page-load", route, status, f"HTTP {code}"))

            links = collect_internal_links(page)
            for href in links:
                full_url = f"{BASE_URL}{href}"
                res = page.request.get(full_url, timeout=10000)
                link_status = "pass" if res.status < 400 else "fail"
                results.append(
                    CheckResult(mode, "link-check", href, link_status, f"HTTP {res.status}")
                )
    finally:
        context.close()

    return results


def run_desktop_interactions(browser: Browser) -> List[CheckResult]:
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    results: List[CheckResult] = []
    errors: List[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    try:
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
        more_btn = page.locator("button.sub-nav__dropdown-btn", has_text="Ещё").first
        more_btn.click(timeout=5000)
        dropdown = page.locator(".sub-nav__more .sub-nav__dropdown")
        visible = dropdown.is_visible()
        results.append(
            CheckResult("desktop", "button", "Ещё dropdown open", "pass" if visible else "fail")
        )

        if visible:
            for text in ["Корзина", "Заказы", "Обратная связь"]:
                item = dropdown.locator("a", has_text=text).first
                results.append(
                    CheckResult(
                        "desktop",
                        "dropdown-item-visible",
                        text,
                        "pass" if item.is_visible() else "fail",
                    )
                )

        if errors:
            results.append(
                CheckResult("desktop", "console-errors", "/", "fail", "; ".join(errors[:10]))
            )
        else:
            results.append(CheckResult("desktop", "console-errors", "/", "pass"))
    except TimeoutError as exc:
        results.append(CheckResult("desktop", "interaction-timeout", "/", "fail", str(exc)))
    finally:
        context.close()
    return results


def run_mobile_interactions(browser: Browser) -> List[CheckResult]:
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    results: List[CheckResult] = []

    try:
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
        burger = page.locator("#mobile-sidebar-toggle").first
        burger.click(timeout=5000)
        drawer = page.locator("#mobile-sidebar-drawer")
        opened = drawer.is_visible()
        results.append(
            CheckResult("mobile", "button", "mobile-sidebar-toggle", "pass" if opened else "fail")
        )

        if opened:
            contact_link = drawer.locator("a", has_text="Доставка").first
            href = contact_link.get_attribute("href") or ""
            results.append(
                CheckResult(
                    "mobile",
                    "mobile-link-present",
                    "Доставка",
                    "pass" if href.startswith("/contact-us") else "fail",
                    href,
                )
            )
    except TimeoutError as exc:
        results.append(CheckResult("mobile", "interaction-timeout", "/", "fail", str(exc)))
    finally:
        context.close()
    return results


def run_all(playwright: Playwright) -> List[CheckResult]:
    browser = playwright.chromium.launch(headless=True)
    try:
        results = []
        results.extend(run_link_checks(browser, "desktop", mobile=False))
        results.extend(run_link_checks(browser, "mobile", mobile=True))
        results.extend(run_desktop_interactions(browser))
        results.extend(run_mobile_interactions(browser))
        return results
    finally:
        browser.close()


def main() -> None:
    with sync_playwright() as playwright:
        results = run_all(playwright)

    failures = [r for r in results if r.status == "fail"]
    summary = {
        "total_checks": len(results),
        "failed_checks": len(failures),
        "failures": [asdict(f) for f in failures],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
