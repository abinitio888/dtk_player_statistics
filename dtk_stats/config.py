from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, field_validator, model_validator


class DateRange(BaseModel):
    from_date: datetime.date
    to_date: datetime.date

    @model_validator(mode="before")
    @classmethod
    def parse_keys(cls, data: dict) -> dict:
        # YAML uses "from" which is a Python keyword — map it
        if "from" in data:
            data["from_date"] = data.pop("from")
        if "to" in data:
            data["to_date"] = data.pop("to")
        return data

    @field_validator("from_date", "to_date", mode="before")
    @classmethod
    def coerce_date(cls, v):
        if isinstance(v, datetime.date):
            return v
        return datetime.date.fromisoformat(str(v))

    @model_validator(mode="after")
    def check_order(self) -> "DateRange":
        if self.from_date > self.to_date:
            raise ValueError(f"period.from ({self.from_date}) must be <= period.to ({self.to_date})")
        return self


class SourceConfig(BaseModel):
    url: str


class PlayerConfig(BaseModel):
    name: str
    sources: List[SourceConfig]


class OutputConfig(BaseModel):
    formats: List[str] = ["csv"]
    directory: str = "./output"

    @field_validator("formats", mode="before")
    @classmethod
    def normalise_formats(cls, v):
        if isinstance(v, str):
            return [v]
        allowed = {"csv", "json"}
        for fmt in v:
            if fmt not in allowed:
                raise ValueError(f"Unsupported format '{fmt}'. Use 'csv' or 'json'.")
        return v


class AppConfig(BaseModel):
    period: DateRange
    output: OutputConfig = OutputConfig()
    players: List[PlayerConfig]


class ConfigError(Exception):
    pass


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    if not raw:
        raise ConfigError(f"Config file is empty: {path}")
    try:
        return AppConfig.model_validate(raw)
    except Exception as e:
        raise ConfigError(f"Invalid config: {e}") from e
