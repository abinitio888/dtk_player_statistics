from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from dtk_stats.config import AppConfig, ConfigError, DateRange, load_config
from dtk_stats.exporter import export_csv, export_json
from dtk_stats.extractor import extract_matches
from dtk_stats.filter import filter_by_period, filter_byes
from dtk_stats.itf_extractor import fetch_itf_matches, is_itf_url
from dtk_stats.models import Match
from dtk_stats.scraper import fetch_page

app = typer.Typer(
    name="dtk-stats",
    help="Extract tennis player match statistics from tournamentsoftware.com",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s", level=level)


def _year_urls(base_url: str, period: DateRange) -> List[str]:
    """
    Expand a player profile URL into per-year tournament URLs.

    e.g. https://svtf.tournamentsoftware.com/player-profile/{UUID}
      → https://svtf.tournamentsoftware.com/player-profile/{UUID}/tournaments/2024
         https://svtf.tournamentsoftware.com/player-profile/{UUID}/tournaments/2025
    """
    base = base_url.rstrip("/")
    return [
        f"{base}/tournaments/{year}"
        for year in range(period.from_date.year, period.to_date.year + 1)
    ]


@app.command()
def fetch(
    config: Path = typer.Option(
        Path("config.yaml"), "--config", "-c", help="Path to YAML config file"
    ),
    players: Optional[List[str]] = typer.Option(
        None, "--player", "-p", help="Filter to player name (repeatable)"
    ),
    from_date: Optional[str] = typer.Option(
        None, "--from-date", help="Override period start date (YYYY-MM-DD)"
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to-date", help="Override period end date (YYYY-MM-DD)"
    ),
    fmt: Optional[str] = typer.Option(
        None, "--format", help="Output format: csv, json, or both"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Override output directory"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be fetched, no HTTP"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Scrape match data for all configured players and export to CSV/JSON."""
    _setup_logging(verbose)

    try:
        cfg = load_config(config)
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1)

    # Apply CLI overrides
    if output_dir:
        cfg.output.directory = str(output_dir)
    if fmt:
        if fmt == "both":
            cfg.output.formats = ["csv", "json"]
        elif fmt in ("csv", "json"):
            cfg.output.formats = [fmt]
        else:
            console.print(f"[red]Invalid format:[/red] {fmt!r}. Use 'csv', 'json', or 'both'.")
            raise typer.Exit(1)

    # Filter players
    target_players = cfg.players
    if players:
        pl_lower = [p.lower() for p in players]
        target_players = [p for p in cfg.players if p.name.lower() in pl_lower]
        if not target_players:
            console.print(f"[yellow]No players matched:[/yellow] {', '.join(players)}")
            raise typer.Exit(1)

    # Build date overrides
    override_period: Optional[DateRange] = None
    if from_date or to_date:
        try:
            fd = datetime.date.fromisoformat(from_date) if from_date else None
            td = datetime.date.fromisoformat(to_date) if to_date else None
        except ValueError as e:
            console.print(f"[red]Invalid date:[/red] {e}")
            raise typer.Exit(1)

    out_root = Path(cfg.output.directory)

    # Resolve period (config value, overridden by CLI flags)
    period = cfg.period
    if from_date:
        period = DateRange(from_date=fd, to_date=period.to_date)
    if to_date:
        period = DateRange(from_date=period.from_date, to_date=td)

    all_matches: List[Match] = []

    for player_cfg in target_players:
        for source in player_cfg.sources:
            if is_itf_url(source.url):
                years = list(range(period.from_date.year, period.to_date.year + 1))
                if dry_run:
                    for year in years:
                        console.print(
                            f"[dim]DRY RUN[/dim] Would fetch ITF API: "
                            f"[cyan]{source.url}[/cyan] year={year} "
                            f"for [bold]{player_cfg.name}[/bold]"
                        )
                    continue

                console.print(
                    f"Fetching ITF [cyan]{source.url}[/cyan] "
                    f"(years {period.from_date.year}–{period.to_date.year}) ..."
                )
                try:
                    raw_matches = fetch_itf_matches(source.url, player_cfg.name, years)
                except Exception as e:
                    console.print(f"  [red]ITF fetch failed:[/red] {e}")
                    continue

                filtered = filter_byes(filter_by_period(raw_matches, period))
                console.print(
                    f"  Found [green]{len(raw_matches)}[/green] matches, "
                    f"[green]{len(filtered)}[/green] in period"
                )
                all_matches.extend(filtered)
            else:
                year_urls = _year_urls(source.url, period)

                for url in year_urls:
                    if dry_run:
                        console.print(
                            f"[dim]DRY RUN[/dim] Would fetch: [cyan]{url}[/cyan] "
                            f"for [bold]{player_cfg.name}[/bold]"
                        )
                        continue

                    console.print(f"Fetching [cyan]{url}[/cyan] ...")
                    try:
                        html = fetch_page(url)
                    except Exception as e:
                        console.print(f"  [red]Fetch failed:[/red] {e}")
                        continue

                    raw_matches = extract_matches(html, player_cfg.name, url)
                    filtered = filter_byes(filter_by_period(raw_matches, period))
                    console.print(
                        f"  Found [green]{len(raw_matches)}[/green] matches, "
                        f"[green]{len(filtered)}[/green] in period"
                    )
                    all_matches.extend(filtered)

    if dry_run or not all_matches:
        return

    # Write one file per format containing all players
    stem = f"matches_{period.from_date}_{period.to_date}"
    for fmt_name in cfg.output.formats:
        out_path = out_root / f"{stem}.{fmt_name}"
        if fmt_name == "csv":
            export_csv(all_matches, out_path)
        else:
            export_json(all_matches, out_path)
        console.print(f"[bold green]Wrote {len(all_matches)} matches →[/bold green] {out_path}")

    console.print(f"\n[bold]Done.[/bold] Total matches: [green]{len(all_matches)}[/green]")


@app.command(name="validate-config")
def validate_config(
    config: Path = typer.Option(
        Path("config.yaml"), "--config", "-c", help="Path to YAML config file"
    ),
) -> None:
    """Validate the config file without fetching any data."""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1)

    console.print(
        f"[green]Config valid.[/green] {len(cfg.players)} player(s) | "
        f"Period: {cfg.period.from_date} → {cfg.period.to_date}\n"
    )

    t = Table("Player", "URLs to fetch")
    for p in cfg.players:
        all_urls = []
        for s in p.sources:
            if is_itf_url(s.url):
                years = list(range(cfg.period.from_date.year, cfg.period.to_date.year + 1))
                all_urls.append(f"{s.url} [ITF API, years: {', '.join(map(str, years))}]")
            else:
                all_urls.extend(_year_urls(s.url, cfg.period))
        t.add_row(p.name, "\n".join(all_urls))
    console.print(t)
