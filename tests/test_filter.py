import datetime

from dtk_stats.config import DateRange
from dtk_stats.filter import filter_by_period, filter_byes


def test_filter_keeps_in_range(sample_matches):
    period = DateRange(from_date=datetime.date(2024, 1, 1), to_date=datetime.date(2024, 12, 31))
    result = filter_by_period(sample_matches, period)
    assert len(result) == 2
    assert all(m.date.year == 2024 for m in result)


def test_filter_excludes_before(sample_matches):
    period = DateRange(from_date=datetime.date(2024, 4, 1), to_date=datetime.date(2024, 12, 31))
    result = filter_by_period(sample_matches, period)
    # March match should be excluded
    assert all(m.date >= datetime.date(2024, 4, 1) for m in result)


def test_filter_inclusive_boundaries(sample_matches):
    period = DateRange(
        from_date=datetime.date(2024, 3, 15),
        to_date=datetime.date(2024, 6, 20),
    )
    result = filter_by_period(sample_matches, period)
    assert len(result) == 2


def test_filter_empty_when_no_match(sample_matches):
    period = DateRange(from_date=datetime.date(2025, 1, 1), to_date=datetime.date(2025, 12, 31))
    result = filter_by_period(sample_matches, period)
    assert result == []


def test_filter_byes_removes_bye(sample_matches):
    import dataclasses
    bye_match = dataclasses.replace(sample_matches[0], opponent="Bye")
    result = filter_byes([bye_match] + sample_matches[1:])
    assert all(m.opponent != "Bye" for m in result)
    assert len(result) == len(sample_matches) - 1


def test_filter_byes_removes_friplats(sample_matches):
    import dataclasses
    friplats = dataclasses.replace(sample_matches[0], opponent="Friplats")
    result = filter_byes([friplats] + sample_matches[1:])
    assert all(m.opponent != "Friplats" for m in result)
    assert len(result) == len(sample_matches) - 1


def test_filter_byes_case_insensitive(sample_matches):
    import dataclasses
    mixed = dataclasses.replace(sample_matches[0], opponent="BYE")
    result = filter_byes([mixed] + sample_matches[1:])
    assert len(result) == len(sample_matches) - 1


def test_filter_byes_keeps_real_opponents(sample_matches):
    result = filter_byes(sample_matches)
    assert len(result) == len(sample_matches)
