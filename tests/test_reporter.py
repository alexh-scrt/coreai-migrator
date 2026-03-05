"""Unit tests for coreai_migrator.reporter.

Verifies JSON and plain-text report serialization correctness, complexity
score calculation display, and rich terminal output generation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coreai_migrator.models import FileReport, Finding, MigrationReport, Severity
from coreai_migrator.reporter import (
    Reporter,
    compute_complexity_label,
    render_json,
    render_plain,
    render_rich,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    deprecated_api: str = "import CoreML",
    replacement_api: str = "import CoreAI",
    severity: Severity = Severity.LOW,
    line_number: int = 1,
    original_line: str = "import CoreML",
    suggested_line: str = "import CoreAI",
    file_path: Path = Path("App/Model.swift"),
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
        migration_note="Replace the deprecated symbol with its Core AI equivalent.",
        diff_lines=[
            "--- original",
            "+++ suggested",
            "@@ -1 +1 @@",
            "-import CoreML",
            "+import CoreAI",
        ],
    )


def _make_report(
    num_findings: int = 2,
    severity: Severity = Severity.MEDIUM,
    scanned: int = 10,
) -> MigrationReport:
    findings = [
        _make_finding(
            deprecated_api=f"MLSymbol{i}",
            replacement_api=f"CAISymbol{i}",
            severity=severity,
            line_number=i + 1,
            original_line=f"    let x = MLSymbol{i}()",
            suggested_line=f"    let x = CAISymbol{i}()",
        )
        for i in range(num_findings)
    ]
    fr = FileReport(
        file_path=Path("App/Model.swift"),
        findings=findings,
        language="swift",
    )
    return MigrationReport(
        root_path=Path("/tmp/MyApp"),
        file_reports=[fr],
        scanned_files=scanned,
    )


def _empty_report() -> MigrationReport:
    return MigrationReport(
        root_path=Path("/tmp/MyApp"),
        file_reports=[],
        scanned_files=5,
    )


# ---------------------------------------------------------------------------
# compute_complexity_label
# ---------------------------------------------------------------------------


class TestComputeComplexityLabel:
    """Tests for the standalone compute_complexity_label utility."""

    @pytest.mark.parametrize("score,expected", [
        (0, "Clean"),
        (1, "Low"),
        (10, "Low"),
        (11, "Medium"),
        (40, "Medium"),
        (41, "High"),
        (100, "High"),
        (101, "Breaking"),
        (9999, "Breaking"),
    ])
    def test_label_thresholds(self, score: int, expected: str) -> None:
        assert compute_complexity_label(score) == expected


# ---------------------------------------------------------------------------
# JSON reporter
# ---------------------------------------------------------------------------


class TestJSONReporter:
    """Tests for the JSON output format."""

    def test_json_is_valid(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report())
        parsed = json.loads(output)  # Should not raise
        assert isinstance(parsed, dict)

    def test_json_top_level_keys(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report())
        parsed = json.loads(output)
        expected = {
            "root_path", "scanned_files", "affected_files",
            "total_findings", "total_complexity_score",
            "complexity_label", "file_reports",
        }
        assert set(parsed.keys()) == expected

    def test_json_scanned_files(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report(scanned=7))
        parsed = json.loads(output)
        assert parsed["scanned_files"] == 7

    def test_json_total_findings(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report(num_findings=3))
        parsed = json.loads(output)
        assert parsed["total_findings"] == 3

    def test_json_affected_files(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report(num_findings=2))
        parsed = json.loads(output)
        assert parsed["affected_files"] == 1

    def test_json_empty_report(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_empty_report())
        parsed = json.loads(output)
        assert parsed["total_findings"] == 0
        assert parsed["complexity_label"] == "Clean"
        assert parsed["file_reports"] == []

    def test_json_file_reports_structure(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report(num_findings=1))
        parsed = json.loads(output)
        assert len(parsed["file_reports"]) == 1
        fr = parsed["file_reports"][0]
        assert "file_path" in fr
        assert "findings" in fr
        assert "finding_count" in fr
        assert "complexity_score" in fr
        assert "language" in fr

    def test_json_finding_keys(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report(num_findings=1))
        parsed = json.loads(output)
        finding = parsed["file_reports"][0]["findings"][0]
        expected_keys = {
            "file_path", "line_number", "column", "deprecated_api",
            "replacement_api", "original_line", "suggested_line",
            "severity", "migration_note", "complexity_score", "diff_lines",
        }
        assert set(finding.keys()) == expected_keys

    def test_json_severity_is_string(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report(severity=Severity.HIGH))
        parsed = json.loads(output)
        finding = parsed["file_reports"][0]["findings"][0]
        assert finding["severity"] == "high"

    def test_json_complexity_score_calculation(self) -> None:
        # MEDIUM weight = 2; 3 findings => score = 6
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report(num_findings=3, severity=Severity.MEDIUM))
        parsed = json.loads(output)
        assert parsed["total_complexity_score"] == 3 * Severity.MEDIUM.weight

    def test_json_complexity_label_correct(self) -> None:
        # BREAKING weight = 8; 15 findings => score = 120 => "Breaking"
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(
            _make_report(num_findings=15, severity=Severity.BREAKING)
        )
        parsed = json.loads(output)
        assert parsed["complexity_label"] == "Breaking"

    def test_json_diff_lines_present(self) -> None:
        finding = _make_finding()
        finding.diff_lines = ["--- a", "+++ b", "@@ -1 +1 @@", "-old", "+new"]
        fr = FileReport(
            file_path=Path("App/Model.swift"),
            findings=[finding],
            language="swift",
        )
        report = MigrationReport(
            root_path=Path("/tmp"),
            file_reports=[fr],
            scanned_files=1,
        )
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(report)
        parsed = json.loads(output)
        assert len(parsed["file_reports"][0]["findings"][0]["diff_lines"]) == 5

    def test_json_write_to_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "report.json"
        reporter = Reporter(output_format="json", output_file=out_file)
        reporter.render(_make_report())
        assert out_file.exists()
        with out_file.open(encoding="utf-8") as fh:
            parsed = json.load(fh)
        assert "total_findings" in parsed

    def test_render_json_convenience(self, tmp_path: Path) -> None:
        out_file = tmp_path / "out.json"
        render_json(_make_report(), output_file=out_file)
        assert out_file.exists()
        parsed = json.loads(out_file.read_text())
        assert parsed["total_findings"] >= 1


# ---------------------------------------------------------------------------
# Plain-text reporter
# ---------------------------------------------------------------------------


class TestPlainReporter:
    """Tests for the plain-text output format."""

    def test_plain_contains_root_path(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report())
        assert "/tmp/MyApp" in output

    def test_plain_contains_finding_count(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report(num_findings=4))
        assert "4" in output

    def test_plain_contains_deprecated_api(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "MLSymbol0" in output

    def test_plain_contains_replacement_api(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "CAISymbol0" in output

    def test_plain_contains_severity(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report(severity=Severity.HIGH))
        assert "HIGH" in output

    def test_plain_contains_complexity_label(self) -> None:
        reporter = Reporter(output_format="plain")
        report = _make_report(num_findings=1, severity=Severity.LOW)
        output = reporter.render_to_string(report)
        # score = 1 => "Low"
        assert "Low" in output

    def test_plain_empty_report_message(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_empty_report())
        assert "No deprecated" in output or "ready" in output

    def test_plain_contains_migration_note_when_enabled(self) -> None:
        reporter = Reporter(output_format="plain", show_notes=True)
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "Replace the deprecated symbol" in output

    def test_plain_no_migration_note_when_disabled(self) -> None:
        reporter = Reporter(output_format="plain", show_notes=False)
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "Replace the deprecated symbol" not in output

    def test_plain_contains_diff_when_enabled(self) -> None:
        finding = _make_finding()
        finding.diff_lines = ["--- a", "+++ b", "-import CoreML", "+import CoreAI"]
        fr = FileReport(
            file_path=Path("App/Model.swift"),
            findings=[finding],
            language="swift",
        )
        report = MigrationReport(
            root_path=Path("/tmp/MyApp"),
            file_reports=[fr],
            scanned_files=1,
        )
        reporter = Reporter(output_format="plain", show_diffs=True)
        output = reporter.render_to_string(report)
        assert "-import CoreML" in output
        assert "+import CoreAI" in output

    def test_plain_no_diff_when_disabled(self) -> None:
        finding = _make_finding()
        finding.diff_lines = ["--- a", "+++ b", "-import CoreML", "+import CoreAI"]
        fr = FileReport(
            file_path=Path("App/Model.swift"),
            findings=[finding],
            language="swift",
        )
        report = MigrationReport(
            root_path=Path("/tmp/MyApp"),
            file_reports=[fr],
            scanned_files=1,
        )
        reporter = Reporter(output_format="plain", show_diffs=False)
        output = reporter.render_to_string(report)
        assert "-import CoreML" not in output

    def test_plain_max_findings_limits_output(self) -> None:
        reporter = Reporter(output_format="plain", max_findings=1)
        output = reporter.render_to_string(_make_report(num_findings=5))
        # Only finding [1] should appear; [2]-[5] capped
        assert "MLSymbol0" in output
        assert "more finding(s)" in output

    def test_plain_contains_line_numbers(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report(num_findings=2))
        # Findings are on lines 1 and 2
        assert "Line 1" in output
        assert "Line 2" in output

    def test_plain_write_to_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "report.txt"
        reporter = Reporter(output_format="plain", output_file=out_file)
        reporter.render(_make_report())
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "Migration Report" in content

    def test_render_plain_convenience(self, tmp_path: Path) -> None:
        out_file = tmp_path / "out.txt"
        render_plain(_make_report(), output_file=out_file)
        assert out_file.exists()
        content = out_file.read_text()
        assert "Migration Report" in content

    def test_plain_scanned_files_shown(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report(scanned=42))
        assert "42" in output

    def test_plain_affected_files_shown(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report(num_findings=1))
        # 1 affected file
        assert "1" in output


# ---------------------------------------------------------------------------
# Rich terminal reporter
# ---------------------------------------------------------------------------


class TestRichReporter:
    """Tests for the rich terminal output format (ANSI stripped)."""

    def test_rich_produces_output(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_make_report())
        assert len(output) > 0

    def test_rich_contains_deprecated_api(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "MLSymbol0" in output

    def test_rich_contains_replacement_api(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "CAISymbol0" in output

    def test_rich_contains_complexity_label(self) -> None:
        reporter = Reporter(output_format="rich")
        report = _make_report(num_findings=1, severity=Severity.LOW)
        output = reporter.render_to_string(report)
        assert "Low" in output or "Clean" in output

    def test_rich_empty_report_clean_message(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_empty_report())
        assert "No deprecated" in output or "ready" in output

    def test_rich_write_to_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "report_rich.txt"
        reporter = Reporter(output_format="rich", output_file=out_file)
        reporter.render(_make_report())
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_render_rich_convenience(self, tmp_path: Path) -> None:
        out_file = tmp_path / "out_rich.txt"
        render_rich(_make_report(), output_file=out_file)
        assert out_file.exists()

    def test_rich_contains_file_path(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_make_report())
        assert "Model.swift" in output

    def test_rich_contains_severity(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_make_report(severity=Severity.HIGH))
        assert "HIGH" in output

    def test_rich_max_findings_limits_output(self) -> None:
        reporter = Reporter(output_format="rich", max_findings=1)
        output = reporter.render_to_string(_make_report(num_findings=5))
        assert "MLSymbol0" in output
        # Should note that more findings exist
        assert "more finding(s)" in output

    def test_rich_contains_migration_note_when_enabled(self) -> None:
        reporter = Reporter(output_format="rich", show_notes=True)
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "Replace the deprecated symbol" in output

    def test_rich_no_migration_note_when_disabled(self) -> None:
        reporter = Reporter(output_format="rich", show_notes=False)
        output = reporter.render_to_string(_make_report(num_findings=1))
        assert "Replace the deprecated symbol" not in output

    def test_rich_diff_shown_when_enabled(self) -> None:
        finding = _make_finding()
        finding.diff_lines = ["--- a", "+++ b", "-import CoreML", "+import CoreAI"]
        fr = FileReport(
            file_path=Path("App/Model.swift"),
            findings=[finding],
            language="swift",
        )
        report = MigrationReport(
            root_path=Path("/tmp/MyApp"),
            file_reports=[fr],
            scanned_files=1,
        )
        reporter = Reporter(output_format="rich", show_diffs=True)
        output = reporter.render_to_string(report)
        assert "CoreML" in output

    def test_rich_contains_summary_panel(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_make_report())
        assert "Summary" in output


# ---------------------------------------------------------------------------
# render_to_string consistency
# ---------------------------------------------------------------------------


class TestRenderToString:
    """Cross-format consistency tests for render_to_string."""

    def test_json_render_to_string_valid_json(self) -> None:
        reporter = Reporter(output_format="json")
        output = reporter.render_to_string(_make_report())
        # Must be valid JSON
        json.loads(output)

    def test_plain_render_to_string_is_string(self) -> None:
        reporter = Reporter(output_format="plain")
        output = reporter.render_to_string(_make_report())
        assert isinstance(output, str)
        assert len(output) > 0

    def test_rich_render_to_string_is_string(self) -> None:
        reporter = Reporter(output_format="rich")
        output = reporter.render_to_string(_make_report())
        assert isinstance(output, str)
        assert len(output) > 0

    def test_all_formats_contain_deprecated_api_name(self) -> None:
        for fmt in ("json", "plain", "rich"):
            reporter = Reporter(output_format=fmt)  # type: ignore[arg-type]
            output = reporter.render_to_string(_make_report(num_findings=1))
            assert "MLSymbol0" in output, f"Format '{fmt}' missing deprecated API name"
