"""
Extracts Match records from tournamentsoftware.com player profile pages.

Both te.tournamentsoftware.com and svtf.tournamentsoftware.com (and other
federation subdomains) share the same HTML structure.

Key selectors:
  Tournament card:   li.list__item
  Tournament name:   h4.media__title .nav-link__value
  Draw/event name:   h5.module-divider .nav-link__value
  Match container:   div.match  (inside ol.match-group)
  Round:             .match__header .nav-link__value
  Player row:        .match__row (two per match; the one with .match__status = our player)
  Result:            .match__status  (W/L on te., V/F on svtf.)
  Opponent name:     other .match__row .match__row-title-value-content .nav-link__value
  Score:             .match__result > ul.points  (one per set; two li.points__cell each)
  Date (te.):        .match__footer time[datetime]  (attr: "2026-02-21 00:00")
  Date (svtf.):      .match__footer .icon-clock + .nav-link__value  (text: "tor 2026-05-07")
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateparser

from dtk_stats.models import Match

logger = logging.getLogger(__name__)

# Maps raw result text → normalised "W" or "L"
_RESULT_MAP = {
    "w": "W", "win": "W", "won": "W", "winner": "W",
    "v": "W",  # Swedish: Vunnen
    "l": "L", "loss": "L", "lost": "L", "loser": "L",
    "f": "L",  # Swedish: Förlorad
    "defeat": "L", "defeated": "L",
}


def _derive_source(url: str) -> str:
    """Extract the source label from the URL subdomain (e.g. 'te' → 'TE')."""
    host = urlparse(url).netloc  # e.g. "te.tournamentsoftware.com"
    subdomain = host.split(".")[0]
    return subdomain.upper()


def _text(el: Optional[Tag]) -> str:
    if el is None:
        return ""
    return el.get_text(separator=" ", strip=True)


def _normalise_result(raw: str) -> str:
    return _RESULT_MAP.get(raw.strip().lower(), raw.strip())


def _parse_date(raw: str) -> Optional[datetime.date]:
    """Parse a date string, handling Swedish day prefixes like 'tor 2026-05-07'."""
    # Strip Swedish/Norwegian day-of-week prefixes (mån, tis, ons, tor, fre, lör, sön, etc.)
    raw = re.sub(r"^[a-zåäö]{2,4}\s+", "", raw.strip(), flags=re.IGNORECASE)
    if not raw:
        return None
    # Try ISO format first (YYYY-MM-DD) — avoids dateutil dayfirst ambiguity
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Fall back to dateutil for other formats (dd/mm/yyyy, "15 Mar 2024", etc.)
    try:
        return dateparser.parse(raw, dayfirst=True).date()
    except Exception:
        return None


def _extract_score(match_div: Tag) -> str:
    """
    Build score string from .match__result > ul.points elements.
    Each ul = one set; first li = row-1 player's score, second li = row-2 player's score.
    Result: "6-1 6-1" or "2-6 1-6" etc.
    """
    sets = match_div.select(".match__result ul.points")
    set_strings = []
    for s in sets:
        cells = s.select("li.points__cell")
        if len(cells) >= 2:
            a = _text(cells[0])
            b = _text(cells[1])
            set_strings.append(f"{a}-{b}")
        elif len(cells) == 1:
            set_strings.append(_text(cells[0]))
    return " ".join(set_strings)


def _extract_match_date(match_div: Tag) -> Optional[object]:
    """Try multiple strategies to find the match date inside a .match div."""
    # Strategy 1: <time datetime="2026-02-21 00:00"> element (te. subdomain)
    time_el = match_div.select_one("time[datetime]")
    if time_el:
        dt_attr = time_el.get("datetime", "")
        d = _parse_date(dt_attr)
        if d:
            return d

    # Strategy 2: footer text next to clock icon (svtf. subdomain)
    for item in match_div.select(".match__footer-list-item"):
        if item.select_one(".icon-clock"):
            text = _text(item.select_one(".nav-link__value") or item)
            d = _parse_date(text)
            if d:
                return d

    # Strategy 3: any text in footer that looks like a date
    footer = match_div.select_one(".match__footer")
    if footer:
        footer_text = _text(footer)
        # Look for ISO-like date patterns
        m = re.search(r"\d{4}-\d{2}-\d{2}", footer_text)
        if m:
            d = _parse_date(m.group())
            if d:
                return d
        # Look for dd/mm/yyyy
        m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", footer_text)
        if m:
            d = _parse_date(m.group())
            if d:
                return d

    return None


def _extract_match(
    match_div: Tag,
    player_name: str,
    tournament_name: str,
    source_url: str,
    fallback_date=None,
) -> Optional[Match]:
    """Extract one Match from a div.match element."""
    # Round
    round_el = match_div.select_one(".match__header .nav-link__value")
    round_name = _text(round_el)

    # Find the two player rows
    rows = match_div.select(".match__row-wrapper > .match__row")
    if not rows:
        return None

    # Identify our player's row (has .match__status)
    our_row = None
    opp_rows = []
    for row in rows:
        if row.select_one(".match__status"):
            our_row = row
        else:
            opp_rows.append(row)

    if our_row is None:
        logger.debug(f"Could not find player's row in match: {round_name}")
        return None

    # Result
    status_el = our_row.select_one(".match__status")
    result_raw = _text(status_el)
    result = _normalise_result(result_raw)

    # Our team's player names (singles: [player], doubles: [player, partner])
    our_names = [
        _text(el)
        for el in our_row.select(".match__row-title-value-content .nav-link__value")
        if _text(el)
    ]
    match_type = "Doubles" if len(our_names) > 1 else "Singles"
    # Partner is whoever else is on our row (case-insensitive comparison)
    partner = next(
        (n for n in our_names if n.lower() != player_name.lower()),
        "",
    )

    # Opponent name(s) — handles singles and doubles
    opp_names = []
    for opp_row in opp_rows:
        names = [_text(el) for el in opp_row.select(".match__row-title-value-content .nav-link__value")]
        opp_names.extend(n for n in names if n)

    # Also handle "Bye"/"Friplats" text which may appear as a plain span in the row
    if not opp_names:
        plain = opp_rows[0].find("span", recursive=False) if opp_rows else None
        if plain:
            t = _text(plain)
            if t:
                opp_names.append(t)

    opponent = " / ".join(opp_names) if opp_names else "Unknown"

    # Score
    score = _extract_score(match_div)

    # Date
    date = _extract_match_date(match_div) or fallback_date
    if date is None:
        logger.debug(f"No date found for match {round_name} vs {opponent} — skipping")
        return None

    return Match(
        player=player_name,
        date=date,
        tournament=tournament_name,
        round=round_name,
        match_type=match_type,
        partner=partner,
        opponent=opponent,
        score=score,
        result=result,
        source=_derive_source(source_url),
        source_url=source_url,
    )


def extract_matches(html: str, player_name: str, source_url: str) -> List[Match]:
    """
    Parse HTML from a tournamentsoftware.com player profile page and return
    a list of Match objects.
    """
    soup = BeautifulSoup(html, "lxml")
    matches: List[Match] = []

    # Find tournament list items — each groups several matches under one tournament
    tournament_items = soup.select("li.list__item")

    if not tournament_items:
        logger.warning(
            f"No tournament items found for {player_name} at {source_url}. "
            "The page may not have loaded correctly."
        )
        return []

    for item in tournament_items:
        # Tournament name
        name_el = item.select_one("h4.media__title .nav-link__value")
        tournament_name = _text(name_el) if name_el else "Unknown Tournament"

        # Draw/event name (may be present as a sub-heading)
        draw_el = item.select_one("h5.module-divider .nav-link__value")
        if draw_el:
            draw_name = _text(draw_el)
            tournament_name = f"{tournament_name} – {draw_name}"

        # Fallback date: tournament start date from the media card
        fallback_date = None
        time_els = item.select("time[datetime]")
        if time_els:
            fallback_date = _parse_date(time_els[0].get("datetime", ""))

        # Extract each match
        for match_div in item.select("div.match"):
            m = _extract_match(
                match_div,
                player_name=player_name,
                tournament_name=tournament_name,
                source_url=source_url,
                fallback_date=fallback_date,
            )
            if m:
                matches.append(m)
                logger.debug(
                    f"  {m.date} {m.tournament} {m.round}: {m.result} vs {m.opponent} ({m.score})"
                )

    logger.info(f"Extracted {len(matches)} matches for {player_name} from {source_url}")
    return matches
