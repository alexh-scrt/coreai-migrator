"""Unit tests for coreai_migrator.scanner.

Verifies that the Scanner discovers the correct files, respects skip-lists,
classifies languages correctly, and handles edge cases such as single-file
inputs and missing paths.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from coreai_migrator.scanner import (
    OBJC_EXTENSIONS,
    SKIPPED_DIRECTORIES,
    SOURCE_EXTENSIONS,
    SWIFT_EXTENSIONS,
    Scanner,
    SourceFile,
    scan_path,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "") -> None:
    """Create parent dirs and write content to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# SourceFile tests
# ---------------------------------------------------------------------------


class TestSourceFile:
    def test_frozen(self) -> None:
        sf = SourceFile(path=Path("App/Foo.swift"), language="swift")
        with pytest.raises((AttributeError, TypeError)):
            sf.language = "objc"  # type: ignore[misc]

    def test_relative_to_returns_path(self) -> None:
        p = Path("App/Foo.swift")
        sf = SourceFile(path=p, language="swift")
        assert sf.relative_to == p


# ---------------------------------------------------------------------------
# Extension / constant sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_swift_extensions(self) -> None:
        assert ".swift" in SWIFT_EXTENSIONS

    def test_objc_extensions(self) -> None:
        for ext in (".m", ".mm", ".h"):
            assert ext in OBJC_EXTENSIONS

    def test_source_extensions_union(self) -> None:
        assert SOURCE_EXTENSIONS == SWIFT_EXTENSIONS | OBJC_EXTENSIONS

    def test_skipped_dirs_contains_expected(self) -> None:
        for name in ("build", "DerivedData", "Pods", ".git"):
            assert name in SKIPPED_DIRECTORIES


# ---------------------------------------------------------------------------
# Scanner tests
# ---------------------------------------------------------------------------


class TestScannerSingleFile:
    def test_single_swift_file(self, tmp_path: Path) -> None:
        swift_file = tmp_path / "Model.swift"
        _write(swift_file, "import CoreML")
        scanner = Scanner(root_path=swift_file)
        results = scanner.scan_to_list()
        assert len(results) == 1
        assert results[0].language == "swift"
        assert results[0].path == swift_file.resolve()

    def test_single_objc_file(self, tmp_path: Path) -> None:
        objc_file = tmp_path / "ViewController.m"
        _write(objc_file, "#import <CoreML/CoreML.h>")
        scanner = Scanner(root_path=objc_file)
        results = scanner.scan_to_list()
        assert len(results) == 1
        assert results[0].language == "objc"

    def test_single_non_source_file_yields_nothing(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "notes.txt"
        _write(txt_file, "some notes")
        scanner = Scanner(root_path=txt_file)
        results = scanner.scan_to_list()
        assert results == []

    def test_missing_path_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent" / "file.swift"
        scanner = Scanner(root_path=missing)
        with pytest.raises(FileNotFoundError):
            scanner.scan_to_list()


class TestScannerDirectory:
    def test_finds_swift_and_objc_files(self, tmp_path: Path) -> None:
        _write(tmp_path / "App" / "Model.swift")
        _write(tmp_path / "App" / "Bridge.h")
        _write(tmp_path / "App" / "Impl.m")
        _write(tmp_path / "App" / "Impl.mm")
        _write(tmp_path / "README.md")
        scanner = Scanner(root_path=tmp_path)
        results = scanner.scan_to_list()
        paths = {r.path.name for r in results}
        assert "Model.swift" in paths
        assert "Bridge.h" in paths
        assert "Impl.m" in paths
        assert "Impl.mm" in paths
        assert "README.md" not in paths

    def test_skips_build_directory(self, tmp_path: Path) -> None:
        _write(tmp_path / "App" / "Model.swift")
        _write(tmp_path / "build" / "Generated.swift")
        scanner = Scanner(root_path=tmp_path)
        results = scanner.scan_to_list()
        names = [r.path.name for r in results]
        assert "Model.swift" in names
        assert "Generated.swift" not in names

    def test_skips_pods_directory(self, tmp_path: Path) -> None:
        _write(tmp_path / "App" / "ViewController.swift")
        _write(tmp_path / "Pods" / "AlamofireMLBridge.swift")
        scanner = Scanner(root_path=tmp_path)
        results = scanner.scan_to_list()
        names = [r.path.name for r in results]
        assert "ViewController.swift" in names
        assert "AlamofireMLBridge.swift" not in names

    def test_skips_extra_dirs(self, tmp_path: Path) -> None:
        _write(tmp_path / "Source" / "Real.swift")
        _write(tmp_path / "Generated" / "AutoGen.swift")
        scanner = Scanner(root_path=tmp_path, extra_skip_dirs={"Generated"})
        results = scanner.scan_to_list()
        names = [r.path.name for r in results]
        assert "Real.swift" in names
        assert "AutoGen.swift" not in names

    def test_language_classification(self, tmp_path: Path) -> None:
        _write(tmp_path / "A.swift")
        _write(tmp_path / "B.m")
        _write(tmp_path / "C.h")
        scanner = Scanner(root_path=tmp_path)
        results = {r.path.name: r.language for r in scanner.scan_to_list()}
        assert results["A.swift"] == "swift"
        assert results["B.m"] == "objc"
        assert results["C.h"] == "objc"

    def test_count_files(self, tmp_path: Path) -> None:
        for i in range(5):
            _write(tmp_path / f"File{i}.swift")
        scanner = Scanner(root_path=tmp_path)
        assert scanner.count_files() == 5

    def test_results_sorted_by_path(self, tmp_path: Path) -> None:
        _write(tmp_path / "Z.swift")
        _write(tmp_path / "A.swift")
        _write(tmp_path / "M.swift")
        scanner = Scanner(root_path=tmp_path)
        results = scanner.scan_to_list()
        paths = [str(r.path) for r in results]
        assert paths == sorted(paths)

    def test_empty_directory_yields_nothing(self, tmp_path: Path) -> None:
        scanner = Scanner(root_path=tmp_path)
        assert scanner.scan_to_list() == []

    def test_skips_oversized_file(self, tmp_path: Path) -> None:
        big_file = tmp_path / "Big.swift"
        _write(big_file, "x" * 10)  # tiny content
        scanner = Scanner(root_path=tmp_path, max_file_size_bytes=5)
        results = scanner.scan_to_list()
        assert results == []

    def test_nested_directories_traversed(self, tmp_path: Path) -> None:
        _write(tmp_path / "a" / "b" / "c" / "Deep.swift")
        scanner = Scanner(root_path=tmp_path)
        results = scanner.scan_to_list()
        assert len(results) == 1
        assert results[0].path.name == "Deep.swift"


class TestScanPath:
    """Tests for the module-level scan_path convenience function."""

    def test_returns_list(self, tmp_path: Path) -> None:
        _write(tmp_path / "Foo.swift")
        result = scan_path(tmp_path)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            scan_path(tmp_path / "no_such_dir")
