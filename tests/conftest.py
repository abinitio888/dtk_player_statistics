import datetime
import pytest
from dtk_stats.models import Match


@pytest.fixture
def sample_matches():
    return [
        Match(
            player="Vincent Englund",
            date=datetime.date(2024, 3, 15),
            tournament="Swedish Open",
            round="R32",
            match_type="Singles",
            partner="",
            opponent="Erik Svensson",
            score="6-4 6-3",
            result="W",
            source="SVTF",
            source_url="https://svtf.tournamentsoftware.com/player-profile/test",
        ),
        Match(
            player="Vincent Englund",
            date=datetime.date(2024, 6, 20),
            tournament="Stockholm Classic",
            round="QF",
            match_type="Singles",
            partner="",
            opponent="Johan Berg",
            score="3-6 4-6",
            result="L",
            source="SVTF",
            source_url="https://svtf.tournamentsoftware.com/player-profile/test",
        ),
        Match(
            player="Vincent Englund",
            date=datetime.date(2023, 12, 1),
            tournament="Year End",
            round="R64",
            match_type="Singles",
            partner="",
            opponent="Lars Nilsson",
            score="6-2 6-1",
            result="W",
            source="SVTF",
            source_url="https://svtf.tournamentsoftware.com/player-profile/test",
        ),
    ]
