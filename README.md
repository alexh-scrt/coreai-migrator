# coreai-migrator

A Python-based CLI tool that scans iOS/macOS Swift and Objective-C codebases for deprecated Core ML API calls and suggests equivalent Core AI framework replacements.

Given Apple's announced transition from Core ML to Core AI in iOS 27, **coreai-migrator** helps developers proactively update their apps by producing a detailed migration report with:

- File paths and line numbers for every deprecated API usage
- API-to-API mapping with suggested replacement code
- Unified code diffs showing exactly what to change
- Per-file and project-wide complexity scores
- Multiple output formats: rich terminal tables, plain text, and JSON

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [CLI Reference](#cli-reference)
   - [scan](#scan-command)
   - [list-mappings](#list-mappings-command)
   - [info](#info-command)
4. [Output Formats](#output-formats)
5. [Severity Levels](#severity-levels)
6. [Complexity Scoring](#complexity-scoring)
7. [Full API Mapping Table](#full-api-mapping-table)
8. [CI/CD Integration](#cicd-integration)
9. [Development](#development)
10. [License](#license)

---

## Installation

### From source

```bash
git clone https://github.com/yourorg/coreai-migrator.git
cd coreai-migrator
pip install -e .
```

### From PyPI (once published)

```bash
pip install coreai-migrator
```

### Requirements

- Python 3.11+
- `click >= 8.1`
- `rich >= 13.7`

---

## Quick Start

```bash
# Scan the current directory (rich terminal output by default)
coreai-migrator scan .

# Scan a specific Xcode project directory
coreai-migrator scan ./MyApp

# Output machine-readable JSON for CI pipelines
coreai-migrator scan ./MyApp --format json --output migration_report.json

# Only show high-severity and breaking findings
coreai-migrator scan ./MyApp --min-severity high

# Dry-run: check for issues without writing any output
coreai-migrator scan ./MyApp --dry-run

# Show all API mappings in the terminal
coreai-migrator list-mappings
```

---

## CLI Reference

### `scan` command

Scans a directory (or single file) for deprecated Core ML API calls.

```
coreai-migrator scan [OPTIONS] [PATH]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH`   | Directory or source file to scan | `.` (current directory) |

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--format {rich,plain,json}` | Output format | `rich` |
| `--output FILE` | Write report to FILE instead of stdout | stdout |
| `--min-severity {low,medium,high,breaking}` | Only report findings at or above this level | all |
| `--no-diffs` | Suppress unified diff output | off |
| `--no-notes` | Suppress migration notes | off |
| `--max-findings N` | Cap findings shown per file | unlimited |
| `--dry-run` | Scan without writing any output | off |
| `--skip-dir DIR` | Skip additional directory (repeatable) | — |
| `--context-lines N` | Context lines around diff hunks | `3` |
| `--follow-symlinks` | Follow symbolic links | off |
| `--verbose / -v` | Enable debug logging to stderr | off |
| `--exit-code` | Exit with code 1 if findings found (CI use) | off |
| `--version` | Show version and exit | — |

**Examples:**

```bash
# Rich colour output (default)
coreai-migrator scan ./MyApp

# Plain text report saved to file
coreai-migrator scan ./MyApp --format plain --output report.txt

# JSON report for CI pipeline
coreai-migrator scan ./MyApp --format json --output report.json --exit-code

# Only breaking changes, no diffs
coreai-migrator scan ./MyApp --min-severity breaking --no-diffs

# Skip vendor/generated directories
coreai-migrator scan ./MyApp --skip-dir Vendor --skip-dir Generated

# Verbose scan with more diff context
coreai-migrator scan ./MyApp --verbose --context-lines 5
```

---

### `list-mappings` command

Displays the full table of deprecated Core ML → Core AI API mappings.

```
coreai-migrator list-mappings [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--category CAT` | Filter by category | all |
| `--severity LEVEL` | Filter by severity | all |
| `--format {rich,plain,json}` | Output format | `rich` |
| `--verbose / -v` | Include migration notes | off |

**Examples:**

```bash
# Show all mappings
coreai-migrator list-mappings

# Show only vision-related mappings
coreai-migrator list-mappings --category vision

# Show only breaking-change mappings with notes
coreai-migrator list-mappings --severity breaking --verbose

# Export mapping table as JSON
coreai-migrator list-mappings --format json > mappings.json
```

---

### `info` command

Displays tool version, total pattern count, and a breakdown by severity and category.

```
coreai-migrator info
```

---

## Output Formats

### `rich` (default)

Colour-coded terminal tables with severity badges, complexity scores, unified diffs rendered with syntax highlighting, and migration notes.

```
╭─────────────────────── Migration Summary ────────────────────────────╮
│ coreai-migrator Migration Report                                      │
│ Root: /Users/dev/MyApp                                                │
│ Scanned: 42 files  Affected: 7 files  Findings: 23                   │
│ Overall complexity: Medium (38 pts)                                   │
╰───────────────────────────────────────────────────────────────────────╯
```

### `plain`

Human-readable plain text suitable for log files and CI output without ANSI codes.

```
========================================================================
  coreai-migrator Migration Report
========================================================================
  Root path      : /Users/dev/MyApp
  Scanned files  : 42
  Affected files : 7
  Total findings : 23
  Complexity     : Medium (score: 38)
========================================================================

------------------------------------------------------------------------
File    : /Users/dev/MyApp/Sources/ModelManager.swift
Language: swift
Findings: 5  Complexity: 14  Max severity: HIGH
------------------------------------------------------------------------
  [1] Line 12, Col 4
      Deprecated : MLModel.init(contentsOf:)
      Replacement: CAIModel.load(contentsOf:)
      Severity   : MEDIUM
      Original   : let model = try MLModel(contentsOf: url)
      Suggested  : let model = try CAIModel(contentsOf: url)
      Note       : Replace MLModel(contentsOf:) with CAIModel.load(contentsOf:).
```

### `json`

Fully structured JSON report ideal for CI/CD integration and further processing.

```json
{
  "root_path": "/Users/dev/MyApp",
  "scanned_files": 42,
  "affected_files": 7,
  "total_findings": 23,
  "total_complexity_score": 38,
  "complexity_label": "Medium",
  "file_reports": [
    {
      "file_path": "/Users/dev/MyApp/Sources/ModelManager.swift",
      "language": "swift",
      "finding_count": 5,
      "complexity_score": 14,
      "max_severity": "high",
      "findings": [
        {
          "line_number": 12,
          "column": 4,
          "deprecated_api": "MLModel.init(contentsOf:)",
          "replacement_api": "CAIModel.load(contentsOf:)",
          "original_line": "    let model = try MLModel(contentsOf: url)",
          "suggested_line": "    let model = try CAIModel(contentsOf: url)",
          "severity": "medium",
          "migration_note": "Replace MLModel(contentsOf:) with CAIModel.load(contentsOf:). ...",
          "complexity_score": 2,
          "diff_lines": ["--- a/...", "+++ b/...", "@@ -12 +12 @@", "-    let model = try MLModel...", "+    let model = try CAIModel..."]
        }
      ]
    }
  ]
}
```

---

## Severity Levels

| Level | Weight | Meaning |
|-------|--------|---------|
| `low` | 1 | Trivial rename with identical API surface. Drop-in replacement. |
| `medium` | 2 | Minor API changes (e.g. async/await conversion, parameter rename). |
| `high` | 4 | Significant refactoring required (e.g. new input/output types). |
| `breaking` | 8 | No direct replacement; requires new training pipeline or significant rewrite. |

---

## Complexity Scoring

Each finding contributes its severity weight to the file's complexity score. File scores are summed to produce the project-wide score, which maps to a human-readable label:

| Score Range | Label |
|-------------|-------|
| 0 | **Clean** – no deprecated APIs found |
| 1–10 | **Low** – a handful of trivial renames |
| 11–40 | **Medium** – moderate effort required |
| 41–100 | **High** – significant migration work |
| > 100 | **Breaking** – major rewrite likely needed |

Use the complexity label to prioritise which files to tackle first.

---

## Full API Mapping Table

### General (import statements)

| Deprecated | Replacement | Severity |
|------------|-------------|----------|
| `import CoreML` | `import CoreAI` | low |
| `@import CoreML;` | `@import CoreAI;` | low |
| `#import <CoreML/CoreML.h>` | `#import <CoreAI/CoreAI.h>` | low |

### Model I/O

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `MLModel.init(contentsOf:)` | `CAIModel.load(contentsOf:)` | medium | New API is async-first; use `await`. |
| `MLModel.init(contentsOf:configuration:)` | `CAIModel.load(contentsOf:configuration:)` | medium | `MLModelConfiguration` → `CAIModelConfiguration`. |
| `MLModel.load(contentsOf:configuration:completionHandler:)` | `CAIModel.load(contentsOf:configuration:)` | low | Remove completion handler; use `await`. |
| `MLModel.compileModel(at:)` | `CAIModel.compile(at:)` | medium | Compiled artefacts now use `.caimodelc`. |
| `MLModelConfiguration` | `CAIModelConfiguration` | low | Most properties have direct equivalents. |
| `MLComputeUnits` | `CAIComputePolicy` | medium | `.all` → `.automatic`, `.cpuOnly` → `.cpu`. |
| `MLModelStructuredProgram` | `CAICompiledModel` | breaking | Recompile with Core AI toolchain. |
| `MLProgram` | `CAICompiledModel` | breaking | Re-export model using Core AI tooling. |
| `MLOptimizationHints` | `CAIOptimizationPolicy` | medium | Migrate `reshapeFrequency` and `specialization`. |
| `MLSpecialization` | `CAISpecializationMode` | low | `.none` → `.disabled`, `.full` → `.full`. |

### Inference

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `MLModel.prediction(from:)` | `CAIModel.perform(_:)` | high | Wrap input in `CAIInferenceRequest`. |
| `MLModel.prediction(from:options:)` | `CAIModel.perform(_:options:)` | high | Migrate `MLPredictionOptions` → `CAIInferenceOptions`. |
| `MLModel.predictions(fromBatch:)` | `CAIModel.perform(batch:)` | high | Batch inputs → `[CAIInferenceRequest]`. |
| `MLPredictionOptions` | `CAIInferenceOptions` | low | `usesCPUOnly` → `computePolicy = .cpu`. |
| `MLBatchProvider` | `CAIBatchRequestProvider` | medium | Implement `count` and `featuresAt(index:)`. |
| `MLArrayBatchProvider` | `CAIArrayBatchProvider` | low | Initialiser signature unchanged. |

### Feature Providers

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `MLFeatureProvider` | `CAIRequestFeatureProvider` | medium | Implement `featureNames` and `featureValue(for:)`. |
| `MLDictionaryFeatureProvider` | `CAIDictionaryFeatureProvider` | low | Initialiser is identical. |
| `MLFeatureValue` | `CAIFeatureValue` | low | Factory constructors unchanged. |
| `MLFeatureType` | `CAIFeatureType` | low | Case names are identical. |
| `id<MLFeatureProvider>` | `id<CAIRequestFeatureProvider>` | medium | ObjC type annotation update. |

### Tensors & Arrays

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `MLMultiArray` | `CAITensor` | high | New init API; migrate element access to `.withUnsafeMutableBytes`. |
| `MLMultiArrayDataType` | `CAITensorDataType` | low | `.double` → `.float64`. |
| `MLSequence` | `CAISequenceTensor` | medium | Use `CAISequenceTensor(strings:)` or `CAISequenceTensor(int64s:)`. |

### Model Introspection

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `MLModelDescription` | `CAIModelDescription` | low | `inputDescriptionsByName` / `outputDescriptionsByName` unchanged. |
| `MLFeatureDescription` | `CAIFeatureDescription` | low | `type` now returns `CAIFeatureType`. |
| `MLModelMetadataKey` | `CAIModelMetadataKey` | low | Key names preserved. |

### Vision Integration

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `VNCoreMLRequest` | `CAIVisionRequest` | high | Initialise with `CAIModel` directly; no Vision wrapper needed. |
| `VNCoreMLModel` | `CAIVisionModel` | medium | Use `CAIVisionModel(model:)` with a `CAIModel` instance. |
| `VNCoreMLFeatureValueObservation` | `CAIVisionFeatureObservation` | medium | Access via `.feature` property. |
| `MLPixelBuffer` | `CAIPixelBuffer` | medium | Underlying `CVPixelBuffer` handling unchanged. |
| `MLImageClassifier` | `CAIImageClassifier` | breaking | Re-export model to `.caimodel` format. |

### NLP Integration

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `NLModel` | `CAILanguageModel` | high | Use `CAILanguageModel.load(contentsOf:)` and `.perform(_:)`. |
| `NLModelConfiguration` | `CAILanguageModelConfiguration` | medium | Direct replacement. |

### Audio

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `MLSoundClassifier` | `CAIAudioClassifier` | breaking | Update training pipeline. |

### On-Device Personalization

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `MLUpdateTask` | `CAIUpdateTask` | high | Callback signature changes to `(CAIUpdateResult)`. |
| `MLUpdateContext` | `CAIUpdateResult` | high | Access updated model via `result.model`. |
| `MLUpdateProgressHandlers` | `CAIUpdateProgressHandler` | medium | Pass a single closure instead of multi-handler struct. |
| `MLMetricKey` | `CAIMetricKey` | low | Key names preserved. |

### Objective-C Specific

| Deprecated | Replacement | Severity | Notes |
|------------|-------------|----------|-------|
| `[MLModel modelWithContentsOfURL:error:]` | `[CAIModel loadWithContentsOfURL:configuration:completionHandler:]` | medium | Remove synchronous error-pointer pattern. |
| `[model predictionFromFeatures:error:]` | `[model performRequest:completionHandler:]` | high | Wrap features in `CAIInferenceRequest`. |
| `[VNCoreMLRequest alloc]` | `[CAIVisionRequest alloc]` | high | Also update `VNCoreMLModel` → `CAIVisionModel`. |

---

## CI/CD Integration

Use `--format json` and `--exit-code` together to integrate coreai-migrator into your CI pipeline:

```yaml
# GitHub Actions example
- name: Check for deprecated Core ML APIs
  run: |
    pip install coreai-migrator
    coreai-migrator scan ./MyApp \
      --format json \
      --output coreml_report.json \
      --min-severity medium \
      --exit-code

- name: Upload migration report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: coreml-migration-report
    path: coreml_report.json
```

```bash
# Shell script example
coreai-migrator scan ./MyApp \
  --format json \
  --output report.json \
  --exit-code

if [ $? -eq 1 ]; then
  echo "Deprecated Core ML APIs found. See report.json for details."
  exit 1
fi
```

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | No findings (or `--exit-code` not set) |
| `1` | Findings found (only when `--exit-code` is set) |
| `2` | Error (invalid path, unwritable output file, etc.) |

---

## Development

### Setup

```bash
git clone https://github.com/yourorg/coreai-migrator.git
cd coreai-migrator
pip install -e ".[dev]"
```

### Running tests

```bash
pytest
# or with verbose output
pytest -v
# run a specific test module
pytest tests/test_analyzer.py -v
```

### Project structure

```
coreai_migrator/
├── __init__.py        # Package init, version string
├── cli.py             # Click CLI entry point
├── scanner.py         # Recursive filesystem walker
├── analyzer.py        # Regex-based deprecated API detector
├── mappings.py        # Core ML → Core AI mapping table (40+ APIs)
├── diff_builder.py    # Unified diff generation via difflib
├── reporter.py        # Rich / plain / JSON output rendering
└── models.py          # Finding, FileReport, MigrationReport dataclasses
tests/
├── fixtures/
│   └── sample_coreml.swift   # Synthetic test fixture
├── test_analyzer.py
├── test_diff_builder.py
├── test_mappings.py
├── test_models.py
├── test_reporter.py
└── test_scanner.py
```

### Adding a new API mapping

1. Open `coreai_migrator/mappings.py`.
2. Add a new entry to the `API_MAPPINGS` dict:

```python
"MLNewSymbol": APIMapping(
    deprecated_api="MLNewSymbol",
    replacement_api="CAINewSymbol",
    pattern=_p(r"\bMLNewSymbol\b"),
    template="CAINewSymbol",
    severity=Severity.MEDIUM,
    migration_note="MLNewSymbol is replaced by CAINewSymbol. ...",
    category="inference",
    doc_url="https://developer.apple.com/documentation/coreai/cainewsymbol",
),
```

3. Add a fixture line to `tests/fixtures/sample_coreml.swift`.
4. Add a test case to `tests/test_analyzer.py`.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
