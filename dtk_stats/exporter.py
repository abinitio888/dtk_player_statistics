import csv
import json
from pathlib import Path
from typing import List

from dtk_stats.models import Match

COLUMNS = ["player", "date", "tournament", "round", "match_type", "partner", "opponent", "score", "result", "source", "source_url"]


def export_csv(matches: List[Match], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(m.to_dict() for m in matches)


def export_json(matches: List[Match], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([m.to_dict() for m in matches], f, indent=2, ensure_ascii=False)
