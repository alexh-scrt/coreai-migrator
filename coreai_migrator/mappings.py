"""Authoritative Core ML → Core AI API mapping table.

This module provides:
- ``API_MAPPINGS``: A dictionary keyed by deprecated Core ML symbol name.
  Each entry is an ``APIMapping`` dataclass with the replacement symbol,
  a regex pattern for detection, a replacement template string, the
  complexity/severity level, and a human-readable migration note.
- ``get_all_patterns()``: Helper that returns every compiled regex along
  with its associated mapping, ready for use by the analyzer engine.
- ``get_mapping(api_name)``: Look up a mapping by deprecated API name.

Replacement template variables
--------------------------------
Templates use Python's ``str.replace`` / ``re.sub`` style.
The special placeholder ``{match}`` refers to the full regex match text
so that the diff builder can perform a straightforward substitution.
Some templates include ``{arg0}`` – ``{argN}`` for positional capture groups.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from coreai_migrator.models import Severity


@dataclass
class APIMapping:
    """Describes how a single deprecated Core ML API maps to its Core AI successor.

    Attributes:
        deprecated_api:   Exact deprecated symbol name (used as the dict key).
        replacement_api:  Recommended Core AI replacement symbol.
        pattern:          Compiled regex that detects the deprecated usage in source.
        template:         Replacement string; ``{match}`` is the full matched text.
                          Capture-group back-references use ``\\1``, ``\\2``, etc.
        severity:         Migration complexity level.
        migration_note:   Developer-facing explanation of what changed and how to adapt.
        category:         Optional grouping label (e.g. "inference", "vision", "model-io").
        doc_url:          Optional link to Apple developer documentation.
    """

    deprecated_api: str
    replacement_api: str
    pattern: re.Pattern
    template: str
    severity: Severity
    migration_note: str
    category: str = "general"
    doc_url: str = ""


def _p(pattern: str, flags: int = 0) -> re.Pattern:
    """Compile a regex pattern with sensible defaults."""
    return re.compile(pattern, re.MULTILINE | flags)


# ---------------------------------------------------------------------------
# Authoritative mapping table
# ---------------------------------------------------------------------------
# Keys are the deprecated Core ML symbol name used as a stable identifier.
# The order within this dict is irrelevant; the analyzer iterates all entries.
# ---------------------------------------------------------------------------

API_MAPPINGS: dict[str, APIMapping] = {
    # -----------------------------------------------------------------------
    # MLModel
    # -----------------------------------------------------------------------
    "MLModel.init(contentsOf:)": APIMapping(
        deprecated_api="MLModel.init(contentsOf:)",
        replacement_api="CAIModel.load(contentsOf:)",
        pattern=_p(r"MLModel\s*\(\s*contentsOf\s*:"),
        template="CAIModel(contentsOf:",
        severity=Severity.MEDIUM,
        migration_note=(
            "Replace MLModel(contentsOf:) with CAIModel.load(contentsOf:). "
            "The new API is async-first; wrap calls in async/await context."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel",
    ),
    "MLModel.init(contentsOf:configuration:)": APIMapping(
        deprecated_api="MLModel.init(contentsOf:configuration:)",
        replacement_api="CAIModel.load(contentsOf:configuration:)",
        pattern=_p(r"MLModel\s*\(\s*contentsOf\s*:.*?configuration\s*:"),
        template="CAIModel(contentsOf:",
        severity=Severity.MEDIUM,
        migration_note=(
            "Replace MLModel(contentsOf:configuration:) with "
            "CAIModel.load(contentsOf:configuration:). "
            "MLModelConfiguration is now CAIModelConfiguration."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel",
    ),
    "MLModel.load(contentsOf:configuration:completionHandler:)": APIMapping(
        deprecated_api="MLModel.load(contentsOf:configuration:completionHandler:)",
        replacement_api="CAIModel.load(contentsOf:configuration:)",
        pattern=_p(r"MLModel\.load\s*\("),
        template="CAIModel.load(",
        severity=Severity.LOW,
        migration_note=(
            "MLModel.load(contentsOf:configuration:completionHandler:) is superseded by "
            "the async CAIModel.load(contentsOf:configuration:). Remove the completion "
            "handler and use await."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel",
    ),
    "MLModelConfiguration": APIMapping(
        deprecated_api="MLModelConfiguration",
        replacement_api="CAIModelConfiguration",
        pattern=_p(r"\bMLModelConfiguration\b"),
        template="CAIModelConfiguration",
        severity=Severity.LOW,
        migration_note=(
            "MLModelConfiguration is replaced by CAIModelConfiguration. "
            "Most properties have direct equivalents; check computeUnits mapping."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caimodelconfiguration",
    ),
    "MLComputeUnits": APIMapping(
        deprecated_api="MLComputeUnits",
        replacement_api="CAIComputePolicy",
        pattern=_p(r"\bMLComputeUnits\b"),
        template="CAIComputePolicy",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLComputeUnits enum is replaced by CAIComputePolicy. "
            "Migrate .all → .automatic, .cpuOnly → .cpu, .cpuAndGPU → .cpuAndGPU, "
            ".cpuAndNeuralEngine → .neuralEngine."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caicomputepolicy",
    ),
    # -----------------------------------------------------------------------
    # Prediction / inference
    # -----------------------------------------------------------------------
    "MLModel.prediction(from:)": APIMapping(
        deprecated_api="MLModel.prediction(from:)",
        replacement_api="CAIModel.perform(_:)",
        pattern=_p(r"\.prediction\s*\(\s*from\s*:"),
        template=".perform(",
        severity=Severity.HIGH,
        migration_note=(
            "MLModel.prediction(from:) is replaced by the async CAIModel.perform(_:) "
            "which accepts a CAIRequest. Wrap input preparation in a CAIInferenceRequest."
        ),
        category="inference",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel/perform(_:)",
    ),
    "MLModel.predictions(fromBatch:)": APIMapping(
        deprecated_api="MLModel.predictions(fromBatch:)",
        replacement_api="CAIModel.perform(batch:)",
        pattern=_p(r"\.predictions\s*\(\s*fromBatch\s*:"),
        template=".perform(batch:",
        severity=Severity.HIGH,
        migration_note=(
            "MLModel.predictions(fromBatch:) is replaced by CAIModel.perform(batch:). "
            "Batch inputs must be wrapped in [CAIInferenceRequest]."
        ),
        category="inference",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel/perform(batch:)",
    ),
    # -----------------------------------------------------------------------
    # Feature providers
    # -----------------------------------------------------------------------
    "MLFeatureProvider": APIMapping(
        deprecated_api="MLFeatureProvider",
        replacement_api="CAIRequestFeatureProvider",
        pattern=_p(r"\bMLFeatureProvider\b"),
        template="CAIRequestFeatureProvider",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLFeatureProvider protocol is replaced by CAIRequestFeatureProvider. "
            "Implement featureNames and featureValue(for:) as before."
        ),
        category="feature-provider",
        doc_url="https://developer.apple.com/documentation/coreai/cairequestfeatureprovider",
    ),
    "MLDictionaryFeatureProvider": APIMapping(
        deprecated_api="MLDictionaryFeatureProvider",
        replacement_api="CAIDictionaryFeatureProvider",
        pattern=_p(r"\bMLDictionaryFeatureProvider\b"),
        template="CAIDictionaryFeatureProvider",
        severity=Severity.LOW,
        migration_note=(
            "MLDictionaryFeatureProvider is replaced by CAIDictionaryFeatureProvider. "
            "The initialiser signature is identical."
        ),
        category="feature-provider",
        doc_url="https://developer.apple.com/documentation/coreai/caidictionaryfeatureprovider",
    ),
    "MLFeatureValue": APIMapping(
        deprecated_api="MLFeatureValue",
        replacement_api="CAIFeatureValue",
        pattern=_p(r"\bMLFeatureValue\b"),
        template="CAIFeatureValue",
        severity=Severity.LOW,
        migration_note=(
            "MLFeatureValue is replaced by CAIFeatureValue. "
            "Factory constructors (int64:, double:, string:, etc.) are unchanged."
        ),
        category="feature-provider",
        doc_url="https://developer.apple.com/documentation/coreai/caifeaturevalue",
    ),
    "MLFeatureType": APIMapping(
        deprecated_api="MLFeatureType",
        replacement_api="CAIFeatureType",
        pattern=_p(r"\bMLFeatureType\b"),
        template="CAIFeatureType",
        severity=Severity.LOW,
        migration_note=(
            "MLFeatureType enum is replaced by CAIFeatureType. "
            "Case names are identical."
        ),
        category="feature-provider",
        doc_url="https://developer.apple.com/documentation/coreai/caifeaturetype",
    ),
    # -----------------------------------------------------------------------
    # Multi-arrays
    # -----------------------------------------------------------------------
    "MLMultiArray": APIMapping(
        deprecated_api="MLMultiArray",
        replacement_api="CAITensor",
        pattern=_p(r"\bMLMultiArray\b"),
        template="CAITensor",
        severity=Severity.HIGH,
        migration_note=(
            "MLMultiArray is replaced by CAITensor which has a different initialisation API. "
            "Use CAITensor(shape:dataType:) and migrate element access from subscript to "
            ".withUnsafeMutableBytes."
        ),
        category="tensor",
        doc_url="https://developer.apple.com/documentation/coreai/caItensor",
    ),
    "MLMultiArrayDataType": APIMapping(
        deprecated_api="MLMultiArrayDataType",
        replacement_api="CAITensorDataType",
        pattern=_p(r"\bMLMultiArrayDataType\b"),
        template="CAITensorDataType",
        severity=Severity.LOW,
        migration_note=(
            "MLMultiArrayDataType is replaced by CAITensorDataType. "
            "Map .float16 → .float16, .float32 → .float32, .double → .float64, "
            ".int32 → .int32."
        ),
        category="tensor",
        doc_url="https://developer.apple.com/documentation/coreai/caitensordatatype",
    ),
    # -----------------------------------------------------------------------
    # Sequences
    # -----------------------------------------------------------------------
    "MLSequence": APIMapping(
        deprecated_api="MLSequence",
        replacement_api="CAISequenceTensor",
        pattern=_p(r"\bMLSequence\b"),
        template="CAISequenceTensor",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLSequence is replaced by CAISequenceTensor. "
            "Use CAISequenceTensor(strings:) or CAISequenceTensor(int64s:) factories."
        ),
        category="tensor",
        doc_url="https://developer.apple.com/documentation/coreai/caisequencetensor",
    ),
    # -----------------------------------------------------------------------
    # Model description / introspection
    # -----------------------------------------------------------------------
    "MLModelDescription": APIMapping(
        deprecated_api="MLModelDescription",
        replacement_api="CAIModelDescription",
        pattern=_p(r"\bMLModelDescription\b"),
        template="CAIModelDescription",
        severity=Severity.LOW,
        migration_note=(
            "MLModelDescription is replaced by CAIModelDescription. "
            "Access inputDescriptionsByName and outputDescriptionsByName as before."
        ),
        category="introspection",
        doc_url="https://developer.apple.com/documentation/coreai/caimodeldescription",
    ),
    "MLFeatureDescription": APIMapping(
        deprecated_api="MLFeatureDescription",
        replacement_api="CAIFeatureDescription",
        pattern=_p(r"\bMLFeatureDescription\b"),
        template="CAIFeatureDescription",
        severity=Severity.LOW,
        migration_note=(
            "MLFeatureDescription is replaced by CAIFeatureDescription. "
            "Property names are preserved; type now returns CAIFeatureType."
        ),
        category="introspection",
        doc_url="https://developer.apple.com/documentation/coreai/caifeatureDescription",
    ),
    "MLModelMetadataKey": APIMapping(
        deprecated_api="MLModelMetadataKey",
        replacement_api="CAIModelMetadataKey",
        pattern=_p(r"\bMLModelMetadataKey\b"),
        template="CAIModelMetadataKey",
        severity=Severity.LOW,
        migration_note=(
            "MLModelMetadataKey constants are replaced by CAIModelMetadataKey. "
            "Key names are identical."
        ),
        category="introspection",
        doc_url="https://developer.apple.com/documentation/coreai/caimodelmetadatakey",
    ),
    # -----------------------------------------------------------------------
    # Vision / VNCoreMLRequest
    # -----------------------------------------------------------------------
    "VNCoreMLRequest": APIMapping(
        deprecated_api="VNCoreMLRequest",
        replacement_api="CAIVisionRequest",
        pattern=_p(r"\bVNCoreMLRequest\b"),
        template="CAIVisionRequest",
        severity=Severity.HIGH,
        migration_note=(
            "VNCoreMLRequest is replaced by CAIVisionRequest from the Core AI framework. "
            "Initialise with a CAIModel directly; the Vision wrapper layer is no longer needed."
        ),
        category="vision",
        doc_url="https://developer.apple.com/documentation/coreai/caivisionrequest",
    ),
    "VNCoreMLModel": APIMapping(
        deprecated_api="VNCoreMLModel",
        replacement_api="CAIVisionModel",
        pattern=_p(r"\bVNCoreMLModel\b"),
        template="CAIVisionModel",
        severity=Severity.MEDIUM,
        migration_note=(
            "VNCoreMLModel wrapper is replaced by CAIVisionModel. "
            "Use CAIVisionModel(model:) passing a CAIModel instance."
        ),
        category="vision",
        doc_url="https://developer.apple.com/documentation/coreai/caivisionmodel",
    ),
    "VNCoreMLFeatureValueObservation": APIMapping(
        deprecated_api="VNCoreMLFeatureValueObservation",
        replacement_api="CAIVisionFeatureObservation",
        pattern=_p(r"\bVNCoreMLFeatureValueObservation\b"),
        template="CAIVisionFeatureObservation",
        severity=Severity.MEDIUM,
        migration_note=(
            "VNCoreMLFeatureValueObservation is replaced by CAIVisionFeatureObservation. "
            "Access featureValue via the .feature property."
        ),
        category="vision",
        doc_url="https://developer.apple.com/documentation/coreai/caivisionfeatureobservation",
    ),
    # -----------------------------------------------------------------------
    # NLP / NaturalLanguage integration
    # -----------------------------------------------------------------------
    "NLModel": APIMapping(
        deprecated_api="NLModel",
        replacement_api="CAILanguageModel",
        pattern=_p(r"\bNLModel\b"),
        template="CAILanguageModel",
        severity=Severity.HIGH,
        migration_note=(
            "NLModel (NaturalLanguage/CoreML bridge) is replaced by CAILanguageModel. "
            "Use CAILanguageModel.load(contentsOf:) and .perform(_:) for inference."
        ),
        category="nlp",
        doc_url="https://developer.apple.com/documentation/coreai/cailanguagemodel",
    ),
    "NLModelConfiguration": APIMapping(
        deprecated_api="NLModelConfiguration",
        replacement_api="CAILanguageModelConfiguration",
        pattern=_p(r"\bNLModelConfiguration\b"),
        template="CAILanguageModelConfiguration",
        severity=Severity.MEDIUM,
        migration_note=(
            "NLModelConfiguration is replaced by CAILanguageModelConfiguration."
        ),
        category="nlp",
        doc_url="https://developer.apple.com/documentation/coreai/cailanguagemodelconfiguration",
    ),
    # -----------------------------------------------------------------------
    # Sound / CreateML
    # -----------------------------------------------------------------------
    "MLSoundClassifier": APIMapping(
        deprecated_api="MLSoundClassifier",
        replacement_api="CAIAudioClassifier",
        pattern=_p(r"\bMLSoundClassifier\b"),
        template="CAIAudioClassifier",
        severity=Severity.BREAKING,
        migration_note=(
            "MLSoundClassifier is fully deprecated with no direct replacement. "
            "Migrate to CAIAudioClassifier and update the training pipeline."
        ),
        category="audio",
        doc_url="https://developer.apple.com/documentation/coreai/caiaudioclassifier",
    ),
    "MLImageClassifier": APIMapping(
        deprecated_api="MLImageClassifier",
        replacement_api="CAIImageClassifier",
        pattern=_p(r"\bMLImageClassifier\b"),
        template="CAIImageClassifier",
        severity=Severity.BREAKING,
        migration_note=(
            "MLImageClassifier (CreateML) is replaced by CAIImageClassifier. "
            "Re-export model to .caimodel format and update training code."
        ),
        category="vision",
        doc_url="https://developer.apple.com/documentation/coreai/caiImageclassifier",
    ),
    # -----------------------------------------------------------------------
    # Objective-C specific patterns
    # -----------------------------------------------------------------------
    "[MLModel modelWithContentsOfURL:error:]": APIMapping(
        deprecated_api="[MLModel modelWithContentsOfURL:error:]",
        replacement_api="[CAIModel loadWithContentsOfURL:configuration:completionHandler:]",
        pattern=_p(r"\[MLModel\s+modelWithContentsOfURL\s*:"),
        template="[CAIModel loadWithContentsOfURL:",
        severity=Severity.MEDIUM,
        migration_note=(
            "ObjC +[MLModel modelWithContentsOfURL:error:] is replaced by the async "
            "+[CAIModel loadWithContentsOfURL:configuration:completionHandler:]. "
            "Remove synchronous error-pointer pattern and use completion handler."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel",
    ),
    "[model predictionFromFeatures:error:]": APIMapping(
        deprecated_api="[model predictionFromFeatures:error:]",
        replacement_api="[model performRequest:completionHandler:]",
        pattern=_p(r"\[\w+\s+predictionFromFeatures\s*:"),
        template="[model performRequest:",
        severity=Severity.HIGH,
        migration_note=(
            "ObjC -[MLModel predictionFromFeatures:error:] is replaced by "
            "-[CAIModel performRequest:completionHandler:]. "
            "Wrap features in CAIInferenceRequest."
        ),
        category="inference",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel",
    ),
    "[VNCoreMLRequest alloc]": APIMapping(
        deprecated_api="[VNCoreMLRequest alloc]",
        replacement_api="[CAIVisionRequest alloc]",
        pattern=_p(r"\[VNCoreMLRequest\s+alloc\]"),
        template="[CAIVisionRequest alloc]",
        severity=Severity.HIGH,
        migration_note=(
            "ObjC [VNCoreMLRequest alloc] must be replaced with [CAIVisionRequest alloc]. "
            "Also update the model wrapper from VNCoreMLModel to CAIVisionModel."
        ),
        category="vision",
        doc_url="https://developer.apple.com/documentation/coreai/caivisionrequest",
    ),
    # -----------------------------------------------------------------------
    # Updating / personalization
    # -----------------------------------------------------------------------
    "MLUpdateTask": APIMapping(
        deprecated_api="MLUpdateTask",
        replacement_api="CAIUpdateTask",
        pattern=_p(r"\bMLUpdateTask\b"),
        template="CAIUpdateTask",
        severity=Severity.HIGH,
        migration_note=(
            "MLUpdateTask is replaced by CAIUpdateTask. "
            "The callback signature changes from (MLUpdateContext) to (CAIUpdateResult)."
        ),
        category="personalization",
        doc_url="https://developer.apple.com/documentation/coreai/caiupdatetask",
    ),
    "MLUpdateContext": APIMapping(
        deprecated_api="MLUpdateContext",
        replacement_api="CAIUpdateResult",
        pattern=_p(r"\bMLUpdateContext\b"),
        template="CAIUpdateResult",
        severity=Severity.HIGH,
        migration_note=(
            "MLUpdateContext is replaced by CAIUpdateResult. "
            "Access updated model via result.model instead of context.model."
        ),
        category="personalization",
        doc_url="https://developer.apple.com/documentation/coreai/caiupdateresult",
    ),
    "MLUpdateProgressHandlers": APIMapping(
        deprecated_api="MLUpdateProgressHandlers",
        replacement_api="CAIUpdateProgressHandler",
        pattern=_p(r"\bMLUpdateProgressHandlers\b"),
        template="CAIUpdateProgressHandler",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLUpdateProgressHandlers struct is replaced by CAIUpdateProgressHandler closure. "
            "Pass a single closure instead of the multi-handler struct."
        ),
        category="personalization",
        doc_url="https://developer.apple.com/documentation/coreai/caiupdateprogresshandler",
    ),
    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------
    "MLMetricKey": APIMapping(
        deprecated_api="MLMetricKey",
        replacement_api="CAIMetricKey",
        pattern=_p(r"\bMLMetricKey\b"),
        template="CAIMetricKey",
        severity=Severity.LOW,
        migration_note=(
            "MLMetricKey constants are replaced by CAIMetricKey. Key names are preserved."
        ),
        category="personalization",
        doc_url="https://developer.apple.com/documentation/coreai/caimetrickey",
    ),
    # -----------------------------------------------------------------------
    # Image buffers
    # -----------------------------------------------------------------------
    "MLPixelBuffer": APIMapping(
        deprecated_api="MLPixelBuffer",
        replacement_api="CAIPixelBuffer",
        pattern=_p(r"\bMLPixelBuffer\b"),
        template="CAIPixelBuffer",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLPixelBuffer is replaced by CAIPixelBuffer. "
            "Underlying CVPixelBuffer handling is unchanged."
        ),
        category="vision",
        doc_url="https://developer.apple.com/documentation/coreai/caipixelbuffer",
    ),
    # -----------------------------------------------------------------------
    # Structured outputs
    # -----------------------------------------------------------------------
    "MLModelStructuredProgram": APIMapping(
        deprecated_api="MLModelStructuredProgram",
        replacement_api="CAICompiledModel",
        pattern=_p(r"\bMLModelStructuredProgram\b"),
        template="CAICompiledModel",
        severity=Severity.BREAKING,
        migration_note=(
            "MLModelStructuredProgram is removed. Use CAICompiledModel and recompile "
            "the model with the Core AI compiler toolchain."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caicompiledmodel",
    ),
    "MLProgram": APIMapping(
        deprecated_api="MLProgram",
        replacement_api="CAICompiledModel",
        pattern=_p(r"\bMLProgram\b"),
        template="CAICompiledModel",
        severity=Severity.BREAKING,
        migration_note=(
            "MLProgram is removed and superseded by CAICompiledModel. "
            "Re-export the model using Core AI tooling."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caicompiledmodel",
    ),
    # -----------------------------------------------------------------------
    # Compiled model URLs
    # -----------------------------------------------------------------------
    "MLModel.compileModel(at:)": APIMapping(
        deprecated_api="MLModel.compileModel(at:)",
        replacement_api="CAIModel.compile(at:)",
        pattern=_p(r"MLModel\.compileModel\s*\("),
        template="CAIModel.compile(",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLModel.compileModel(at:) is replaced by the async CAIModel.compile(at:). "
            "Compiled artefacts now use the .caimodelc extension."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel/compile(at:)",
    ),
    # -----------------------------------------------------------------------
    # Objective-C: MLFeatureProvider protocol reference
    # -----------------------------------------------------------------------
    "id<MLFeatureProvider>": APIMapping(
        deprecated_api="id<MLFeatureProvider>",
        replacement_api="id<CAIRequestFeatureProvider>",
        pattern=_p(r"id\s*<\s*MLFeatureProvider\s*>"),
        template="id<CAIRequestFeatureProvider>",
        severity=Severity.MEDIUM,
        migration_note=(
            "ObjC id<MLFeatureProvider> type annotations must become "
            "id<CAIRequestFeatureProvider>."
        ),
        category="feature-provider",
        doc_url="https://developer.apple.com/documentation/coreai/cairequestfeatureprovider",
    ),
    # -----------------------------------------------------------------------
    # Batch providers
    # -----------------------------------------------------------------------
    "MLBatchProvider": APIMapping(
        deprecated_api="MLBatchProvider",
        replacement_api="CAIBatchRequestProvider",
        pattern=_p(r"\bMLBatchProvider\b"),
        template="CAIBatchRequestProvider",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLBatchProvider protocol is replaced by CAIBatchRequestProvider. "
            "Implement count and featuresAt(index:) as before."
        ),
        category="inference",
        doc_url="https://developer.apple.com/documentation/coreai/caibatchrequestprovider",
    ),
    "MLArrayBatchProvider": APIMapping(
        deprecated_api="MLArrayBatchProvider",
        replacement_api="CAIArrayBatchProvider",
        pattern=_p(r"\bMLArrayBatchProvider\b"),
        template="CAIArrayBatchProvider",
        severity=Severity.LOW,
        migration_note=(
            "MLArrayBatchProvider is replaced by CAIArrayBatchProvider. "
            "The initialiser signature is unchanged."
        ),
        category="inference",
        doc_url="https://developer.apple.com/documentation/coreai/caiarraybatchprovider",
    ),
    # -----------------------------------------------------------------------
    # Specialization / optimization
    # -----------------------------------------------------------------------
    "MLOptimizationHints": APIMapping(
        deprecated_api="MLOptimizationHints",
        replacement_api="CAIOptimizationPolicy",
        pattern=_p(r"\bMLOptimizationHints\b"),
        template="CAIOptimizationPolicy",
        severity=Severity.MEDIUM,
        migration_note=(
            "MLOptimizationHints is replaced by CAIOptimizationPolicy struct. "
            "Migrate reshapeFrequency and specialization properties accordingly."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caioptimizationpolicy",
    ),
    "MLSpecialization": APIMapping(
        deprecated_api="MLSpecialization",
        replacement_api="CAISpecializationMode",
        pattern=_p(r"\bMLSpecialization\b"),
        template="CAISpecializationMode",
        severity=Severity.LOW,
        migration_note=(
            "MLSpecialization enum is replaced by CAISpecializationMode. "
            "Map .none → .disabled, .full → .full."
        ),
        category="model-io",
        doc_url="https://developer.apple.com/documentation/coreai/caispecializationmode",
    ),
    # -----------------------------------------------------------------------
    # Async prediction helpers
    # -----------------------------------------------------------------------
    "MLModel.prediction(from:options:)": APIMapping(
        deprecated_api="MLModel.prediction(from:options:)",
        replacement_api="CAIModel.perform(_:options:)",
        pattern=_p(r"\.prediction\s*\(\s*from\s*:.*?options\s*:"),
        template=".perform(",
        severity=Severity.HIGH,
        migration_note=(
            "MLModel.prediction(from:options:) is replaced by the async "
            "CAIModel.perform(_:options:). Wrap input in CAIInferenceRequest and "
            "migrate MLPredictionOptions to CAIInferenceOptions."
        ),
        category="inference",
        doc_url="https://developer.apple.com/documentation/coreai/caimodel/perform(_:options:)",
    ),
    "MLPredictionOptions": APIMapping(
        deprecated_api="MLPredictionOptions",
        replacement_api="CAIInferenceOptions",
        pattern=_p(r"\bMLPredictionOptions\b"),
        template="CAIInferenceOptions",
        severity=Severity.LOW,
        migration_note=(
            "MLPredictionOptions is replaced by CAIInferenceOptions. "
            "Migrate usesCPUOnly → computePolicy = .cpu."
        ),
        category="inference",
        doc_url="https://developer.apple.com/documentation/coreai/caiinferenceoptions",
    ),
    # -----------------------------------------------------------------------
    # Import statements
    # -----------------------------------------------------------------------
    "import CoreML": APIMapping(
        deprecated_api="import CoreML",
        replacement_api="import CoreAI",
        pattern=_p(r"^\s*import\s+CoreML\b"),
        template="import CoreAI",
        severity=Severity.LOW,
        migration_note=(
            "Replace 'import CoreML' with 'import CoreAI' at the top of each file."
        ),
        category="general",
        doc_url="https://developer.apple.com/documentation/coreai",
    ),
    "@import CoreML;": APIMapping(
        deprecated_api="@import CoreML;",
        replacement_api="@import CoreAI;",
        pattern=_p(r"^\s*@import\s+CoreML\s*;"),
        template="@import CoreAI;",
        severity=Severity.LOW,
        migration_note=(
            "Replace '@import CoreML;' with '@import CoreAI;' at the top of each file."
        ),
        category="general",
        doc_url="https://developer.apple.com/documentation/coreai",
    ),
    "#import <CoreML/CoreML.h>": APIMapping(
        deprecated_api="#import <CoreML/CoreML.h>",
        replacement_api="#import <CoreAI/CoreAI.h>",
        pattern=_p(r"#\s*import\s+<CoreML/CoreML\.h>"),
        template="#import <CoreAI/CoreAI.h>",
        severity=Severity.LOW,
        migration_note=(
            "Replace '#import <CoreML/CoreML.h>' with '#import <CoreAI/CoreAI.h>'."
        ),
        category="general",
        doc_url="https://developer.apple.com/documentation/coreai",
    ),
}


def get_all_patterns() -> list[tuple[re.Pattern, APIMapping]]:
    """Return every (compiled_pattern, APIMapping) pair from the mapping table.

    The result is sorted so that longer / more specific patterns appear
    first, reducing the chance that a generic pattern shadows a specific one.

    Returns:
        A list of ``(pattern, mapping)`` tuples ready for the analyzer engine.
    """
    pairs = [(mapping.pattern, mapping) for mapping in API_MAPPINGS.values()]
    # Sort by pattern string length descending so specific patterns match first
    pairs.sort(key=lambda x: len(x[0].pattern), reverse=True)
    return pairs


def get_mapping(api_name: str) -> Optional[APIMapping]:
    """Look up a mapping by its deprecated API name.

    Args:
        api_name: The deprecated symbol name as it appears in ``API_MAPPINGS``.

    Returns:
        The ``APIMapping`` if found, otherwise ``None``.
    """
    return API_MAPPINGS.get(api_name)


def get_mappings_by_category(category: str) -> list[APIMapping]:
    """Return all mappings that belong to the specified category.

    Args:
        category: Category label such as ``'inference'``, ``'vision'``, etc.

    Returns:
        A list of ``APIMapping`` objects matching the category.
    """
    return [m for m in API_MAPPINGS.values() if m.category == category]


def get_mappings_by_severity(severity: Severity) -> list[APIMapping]:
    """Return all mappings whose severity matches the specified level.

    Args:
        severity: A ``Severity`` enum value.

    Returns:
        A list of ``APIMapping`` objects at that severity level.
    """
    return [m for m in API_MAPPINGS.values() if m.severity == severity]


# Convenience set of all deprecated symbol names for quick membership tests.
ALL_DEPRECATED_APIS: frozenset[str] = frozenset(API_MAPPINGS.keys())

# Category labels present in the table (computed once at import time).
ALL_CATEGORIES: frozenset[str] = frozenset(m.category for m in API_MAPPINGS.values())
