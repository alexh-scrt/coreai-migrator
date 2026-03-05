"""Unit tests for coreai_migrator.analyzer.

Verifies API pattern detection accuracy against synthetic Swift/ObjC source
snippets, severity filtering, de-duplication, and the MigrationReport builder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from coreai_migrator.analyzer import Analyzer, analyze_source_files
from coreai_migrator.models import FileReport, MigrationReport, Severity
from coreai_migrator.scanner import SourceFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_coreml.swift"


def _analyze(content: str, language: str = "swift", severity_filter: Severity | None = None) -> FileReport:
    analyzer = Analyzer(severity_filter=severity_filter)
    return analyzer.analyze_content(content, file_path=Path("Test.swift"), language=language)


# ---------------------------------------------------------------------------
# Basic detection
# ---------------------------------------------------------------------------


class TestBasicDetection:
    """Verify that individual deprecated API patterns are detected correctly."""

    @pytest.mark.parametrize("snippet,expected_api", [
        ("import CoreML", "import CoreML"),
        ("@import CoreML;", "@import CoreML;"),
        ("#import <CoreML/CoreML.h>", "#import <CoreML/CoreML.h>"),
        ("let model = try MLModel(contentsOf: url)", "MLModel.init(contentsOf:)"),
        ("let cfg = MLModelConfiguration()", "MLModelConfiguration"),
        ("cfg.computeUnits = MLComputeUnits.all", "MLComputeUnits"),
        ("let arr = try MLMultiArray(shape: [1], dataType: .float32)", "MLMultiArray"),
        ("let dt = MLMultiArrayDataType.float32", "MLMultiArrayDataType"),
        ("class MyProvider: MLFeatureProvider {", "MLFeatureProvider"),
        ("let val = MLFeatureValue(int64: 42)", "MLFeatureValue"),
        ("let type: MLFeatureType = .int64", "MLFeatureType"),
        ("let dict = MLDictionaryFeatureProvider(dictionary: d)", "MLDictionaryFeatureProvider"),
        ("let result = try model.prediction(from: features)", "MLModel.prediction(from:)"),
        ("let results = try model.predictions(fromBatch: batch)", "MLModel.predictions(fromBatch:)"),
        ("let opts = MLPredictionOptions()", "MLPredictionOptions"),
        ("let desc: MLModelDescription = model.modelDescription", "MLModelDescription"),
        ("let fd: MLFeatureDescription = desc.inputDescriptionsByName[name]!", "MLFeatureDescription"),
        ("let key = MLModelMetadataKey.author", "MLModelMetadataKey"),
        ("let vnModel = try VNCoreMLModel(for: mlModel)", "VNCoreMLModel"),
        ("let request = VNCoreMLRequest(model: vnModel)", "VNCoreMLRequest"),
        ("let obs: VNCoreMLFeatureValueObservation = result", "VNCoreMLFeatureValueObservation"),
        ("let nlModel = try NLModel(contentsOf: url)", "NLModel"),
        ("let nlCfg = NLModelConfiguration()", "NLModelConfiguration"),
        ("let task = MLUpdateTask(forModelAt: url, ", "MLUpdateTask"),
        ("let ctx: MLUpdateContext = context", "MLUpdateContext"),
        ("let ph = MLUpdateProgressHandlers(forEvents: [])", "MLUpdateProgressHandlers"),
        ("let metric = MLMetricKey.lossValue", "MLMetricKey"),
        ("let seq: MLSequence = MLSequence.init(strings: [])", "MLSequence"),
        ("let pb: MLPixelBuffer = buffer", "MLPixelBuffer"),
        ("class Batch: MLBatchProvider {", "MLBatchProvider"),
        ("let ap = MLArrayBatchProvider(array: providers)", "MLArrayBatchProvider"),
        ("let hints = MLOptimizationHints()", "MLOptimizationHints"),
        ("let spec = MLSpecialization.full", "MLSpecialization"),
        ("let url = try MLModel.compileModel(at: modelURL)", "MLModel.compileModel(at:)"),
        ("MLModel.load(contentsOf: url, configuration: config)", "MLModel.load(contentsOf:configuration:completionHandler:)"),
        ("let sound = MLSoundClassifier()", "MLSoundClassifier"),
        ("let imgCls = MLImageClassifier()", "MLImageClassifier"),
    ])
    def test_detects_api(self, snippet: str, expected_api: str) -> None:
        report = _analyze(snippet)
        apis = {f.deprecated_api for f in report.findings}
        assert expected_api in apis, (
            f"Expected to detect '{expected_api}' in snippet: {snippet!r}\n"
            f"Found: {apis}"
        )

    def test_no_false_positive_on_cai_import(self) -> None:
        report = _analyze("import CoreAI")
        assert len(report.findings) == 0

    def test_no_false_positive_on_cai_model(self) -> None:
        report = _analyze("let model = try CAIModel(contentsOf: url)")
        apis = {f.deprecated_api for f in report.findings}
        assert "MLModel.init(contentsOf:)" not in apis

    def test_no_false_positive_on_cai_vision(self) -> None:
        report = _analyze("let req = CAIVisionRequest(model: model)")
        apis = {f.deprecated_api for f in report.findings}
        assert "VNCoreMLRequest" not in apis


# ---------------------------------------------------------------------------
# Replacement suggestion
# ---------------------------------------------------------------------------


class TestReplacementSuggestion:
    """Verify that suggested_line is produced correctly."""

    def test_import_coreml_replacement(self) -> None:
        report = _analyze("import CoreML")
        f = next(x for x in report.findings if x.deprecated_api == "import CoreML")
        assert "CoreAI" in f.suggested_line
        assert "CoreML" not in f.suggested_line

    def test_mlmodelconfiguration_replacement(self) -> None:
        report = _analyze("let cfg = MLModelConfiguration()")
        f = next(x for x in report.findings if x.deprecated_api == "MLModelConfiguration")
        assert "CAIModelConfiguration" in f.suggested_line

    def test_mlmultiarray_replacement(self) -> None:
        report = _analyze("let arr: MLMultiArray = tensor")
        f = next(x for x in report.findings if x.deprecated_api == "MLMultiArray")
        assert "CAITensor" in f.suggested_line

    def test_vncoremlrequest_replacement(self) -> None:
        report = _analyze("let req = VNCoreMLRequest(model: m)")
        f = next(x for x in report.findings if x.deprecated_api == "VNCoreMLRequest")
        assert "CAIVisionRequest" in f.suggested_line

    def test_original_line_preserved(self) -> None:
        source = "    let model = try MLModel(contentsOf: url)  // load"
        report = _analyze(source)
        findings = [f for f in report.findings if f.deprecated_api == "MLModel.init(contentsOf:)"]
        assert len(findings) >= 1
        assert findings[0].original_line == source


# ---------------------------------------------------------------------------
# Line number and column accuracy
# ---------------------------------------------------------------------------


class TestLocationAccuracy:
    def test_line_number_correct(self) -> None:
        content = "let a = 1\nimport CoreML\nlet b = 2"
        report = _analyze(content)
        f = next(x for x in report.findings if x.deprecated_api == "import CoreML")
        assert f.line_number == 2

    def test_column_correct(self) -> None:
        content = "    import CoreML"
        report = _analyze(content)
        f = next(x for x in report.findings if x.deprecated_api == "import CoreML")
        # column should point to 'import' which starts at index 4
        assert f.column == 4

    def test_multiple_findings_sorted_by_line(self) -> None:
        content = (
            "import CoreML\n"
            "let cfg = MLModelConfiguration()\n"
            "let arr = try MLMultiArray(shape: [], dataType: .float32)\n"
        )
        report = _analyze(content)
        line_numbers = [f.line_number for f in report.findings]
        assert line_numbers == sorted(line_numbers)


# ---------------------------------------------------------------------------
# Severity filtering
# ---------------------------------------------------------------------------


class TestSeverityFilter:
    def test_filter_low_includes_all(self) -> None:
        content = "import CoreML\nlet arr: MLMultiArray = t\nlet cls = MLSoundClassifier()"
        report_all = _analyze(content, severity_filter=Severity.LOW)
        report_none = _analyze(content)
        assert report_all.finding_count == report_none.finding_count

    def test_filter_breaking_excludes_low(self) -> None:
        content = "import CoreML\nlet cls = MLSoundClassifier()"
        report = _analyze(content, severity_filter=Severity.BREAKING)
        severities = {f.severity for f in report.findings}
        assert Severity.LOW not in severities
        assert Severity.BREAKING in severities

    def test_filter_high_excludes_low_and_medium(self) -> None:
        content = (
            "import CoreML\n"          # LOW
            "let cfg = MLModelConfiguration()\n"   # LOW
            "let arr: MLMultiArray = t\n"           # HIGH
            "let req = VNCoreMLRequest(model: m)\n" # HIGH
        )
        report = _analyze(content, severity_filter=Severity.HIGH)
        for f in report.findings:
            assert f.severity in (Severity.HIGH, Severity.BREAKING)

    def test_no_filter_returns_all_severities(self) -> None:
        content = (
            "import CoreML\n"          # LOW
            "let arr: MLMultiArray = t\n"           # HIGH
        )
        report = _analyze(content, severity_filter=None)
        severities = {f.severity for f in report.findings}
        assert Severity.LOW in severities
        assert Severity.HIGH in severities


# ---------------------------------------------------------------------------
# De-duplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_same_api_same_line_detected_once(self) -> None:
        # A line with two references to the same API should yield only one finding
        # for that API on that line.
        content = "let a: MLMultiArray = b as! MLMultiArray"
        report = _analyze(content)
        ml_findings = [f for f in report.findings if f.deprecated_api == "MLMultiArray"]
        assert len(ml_findings) == 1

    def test_same_api_different_lines_detected_separately(self) -> None:
        content = "let a: MLMultiArray = x\nlet b: MLMultiArray = y"
        report = _analyze(content)
        ml_findings = [f for f in report.findings if f.deprecated_api == "MLMultiArray"]
        assert len(ml_findings) == 2
        assert ml_findings[0].line_number == 1
        assert ml_findings[1].line_number == 2


# ---------------------------------------------------------------------------
# Objective-C patterns
# ---------------------------------------------------------------------------


class TestObjCPatterns:
    def test_objc_import(self) -> None:
        report = _analyze("#import <CoreML/CoreML.h>", language="objc")
        apis = {f.deprecated_api for f in report.findings}
        assert "#import <CoreML/CoreML.h>" in apis

    def test_objc_at_import(self) -> None:
        report = _analyze("@import CoreML;", language="objc")
        apis = {f.deprecated_api for f in report.findings}
        assert "@import CoreML;" in apis

    def test_objc_model_with_contents_of_url(self) -> None:
        snippet = "MLModel *model = [MLModel modelWithContentsOfURL:url error:&err];"
        report = _analyze(snippet, language="objc")
        apis = {f.deprecated_api for f in report.findings}
        assert "[MLModel modelWithContentsOfURL:error:]" in apis

    def test_objc_prediction_from_features(self) -> None:
        snippet = "id<MLFeatureProvider> out = [model predictionFromFeatures:input error:nil];"
        report = _analyze(snippet, language="objc")
        apis = {f.deprecated_api for f in report.findings}
        assert "[model predictionFromFeatures:error:]" in apis

    def test_objc_id_mlfeatureprovider(self) -> None:
        snippet = "id<MLFeatureProvider> provider = [[MyProvider alloc] init];"
        report = _analyze(snippet, language="objc")
        apis = {f.deprecated_api for f in report.findings}
        assert "id<MLFeatureProvider>" in apis

    def test_objc_vncoremlrequest_alloc(self) -> None:
        snippet = "VNCoreMLRequest *req = [[VNCoreMLRequest alloc] initWithModel:model];"
        report = _analyze(snippet, language="objc")
        apis = {f.deprecated_api for f in report.findings}
        assert "[VNCoreMLRequest alloc]" in apis


# ---------------------------------------------------------------------------
# FileReport metadata
# ---------------------------------------------------------------------------


class TestFileReportMetadata:
    def test_language_preserved(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        if FIXTURE_PATH.exists():
            report = analyzer.analyze_file(sf)
            assert report.language == "swift"

    def test_empty_content_gives_empty_report(self) -> None:
        report = _analyze("")
        assert report.finding_count == 0
        assert report.complexity_score == 0

    def test_clean_content_gives_empty_report(self) -> None:
        clean = (
            "import CoreAI\n"
            "let model = try CAIModel(contentsOf: url)\n"
            "let tensor = CAITensor(shape: [], dataType: .float32)\n"
        )
        report = _analyze(clean)
        assert report.finding_count == 0


# ---------------------------------------------------------------------------
# Sample fixture integration
# ---------------------------------------------------------------------------


class TestFixtureIntegration:
    """Run the analyzer against the bundled sample fixture."""

    @pytest.fixture(autouse=True)
    def require_fixture(self) -> None:
        if not FIXTURE_PATH.exists():
            pytest.skip("Fixture file not found")

    def test_fixture_has_findings(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        report = analyzer.analyze_file(sf)
        assert report.finding_count > 0

    def test_fixture_detects_import_coreml(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        report = analyzer.analyze_file(sf)
        apis = {f.deprecated_api for f in report.findings}
        assert "import CoreML" in apis

    def test_fixture_detects_mlmodel(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        report = analyzer.analyze_file(sf)
        apis = {f.deprecated_api for f in report.findings}
        assert "MLModel.init(contentsOf:)" in apis

    def test_fixture_detects_vncoremlrequest(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        report = analyzer.analyze_file(sf)
        apis = {f.deprecated_api for f in report.findings}
        assert "VNCoreMLRequest" in apis

    def test_fixture_detects_mlmultiarray(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        report = analyzer.analyze_file(sf)
        apis = {f.deprecated_api for f in report.findings}
        assert "MLMultiArray" in apis

    def test_fixture_complexity_score_positive(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        report = analyzer.analyze_file(sf)
        assert report.complexity_score > 0

    def test_findings_sorted_by_line(self) -> None:
        analyzer = Analyzer()
        sf = SourceFile(path=FIXTURE_PATH, language="swift")
        report = analyzer.analyze_file(sf)
        line_numbers = [f.line_number for f in report.findings]
        assert line_numbers == sorted(line_numbers)


# ---------------------------------------------------------------------------
# MigrationReport builder
# ---------------------------------------------------------------------------


class TestMigrationReportBuilder:
    def test_build_from_multiple_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "A.swift"
        f2 = tmp_path / "B.swift"
        f1.write_text("import CoreML\nlet arr: MLMultiArray = x", encoding="utf-8")
        f2.write_text("let cfg = MLModelConfiguration()", encoding="utf-8")

        source_files = [
            SourceFile(path=f1, language="swift"),
            SourceFile(path=f2, language="swift"),
        ]
        report = analyze_source_files(source_files, root_path=tmp_path)
        assert isinstance(report, MigrationReport)
        assert report.scanned_files == 2
        assert report.affected_files == 2
        assert report.total_findings >= 3

    def test_clean_files_excluded_from_report(self, tmp_path: Path) -> None:
        clean = tmp_path / "Clean.swift"
        dirty = tmp_path / "Dirty.swift"
        clean.write_text("// No deprecated APIs here", encoding="utf-8")
        dirty.write_text("import CoreML", encoding="utf-8")

        source_files = [
            SourceFile(path=clean, language="swift"),
            SourceFile(path=dirty, language="swift"),
        ]
        report = analyze_source_files(source_files, root_path=tmp_path)
        assert report.affected_files == 1
        assert report.scanned_files == 2

    def test_all_clean_files_gives_clean_report(self, tmp_path: Path) -> None:
        clean = tmp_path / "Clean.swift"
        clean.write_text("import Foundation\nlet x = 42", encoding="utf-8")
        source_files = [SourceFile(path=clean, language="swift")]
        report = analyze_source_files(source_files, root_path=tmp_path)
        assert report.total_findings == 0
        assert report.complexity_label == "Clean"

    def test_severity_filter_propagates(self, tmp_path: Path) -> None:
        f = tmp_path / "Mixed.swift"
        f.write_text(
            "import CoreML\nlet arr: MLMultiArray = x\nlet cls = MLSoundClassifier()",
            encoding="utf-8",
        )
        source_files = [SourceFile(path=f, language="swift")]
        report_all = analyze_source_files(source_files, root_path=tmp_path)
        report_breaking = analyze_source_files(
            source_files, root_path=tmp_path, severity_filter=Severity.BREAKING
        )
        assert report_breaking.total_findings < report_all.total_findings
