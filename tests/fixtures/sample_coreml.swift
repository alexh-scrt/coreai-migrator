// sample_coreml.swift
// A synthetic Swift file containing various deprecated Core ML API calls.
// Used as a test fixture for coreai_migrator unit tests.

import CoreML
import Vision
import NaturalLanguage
import UIKit

// MARK: - Model Loading

class ModelLoader {

    /// Synchronous model load (deprecated)
    func loadModelSync(url: URL) throws -> MLModel {
        let model = try MLModel(contentsOf: url)
        return model
    }

    /// Synchronous model load with configuration (deprecated)
    func loadModelWithConfig(url: URL) throws -> MLModel {
        let config = MLModelConfiguration()
        config.computeUnits = MLComputeUnits.all
        let model = try MLModel(contentsOf: url, configuration: config)
        return model
    }

    /// Async model load via completion handler (deprecated style)
    func loadModelAsync(url: URL, completion: @escaping (MLModel?) -> Void) {
        MLModel.load(contentsOf: url, configuration: MLModelConfiguration()) { result in
            switch result {
            case .success(let model):
                completion(model)
            case .failure:
                completion(nil)
            }
        }
    }

    /// Compile a model from URL (deprecated)
    func compileModel(at url: URL) throws -> URL {
        let compiledURL = try MLModel.compileModel(at: url)
        return compiledURL
    }
}

// MARK: - Feature Providers

class MyFeatureProvider: MLFeatureProvider {

    var featureNames: Set<String> {
        return ["inputImage", "inputText"]
    }

    func featureValue(for featureName: String) -> MLFeatureValue? {
        if featureName == "inputText" {
            return MLFeatureValue(string: "hello world")
        }
        if featureName == "inputInt" {
            return MLFeatureValue(int64: 42)
        }
        return nil
    }
}

class BatchRunner {

    func runBatch(model: MLModel, batch: MLBatchProvider) throws -> MLBatchProvider {
        let options = MLPredictionOptions()
        options.usesCPUOnly = false
        let results = try model.predictions(fromBatch: batch)
        return results
    }

    func predict(model: MLModel, features: MLFeatureProvider) throws -> MLFeatureProvider {
        let result = try model.prediction(from: features)
        return result
    }

    func predictWithOptions(
        model: MLModel,
        features: MLFeatureProvider,
        options: MLPredictionOptions
    ) throws -> MLFeatureProvider {
        let result = try model.prediction(from: features, options: options)
        return result
    }
}

// MARK: - Multi-Array / Tensor

class TensorUtils {

    func makeFloatTensor() throws -> MLMultiArray {
        let shape: [NSNumber] = [1, 3, 224, 224]
        let array = try MLMultiArray(shape: shape, dataType: MLMultiArrayDataType.float32)
        return array
    }

    func makeDoubleTensor(shape: [NSNumber]) throws -> MLMultiArray {
        return try MLMultiArray(shape: shape, dataType: .double)
    }

    func makeSequence(strings: [String]) -> MLSequence {
        return MLSequence.init(strings: strings)
    }
}

// MARK: - Dictionary Feature Provider

func buildDictProvider() -> MLDictionaryFeatureProvider {
    let dict: [String: MLFeatureValue] = [
        "input": MLFeatureValue(int64: 1)
    ]
    return try! MLDictionaryFeatureProvider(dictionary: dict)
}

// MARK: - Model Description / Introspection

func inspectModel(_ model: MLModel) {
    let description: MLModelDescription = model.modelDescription
    let inputNames = description.inputDescriptionsByName.keys
    let outputNames = description.outputDescriptionsByName.keys

    for name in inputNames {
        if let featureDesc: MLFeatureDescription = description.inputDescriptionsByName[name] {
            let featureType: MLFeatureType = featureDesc.type
            print("Input: \(name) type: \(featureType)")
        }
    }

    let metadata = description.metadata
    if let author = metadata[MLModelMetadataKey.author] {
        print("Author: \(author)")
    }
}

// MARK: - Vision Integration

class VisionRunner {

    var request: VNCoreMLRequest?

    func setupVision(model: MLModel) throws {
        let vnModel = try VNCoreMLModel(for: model)
        self.request = VNCoreMLRequest(model: vnModel) { request, error in
            guard let results = request.results as? [VNCoreMLFeatureValueObservation] else {
                return
            }
            for observation in results {
                print(observation.featureValue)
            }
        }
    }

    func runVision(pixelBuffer: MLPixelBuffer) {
        guard let request = self.request else { return }
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer as! CVPixelBuffer)
        try? handler.perform([request])
    }
}

// MARK: - On-device Update / Personalization

class PersonalizationManager {

    func startUpdate(modelURL: URL, trainingData: MLBatchProvider) {
        let progressHandlers = MLUpdateProgressHandlers(
            forEvents: [.trainingBegin, .epochEnd],
            progressHandler: { context in
                print("Loss: \(context.metrics[MLMetricKey.lossValue]!)")
            },
            completionHandler: { context in
                self.handleCompletion(context: context)
            }
        )

        let updateTask = try! MLUpdateTask(
            forModelAt: modelURL,
            trainingData: trainingData,
            configuration: MLModelConfiguration(),
            progressHandlers: progressHandlers
        )
        updateTask.resume()
    }

    private func handleCompletion(context: MLUpdateContext) {
        let updatedModel = context.model
        print("Updated model: \(updatedModel)")
    }
}

// MARK: - NLP Integration

class NLPRunner {

    func loadLanguageModel(url: URL) throws -> NLModel {
        let config = NLModelConfiguration()
        let model = try NLModel(contentsOf: url)
        return model
    }
}

// MARK: - Optimization Hints

func buildOptimizedConfig() -> MLModelConfiguration {
    let config = MLModelConfiguration()
    config.computeUnits = MLComputeUnits.cpuAndNeuralEngine
    let hints = MLOptimizationHints()
    hints.reshapeFrequency = MLOptimizationHints.ReshapeFrequency.never
    config.optimizationHints = hints
    return config
}

// MARK: - Array Batch Provider

func buildArrayBatch(providers: [MLFeatureProvider]) -> MLArrayBatchProvider {
    return MLArrayBatchProvider(array: providers)
}

// MARK: - Compiled Model URL

func ensureCompiledModel(at url: URL) throws -> URL {
    let compiled = try MLModel.compileModel(at: url)
    return compiled
}

// MARK: - Prediction Options

func makePredictionOptions() -> MLPredictionOptions {
    let opts = MLPredictionOptions()
    opts.usesCPUOnly = true
    return opts
}
