"""Unified diff generation for coreai_migrator.

This module provides the :class:`DiffBuilder` class, which takes
:class:`~coreai_migrator.models.Finding` objects (or entire
:class:`~coreai_migrator.models.FileReport` objects) and generates unified
diff lines using :mod:`difflib`.  The diffs are stored back onto the
finding's ``diff_lines`` attribute so they can be rendered by the reporter.

Typical usage::

    from coreai_migrator.diff_builder import DiffBuilder
    from coreai_migrator.models import MigrationReport

    builder = DiffBuilder(context_lines=3)
    builder.attach_diffs(migration_report)
    # Each finding in migration_report now has .diff_lines populated.
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path
from typing import Optional

from coreai_migrator.models import FileReport, Finding, MigrationReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default number of context lines around each change in the unified diff.
DEFAULT_CONTEXT_LINES: int = 3


# ---------------------------------------------------------------------------
# DiffBuilder
# ---------------------------------------------------------------------------


class DiffBuilder:
    """Generates unified diffs for deprecated API findings.

    For each :class:`~coreai_migrator.models.Finding`, a minimal unified diff
    is produced that shows the original source line replaced by the suggested
    line.  The diff is stored as a list of strings on the finding's
    ``diff_lines`` attribute.

    When a full file's content is available (via :meth:`attach_file_diffs`),
    a richer diff is produced that spans the entire file, making it easier
    to see context around every change.

    Args:
        context_lines: Number of unchanged context lines to include around
                       each hunk (default :data:`DEFAULT_CONTEXT_LINES`).
    """

    def __init__(self, context_lines: int = DEFAULT_CONTEXT_LINES) -> None:
        self._context_lines = context_lines

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_finding_diff(
        self,
        finding: Finding,
        fromfile: str = "original",
        tofile: str = "suggested",
    ) -> list[str]:
        """Generate a unified diff for a single *finding*.

        The diff compares the ``original_line`` to the ``suggested_line``
        embedded in a minimal context derived from the finding's line number.

        Args:
            finding:  The :class:`~coreai_migrator.models.Finding` to diff.
            fromfile: Label for the "before" side of the diff header.
            tofile:   Label for the "after" side of the diff header.

        Returns:
            A list of unified diff line strings (including the ``---``/``+++``
            header lines and hunk markers).  Returns an empty list if
            ``original_line`` equals ``suggested_line``.
        """
        original = finding.original_line
        suggested = finding.suggested_line

        if original == suggested:
            return []

        # Wrap each line in a list so difflib can diff them
        original_lines = [original + "\n"] if not original.endswith("\n") else [original]
        suggested_lines = [suggested + "\n"] if not suggested.endswith("\n") else [suggested]

        diff = list(
            difflib.unified_diff(
                original_lines,
                suggested_lines,
                fromfile=fromfile,
                tofile=tofile,
                lineterm="",
                n=0,  # No extra context – single-line diff
            )
        )
        return diff

    def build_file_diff(
        self,
        file_report: FileReport,
        original_content: str,
        fromfile: Optional[str] = None,
        tofile: Optional[str] = None,
    ) -> list[str]:
        """Generate a unified diff for an entire file, applying all findings.

        All replacements in *file_report* are applied simultaneously to the
        original content lines before diffing, so the hunk offsets are
        consistent.

        Args:
            file_report:      The :class:`~coreai_migrator.models.FileReport`
                              whose findings drive the substitutions.
            original_content: Full text of the original source file.
            fromfile:         Label for the "before" header (defaults to
                              ``"a/<file_path>"``).
            tofile:           Label for the "after" header (defaults to
                              ``"b/<file_path>"``).

        Returns:
            A list of unified diff line strings for the whole file.
            Returns an empty list if no changes were made.
        """
        path_str = str(file_report.file_path)
        from_label = fromfile or f"a/{path_str}"
        to_label = tofile or f"b/{path_str}"

        original_lines = original_content.splitlines(keepends=True)
        # Ensure every line ends with a newline for consistent diffing
        original_lines = [
            line if line.endswith("\n") else line + "\n"
            for line in original_lines
        ]

        modified_lines = self._apply_findings_to_lines(
            original_lines=original_lines,
            findings=file_report.findings,
        )

        if original_lines == modified_lines:
            return []

        diff = list(
            difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=from_label,
                tofile=to_label,
                lineterm="",
                n=self._context_lines,
            )
        )
        return diff

    def attach_diffs(self, report: MigrationReport) -> None:
        """Populate ``diff_lines`` for every finding in *report* in-place.

        For each file report, this method attempts to read the source file
        from disk and generate per-finding diffs.  If the file cannot be
        read, a fallback single-line diff is generated from the finding's
        ``original_line`` / ``suggested_line`` attributes.

        Args:
            report: The top-level :class:`~coreai_migrator.models.MigrationReport`
                    to annotate.  Modified in-place.
        """
        for file_report in report.file_reports:
            self.attach_file_report_diffs(file_report)

    def attach_file_report_diffs(self, file_report: FileReport) -> None:
        """Populate ``diff_lines`` for every finding in *file_report* in-place.

        Tries to read the source file; falls back to single-line diffs if the
        file is unavailable.

        Args:
            file_report: The :class:`~coreai_migrator.models.FileReport` to
                         annotate.  Modified in-place.
        """
        original_content: Optional[str] = None
        try:
            original_content = file_report.file_path.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError as exc:
            logger.warning(
                "DiffBuilder cannot read %s: %s – using single-line diffs",
                file_report.file_path,
                exc,
            )

        if original_content is not None:
            self._attach_diffs_from_content(file_report, original_content)
        else:
            # Fallback: generate single-line diffs for each finding independently
            for finding in file_report.findings:
                finding.diff_lines = self.build_finding_diff(
                    finding,
                    fromfile=str(file_report.file_path),
                    tofile=str(file_report.file_path),
                )

    def attach_diffs_from_content(
        self,
        file_report: FileReport,
        content: str,
    ) -> None:
        """Populate ``diff_lines`` for findings using already-loaded *content*.

        This variant is used in tests and pipelines where the file content is
        already in memory.

        Args:
            file_report: The file report to annotate in-place.
            content:     Full source text of the file.
        """
        self._attach_diffs_from_content(file_report, content)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _attach_diffs_from_content(
        self,
        file_report: FileReport,
        original_content: str,
    ) -> None:
        """Core implementation: generate per-finding diffs from *original_content*.

        Each finding receives a minimal unified diff showing only the lines
        that change, with up to :attr:`_context_lines` lines of context drawn
        from the real file content.

        Args:
            file_report:      The file report whose findings are annotated.
            original_content: Full source text of the original file.
        """
        path_str = str(file_report.file_path)
        original_lines = original_content.splitlines(keepends=True)
        # Normalise line endings for display
        original_lines = [
            line if line.endswith("\n") else line + "\n"
            for line in original_lines
        ]

        for finding in file_report.findings:
            line_idx = finding.line_number - 1  # convert to 0-based

            if line_idx < 0 or line_idx >= len(original_lines):
                # Line number out of range – fall back to single-line diff
                finding.diff_lines = self.build_finding_diff(
                    finding,
                    fromfile=path_str,
                    tofile=path_str,
                )
                continue

            original_line = finding.original_line
            suggested_line = finding.suggested_line

            if original_line == suggested_line:
                finding.diff_lines = []
                continue

            # Build modified lines list with just this one change applied
            modified_lines = list(original_lines)
            new_line = suggested_line if suggested_line.endswith("\n") else suggested_line + "\n"
            modified_lines[line_idx] = new_line

            diff = list(
                difflib.unified_diff(
                    original_lines,
                    modified_lines,
                    fromfile=path_str,
                    tofile=path_str,
                    lineterm="",
                    n=self._context_lines,
                )
            )
            finding.diff_lines = diff

    def _apply_findings_to_lines(
        self,
        original_lines: list[str],
        findings: list[Finding],
    ) -> list[str]:
        """Return a copy of *original_lines* with all finding replacements applied.

        When multiple findings affect the same line, the replacements are
        applied in order.  The first finding's ``suggested_line`` replaces the
        original; subsequent findings on the same line are ignored (since the
        line has already been rewritten).

        Args:
            original_lines: List of source lines (with newlines).
            findings:       Ordered list of findings (by line number).

        Returns:
            New list of lines with replacements applied.
        """
        modified = list(original_lines)
        rewritten: set[int] = set()

        for finding in findings:
            line_idx = finding.line_number - 1
            if line_idx < 0 or line_idx >= len(modified):
                continue
            if line_idx in rewritten:
                # Already rewritten by a prior finding on this line – skip
                continue
            suggested = finding.suggested_line
            modified[line_idx] = suggested if suggested.endswith("\n") else suggested + "\n"
            rewritten.add(line_idx)

        return modified


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def attach_diffs(
    report: MigrationReport,
    context_lines: int = DEFAULT_CONTEXT_LINES,
) -> None:
    """Convenience function: attach unified diffs to all findings in *report* in-place.

    Args:
        report:        The :class:`~coreai_migrator.models.MigrationReport` to
                       annotate.  Modified in-place.
        context_lines: Number of context lines in each hunk.
    """
    builder = DiffBuilder(context_lines=context_lines)
    builder.attach_diffs(report)


def build_finding_diff(
    finding: Finding,
    context_lines: int = DEFAULT_CONTEXT_LINES,
) -> list[str]:
    """Convenience function: generate a unified diff for a single finding.

    Args:
        finding:       The finding to diff.
        context_lines: Number of context lines (not used for single-line diffs
                       but kept for API consistency).

    Returns:
        List of unified diff line strings.
    """
    builder = DiffBuilder(context_lines=context_lines)
    return builder.build_finding_diff(finding)
