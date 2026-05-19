from dataclasses import dataclass, asdict
import datetime


@dataclass
class Match:
    player: str
    date: datetime.date
    tournament: str
    round: str
    match_type: str    # "Singles" or "Doubles"
    partner: str       # doubles partner name, empty for singles
    opponent: str
    score: str
    result: str        # "W" or "L"
    source: str        # e.g. "TE", "SVTF", "ITF" — derived from source_url subdomain
    source_url: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        return d
