"""Unit tests for coreai_migrator.models.

Verifies that Finding, FileReport, and MigrationReport dataclasses compute
correct complexity scores, serialise cleanly to dicts, and handle edge cases
such as empty findings lists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from coreai_migrator.models import Finding, FileReport, MigrationReport, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    deprecated_api: str = "MLModel.init(contentsOf:)",
    replacement_api: str = "CAIModel.load(contentsOf:)",
    severity: Severity = Severity.MEDIUM,
    line_number: int = 10,
) -> Finding:
    return Finding(
        file_path=Path("App/Model.swift"),
        line_number=line_number,
        column=4,
        deprecated_api=deprecated_api,
        replacement_api=replacement_api,
        original_line="    let model = try MLModel(contentsOf: url)\n",
        suggested_line="    let model = try CAIModel(contentsOf: url)\n",
        severity=severity,
        migration_note="Replace MLModel with CAIModel.",
    )


# ---------------------------------------------------------------------------
# Severity tests
# ---------------------------------------------------------------------------

class TestSeverity:
    def test_weights_are_ordered(self) -> None:
        assert Severity.LOW.weight < Severity.MEDIUM.weight
        assert Severity.MEDIUM.weight < Severity.HIGH.weight
        assert Severity.HIGH.weight < Severity.BREAKING.weight

    def test_str_returns_value(self) -> None:
        assert str(Severity.LOW) == "low"
        assert str(Severity.BREAKING) == "breaking"

    def test_rich_style_returns_string(self) -> None:
        for sev in Severity:
            assert isinstance(sev.rich_style, str)
            assert len(sev.rich_style) > 0


# ---------------------------------------------------------------------------
# Finding tests
# ---------------------------------------------------------------------------

class TestFinding:
    def test_complexity_score_equals_weight(self) -> None:
        for sev in Severity:
            finding = _make_finding(severity=sev)
            assert finding.complexity_score == sev.weight

    def test_to_dict_keys(self) -> None:
        finding = _make_finding()
        d = finding.to_dict()
        expected_keys = {
            "file_path", "line_number", "column", "deprecated_api",
            "replacement_api", "original_line", "suggested_line",
            "severity", "migration_note", "complexity_score", "diff_lines",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_severity_is_string(self) -> None:
        finding = _make_finding(severity=Severity.HIGH)
        assert finding.to_dict()["severity"] == "high"

    def test_to_dict_file_path_is_string(self) -> None:
        finding = _make_finding()
        assert isinstance(finding.to_dict()["file_path"], str)

    def test_diff_lines_default_empty(self) -> None:
        finding = _make_finding()
        assert finding.diff_lines == []


# ---------------------------------------------------------------------------
# FileReport tests
# ---------------------------------------------------------------------------

class TestFileReport:
    def test_empty_report_zero_score(self) -> None:
        report = FileReport(file_path=Path("App/Empty.swift"))
        assert report.complexity_score == 0
        assert report.finding_count == 0
        assert report.max_severity is None

    def test_complexity_score_sums_findings(self) -> None:
        findings = [
            _make_finding(severity=Severity.LOW),    # weight 1
            _make_finding(severity=Severity.HIGH),   # weight 4
        ]
        report = FileReport(file_path=Path("App/Model.swift"), findings=findings)
        assert report.complexity_score == 1 + 4

    def test_max_severity_single_finding(self) -> None:
        report = FileReport(
            file_path=Path("App/Model.swift"),
            findings=[_make_finding(severity=Severity.HIGH)],
        )
        assert report.max_severity == Severity.HIGH

    def test_max_severity_multiple_findings(self) -> None:
        findings = [
            _make_finding(severity=Severity.LOW),
            _make_finding(severity=Severity.BREAKING),
            _make_finding(severity=Severity.MEDIUM),
        ]
        report = FileReport(file_path=Path("App/Model.swift"), findings=findings)
        assert report.max_severity == Severity.BREAKING

    def test_findings_by_severity_filters_correctly(self) -> None:
        findings = [
            _make_finding(severity=Severity.LOW),
            _make_finding(severity=Severity.LOW),
            _make_finding(severity=Severity.HIGH),
        ]
        report = FileReport(file_path=Path("App/Model.swift"), findings=findings)
        assert len(report.findings_by_severity(Severity.LOW)) == 2
        assert len(report.findings_by_severity(Severity.HIGH)) == 1
        assert len(report.findings_by_severity(Severity.BREAKING)) == 0

    def test_to_dict_structure(self) -> None:
        report = FileReport(
            file_path=Path("App/Model.swift"),
            language="swift",
            findings=[_make_finding()],
        )
        d = report.to_dict()
        assert d["language"] == "swift"
        assert d["finding_count"] == 1
        assert isinstance(d["findings"], list)
        assert len(d["findings"]) == 1


# ---------------------------------------------------------------------------
# MigrationReport tests
# ---------------------------------------------------------------------------

class TestMigrationReport:
    def test_empty_report(self) -> None:
        report = MigrationReport(root_path=Path("."), scanned_files=5)
        assert report.total_findings == 0
        assert report.total_complexity_score == 0
        assert report.affected_files == 0
        assert report.complexity_label == "Clean"

    def test_total_findings_sums_across_files(self) -> None:
        fr1 = FileReport(
            file_path=Path("A.swift"),
            findings=[_make_finding(), _make_finding()],
        )
        fr2 = FileReport(
            file_path=Path("B.swift"),
            findings=[_make_finding()],
        )
        report = MigrationReport(root_path=Path("."), file_reports=[fr1, fr2])
        assert report.total_findings == 3

    def test_complexity_labels(self) -> None:
        def _report_with_score(score: int) -> MigrationReport:
            # Build a report whose total_complexity_score equals score
            # by using LOW findings (weight=1)
            findings = [_make_finding(severity=Severity.LOW) for _ in range(score)]
            fr = FileReport(file_path=Path("A.swift"), findings=findings)
            return MigrationReport(root_path=Path("."), file_reports=[fr])

        assert _report_with_score(0).complexity_label == "Clean"
        assert _report_with_score(1).complexity_label == "Low"
        assert _report_with_score(10).complexity_label == "Low"
        assert _report_with_score(11).complexity_label == "Medium"
        assert _report_with_score(40).complexity_label == "Medium"
        assert _report_with_score(41).complexity_label == "High"
        assert _report_with_score(100).complexity_label == "High"
        assert _report_with_score(101).complexity_label == "Breaking"

    def test_all_findings_flat_list(self) -> None:
        fr1 = FileReport(
            file_path=Path("A.swift"),
            findings=[_make_finding(line_number=1), _make_finding(line_number=2)],
        )
        fr2 = FileReport(
            file_path=Path("B.swift"),
            findings=[_make_finding(line_number=3)],
        )
        report = MigrationReport(root_path=Path("."), file_reports=[fr1, fr2])
        assert len(report.all_findings()) == 3

    def test_findings_by_severity_across_files(self) -> None:
        fr1 = FileReport(
            file_path=Path("A.swift"),
            findings=[_make_finding(severity=Severity.BREAKING)],
        )
        fr2 = FileReport(
            file_path=Path("B.swift"),
            findings=[_make_finding(severity=Severity.LOW)],
        )
        report = MigrationReport(root_path=Path("."), file_reports=[fr1, fr2])
        assert len(report.findings_by_severity(Severity.BREAKING)) == 1
        assert len(report.findings_by_severity(Severity.LOW)) == 1
        assert len(report.findings_by_severity(Severity.MEDIUM)) == 0

    def test_to_dict_top_level_keys(self) -> None:
        report = MigrationReport(root_path=Path("/tmp/MyApp"), scanned_files=10)
        d = report.to_dict()
        expected_keys = {
            "root_path", "scanned_files", "affected_files",
            "total_findings", "total_complexity_score",
            "complexity_label", "file_reports",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_root_path_is_string(self) -> None:
        report = MigrationReport(root_path=Path("/tmp/MyApp"))
        assert isinstance(report.to_dict()["root_path"], str)
