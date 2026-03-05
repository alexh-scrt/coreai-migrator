"""Regex-based analyzer engine for coreai_migrator.

This module provides the :class:`Analyzer` class, which reads Swift and
Objective-C source files line by line, matches every line against the
deprecated Core ML API patterns defined in :mod:`coreai_migrator.mappings`,
and produces :class:`~coreai_migrator.models.Finding` objects.

Multiple patterns may match the same line (e.g. a line that both contains
``import CoreML`` and is part of a more complex expression is unusual, but
the engine de-duplicates findings at the same location for the same API).

Typical usage::

    from coreai_migrator.analyzer import Analyzer
    from coreai_migrator.scanner import SourceFile
    from pathlib import Path

    analyzer = Analyzer()
    source_file = SourceFile(path=Path("App/Model.swift"), language="swift")
    file_report = analyzer.analyze_file(source_file)
    for finding in file_report.findings:
        print(finding.line_number, finding.deprecated_api)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from coreai_migrator.mappings import APIMapping, get_all_patterns
from coreai_migrator.models import FileReport, Finding, MigrationReport, Severity
from coreai_migrator.scanner import SourceFile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_template(original_line: str, match: re.Match, mapping: APIMapping) -> str:
    """Apply the replacement template to produce the suggested source line.

    The template uses a straightforward string replacement of the matched
    text with the mapping's template string.  This preserves surrounding
    code (indentation, semicolons, trailing comments, etc.).

    Args:
        original_line: The raw source line as read from the file.
        match:         The regex match object for the deprecated pattern.
        mapping:       The :class:`~coreai_migrator.mappings.APIMapping`
                       containing the replacement template.

    Returns:
        The source line with the deprecated fragment replaced by the
        template string.  If the substitution raises any exception the
        original line is returned unchanged.
    """
    try:
        matched_text = match.group(0)
        # Use re.sub for the specific matched region so we only replace the
        # first occurrence of the exact matched text on this line.
        suggested = original_line.replace(matched_text, mapping.template, 1)
        return suggested
    except Exception as exc:  # pragma: no cover
        logger.debug(
            "Template application failed for '%s': %s", mapping.deprecated_api, exc
        )
        return original_line


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class Analyzer:
    """Matches deprecated Core ML API patterns in Swift and Objective-C source files.

    The analyzer iterates over every line in a source file and tests it against
    each compiled regex pattern from the mapping table.  When a pattern matches,
    a :class:`~coreai_migrator.models.Finding` is created capturing the location,
    deprecated symbol, replacement suggestion, and severity.

    Args:
        severity_filter: If given, only findings at or above this severity level
                         are recorded.  ``None`` means all findings are kept.
        patterns:        Pre-computed list of ``(pattern, mapping)`` tuples.
                         Defaults to :func:`~coreai_migrator.mappings.get_all_patterns`.
    """

    _SEVERITY_ORDER: list[Severity] = [
        Severity.LOW,
        Severity.MEDIUM,
        Severity.HIGH,
        Severity.BREAKING,
    ]

    def __init__(
        self,
        severity_filter: Optional[Severity] = None,
        patterns: Optional[list[tuple[re.Pattern, APIMapping]]] = None,
    ) -> None:
        self._severity_filter = severity_filter
        self._patterns: list[tuple[re.Pattern, APIMapping]] = (
            patterns if patterns is not None else get_all_patterns()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_file(self, source_file: SourceFile) -> FileReport:
        """Analyze a single source file and return a :class:`~coreai_migrator.models.FileReport`.

        Args:
            source_file: A :class:`~coreai_migrator.scanner.SourceFile` as
                         produced by the :class:`~coreai_migrator.scanner.Scanner`.

        Returns:
            A :class:`~coreai_migrator.models.FileReport` containing all
            findings (sorted by line number).  If the file cannot be read,
            an empty report is returned and a warning is logged.
        """
        try:
            content = source_file.path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read file %s: %s", source_file.path, exc)
            return FileReport(
                file_path=source_file.path,
                findings=[],
                language=source_file.language,
            )

        findings = self._analyze_content(
            content=content,
            file_path=source_file.path,
            language=source_file.language,
        )

        return FileReport(
            file_path=source_file.path,
            findings=findings,
            language=source_file.language,
        )

    def analyze_content(
        self,
        content: str,
        file_path: Path,
        language: str = "swift",
    ) -> FileReport:
        """Analyze raw source code text and return a :class:`~coreai_migrator.models.FileReport`.

        This is useful in tests where the content is already in memory rather
        than stored on disk.

        Args:
            content:   Full source code as a string.
            file_path: Logical file path to associate with the findings
                       (does not need to exist on disk).
            language:  Source language label (``'swift'`` or ``'objc'``).

        Returns:
            A :class:`~coreai_migrator.models.FileReport`.
        """
        findings = self._analyze_content(
            content=content,
            file_path=Path(file_path),
            language=language,
        )
        return FileReport(
            file_path=Path(file_path),
            findings=findings,
            language=language,
        )

    def analyze_files(
        self,
        source_files: list[SourceFile],
    ) -> list[FileReport]:
        """Analyze multiple source files and return a list of file reports.

        Only files that contain at least one finding are included in the result.

        Args:
            source_files: List of :class:`~coreai_migrator.scanner.SourceFile`
                          objects to analyse.

        Returns:
            List of :class:`~coreai_migrator.models.FileReport` objects,
            one per file that had findings, sorted by file path.
        """
        reports: list[FileReport] = []
        for sf in source_files:
            report = self.analyze_file(sf)
            if report.findings:
                reports.append(report)
        reports.sort(key=lambda r: str(r.file_path))
        return reports

    def build_migration_report(
        self,
        source_files: list[SourceFile],
        root_path: Path,
    ) -> MigrationReport:
        """Analyze all *source_files* and assemble a top-level :class:`~coreai_migrator.models.MigrationReport`.

        Args:
            source_files: All source files discovered by the scanner.
            root_path:    The root directory of the scan.

        Returns:
            A fully populated :class:`~coreai_migrator.models.MigrationReport`.
        """
        file_reports = self.analyze_files(source_files)
        return MigrationReport(
            root_path=root_path,
            file_reports=file_reports,
            scanned_files=len(source_files),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _analyze_content(
        self,
        content: str,
        file_path: Path,
        language: str,
    ) -> list[Finding]:
        """Core analysis loop: match patterns against each source line.

        A *seen* set prevents multiple findings for the exact same
        (line_number, deprecated_api) pair, which can happen when more than
        one overlapping pattern matches the same token.

        Args:
            content:   Full source code text.
            file_path: File path to embed in findings.
            language:  Source language label.

        Returns:
            Sorted list of :class:`~coreai_migrator.models.Finding` objects.
        """
        lines = content.splitlines(keepends=True)
        findings: list[Finding] = []
        # Track (line_number, deprecated_api) pairs already recorded
        seen: set[tuple[int, str]] = set()

        for line_index, raw_line in enumerate(lines):
            line_number = line_index + 1  # 1-based

            for pattern, mapping in self._patterns:
                # Skip if this (line, api) pair was already recorded
                dedup_key = (line_number, mapping.deprecated_api)
                if dedup_key in seen:
                    continue

                match = pattern.search(raw_line)
                if match is None:
                    continue

                # Apply severity filter
                if not self._passes_filter(mapping.severity):
                    continue

                suggested_line = _apply_template(raw_line, match, mapping)

                finding = Finding(
                    file_path=file_path,
                    line_number=line_number,
                    column=match.start(),
                    deprecated_api=mapping.deprecated_api,
                    replacement_api=mapping.replacement_api,
                    original_line=raw_line.rstrip("\n"),
                    suggested_line=suggested_line.rstrip("\n"),
                    severity=mapping.severity,
                    migration_note=mapping.migration_note,
                    diff_lines=[],  # populated later by diff_builder
                )
                findings.append(finding)
                seen.add(dedup_key)

        findings.sort(key=lambda f: (f.line_number, f.deprecated_api))
        return findings

    def _passes_filter(self, severity: Severity) -> bool:
        """Return ``True`` if *severity* meets the configured severity filter.

        Args:
            severity: The severity of the candidate finding.

        Returns:
            ``True`` if the finding should be included in the report.
        """
        if self._severity_filter is None:
            return True
        return (
            self._SEVERITY_ORDER.index(severity)
            >= self._SEVERITY_ORDER.index(self._severity_filter)
        )


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


def analyze_source_files(
    source_files: list[SourceFile],
    root_path: Path,
    severity_filter: Optional[Severity] = None,
) -> MigrationReport:
    """Convenience function: analyse a list of source files and return a migration report.

    Args:
        source_files:    Files to analyse (typically produced by
                         :func:`~coreai_migrator.scanner.scan_path`).
        root_path:       Root directory of the scanned project.
        severity_filter: If specified, exclude findings below this severity.

    Returns:
        A fully populated :class:`~coreai_migrator.models.MigrationReport`.
    """
    analyzer = Analyzer(severity_filter=severity_filter)
    return analyzer.build_migration_report(
        source_files=source_files,
        root_path=root_path,
    )
