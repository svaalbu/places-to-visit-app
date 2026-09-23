import Combine
import SwiftUI
import UIKit

enum FlowStep {
    case capture
    case crop
    case generate
    case preview
}

@MainActor
final class AppState: ObservableObject {
    @Published var step: FlowStep = .capture
    @Published var capturedImage: UIImage?
    @Published var croppedImage: UIImage?
    @Published var job: JobStatus?
    @Published var previewMesh: PreviewMesh?
    @Published var sizeMM: Double = AppConfig.defaultSizeMM
    @Published var isBusy = false
    @Published var errorMessage: String?
    @Published var shareURL: URL?
    @Published var isSharing = false

    let api: APIClient

    init(api: APIClient = APIClient()) {
        self.api = api
    }

    func reset() {
        step = .capture
        capturedImage = nil
        croppedImage = nil
        job = nil
        previewMesh = nil
        sizeMM = AppConfig.defaultSizeMM
        isBusy = false
        errorMessage = nil
        shareURL = nil
        isSharing = false
    }

    func acceptCapture(_ image: UIImage) {
        capturedImage = image
        errorMessage = nil
        step = .crop
    }

    func acceptCrop(_ image: UIImage) {
        croppedImage = ImagePrep.enhance(image)
        errorMessage = nil
        step = .generate
        Task { await generate() }
    }

    func generate() async {
        guard let image = croppedImage else { return }
        isBusy = true
        errorMessage = nil
        job = nil
        previewMesh = nil
        do {
            guard let jpeg = image.jpegData(compressionQuality: 0.92) else {
                throw APIClientError.badImage
            }
            let created = try await api.createJob(imageJPEG: jpeg, targetSizeMM: sizeMM)
            var current = try await api.job(id: created.id)
            job = current
            while current.status.isInFlight {
                try await Task.sleep(for: .seconds(1.2))
                current = try await api.job(id: created.id)
                job = current
            }
            if current.status == .failed {
                errorMessage = current.error ?? "Generation failed."
                isBusy = false
                return
            }
            previewMesh = try await api.previewMesh(jobID: created.id, sizeMM: sizeMM)
            job = try await api.job(id: created.id)
            step = .preview
        } catch is CancellationError {
            return
        } catch {
            errorMessage = error.localizedDescription
        }
        isBusy = false
    }

    func share(format: ShareFormat) async {
        guard let job else { return }
        isBusy = true
        errorMessage = nil
        do {
            let data: Data
            let filename: String
            switch format {
            case .threeMF:
                data = try await api.export3MF(jobID: job.id, sizeMM: sizeMM)
                filename = "Drawing.3mf"
            case .stl:
                data = try await api.exportSTL(jobID: job.id, sizeMM: sizeMM)
                filename = "Drawing.stl"
            }
            let url = FileManager.default.temporaryDirectory.appendingPathComponent(filename)
            try data.write(to: url, options: .atomic)
            shareURL = url
            isSharing = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isBusy = false
    }
}

enum ShareFormat {
    case threeMF
    case stl
}
