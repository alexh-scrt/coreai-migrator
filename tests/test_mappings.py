"""Unit tests for coreai_migrator.mappings.

Verifies the structure, completeness, and correctness of the API mapping table.
"""

from __future__ import annotations

import re

import pytest

from coreai_migrator.mappings import (
    API_MAPPINGS,
    ALL_CATEGORIES,
    ALL_DEPRECATED_APIS,
    APIMapping,
    get_all_patterns,
    get_mapping,
    get_mappings_by_category,
    get_mappings_by_severity,
)
from coreai_migrator.models import Severity


class TestAPIMapping:
    """Tests for the APIMapping dataclass."""

    def test_all_entries_have_non_empty_deprecated_api(self) -> None:
        for key, mapping in API_MAPPINGS.items():
            assert mapping.deprecated_api, f"Empty deprecated_api for key '{key}'"

    def test_all_entries_have_non_empty_replacement_api(self) -> None:
        for key, mapping in API_MAPPINGS.items():
            assert mapping.replacement_api, f"Empty replacement_api for key '{key}'"

    def test_all_entries_have_non_empty_template(self) -> None:
        for key, mapping in API_MAPPINGS.items():
            assert mapping.template, f"Empty template for key '{key}'"

    def test_all_entries_have_compiled_pattern(self) -> None:
        for key, mapping in API_MAPPINGS.items():
            assert isinstance(mapping.pattern, re.Pattern), (
                f"Pattern for '{key}' is not a compiled regex"
            )

    def test_all_entries_have_valid_severity(self) -> None:
        valid_severities = set(Severity)
        for key, mapping in API_MAPPINGS.items():
            assert mapping.severity in valid_severities, (
                f"Invalid severity for '{key}': {mapping.severity}"
            )

    def test_all_entries_have_migration_note(self) -> None:
        for key, mapping in API_MAPPINGS.items():
            assert len(mapping.migration_note) > 10, (
                f"Migration note too short for '{key}'"
            )

    def test_keys_match_deprecated_api(self) -> None:
        for key, mapping in API_MAPPINGS.items():
            assert key == mapping.deprecated_api, (
                f"Key '{key}' does not match deprecated_api '{mapping.deprecated_api}'"
            )


class TestGetAllPatterns:
    """Tests for the get_all_patterns() helper."""

    def test_returns_list_of_correct_length(self) -> None:
        patterns = get_all_patterns()
        assert len(patterns) == len(API_MAPPINGS)

    def test_returns_list_of_tuples(self) -> None:
        for pattern, mapping in get_all_patterns():
            assert isinstance(pattern, re.Pattern)
            assert isinstance(mapping, APIMapping)

    def test_sorted_by_pattern_length_descending(self) -> None:
        patterns = get_all_patterns()
        lengths = [len(p.pattern) for p, _ in patterns]
        assert lengths == sorted(lengths, reverse=True)


class TestGetMapping:
    """Tests for the get_mapping() lookup function."""

    def test_returns_mapping_for_known_key(self) -> None:
        mapping = get_mapping("MLModel.init(contentsOf:)")
        assert mapping is not None
        assert mapping.replacement_api == "CAIModel.load(contentsOf:)"

    def test_returns_none_for_unknown_key(self) -> None:
        assert get_mapping("NonExistentSymbol") is None

    def test_all_keys_are_resolvable(self) -> None:
        for key in API_MAPPINGS:
            assert get_mapping(key) is not None


class TestGetMappingsByCategory:
    """Tests for the get_mappings_by_category() helper."""

    def test_known_category_returns_results(self) -> None:
        results = get_mappings_by_category("inference")
        assert len(results) > 0

    def test_unknown_category_returns_empty(self) -> None:
        assert get_mappings_by_category("nonexistent_category") == []

    def test_all_categories_return_results(self) -> None:
        for cat in ALL_CATEGORIES:
            results = get_mappings_by_category(cat)
            assert len(results) > 0, f"Category '{cat}' returned no mappings"


class TestGetMappingsBySeverity:
    """Tests for the get_mappings_by_severity() helper."""

    def test_each_severity_level_has_at_least_one_mapping(self) -> None:
        for sev in Severity:
            results = get_mappings_by_severity(sev)
            assert len(results) > 0, f"No mappings found for severity '{sev}'"


class TestPatternMatching:
    """Verify that patterns correctly match expected source snippets."""

    @pytest.mark.parametrize("deprecated_api, source_snippet", [
        ("MLModel.init(contentsOf:)", "let m = try MLModel(contentsOf: url)"),
        ("MLModelConfiguration", "let cfg = MLModelConfiguration()"),
        ("MLComputeUnits", "cfg.computeUnits = MLComputeUnits.all"),
        ("MLMultiArray", "let arr = try MLMultiArray(shape: [1], dataType: .float32)"),
        ("MLFeatureProvider", "class MyProvider: MLFeatureProvider {"),
        ("VNCoreMLRequest", "let request = VNCoreMLRequest(model: vnModel)"),
        ("VNCoreMLModel", "let vnModel = try VNCoreMLModel(for: mlModel)"),
        ("MLUpdateTask", "let task = MLUpdateTask(forModelAt: url,"),
        ("import CoreML", "import CoreML"),
        ("@import CoreML;", "@import CoreML;"),
        ("#import <CoreML/CoreML.h>", "#import <CoreML/CoreML.h>"),
        ("MLFeatureValue", "let v = MLFeatureValue(int64: 42)"),
        ("MLBatchProvider", "class MyBatch: MLBatchProvider {"),
        ("MLPredictionOptions", "let opts = MLPredictionOptions()"),
        ("MLModel.compileModel(at:)", "let url = try MLModel.compileModel(at: modelURL)"),
        ("NLModel", "let nlModel = try NLModel(contentsOf: url)"),
    ])
    def test_pattern_matches_source(self, deprecated_api: str, source_snippet: str) -> None:
        mapping = get_mapping(deprecated_api)
        assert mapping is not None, f"No mapping found for '{deprecated_api}'"
        assert mapping.pattern.search(source_snippet), (
            f"Pattern for '{deprecated_api}' did not match: {source_snippet!r}"
        )

    @pytest.mark.parametrize("deprecated_api, clean_snippet", [
        ("import CoreML", "import CoreAI"),
        ("MLModel.init(contentsOf:)", "let m = try CAIModel(contentsOf: url)"),
        ("VNCoreMLRequest", "let request = CAIVisionRequest(model: aiModel)"),
    ])
    def test_pattern_does_not_match_replacement(self, deprecated_api: str, clean_snippet: str) -> None:
        mapping = get_mapping(deprecated_api)
        assert mapping is not None
        # The pattern should NOT match the already-migrated replacement snippet
        assert not mapping.pattern.search(clean_snippet), (
            f"Pattern for '{deprecated_api}' incorrectly matched replacement: {clean_snippet!r}"
        )


class TestConvenienceSets:
    """Tests for the module-level frozensets."""

    def test_all_deprecated_apis_contains_all_keys(self) -> None:
        assert ALL_DEPRECATED_APIS == frozenset(API_MAPPINGS.keys())

    def test_all_categories_is_frozenset(self) -> None:
        assert isinstance(ALL_CATEGORIES, frozenset)
        assert len(ALL_CATEGORIES) > 0

    def test_general_category_present(self) -> None:
        assert "general" in ALL_CATEGORIES

    def test_vision_category_present(self) -> None:
        assert "vision" in ALL_CATEGORIES
