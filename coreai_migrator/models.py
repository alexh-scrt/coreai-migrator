"""Data models for coreai_migrator.

Defines the core dataclasses used throughout the migration pipeline:
- Finding: A single deprecated API usage found in a source file.
- FileReport: Aggregated findings and complexity score for a single file.
- MigrationReport: Top-level report aggregating all file reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(str, Enum):
    """Severity / migration complexity level for a deprecated API."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BREAKING = "breaking"

    def __str__(self) -> str:  # noqa: D105
        return self.value

    @property
    def weight(self) -> int:
        """Numeric weight used when computing complexity scores."""
        return {
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 4,
            Severity.BREAKING: 8,
        }[self]

    @property
    def rich_style(self) -> str:
        """Rich markup style string for terminal colour-coding."""
        return {
            Severity.LOW: "green",
            Severity.MEDIUM: "yellow",
            Severity.HIGH: "orange1",
            Severity.BREAKING: "bold red",
        }[self]


@dataclass
class Finding:
    """A single occurrence of a deprecated Core ML API in a source file.

    Attributes:
        file_path:        Absolute or project-relative path of the source file.
        line_number:      1-based line number where the deprecated call appears.
        column:           0-based column offset where the match starts (best-effort).
        deprecated_api:   The deprecated Core ML symbol that was matched.
        replacement_api:  The recommended Core AI symbol to use instead.
        original_line:    The raw source line as it appears in the file.
        suggested_line:   The source line after applying the replacement template.
        severity:         Migration complexity level.
        migration_note:   Human-readable explanation of what to change and why.
        diff_lines:       Unified diff lines for this finding (populated by diff_builder).
    """

    file_path: Path
    line_number: int
    column: int
    deprecated_api: str
    replacement_api: str
    original_line: str
    suggested_line: str
    severity: Severity
    migration_note: str
    diff_lines: list[str] = field(default_factory=list)

    @property
    def complexity_score(self) -> int:
        """Numeric complexity contribution of this single finding."""
        return self.severity.weight

    def to_dict(self) -> dict:
        """Serialise the finding to a plain dictionary suitable for JSON output."""
        return {
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "column": self.column,
            "deprecated_api": self.deprecated_api,
            "replacement_api": self.replacement_api,
            "original_line": self.original_line,
            "suggested_line": self.suggested_line,
            "severity": str(self.severity),
            "migration_note": self.migration_note,
            "complexity_score": self.complexity_score,
            "diff_lines": self.diff_lines,
        }


@dataclass
class FileReport:
    """Aggregated migration findings for a single source file.

    Attributes:
        file_path:        Path to the source file.
        findings:         Ordered list of Finding objects (by line number).
        language:         Detected source language, e.g. ``'swift'`` or ``'objc'``.
    """

    file_path: Path
    findings: list[Finding] = field(default_factory=list)
    language: str = "unknown"

    @property
    def complexity_score(self) -> int:
        """Sum of all per-finding complexity weights for this file."""
        return sum(f.complexity_score for f in self.findings)

    @property
    def finding_count(self) -> int:
        """Total number of findings in this file."""
        return len(self.findings)

    @property
    def max_severity(self) -> Optional[Severity]:
        """Highest severity level found in this file, or ``None`` if no findings."""
        if not self.findings:
            return None
        order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.BREAKING]
        return max(self.findings, key=lambda f: order.index(f.severity)).severity

    def findings_by_severity(self, severity: Severity) -> list[Finding]:
        """Return only the findings that match the given severity level."""
        return [f for f in self.findings if f.severity == severity]

    def to_dict(self) -> dict:
        """Serialise the file report to a plain dictionary suitable for JSON output."""
        return {
            "file_path": str(self.file_path),
            "language": self.language,
            "finding_count": self.finding_count,
            "complexity_score": self.complexity_score,
            "max_severity": str(self.max_severity) if self.max_severity else None,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class MigrationReport:
    """Top-level report aggregating findings across an entire codebase scan.

    Attributes:
        root_path:     The directory that was scanned.
        file_reports:  One FileReport per file that contained findings.
        scanned_files: Total number of source files examined (including clean ones).
    """

    root_path: Path
    file_reports: list[FileReport] = field(default_factory=list)
    scanned_files: int = 0

    @property
    def total_findings(self) -> int:
        """Total number of deprecated API usages found across all files."""
        return sum(r.finding_count for r in self.file_reports)

    @property
    def total_complexity_score(self) -> int:
        """Project-wide sum of all complexity weights."""
        return sum(r.complexity_score for r in self.file_reports)

    @property
    def affected_files(self) -> int:
        """Number of files that contained at least one finding."""
        return len(self.file_reports)

    @property
    def complexity_label(self) -> str:
        """Human-readable overall complexity bucket.

        Thresholds:
        - 0        → "Clean"
        - 1-10     → "Low"
        - 11-40    → "Medium"
        - 41-100   → "High"
        - >100     → "Breaking"
        """
        score = self.total_complexity_score
        if score == 0:
            return "Clean"
        if score <= 10:
            return "Low"
        if score <= 40:
            return "Medium"
        if score <= 100:
            return "High"
        return "Breaking"

    def findings_by_severity(self, severity: Severity) -> list[Finding]:
        """Return all findings across all files that match the given severity."""
        result: list[Finding] = []
        for report in self.file_reports:
            result.extend(report.findings_by_severity(severity))
        return result

    def all_findings(self) -> list[Finding]:
        """Return a flat list of every Finding across all file reports."""
        result: list[Finding] = []
        for report in self.file_reports:
            result.extend(report.findings)
        return result

    def to_dict(self) -> dict:
        """Serialise the full migration report to a plain dictionary for JSON output."""
        return {
            "root_path": str(self.root_path),
            "scanned_files": self.scanned_files,
            "affected_files": self.affected_files,
            "total_findings": self.total_findings,
            "total_complexity_score": self.total_complexity_score,
            "complexity_label": self.complexity_label,
            "file_reports": [r.to_dict() for r in self.file_reports],
        }
