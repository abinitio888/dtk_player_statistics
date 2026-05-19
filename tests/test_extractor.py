"""
Tests for the HTML extractor using synthetic HTML that mirrors
the tournamentsoftware.com player profile structure.
"""

import datetime
from dtk_stats.extractor import extract_matches, _normalise_result, _parse_date

# Minimal HTML mirroring tournamentsoftware.com structure
SAMPLE_HTML = """
<html><body>
<ul class="list list--naked list--spacing">
  <li class="list__item">
    <h4 class="media__title">
      <a class="media__link"><span class="nav-link__value">Swedish Open 2024</span></a>
    </h4>
    <h5 class="module-divider">
      <span class="module-divider__body">
        <a><span class="nav-link__value">Boys Singles Qualifying</span></a>
      </span>
    </h5>
    <ol class="match-group">
      <!-- Match 1: Win vs Erik -->
      <li class="match-group__item">
        <div class="match">
          <div class="match__header">
            <ul class="match__header-title">
              <li><span class="nav-link"><span class="nav-link__value">Round of 32</span></span></li>
            </ul>
          </div>
          <div class="match__body">
            <div class="match__row-wrapper">
              <div class="match__row has-won">
                <div class="match__row-title">
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a class="nav-link"><span class="nav-link__value">Vincent ENGLUND</span></a>
                    </span>
                  </div>
                </div>
                <span class="tag--success tag match__status">W</span>
              </div>
              <div class="match__row">
                <div class="match__row-title">
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a class="nav-link"><span class="nav-link__value">Erik Svensson</span></a>
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div class="match__result">
              <ul class="points">
                <li class="points__cell points__cell--won">6</li>
                <li class="points__cell">4</li>
              </ul>
              <ul class="points">
                <li class="points__cell points__cell--won">6</li>
                <li class="points__cell">3</li>
              </ul>
            </div>
          </div>
          <div class="match__footer">
            <ul class="match__footer-list">
              <li class="match__footer-list-item">
                <span class="nav-link">
                  <svg class="icon-clock nav-link__prefix"></svg>
                  <span class="nav-link__value">Fri 15/03/2024</span>
                </span>
              </li>
            </ul>
          </div>
        </div>
      </li>
      <!-- Match 2: Loss vs Johan (Swedish result "F") -->
      <li class="match-group__item">
        <div class="match">
          <div class="match__header">
            <ul class="match__header-title">
              <li><span class="nav-link"><span class="nav-link__value">QF</span></span></li>
            </ul>
          </div>
          <div class="match__body">
            <div class="match__row-wrapper">
              <div class="match__row">
                <div class="match__row-title">
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a class="nav-link"><span class="nav-link__value">Johan Berg</span></a>
                    </span>
                  </div>
                </div>
              </div>
              <div class="match__row">
                <div class="match__row-title">
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a class="nav-link"><span class="nav-link__value">Vincent ENGLUND</span></a>
                    </span>
                  </div>
                </div>
                <span class="tag--danger tag match__status">F</span>
              </div>
            </div>
            <div class="match__result">
              <ul class="points">
                <li class="points__cell points__cell--won">6</li>
                <li class="points__cell">3</li>
              </ul>
              <ul class="points">
                <li class="points__cell points__cell--won">6</li>
                <li class="points__cell">4</li>
              </ul>
            </div>
          </div>
          <div class="match__footer">
            <ul class="match__footer-list">
              <li class="match__footer-list-item">
                <span class="nav-link">
                  <svg class="icon-clock nav-link__prefix"></svg>
                  <span class="nav-link__value">tor 2024-06-20</span>
                </span>
              </li>
            </ul>
          </div>
        </div>
      </li>
    </ol>
  </li>
</ul>
</body></html>
"""

HTML_WITH_TIME_ATTR = """
<html><body>
<ul class="list list--naked list--spacing">
  <li class="list__item">
    <h4 class="media__title">
      <a class="media__link"><span class="nav-link__value">TE 14 Stavanger</span></a>
    </h4>
    <time datetime="2024-03-10 00:00">10/03/2024</time>
    <ol class="match-group">
      <li class="match-group__item">
        <div class="match">
          <div class="match__header">
            <ul><li><span class="nav-link"><span class="nav-link__value">R32</span></span></li></ul>
          </div>
          <div class="match__body">
            <div class="match__row-wrapper">
              <div class="match__row has-won">
                <div class="match__row-title">
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a><span class="nav-link__value">Vincent ENGLUND</span></a>
                    </span>
                  </div>
                </div>
                <span class="match__status">W</span>
              </div>
              <div class="match__row"><span>Bye</span></div>
            </div>
            <div class="match__result"></div>
          </div>
          <div class="match__footer">
            <ul class="match__footer-list">
              <li class="match__footer-list-item">
                <span class="nav-link">
                  <span class="nav-link__value">Stavanger Tennis Club</span>
                </span>
              </li>
            </ul>
          </div>
        </div>
      </li>
    </ol>
  </li>
</ul>
</body></html>
"""


def test_extract_win():
    matches = extract_matches(SAMPLE_HTML, "Vincent ENGLUND", "https://example.com")
    assert len(matches) >= 1
    win = next(m for m in matches if m.result == "W")
    assert win.tournament == "Swedish Open 2024 – Boys Singles Qualifying"
    assert win.round == "Round of 32"
    assert win.opponent == "Erik Svensson"
    assert win.score == "6-4 6-3"
    assert win.date == datetime.date(2024, 3, 15)
    assert win.player == "Vincent ENGLUND"
    assert win.match_type == "Singles"
    assert win.partner == ""


def test_extract_loss_swedish_result():
    matches = extract_matches(SAMPLE_HTML, "Vincent ENGLUND", "https://example.com")
    loss = next(m for m in matches if m.result == "L")
    assert loss.opponent == "Johan Berg"
    assert loss.result == "L"
    assert loss.date == datetime.date(2024, 6, 20)


def test_extract_bye_with_fallback_date():
    matches = extract_matches(HTML_WITH_TIME_ATTR, "Vincent ENGLUND", "https://example.com")
    assert len(matches) == 1
    assert matches[0].opponent == "Bye"
    assert matches[0].date == datetime.date(2024, 3, 10)


def test_extract_empty_html():
    matches = extract_matches("<html><body></body></html>", "Player", "https://example.com")
    assert matches == []


def test_extract_source_url_recorded():
    url = "https://te.tournamentsoftware.com/player-profile/ABC"
    matches = extract_matches(SAMPLE_HTML, "Vincent ENGLUND", url)
    for m in matches:
        assert m.source_url == url


DOUBLES_HTML = """
<html><body>
<ul class="list list--naked list--spacing">
  <li class="list__item">
    <h4 class="media__title">
      <a class="media__link"><span class="nav-link__value">Uppsala Cup 2024</span></a>
    </h4>
    <h5 class="module-divider">
      <span class="module-divider__body"><a><span class="nav-link__value">PD14</span></a></span>
    </h5>
    <ol class="match-group">
      <li class="match-group__item">
        <div class="match">
          <div class="match__header">
            <ul><li><span class="nav-link"><span class="nav-link__value">QF</span></span></li></ul>
          </div>
          <div class="match__body">
            <div class="match__row-wrapper">
              <div class="match__row">
                <div class="match__row-title">
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a><span class="nav-link__value">Sixten Hakansson</span></a>
                    </span>
                  </div>
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a><span class="nav-link__value">Julian Lukic</span></a>
                    </span>
                  </div>
                </div>
              </div>
              <div class="match__row has-won">
                <div class="match__row-title">
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a><span class="nav-link__value">Vincent ENGLUND</span></a>
                    </span>
                  </div>
                  <div class="match__row-title-value">
                    <span class="match__row-title-value-content">
                      <a><span class="nav-link__value">Hugo Rodziewicz</span></a>
                    </span>
                  </div>
                </div>
                <span class="tag match__status">V</span>
              </div>
            </div>
            <div class="match__result">
              <ul class="points">
                <li class="points__cell points__cell--won">6</li>
                <li class="points__cell">1</li>
              </ul>
              <ul class="points">
                <li class="points__cell points__cell--won">6</li>
                <li class="points__cell">2</li>
              </ul>
            </div>
          </div>
          <div class="match__footer">
            <ul class="match__footer-list">
              <li class="match__footer-list-item">
                <span class="nav-link">
                  <svg class="icon-clock nav-link__prefix"></svg>
                  <span class="nav-link__value">tor 2024-05-09</span>
                </span>
              </li>
            </ul>
          </div>
        </div>
      </li>
    </ol>
  </li>
</ul>
</body></html>
"""


def test_extract_doubles_match_type():
    matches = extract_matches(DOUBLES_HTML, "Vincent ENGLUND", "https://example.com")
    assert len(matches) == 1
    m = matches[0]
    assert m.match_type == "Doubles"
    assert m.partner == "Hugo Rodziewicz"
    assert m.opponent == "Sixten Hakansson / Julian Lukic"
    assert m.result == "W"
    assert m.score == "6-1 6-2"


def test_normalise_result():
    assert _normalise_result("W") == "W"
    assert _normalise_result("w") == "W"
    assert _normalise_result("Win") == "W"
    assert _normalise_result("V") == "W"     # Swedish: Vunnen
    assert _normalise_result("L") == "L"
    assert _normalise_result("l") == "L"
    assert _normalise_result("F") == "L"     # Swedish: Förlorad
    assert _normalise_result("lost") == "L"
    assert _normalise_result("unknown") == "unknown"


def test_parse_date_iso():
    from dtk_stats.extractor import _parse_date
    import datetime
    assert _parse_date("2024-06-20") == datetime.date(2024, 6, 20)


def test_parse_date_swedish_prefix():
    from dtk_stats.extractor import _parse_date
    import datetime
    assert _parse_date("tor 2026-05-07") == datetime.date(2026, 5, 7)
    assert _parse_date("mån 2024-03-15") == datetime.date(2024, 3, 15)
