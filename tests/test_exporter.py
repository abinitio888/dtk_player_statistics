import csv
import json
from pathlib import Path

from dtk_stats.exporter import export_csv, export_json


def test_export_csv(tmp_path, sample_matches):
    out = tmp_path / "results.csv"
    export_csv(sample_matches, out)
    assert out.exists()

    with open(out) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 3
    assert rows[0]["player"] == "Vincent Englund"
    assert rows[0]["result"] in ("W", "L")
    assert rows[0]["date"]  # ISO string present


def test_export_json(tmp_path, sample_matches):
    out = tmp_path / "results.json"
    export_json(sample_matches, out)
    assert out.exists()

    data = json.loads(out.read_text())
    assert len(data) == 3
    assert data[0]["player"] == "Vincent Englund"
    assert isinstance(data[0]["date"], str)


def test_export_creates_directory(tmp_path, sample_matches):
    out = tmp_path / "nested" / "dir" / "results.csv"
    export_csv(sample_matches, out)
    assert out.exists()


def test_export_csv_columns(tmp_path, sample_matches):
    out = tmp_path / "results.csv"
    export_csv(sample_matches, out)

    with open(out) as f:
        reader = csv.DictReader(f)
        expected = {"player", "date", "tournament", "round", "match_type", "partner", "opponent", "score", "result", "source", "source_url"}
        assert set(reader.fieldnames) == expected
