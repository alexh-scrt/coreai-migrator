"""Recursive filesystem walker for coreai_migrator.

This module provides the ``Scanner`` class, which traverses a directory tree
(or accepts a single file path) and yields all Swift (``.swift``) and
Objective-C (``.m``, ``.mm``, ``.h``) source files suitable for analysis.

Typical usage::

    from coreai_migrator.scanner import Scanner

    scanner = Scanner(root_path=Path("./MyApp"))
    for source_file in scanner.scan():
        print(source_file.path, source_file.language)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: File extensions recognised as Swift source files.
SWIFT_EXTENSIONS: frozenset[str] = frozenset({".swift"})

#: File extensions recognised as Objective-C / Objective-C++ source files.
OBJC_EXTENSIONS: frozenset[str] = frozenset({".m", ".mm", ".h"})

#: All source extensions that the scanner will process.
SOURCE_EXTENSIONS: frozenset[str] = SWIFT_EXTENSIONS | OBJC_EXTENSIONS

#: Directory names to skip unconditionally (build artefacts, VCS metadata, etc.).
SKIPPED_DIRECTORIES: frozenset[str] = frozenset({
    ".git",
    ".svn",
    ".hg",
    ".DS_Store",
    "build",
    "Build",
    "DerivedData",
    ".build",
    "Pods",
    "Carthage",
    ".swiftpm",
    "__pycache__",
    "node_modules",
    ".idea",
    ".vscode",
})


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceFile:
    """Represents a single source file discovered during a scan.

    Attributes:
        path:     Absolute path to the source file.
        language: Either ``'swift'`` or ``'objc'``.
    """

    path: Path
    language: str

    @property
    def relative_to(self) -> Path:
        """Return path as-is (callers may call Path.relative_to themselves)."""
        return self.path


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class Scanner:
    """Discovers Swift and Objective-C source files under a given root path.

    The scanner walks the directory tree recursively, skipping well-known
    directories that should never contain app source code (e.g. ``.git``,
    ``DerivedData``, ``Pods``).

    Args:
        root_path:           Directory to scan, or a single source file path.
        extra_skip_dirs:     Additional directory names to skip.
        follow_symlinks:     Whether to follow symbolic links (default ``False``).
        max_file_size_bytes: Files larger than this are skipped to avoid reading
                             huge generated files (default 5 MB).
    """

    def __init__(
        self,
        root_path: Path,
        extra_skip_dirs: Optional[set[str]] = None,
        follow_symlinks: bool = False,
        max_file_size_bytes: int = 5 * 1024 * 1024,  # 5 MB
    ) -> None:
        self._root_path = Path(root_path).resolve()
        self._skip_dirs: frozenset[str] = (
            SKIPPED_DIRECTORIES | frozenset(extra_skip_dirs or set())
        )
        self._follow_symlinks = follow_symlinks
        self._max_file_size_bytes = max_file_size_bytes

    @property
    def root_path(self) -> Path:
        """The resolved root path being scanned."""
        return self._root_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self) -> Generator[SourceFile, None, None]:
        """Yield :class:`SourceFile` objects for every relevant source file found.

        If :attr:`root_path` is a regular file, it is yielded directly
        (provided its extension is recognised).  If it is a directory, the
        entire subtree is walked.

        Yields:
            :class:`SourceFile` instances in filesystem traversal order.

        Raises:
            FileNotFoundError: If :attr:`root_path` does not exist.
            NotADirectoryError: If :attr:`root_path` is neither a file nor a
                directory (e.g. a device node).
        """
        if not self._root_path.exists():
            raise FileNotFoundError(
                f"Scan root does not exist: {self._root_path}"
            )

        if self._root_path.is_file():
            source_file = self._classify_file(self._root_path)
            if source_file is not None:
                yield source_file
            return

        if not self._root_path.is_dir():
            raise NotADirectoryError(
                f"Scan root is neither a file nor a directory: {self._root_path}"
            )

        yield from self._walk_directory(self._root_path)

    def scan_to_list(self) -> list[SourceFile]:
        """Convenience wrapper that collects :meth:`scan` results into a list.

        Returns:
            Sorted list of :class:`SourceFile` objects (sorted by path string).
        """
        files = list(self.scan())
        files.sort(key=lambda sf: str(sf.path))
        return files

    def count_files(self) -> int:
        """Return the total number of source files that would be scanned.

        This consumes the generator returned by :meth:`scan` without storing
        results.

        Returns:
            Integer count of discovered source files.
        """
        return sum(1 for _ in self.scan())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _walk_directory(self, directory: Path) -> Generator[SourceFile, None, None]:
        """Recursively walk *directory*, yielding classified source files.

        Args:
            directory: The directory to walk.

        Yields:
            :class:`SourceFile` instances.
        """
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except PermissionError as exc:
            logger.warning("Permission denied scanning directory: %s (%s)", directory, exc)
            return
        except OSError as exc:
            logger.warning("OS error scanning directory: %s (%s)", directory, exc)
            return

        for entry in entries:
            # Skip symlinks unless explicitly requested
            if entry.is_symlink() and not self._follow_symlinks:
                logger.debug("Skipping symlink: %s", entry)
                continue

            if entry.is_dir():
                if entry.name in self._skip_dirs:
                    logger.debug("Skipping directory: %s", entry)
                    continue
                yield from self._walk_directory(entry)

            elif entry.is_file():
                source_file = self._classify_file(entry)
                if source_file is not None:
                    yield source_file

    def _classify_file(self, file_path: Path) -> Optional[SourceFile]:
        """Determine whether *file_path* is a Swift or Objective-C source file.

        Files that are too large or have unrecognised extensions are silently
        ignored.

        Args:
            file_path: Path to the candidate file.

        Returns:
            A :class:`SourceFile` if the file should be analysed, otherwise
            ``None``.
        """
        suffix = file_path.suffix.lower()
        if suffix not in SOURCE_EXTENSIONS:
            return None

        # Skip files that are too large
        try:
            size = file_path.stat().st_size
        except OSError as exc:
            logger.warning("Cannot stat file %s: %s", file_path, exc)
            return None

        if size > self._max_file_size_bytes:
            logger.warning(
                "Skipping oversized file (%d bytes): %s", size, file_path
            )
            return None

        language = "swift" if suffix in SWIFT_EXTENSIONS else "objc"
        return SourceFile(path=file_path, language=language)


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def scan_path(
    root_path: Path,
    extra_skip_dirs: Optional[set[str]] = None,
    follow_symlinks: bool = False,
    max_file_size_bytes: int = 5 * 1024 * 1024,
) -> list[SourceFile]:
    """Convenience function: scan *root_path* and return a sorted list of source files.

    Args:
        root_path:           Directory or file to scan.
        extra_skip_dirs:     Additional directory names to skip.
        follow_symlinks:     Whether to follow symbolic links.
        max_file_size_bytes: Maximum file size to process.

    Returns:
        Sorted list of :class:`SourceFile` objects.

    Raises:
        FileNotFoundError: If *root_path* does not exist.
    """
    scanner = Scanner(
        root_path=root_path,
        extra_skip_dirs=extra_skip_dirs,
        follow_symlinks=follow_symlinks,
        max_file_size_bytes=max_file_size_bytes,
    )
    return scanner.scan_to_list()
