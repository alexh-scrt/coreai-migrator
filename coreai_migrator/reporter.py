"""Report rendering for coreai_migrator.

This module provides the :class:`Reporter` class, which renders a
:class:`~coreai_migrator.models.MigrationReport` in three output formats:

* **rich** – colour-coded terminal tables using the :mod:`rich` library.
* **plain** – plain-text output suitable for log files and CI output.
* **json** – machine-readable JSON for CI/CD pipeline integration.

Typical usage::

    from coreai_migrator.reporter import Reporter
    from coreai_migrator.models import MigrationReport

    reporter = Reporter(output_format="rich")
    reporter.render(migration_report)
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import IO, Literal, Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich import box

from coreai_migrator.models import FileReport, Finding, MigrationReport, Severity

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

OutputFormat = Literal["rich", "plain", "json"]

# ---------------------------------------------------------------------------
# Severity display helpers
# ---------------------------------------------------------------------------

_SEVERITY_BADGE: dict[Severity, str] = {
    Severity.LOW: "[green]LOW[/green]",
    Severity.MEDIUM: "[yellow]MEDIUM[/yellow]",
    Severity.HIGH: "[orange1]HIGH[/orange1]",
    Severity.BREAKING: "[bold red]BREAKING[/bold red]",
}

_SEVERITY_PLAIN: dict[Severity, str] = {
    Severity.LOW: "LOW",
    Severity.MEDIUM: "MEDIUM",
    Severity.HIGH: "HIGH",
    Severity.BREAKING: "BREAKING",
}

_COMPLEXITY_COLOUR: dict[str, str] = {
    "Clean": "bold green",
    "Low": "green",
    "Medium": "yellow",
    "High": "orange1",
    "Breaking": "bold red",
}


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------


class Reporter:
    """Renders a :class:`~coreai_migrator.models.MigrationReport` to various formats.

    Args:
        output_format:   One of ``'rich'``, ``'plain'``, or ``'json'``.
        output_file:     Path to write output to.  ``None`` means stdout.
        show_diffs:      Whether to include unified diffs in the output
                         (default ``True``).
        show_notes:      Whether to include migration notes (default ``True``).
        max_findings:    If set, cap the number of findings shown per file
                         (``None`` means unlimited).
        force_color:     Force rich colour output even when not in a TTY.
    """

    def __init__(
        self,
        output_format: OutputFormat = "rich",
        output_file: Optional[Path] = None,
        show_diffs: bool = True,
        show_notes: bool = True,
        max_findings: Optional[int] = None,
        force_color: bool = False,
    ) -> None:
        self._format = output_format
        self._output_file = output_file
        self._show_diffs = show_diffs
        self._show_notes = show_notes
        self._max_findings = max_findings
        self._force_color = force_color

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, report: MigrationReport) -> None:
        """Render *report* according to the configured output format.

        Output is written to the configured output file, or to stdout if no
        file was provided.

        Args:
            report: The :class:`~coreai_migrator.models.MigrationReport` to
                    render.
        """
        if self._format == "json":
            self._render_json(report)
        elif self._format == "plain":
            self._render_plain(report)
        else:
            self._render_rich(report)

    def render_to_string(self, report: MigrationReport) -> str:
        """Render *report* and return the result as a string instead of writing it.

        Useful in tests and when the caller needs to post-process the output.

        Args:
            report: The migration report to render.

        Returns:
            The rendered output as a plain string (ANSI codes stripped for
            ``'rich'`` format).
        """
        buffer = StringIO()
        if self._format == "json":
            self._write_json(report, buffer)
        elif self._format == "plain":
            self._write_plain(report, buffer)
        else:
            self._write_rich_to_file(report, buffer)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # JSON renderer
    # ------------------------------------------------------------------

    def _render_json(self, report: MigrationReport) -> None:
        """Write JSON-encoded report to the output destination."""
        if self._output_file:
            with self._output_file.open("w", encoding="utf-8") as fh:
                self._write_json(report, fh)
        else:
            self._write_json(report, sys.stdout)

    def _write_json(self, report: MigrationReport, stream: IO[str]) -> None:
        """Serialise *report* to JSON and write to *stream*."""
        data = report.to_dict()
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")

    # ------------------------------------------------------------------
    # Plain-text renderer
    # ------------------------------------------------------------------

    def _render_plain(self, report: MigrationReport) -> None:
        """Write plain-text report to the output destination."""
        if self._output_file:
            with self._output_file.open("w", encoding="utf-8") as fh:
                self._write_plain(report, fh)
        else:
            self._write_plain(report, sys.stdout)

    def _write_plain(self, report: MigrationReport, stream: IO[str]) -> None:
        """Write a plain-text migration report to *stream*."""
        w = stream.write
        sep = "=" * 72
        thin = "-" * 72

        w(f"{sep}\n")
        w("  coreai-migrator Migration Report\n")
        w(f"{sep}\n")
        w(f"  Root path      : {report.root_path}\n")
        w(f"  Scanned files  : {report.scanned_files}\n")
        w(f"  Affected files : {report.affected_files}\n")
        w(f"  Total findings : {report.total_findings}\n")
        w(f"  Complexity     : {report.complexity_label} "
          f"(score: {report.total_complexity_score})\n")
        w(f"{sep}\n\n")

        if not report.file_reports:
            w("No deprecated Core ML API usages found. Your codebase is ready!\n")
            return

        for file_report in report.file_reports:
            w(f"{thin}\n")
            w(f"File    : {file_report.file_path}\n")
            w(f"Language: {file_report.language}\n")
            w(f"Findings: {file_report.finding_count}  "
              f"Complexity: {file_report.complexity_score}")
            if file_report.max_severity:
                w(f"  Max severity: {_SEVERITY_PLAIN[file_report.max_severity]}")
            w("\n")
            w(f"{thin}\n")

            findings = file_report.findings
            if self._max_findings is not None:
                findings = findings[: self._max_findings]

            for idx, finding in enumerate(findings, start=1):
                w(f"  [{idx}] Line {finding.line_number}, Col {finding.column}\n")
                w(f"      Deprecated : {finding.deprecated_api}\n")
                w(f"      Replacement: {finding.replacement_api}\n")
                w(f"      Severity   : {_SEVERITY_PLAIN[finding.severity]}\n")
                w(f"      Original   : {finding.original_line.strip()}\n")
                w(f"      Suggested  : {finding.suggested_line.strip()}\n")
                if self._show_notes and finding.migration_note:
                    # Wrap note at ~66 chars
                    note = finding.migration_note
                    w(f"      Note       : {note}\n")
                if self._show_diffs and finding.diff_lines:
                    w("      Diff:\n")
                    for diff_line in finding.diff_lines:
                        w(f"        {diff_line}\n")
                w("\n")

            if self._max_findings is not None and len(file_report.findings) > self._max_findings:
                remaining = len(file_report.findings) - self._max_findings
                w(f"  ... and {remaining} more finding(s) not shown.\n\n")

        w(f"{sep}\n")
        w(f"Summary: {report.total_findings} finding(s) across "
          f"{report.affected_files} file(s).  "
          f"Overall complexity: {report.complexity_label} "
          f"({report.total_complexity_score} pts)\n")
        w(f"{sep}\n")

    # ------------------------------------------------------------------
    # Rich terminal renderer
    # ------------------------------------------------------------------

    def _render_rich(self, report: MigrationReport) -> None:
        """Write rich colour-coded output to the terminal or output file."""
        if self._output_file:
            with self._output_file.open("w", encoding="utf-8") as fh:
                self._write_rich_to_file(report, fh)
        else:
            console = Console(
                force_terminal=self._force_color,
                highlight=False,
            )
            self._write_rich_to_console(report, console)

    def _write_rich_to_file(self, report: MigrationReport, stream: IO[str]) -> None:
        """Render rich output to a file-like stream (ANSI stripped)."""
        console = Console(
            file=stream,
            force_terminal=False,
            no_color=True,
            highlight=False,
        )
        self._write_rich_to_console(report, console)

    def _write_rich_to_console(self, report: MigrationReport, console: Console) -> None:
        """Render the full migration report to *console*."""
        # ---- Header panel ------------------------------------------------
        complexity_colour = _COMPLEXITY_COLOUR.get(
            report.complexity_label, "white"
        )
        header_text = Text()
        header_text.append("coreai-migrator", style="bold cyan")
        header_text.append(" Migration Report\n", style="bold")
        header_text.append(f"Root: ", style="dim")
        header_text.append(str(report.root_path), style="cyan")
        header_text.append("\n")
        header_text.append(f"Scanned: ", style="dim")
        header_text.append(str(report.scanned_files), style="bold")
        header_text.append(" files  ", style="dim")
        header_text.append(f"Affected: ", style="dim")
        header_text.append(str(report.affected_files), style="bold")
        header_text.append(" files  ", style="dim")
        header_text.append(f"Findings: ", style="dim")
        header_text.append(str(report.total_findings), style="bold")
        header_text.append("\n")
        header_text.append("Overall complexity: ", style="dim")
        header_text.append(
            f"{report.complexity_label} ({report.total_complexity_score} pts)",
            style=complexity_colour,
        )

        console.print(
            Panel(header_text, title="[bold]Migration Summary[/bold]", border_style="cyan")
        )

        if not report.file_reports:
            console.print(
                "[bold green]✓ No deprecated Core ML API usages found. "
                "Your codebase is ready![/bold green]"
            )
            return

        # ---- Per-file summary table --------------------------------------
        summary_table = Table(
            title="Files with Deprecated API Usage",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            expand=False,
        )
        summary_table.add_column("File", style="cyan", no_wrap=False, ratio=5)
        summary_table.add_column("Lang", style="dim", justify="center", width=6)
        summary_table.add_column("Findings", justify="right", width=9)
        summary_table.add_column("Complexity", justify="right", width=11)
        summary_table.add_column("Max Severity", justify="center", width=13)

        for fr in report.file_reports:
            max_sev = fr.max_severity
            sev_display = (
                _SEVERITY_BADGE.get(max_sev, str(max_sev))
                if max_sev
                else "-"
            )
            summary_table.add_row(
                str(fr.file_path),
                fr.language,
                str(fr.finding_count),
                str(fr.complexity_score),
                sev_display,
            )

        console.print(summary_table)
        console.print()

        # ---- Detailed findings per file ----------------------------------
        for file_report in report.file_reports:
            self._render_rich_file_report(file_report, console)

        # ---- Footer summary ----------------------------------------------
        footer = Text()
        footer.append(f"Total: ", style="dim")
        footer.append(str(report.total_findings), style="bold")
        footer.append(" finding(s) across ", style="dim")
        footer.append(str(report.affected_files), style="bold")
        footer.append(" file(s).  Overall complexity: ", style="dim")
        footer.append(
            f"{report.complexity_label} ({report.total_complexity_score} pts)",
            style=complexity_colour,
        )
        console.print(
            Panel(footer, title="[bold]Summary[/bold]", border_style="dim")
        )

    def _render_rich_file_report(
        self, file_report: FileReport, console: Console
    ) -> None:
        """Render a single :class:`~coreai_migrator.models.FileReport` to *console*."""
        max_sev = file_report.max_severity
        sev_badge = _SEVERITY_BADGE.get(max_sev, "-") if max_sev else "-"
        title = (
            f"[cyan]{file_report.file_path}[/cyan]  "
            f"[dim]{file_report.language}[/dim]  "
            f"{sev_badge}  "
            f"[dim]complexity:[/dim] [bold]{file_report.complexity_score}[/bold]"
        )

        findings_table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold",
            expand=True,
            padding=(0, 1),
        )
        findings_table.add_column("Line", justify="right", style="dim", width=6)
        findings_table.add_column("Col", justify="right", style="dim", width=5)
        findings_table.add_column("Deprecated API", style="red", ratio=3)
        findings_table.add_column("Replacement API", style="green", ratio=3)
        findings_table.add_column("Severity", justify="center", width=12)
        findings_table.add_column("Score", justify="right", width=6)

        findings = file_report.findings
        if self._max_findings is not None:
            findings = findings[: self._max_findings]

        for finding in findings:
            findings_table.add_row(
                str(finding.line_number),
                str(finding.column),
                finding.deprecated_api,
                finding.replacement_api,
                _SEVERITY_BADGE.get(finding.severity, str(finding.severity)),
                str(finding.complexity_score),
            )

        console.print(
            Panel(findings_table, title=title, border_style="blue")
        )

        # ---- Per-finding details (notes + diffs) -------------------------
        for finding in findings:
            self._render_rich_finding_detail(finding, console)

        if self._max_findings is not None and len(file_report.findings) > self._max_findings:
            remaining = len(file_report.findings) - self._max_findings
            console.print(
                f"  [dim]... and {remaining} more finding(s) not shown.[/dim]\n"
            )

    def _render_rich_finding_detail(self, finding: Finding, console: Console) -> None:
        """Render detailed information (note + diff) for a single finding."""
        header = (
            f"[dim]Line {finding.line_number}[/dim]  "
            f"[red]{finding.deprecated_api}[/red] → "
            f"[green]{finding.replacement_api}[/green]"
        )

        detail_parts: list[str] = []

        # Code change line
        detail_parts.append(
            f"[dim]Before:[/dim] [red]{finding.original_line.strip()}[/red]"
        )
        detail_parts.append(
            f"[dim]After: [/dim] [green]{finding.suggested_line.strip()}[/green]"
        )

        if self._show_notes and finding.migration_note:
            detail_parts.append(f"[dim]Note:  [/dim] {finding.migration_note}")

        note_text = Text.from_markup("\n".join(detail_parts))
        console.print(
            Panel(
                note_text,
                title=header,
                border_style="dim",
                padding=(0, 2),
            )
        )

        if self._show_diffs and finding.diff_lines:
            diff_text = "\n".join(finding.diff_lines)
            syntax = Syntax(
                diff_text,
                "diff",
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
            )
            console.print(syntax)

        console.print()


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def render_rich(
    report: MigrationReport,
    output_file: Optional[Path] = None,
    show_diffs: bool = True,
    show_notes: bool = True,
    max_findings: Optional[int] = None,
) -> None:
    """Convenience function: render *report* as a rich terminal table.

    Args:
        report:       The migration report to render.
        output_file:  Write output here instead of stdout.
        show_diffs:   Include unified diffs.
        show_notes:   Include migration notes.
        max_findings: Cap findings shown per file.
    """
    reporter = Reporter(
        output_format="rich",
        output_file=output_file,
        show_diffs=show_diffs,
        show_notes=show_notes,
        max_findings=max_findings,
    )
    reporter.render(report)


def render_plain(
    report: MigrationReport,
    output_file: Optional[Path] = None,
    show_diffs: bool = True,
    show_notes: bool = True,
    max_findings: Optional[int] = None,
) -> None:
    """Convenience function: render *report* as plain text.

    Args:
        report:       The migration report to render.
        output_file:  Write output here instead of stdout.
        show_diffs:   Include unified diffs.
        show_notes:   Include migration notes.
        max_findings: Cap findings shown per file.
    """
    reporter = Reporter(
        output_format="plain",
        output_file=output_file,
        show_diffs=show_diffs,
        show_notes=show_notes,
        max_findings=max_findings,
    )
    reporter.render(report)


def render_json(
    report: MigrationReport,
    output_file: Optional[Path] = None,
) -> None:
    """Convenience function: render *report* as JSON.

    Args:
        report:      The migration report to render.
        output_file: Write output here instead of stdout.
    """
    reporter = Reporter(
        output_format="json",
        output_file=output_file,
    )
    reporter.render(report)


def compute_complexity_label(score: int) -> str:
    """Return the human-readable complexity label for a raw *score*.

    This mirrors :attr:`~coreai_migrator.models.MigrationReport.complexity_label`
    and is provided here as a standalone utility for callers that only have a
    numeric score.

    Args:
        score: Total complexity score (sum of finding weights).

    Returns:
        One of ``'Clean'``, ``'Low'``, ``'Medium'``, ``'High'``, or
        ``'Breaking'``.
    """
    if score == 0:
        return "Clean"
    if score <= 10:
        return "Low"
    if score <= 40:
        return "Medium"
    if score <= 100:
        return "High"
    return "Breaking"
