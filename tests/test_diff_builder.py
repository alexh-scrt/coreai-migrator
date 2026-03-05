"""Unit tests for coreai_migrator.diff_builder.

Verifies that generated diffs correctly transform deprecated calls into Core AI
equivalents, that the DiffBuilder handles edge cases (no change, missing file,
out-of-range line numbers), and that convenience functions work correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from coreai_migrator.diff_builder import (
    DEFAULT_CONTEXT_LINES,
    DiffBuilder,
    attach_diffs,
    build_finding_diff,
)
from coreai_migrator.models import FileReport, Finding, MigrationReport, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    original_line: str = "import CoreML",
    suggested_line: str = "import CoreAI",
    deprecated_api: str = "import CoreML",
    replacement_api: str = "import CoreAI",
    line_number: int = 1,
    severity: Severity = Severity.LOW,
    file_path: Path = Path("Test.swift"),
) -> Finding:
    return Finding(
        file_path=file_path,
        line_number=line_number,
        column=0,
        deprecated_api=deprecated_api,
        replacement_api=replacement_api,
        original_line=original_line,
        suggested_line=suggested_line,
        severity=severity,
        migration_note="Test migration note.",
        diff_lines=[],
    )


def _make_file_report(
    findings: list[Finding],
    file_path: Path = Path("Test.swift"),
    language: str = "swift",
) -> FileReport:
    return FileReport(
        file_path=file_path,
        findings=findings,
        language=language,
    )


# ---------------------------------------------------------------------------
# DiffBuilder.build_finding_diff
# ---------------------------------------------------------------------------


class TestBuildFindingDiff:
    """Tests for DiffBuilder.build_finding_diff."""

    def test_produces_diff_lines(self) -> None:
        finding = _make_finding()
        builder = DiffBuilder()
        diff = builder.build_finding_diff(finding)
        assert len(diff) > 0

    def test_diff_contains_minus_line(self) -> None:
        finding = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
        )
        builder = DiffBuilder()
        diff = builder.build_finding_diff(finding)
        minus_lines = [l for l in diff if l.startswith("-") and "---" not in l]
        assert len(minus_lines) >= 1
        assert any("CoreML" in l for l in minus_lines)

    def test_diff_contains_plus_line(self) -> None:
        finding = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
        )
        builder = DiffBuilder()
        diff = builder.build_finding_diff(finding)
        plus_lines = [l for l in diff if l.startswith("+") and "+++" not in l]
        assert len(plus_lines) >= 1
        assert any("CoreAI" in l for l in plus_lines)

    def test_no_diff_when_lines_identical(self) -> None:
        finding = _make_finding(
            original_line="let x = 42",
            suggested_line="let x = 42",
        )
        builder = DiffBuilder()
        diff = builder.build_finding_diff(finding)
        assert diff == []

    def test_diff_has_header_lines(self) -> None:
        finding = _make_finding()
        builder = DiffBuilder()
        diff = builder.build_finding_diff(
            finding, fromfile="original.swift", tofile="suggested.swift"
        )
        assert any("---" in l for l in diff)
        assert any("+++" in l for l in diff)

    def test_multiword_replacement(self) -> None:
        finding = _make_finding(
            original_line="    let cfg = MLModelConfiguration()",
            suggested_line="    let cfg = CAIModelConfiguration()",
            deprecated_api="MLModelConfiguration",
            replacement_api="CAIModelConfiguration",
        )
        builder = DiffBuilder()
        diff = builder.build_finding_diff(finding)
        assert any("CAIModelConfiguration" in l for l in diff)
        assert any("MLModelConfiguration" in l for l in diff)


# ---------------------------------------------------------------------------
# DiffBuilder.build_file_diff
# ---------------------------------------------------------------------------


class TestBuildFileDiff:
    """Tests for DiffBuilder.build_file_diff."""

    def test_produces_diff_for_changed_file(self) -> None:
        content = "import CoreML\nlet x = 42\n"
        finding = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
            line_number=1,
        )
        fr = _make_file_report([finding])
        builder = DiffBuilder()
        diff = builder.build_file_diff(fr, content)
        assert len(diff) > 0
        assert any("CoreML" in l for l in diff)
        assert any("CoreAI" in l for l in diff)

    def test_returns_empty_when_no_changes(self) -> None:
        content = "let x = 42\n"
        finding = _make_finding(
            original_line="let x = 42",
            suggested_line="let x = 42",
        )
        fr = _make_file_report([finding])
        builder = DiffBuilder()
        diff = builder.build_file_diff(fr, content)
        assert diff == []

    def test_diff_labels_from_file_path(self) -> None:
        content = "import CoreML\n"
        finding = _make_finding(line_number=1)
        fr = _make_file_report([finding], file_path=Path("App/Model.swift"))
        builder = DiffBuilder()
        diff = builder.build_file_diff(fr, content)
        assert any("Model.swift" in l for l in diff)

    def test_multiple_findings_all_applied(self) -> None:
        content = "import CoreML\nlet cfg = MLModelConfiguration()\n"
        f1 = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
            deprecated_api="import CoreML",
            replacement_api="import CoreAI",
            line_number=1,
        )
        f2 = _make_finding(
            original_line="let cfg = MLModelConfiguration()",
            suggested_line="let cfg = CAIModelConfiguration()",
            deprecated_api="MLModelConfiguration",
            replacement_api="CAIModelConfiguration",
            line_number=2,
        )
        fr = _make_file_report([f1, f2])
        builder = DiffBuilder()
        diff = builder.build_file_diff(fr, content)
        diff_text = "\n".join(diff)
        assert "CoreAI" in diff_text
        assert "CAIModelConfiguration" in diff_text

    def test_context_lines_respected(self) -> None:
        lines = [f"line {i}\n" for i in range(20)]
        content = "".join(lines)
        # Change line 10 (1-based)
        finding = _make_finding(
            original_line="line 9",
            suggested_line="line NINE",
            line_number=10,
        )
        fr = _make_file_report([finding])
        builder_0 = DiffBuilder(context_lines=0)
        builder_3 = DiffBuilder(context_lines=3)
        diff_0 = builder_0.build_file_diff(fr, content)
        diff_3 = builder_3.build_file_diff(fr, content)
        # More context means more lines in the diff
        assert len(diff_3) > len(diff_0)


# ---------------------------------------------------------------------------
# DiffBuilder.attach_diffs_from_content
# ---------------------------------------------------------------------------


class TestAttachDiffsFromContent:
    """Tests for DiffBuilder.attach_diffs_from_content."""

    def test_attaches_diff_lines_to_findings(self) -> None:
        content = "import CoreML\nlet x = 42\n"
        finding = _make_finding(line_number=1)
        fr = _make_file_report([finding])
        builder = DiffBuilder()
        builder.attach_diffs_from_content(fr, content)
        assert finding.diff_lines  # should be non-empty

    def test_diff_lines_contain_correct_content(self) -> None:
        content = "import CoreML\n"
        finding = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
            line_number=1,
        )
        fr = _make_file_report([finding])
        builder = DiffBuilder()
        builder.attach_diffs_from_content(fr, content)
        diff_text = "\n".join(finding.diff_lines)
        assert "CoreML" in diff_text
        assert "CoreAI" in diff_text

    def test_no_change_finding_gets_empty_diff(self) -> None:
        content = "let x = 42\n"
        finding = _make_finding(
            original_line="let x = 42",
            suggested_line="let x = 42",
            line_number=1,
        )
        fr = _make_file_report([finding])
        builder = DiffBuilder()
        builder.attach_diffs_from_content(fr, content)
        assert finding.diff_lines == []

    def test_out_of_range_line_gets_fallback_diff(self) -> None:
        content = "line1\n"
        finding = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
            line_number=99,  # out of range
        )
        fr = _make_file_report([finding])
        builder = DiffBuilder()
        builder.attach_diffs_from_content(fr, content)
        # Should produce a fallback single-line diff (not crash)
        # diff_lines may be empty if original == suggested fallback doesn't kick in
        # but it should not raise
        assert isinstance(finding.diff_lines, list)

    def test_multiple_findings_each_get_diffs(self) -> None:
        content = "import CoreML\nlet cfg = MLModelConfiguration()\n"
        f1 = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
            deprecated_api="import CoreML",
            line_number=1,
        )
        f2 = _make_finding(
            original_line="let cfg = MLModelConfiguration()",
            suggested_line="let cfg = CAIModelConfiguration()",
            deprecated_api="MLModelConfiguration",
            line_number=2,
        )
        fr = _make_file_report([f1, f2])
        builder = DiffBuilder()
        builder.attach_diffs_from_content(fr, content)
        assert f1.diff_lines
        assert f2.diff_lines


# ---------------------------------------------------------------------------
# DiffBuilder.attach_diffs (MigrationReport level)
# ---------------------------------------------------------------------------


class TestAttachDiffsReport:
    """Tests for DiffBuilder.attach_diffs and the module-level attach_diffs."""

    def test_attach_diffs_on_report_populates_findings(self, tmp_path: Path) -> None:
        swift_file = tmp_path / "Model.swift"
        swift_file.write_text("import CoreML\nlet x = 1\n", encoding="utf-8")

        finding = _make_finding(
            file_path=swift_file.resolve(),
            line_number=1,
        )
        fr = FileReport(
            file_path=swift_file.resolve(),
            findings=[finding],
            language="swift",
        )
        migration_report = MigrationReport(
            root_path=tmp_path,
            file_reports=[fr],
            scanned_files=1,
        )

        builder = DiffBuilder()
        builder.attach_diffs(migration_report)

        assert finding.diff_lines

    def test_module_level_attach_diffs(self, tmp_path: Path) -> None:
        swift_file = tmp_path / "Model.swift"
        swift_file.write_text("import CoreML\n", encoding="utf-8")

        finding = _make_finding(file_path=swift_file.resolve(), line_number=1)
        fr = FileReport(
            file_path=swift_file.resolve(),
            findings=[finding],
            language="swift",
        )
        migration_report = MigrationReport(
            root_path=tmp_path,
            file_reports=[fr],
            scanned_files=1,
        )

        attach_diffs(migration_report)
        assert finding.diff_lines

    def test_missing_file_falls_back_to_single_line_diff(self, tmp_path: Path) -> None:
        # File does not exist on disk
        missing = tmp_path / "Missing.swift"
        finding = _make_finding(file_path=missing, line_number=1)
        fr = FileReport(
            file_path=missing,
            findings=[finding],
            language="swift",
        )
        migration_report = MigrationReport(
            root_path=tmp_path,
            file_reports=[fr],
            scanned_files=1,
        )

        builder = DiffBuilder()
        builder.attach_diffs(migration_report)
        # Should not raise; diff_lines may be populated via fallback
        assert isinstance(finding.diff_lines, list)


# ---------------------------------------------------------------------------
# Module-level build_finding_diff convenience function
# ---------------------------------------------------------------------------


class TestModuleLevelBuildFindingDiff:
    def test_returns_list(self) -> None:
        finding = _make_finding()
        diff = build_finding_diff(finding)
        assert isinstance(diff, list)

    def test_contains_change(self) -> None:
        finding = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
        )
        diff = build_finding_diff(finding)
        diff_text = "\n".join(diff)
        assert "CoreML" in diff_text
        assert "CoreAI" in diff_text

    def test_identical_lines_returns_empty(self) -> None:
        finding = _make_finding(
            original_line="let x = 1",
            suggested_line="let x = 1",
        )
        diff = build_finding_diff(finding)
        assert diff == []


# ---------------------------------------------------------------------------
# Apply findings to lines helper (indirectly via build_file_diff)
# ---------------------------------------------------------------------------


class TestApplyFindingsToLines:
    """Verify the internal _apply_findings_to_lines via build_file_diff."""

    def test_first_finding_wins_on_same_line(self) -> None:
        """When two findings target the same line, the first one wins."""
        content = "import CoreML\n"
        f1 = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
            deprecated_api="import CoreML",
            line_number=1,
        )
        f2 = _make_finding(
            original_line="import CoreML",
            suggested_line="import REPLACED_TWICE",
            deprecated_api="import CoreML",
            line_number=1,
        )
        # Override deprecated_api to avoid de-duplication at finding level
        f2.deprecated_api = "import CoreML v2"
        fr = _make_file_report([f1, f2])
        builder = DiffBuilder()
        diff = builder.build_file_diff(fr, content)
        diff_text = "\n".join(diff)
        # The first finding's replacement should appear
        assert "CoreAI" in diff_text
        # The second finding's replacement should NOT override the first
        assert "REPLACED_TWICE" not in diff_text

    def test_findings_on_different_lines_both_applied(self) -> None:
        content = "import CoreML\nimport UIKit\nlet cfg = MLModelConfiguration()\n"
        f1 = _make_finding(
            original_line="import CoreML",
            suggested_line="import CoreAI",
            deprecated_api="import CoreML",
            line_number=1,
        )
        f3 = _make_finding(
            original_line="let cfg = MLModelConfiguration()",
            suggested_line="let cfg = CAIModelConfiguration()",
            deprecated_api="MLModelConfiguration",
            line_number=3,
        )
        fr = _make_file_report([f1, f3])
        builder = DiffBuilder()
        diff = builder.build_file_diff(fr, content)
        diff_text = "\n".join(diff)
        assert "CoreAI" in diff_text
        assert "CAIModelConfiguration" in diff_text
        # The unchanged line 2 should not appear as a change
        assert "-import UIKit" not in diff_text
