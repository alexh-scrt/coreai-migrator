"""coreai_migrator - CLI tool for migrating deprecated Core ML APIs to Core AI.

This package scans iOS/macOS Swift and Objective-C codebases for deprecated
Core ML API calls and produces a detailed migration report with file paths,
line numbers, API-to-API mappings, unified code diffs, and complexity scores.

Typical usage::

    from coreai_migrator import __version__
    print(__version__)

Or via the CLI::

    coreai-migrator scan ./MyApp --format rich
"""

__version__ = "0.1.0"
__author__ = "coreai_migrator contributors"
__license__ = "MIT"

__all__ = ["__version__", "__author__", "__license__"]
