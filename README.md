# coreai-migrator

> Scan once. Migrate confidently. Ship for iOS 27.

**coreai-migrator** is a Python CLI tool that scans iOS/macOS Swift and Objective-C codebases for deprecated Core ML API calls and maps them to their Core AI framework replacements. With Apple's transition from Core ML to Core AI in iOS 27, it produces a detailed migration report complete with file paths, line numbers, unified diffs, and a complexity score — so your team knows exactly what needs to change and where to start.

---

## Quick Start

```bash
# Install
pip install coreai-migrator

# Scan your project (rich terminal output by default)
coreai-migrator scan ./MyApp

# Export a JSON report for CI/CD
coreai-migrator scan ./MyApp --format json --output report.json
```

That's it. After running `scan`, you'll see a colour-coded table of every deprecated API call, its suggested replacement, and the overall migration complexity score for your project.

---

## Features

- **40+ deprecated API patterns** — Detects `MLModel`, `MLFeatureProvider`, `VNCoreMLRequest`, and more across Swift and Objective-C (`.swift`, `.m`, `.mm`, `.h`) files with line-precise findings.
- **Authoritative Core ML → Core AI mapping table** — Every deprecated symbol ships with a drop-in replacement template, a migration note, and a complexity weight (`low` / `medium` / `high` / `breaking`).
- **Automatic unified diff generation** — For each finding, see exactly how the deprecated call should be rewritten — no guesswork required.
- **Multiple output formats** — Rich colour-coded terminal tables, plain text for log files, and machine-readable JSON for CI/CD pipeline integration.
- **Per-file and project-wide complexity scores** — Prioritise which files to tackle first based on aggregated migration effort scores.

---

## Usage Examples

### Scan a project with rich terminal output

```bash
coreai-migrator scan ./MyApp
```

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ File                       ┃ Line ┃ Deprecated API        ┃ Replacement               ┃ Severity ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ Sources/ModelLoader.swift  │   14 │ MLModel(contentsOf:)  │ CAIModel(loading:)        │ 🟡 medium │
│ Sources/ModelLoader.swift  │   31 │ MLModelConfiguration  │ CAIModelConfiguration     │ 🟢 low    │
│ Sources/VisionBridge.swift │   42 │ VNCoreMLRequest       │ CAIVisionRequest          │ 🔴 high   │
│ Sources/NLPipeline.swift   │   88 │ NLModel               │ CAILanguageModel          │ 🔴 high   │
└────────────────────────────┴──────┴───────────────────────┴───────────────────────────┴──────────┘

Project complexity score: 47 / 100  (medium)  •  4 findings across 3 files
```

### Filter by minimum severity

```bash
coreai-migrator scan ./MyApp --min-severity high
```

### Output plain text to a log file

```bash
coreai-migrator scan ./MyApp --format plain --output migration.txt
```

### Export JSON for CI/CD integration

```bash
coreai-migrator scan ./MyApp --format json --output report.json
```

```json
{
  "summary": {
    "total_findings": 4,
    "files_affected": 3,
    "complexity_score": 47,
    "complexity_label": "medium"
  },
  "files": [
    {
      "path": "Sources/ModelLoader.swift",
      "complexity_score": 18,
      "findings": [
        {
          "line": 14,
          "deprecated_api": "MLModel(contentsOf:)",
          "replacement": "CAIModel(loading:)",
          "severity": "medium",
          "note": "Use async CAIModel(loading:) and await the result.",
          "diff": "--- a/Sources/ModelLoader.swift\n+++ b/Sources/ModelLoader.swift\n@@ -12,7 +12,7 @@\n ...\n"
        }
      ]
    }
  ]
}
```

### Dry run (no files written)

```bash
coreai-migrator scan ./MyApp --dry-run
```

---

## CLI Reference

```
Usage: coreai-migrator scan [OPTIONS] PATH

  Scan a Swift/Objective-C codebase for deprecated Core ML APIs.

Arguments:
  PATH  Root directory or single source file to scan.  [required]

Options:
  --format [rich|plain|json]   Output format.  [default: rich]
  --output FILE                Write output to FILE instead of stdout.
  --min-severity [low|medium|high|breaking]
                               Only report findings at or above this severity.
  --dry-run                    Analyse and print findings without writing output files.
  --help                       Show this message and exit.
```

---

## API Mapping Reference (sample)

| Deprecated (Core ML) | Replacement (Core AI) | Severity | Notes |
|---|---|---|---|
| `MLModel(contentsOf:)` | `CAIModel(loading:)` | medium | Switch to async API |
| `MLModelConfiguration` | `CAIModelConfiguration` | low | Drop-in rename |
| `MLFeatureProvider` | `CAIFeatureProvider` | medium | Protocol conformance updated |
| `VNCoreMLRequest` | `CAIVisionRequest` | high | New initialiser signature |
| `NLModel` | `CAILanguageModel` | high | New inference API |
| `MLPredictionOptions` | `CAIPredictionOptions` | low | Property names changed |

> The full mapping table (40+ APIs) lives in `coreai_migrator/mappings.py`.

---

## Project Structure

```
coreai-migrator/
├── pyproject.toml               # Project metadata, build config, CLI entry point
├── requirements.txt             # Pinned runtime dependencies
├── README.md
├── coreai_migrator/
│   ├── __init__.py              # Package init, version string
│   ├── cli.py                   # Click CLI entry point
│   ├── scanner.py               # Recursive file-system walker
│   ├── analyzer.py              # Regex-based API pattern detection engine
│   ├── mappings.py              # Core ML → Core AI mapping table
│   ├── diff_builder.py          # Unified diff generation per finding
│   ├── reporter.py              # Rich / plain / JSON report rendering
│   └── models.py                # Finding, FileReport, MigrationReport dataclasses
└── tests/
    ├── __init__.py
    ├── test_analyzer.py         # Pattern detection accuracy tests
    ├── test_diff_builder.py     # Diff generation correctness tests
    ├── test_reporter.py         # JSON and plain-text serialization tests
    ├── test_scanner.py          # File discovery and language classification tests
    ├── test_models.py           # Dataclass and complexity score tests
    ├── test_mappings.py         # Mapping table structure and completeness tests
    └── fixtures/
        └── sample_coreml.swift  # Synthetic Swift fixture with deprecated API calls
```

---

## Configuration

coreai-migrator is configured entirely via CLI flags — no config file required. The key options are:

| Option | Default | Description |
|---|---|---|
| `--format` | `rich` | Output format: `rich`, `plain`, or `json` |
| `--output` | stdout | Write report to a file instead of the terminal |
| `--min-severity` | `low` | Filter findings below this severity level |
| `--dry-run` | off | Print findings without writing any output files |

For CI/CD pipelines, the recommended invocation is:

```bash
coreai-migrator scan . --format json --output coreai-report.json --min-severity medium
```

The process exits with code `0` when no findings meet the severity threshold, and `1` when findings are present — making it easy to gate pull requests.

---

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/your-org/coreai-migrator.git
cd coreai-migrator
pip install -e ".[dev]"

# Run tests
pytest tests/
```

---

## License

MIT © coreai_migrator contributors. See [LICENSE](LICENSE) for details.

---

*Built with [Jitter](https://github.com/jitter-ai) - an AI agent that ships code daily.*
