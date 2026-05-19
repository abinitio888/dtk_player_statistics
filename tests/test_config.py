import datetime
import textwrap
from pathlib import Path

import pytest

from dtk_stats.config import ConfigError, load_config


def write_yaml(tmp_path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_valid_config(tmp_path):
    path = write_yaml(tmp_path, """
        period:
          from: "2024-01-01"
          to: "2024-12-31"
        players:
          - name: "Vincent Englund"
            sources:
              - url: "https://te.tournamentsoftware.com/player-profile/ABC"
    """)
    cfg = load_config(path)
    assert cfg.period.from_date == datetime.date(2024, 1, 1)
    assert cfg.period.to_date == datetime.date(2024, 12, 31)
    assert len(cfg.players) == 1
    assert cfg.players[0].name == "Vincent Englund"
    assert cfg.players[0].sources[0].url == "https://te.tournamentsoftware.com/player-profile/ABC"


def test_default_output(tmp_path):
    path = write_yaml(tmp_path, """
        period:
          from: "2024-01-01"
          to: "2024-06-30"
        players:
          - name: "Player One"
            sources:
              - url: "https://example.com/player/1"
    """)
    cfg = load_config(path)
    assert cfg.output.formats == ["csv"]
    assert cfg.output.directory == "./output"


def test_invalid_period_order(tmp_path):
    path = write_yaml(tmp_path, """
        period:
          from: "2024-12-31"
          to: "2024-01-01"
        players:
          - name: "Player"
            sources:
              - url: "https://example.com"
    """)
    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_multiple_players(tmp_path):
    path = write_yaml(tmp_path, """
        period:
          from: "2024-01-01"
          to: "2024-09-30"
        output:
          formats: [csv, json]
          directory: ./results
        players:
          - name: "Player A"
            sources:
              - url: "https://example.com/a"
          - name: "Player B"
            sources:
              - url: "https://example.com/b1"
              - url: "https://example.com/b2"
    """)
    cfg = load_config(path)
    assert cfg.period.from_date == datetime.date(2024, 1, 1)
    assert len(cfg.players) == 2
    assert cfg.output.formats == ["csv", "json"]
    assert cfg.output.directory == "./results"
    assert len(cfg.players[1].sources) == 2
