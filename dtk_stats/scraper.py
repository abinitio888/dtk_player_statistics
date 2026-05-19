"""
Playwright-based scraper for tournamentsoftware.com player profile pages.

Handles:
  - Cookie consent banners (English and Swedish)
  - JavaScript-rendered content
  - Returns raw HTML of the fully rendered page
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Cookie consent button text patterns (case-insensitive substring match)
_CONSENT_PATTERNS = [
    "accept all",
    "accept cookies",
    "godkänn alla",
    "godkänn",
    "acceptera alla",
    "acceptera",
    "tillåt alla",
    "allow all",
    "i agree",
    "agree",
]


async def _fetch_page_async(url: str, timeout_ms: int = 15000) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        logger.debug(f"Navigating to {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        # Attempt to dismiss cookie consent banner
        await _dismiss_cookies(page, timeout_ms=5000)

        # Wait for some meaningful content to appear
        try:
            await page.wait_for_selector("table, .match, .results, #matches", timeout=timeout_ms)
        except Exception:
            logger.debug("No specific content selector matched — using current page state")

        # Give JS a moment to settle
        await page.wait_for_timeout(1500)

        html = await page.content()
        await browser.close()
        return html


async def _dismiss_cookies(page, timeout_ms: int = 5000) -> None:
    """Try to click an accept/consent button if one is present."""
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    # First try: look for buttons matching known consent text patterns
    for pattern in _CONSENT_PATTERNS:
        try:
            # Playwright's text selector is case-insensitive with /i
            btn = page.get_by_role("button", name=pattern)
            if await btn.count() > 0:
                await btn.first.click(timeout=3000)
                logger.debug(f"Dismissed cookie consent via button text: '{pattern}'")
                await page.wait_for_timeout(800)
                return
        except Exception:
            continue

    # Second try: any button/link containing "accept" or "godkänn" in its text
    for selector in [
        "button:has-text('Accept')",
        "button:has-text('Godkänn')",
        "button:has-text('Acceptera')",
        "a:has-text('Accept all')",
        "a:has-text('Godkänn alla')",
        "[id*='accept']",
        "[class*='accept']",
        "[id*='consent'] button",
        ".cookie-consent button",
        "#cookie-banner button",
        ".cc-btn.cc-allow",
    ]:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                await locator.first.click(timeout=3000)
                logger.debug(f"Dismissed cookie consent via selector: {selector}")
                await page.wait_for_timeout(800)
                return
        except Exception:
            continue

    logger.debug("No cookie consent button found — continuing without dismissal")


def fetch_page(url: str, timeout_ms: int = 15000) -> str:
    """Synchronous wrapper around the async Playwright fetch."""
    return asyncio.run(_fetch_page_async(url, timeout_ms=timeout_ms))
