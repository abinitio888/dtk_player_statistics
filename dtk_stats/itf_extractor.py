"""
ITF tennis activity extractor for itftennis.com player profile pages.

ITF pages are protected by Incapsula and use a JSON API. We navigate to the
player's page with Playwright (to establish session cookies), then call the
GetPlayerActivity API from within the browser context.

API endpoint:
  GET https://www.itftennis.com/tennis/api/PlayerApi/GetPlayerActivity
  Params: circuitCode, matchTypeCode (S/D), playerId, skip, take, year
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import List, Optional
from urllib.parse import urlencode, urlparse

from dateutil import parser as dateparser

from dtk_stats.models import Match

logger = logging.getLogger(__name__)

_ITF_API_BASE = "https://www.itftennis.com/tennis/api/PlayerApi/GetPlayerActivity"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# URL path segment → API circuit code
_CIRCUIT_MAP = {
    "junior": "JT",
    "women": "WS",
    "men": "MS",
    "wheelchair": "WH",
    "beach": "BT",
}


def is_itf_url(url: str) -> bool:
    return "itftennis.com" in urlparse(url).netloc


def _extract_player_id(url: str) -> Optional[str]:
    """Extract numeric player ID from ITF URL path."""
    m = re.search(r"/(\d{6,12})/", url)
    return m.group(1) if m else None


def _extract_circuit_code(url: str) -> str:
    """Detect circuit from URL path segment (e.g. '/junior/' → 'JT')."""
    path = urlparse(url).path.lower()
    for segment, code in _CIRCUIT_MAP.items():
        if f"/{segment}/" in path:
            return code
    return "JT"  # default to juniors


def _parse_tournament_date(dates_str: str) -> Optional[datetime.date]:
    """
    Parse ITF tournament date string like '31 Dec to 04 Jan 2026'.
    Uses the end date (which carries the year).
    """
    if not dates_str:
        return None
    parts = re.split(r"\s+to\s+", dates_str.strip(), flags=re.IGNORECASE)
    candidate = parts[-1].strip()
    # Try ISO format first
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", candidate)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Fall back to dateutil
    try:
        return dateparser.parse(candidate, dayfirst=True).date()
    except Exception:
        return None


def _build_score(scores: list, result_code: str) -> str:
    """
    Build score string from ITF scores list.
    Each entry has scoreOne (our player) and scoreTwo (opponent).
    """
    if not scores:
        return ""
    parts = []
    for s in scores:
        one = s.get("scoreOne", "")
        two = s.get("scoreTwo", "")
        if one != "" and two != "":
            parts.append(f"{one}-{two}")
    return " ".join(parts)


def _parse_itf_response(
    data: dict,
    player_name: str,
    source_url: str,
    match_type_code: str,
) -> List[Match]:
    """Convert GetPlayerActivity JSON response into Match objects."""
    matches: List[Match] = []
    items = data.get("items") or []

    for tournament in items:
        tournament_name = tournament.get("tournamentName", "Unknown Tournament")
        dates_str = tournament.get("dates", "")
        tournament_date = _parse_tournament_date(dates_str)

        for event in tournament.get("events") or []:
            draw_type = event.get("drawType", "")
            full_name = f"{tournament_name} – {draw_type}" if draw_type else tournament_name

            match_type = "Doubles" if match_type_code == "D" else "Singles"
            # Partner info available at event level for doubles
            partner_obj = event.get("partner")
            if partner_obj:
                partner = f"{partner_obj.get('givenName', '')} {partner_obj.get('familyName', '')}".strip()
            else:
                partner = ""

            for match in event.get("matches") or []:
                # Opponents
                opp_list = match.get("opponents") or []
                opp_names = [
                    f"{o.get('givenName', '')} {o.get('familyName', '')}".strip()
                    for o in opp_list
                    if o.get("givenName") or o.get("familyName")
                ]
                opponent = " / ".join(opp_names) if opp_names else "Unknown"

                # Result (already W/L in ITF response)
                result_raw = (match.get("resultCode") or "").strip().upper()
                result = result_raw if result_raw in ("W", "L") else result_raw

                # Round
                round_group = match.get("roundGroup") or {}
                round_name = round_group.get("Value") or round_group.get("value") or ""

                # Score
                score = _build_score(match.get("scores") or [], result_raw)

                # Date — try match-level first, fall back to tournament date
                match_date = tournament_date
                raw_date = match.get("date") or match.get("matchDate") or ""
                if raw_date:
                    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw_date)
                    if m:
                        try:
                            match_date = datetime.date(
                                int(m.group(1)), int(m.group(2)), int(m.group(3))
                            )
                        except ValueError:
                            pass

                if match_date is None:
                    logger.debug(
                        f"No date for ITF match {round_name} vs {opponent} in {tournament_name} — skipping"
                    )
                    continue

                matches.append(
                    Match(
                        player=player_name,
                        date=match_date,
                        tournament=full_name,
                        round=round_name,
                        match_type=match_type,
                        partner=partner,
                        opponent=opponent,
                        score=score,
                        result=result,
                        source="ITF",
                        source_url=source_url,
                    )
                )
                logger.debug(
                    f"  ITF {match_date} {full_name} {round_name}: {result} vs {opponent} ({score})"
                )

    return matches


async def _fetch_itf_matches_async(
    source_url: str,
    player_name: str,
    years: List[int],
    timeout_ms: int = 30000,
) -> List[Match]:
    from playwright.async_api import async_playwright

    player_id = _extract_player_id(source_url)
    if not player_id:
        logger.error(f"Could not extract ITF player ID from URL: {source_url}")
        return []

    circuit_code = _extract_circuit_code(source_url)
    logger.debug(f"ITF player_id={player_id}, circuit={circuit_code}")

    all_matches: List[Match] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=_USER_AGENT)
        page = await context.new_page()

        # Navigate to establish session cookies
        logger.debug(f"Navigating to ITF page: {source_url}")
        try:
            await page.goto(source_url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as e:
            logger.warning(f"ITF page navigation failed: {e}")

        # Dismiss cookie consent if present
        await _dismiss_itf_cookies(page)
        await page.wait_for_timeout(2000)

        # Fetch data for each year and match type
        for year in years:
            for match_type_code in ("S", "D"):
                params = {
                    "circuitCode": circuit_code,
                    "matchTypeCode": match_type_code,
                    "playerId": player_id,
                    "skip": 0,
                    "take": 200,
                    "surfaceCode": "",
                    "tourCategoryCode": "",
                    "year": str(year),
                }
                api_url = f"{_ITF_API_BASE}?{urlencode(params)}"
                logger.debug(f"Calling ITF API: {api_url}")

                try:
                    data = await page.evaluate(
                        """async (url) => {
                            const response = await fetch(url, {
                                headers: {
                                    'Accept': 'application/json',
                                    'X-Requested-With': 'XMLHttpRequest',
                                }
                            });
                            if (!response.ok) return null;
                            return await response.json();
                        }""",
                        api_url,
                    )
                except Exception as e:
                    logger.warning(
                        f"ITF API fetch failed (year={year}, type={match_type_code}): {e}"
                    )
                    continue

                if not data:
                    logger.debug(
                        f"ITF API returned empty for year={year}, type={match_type_code}"
                    )
                    continue

                matches = _parse_itf_response(data, player_name, source_url, match_type_code)
                logger.debug(
                    f"  ITF year={year} type={match_type_code}: {len(matches)} matches"
                )
                all_matches.extend(matches)

        await browser.close()

    return all_matches


async def _dismiss_itf_cookies(page) -> None:
    """Attempt to dismiss ITF cookie consent."""
    patterns = [
        "Accept All",
        "Accept all",
        "Accept",
        "Agree",
        "OK",
        "Godkänn",
    ]
    for text in patterns:
        try:
            btn = page.get_by_role("button", name=text)
            if await btn.count() > 0:
                await btn.first.click(timeout=3000)
                await page.wait_for_timeout(500)
                return
        except Exception:
            continue


def fetch_itf_matches(
    source_url: str,
    player_name: str,
    years: List[int],
    timeout_ms: int = 30000,
) -> List[Match]:
    """Synchronous wrapper: fetch ITF matches via Playwright."""
    import asyncio

    return asyncio.run(
        _fetch_itf_matches_async(source_url, player_name, years, timeout_ms=timeout_ms)
    )
