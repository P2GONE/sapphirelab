"""
테스트 결과를 JSON 저장 + Rich 콘솔 리포트로 출력.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box

from runner.image_runner import TestResult

console = Console(highlight=False, emoji=False)


def save_results(results: list[TestResult], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"image_fuzz_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    return path


def print_image_summary(results: list[TestResult]) -> None:
    total    = len(results)
    errors   = sum(1 for r in results if r.error)
    bypassed = sum(1 for r in results if r.bypassed and not r.error)
    blocked  = total - bypassed - errors

    console.print("\n")
    console.rule("[bold red]Image Fuzzer — Results Summary[/bold red]")

    # Per-strategy breakdown
    by_strategy: dict[str, list[TestResult]] = defaultdict(list)
    for r in results:
        by_strategy[r.strategy].append(r)

    strat_table = Table(title="By Mutation Strategy", box=box.SIMPLE_HEAVY)
    strat_table.add_column("Strategy",  style="cyan", min_width=32)
    strat_table.add_column("Total",  justify="right")
    strat_table.add_column("Bypass", justify="right", style="red")
    strat_table.add_column("Blocked",justify="right", style="green")
    strat_table.add_column("Error",  justify="right", style="yellow")
    strat_table.add_column("Bypass%",justify="right")

    for strategy, rs in sorted(by_strategy.items()):
        t    = len(rs)
        b    = sum(1 for r in rs if r.bypassed and not r.error)
        bl   = sum(1 for r in rs if not r.bypassed and not r.error)
        e    = sum(1 for r in rs if r.error)
        rate = f"{b / t * 100:.0f}%" if t else "-"
        strat_table.add_row(strategy, str(t), str(b), str(bl), str(e), rate)

    console.print(strat_table)

    # Per-payload breakdown
    by_payload: dict[str, list[TestResult]] = defaultdict(list)
    for r in results:
        by_payload[r.payload_id].append(r)

    payload_table = Table(title="By Payload", box=box.SIMPLE_HEAVY)
    payload_table.add_column("Payload ID", style="cyan")
    payload_table.add_column("Category",   style="magenta")
    payload_table.add_column("Severity",   style="yellow")
    payload_table.add_column("Total",   justify="right")
    payload_table.add_column("Bypass",  justify="right", style="red")
    payload_table.add_column("Bypass%", justify="right")

    for pid, rs in sorted(by_payload.items()):
        t        = len(rs)
        b        = sum(1 for r in rs if r.bypassed and not r.error)
        category = rs[0].payload_category if rs else ""
        severity = rs[0].payload_severity if rs else ""
        rate     = f"{b / t * 100:.0f}%" if t else "-"
        payload_table.add_row(pid, category, severity, str(t), str(b), rate)

    console.print(payload_table)

    # Overall stats
    bypass_rate = bypassed / (total - errors) * 100 if (total - errors) > 0 else 0
    console.print(
        f"\nTotal: {total}  |  "
        f"[red]Bypassed: {bypassed}[/red]  |  "
        f"[green]Blocked: {blocked}[/green]  |  "
        f"[yellow]Errors: {errors}[/yellow]  |  "
        f"Bypass rate: [bold]{bypass_rate:.1f}%[/bold]"
    )

    # Bypassed detail
    bypassed_results = [r for r in results if r.bypassed and not r.error]
    if bypassed_results:
        console.print("\n[bold red]Bypassed cases:[/bold red]")
        for r in bypassed_results:
            console.print(
                f"  [red]{r.payload_id}[/red] / [cyan]{r.strategy}[/cyan]"
                f" — {r.bypass_reason}"
            )
            preview = r.response[:120].replace("\n", " ")
            console.print(f"    Response: {preview}...")
