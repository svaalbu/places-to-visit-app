import Foundation

enum JobStatusKind: String, Codable {
    case queued
    case generating
    case repairing
    case ready
    case failed

    var isInFlight: Bool {
        switch self {
        case .queued, .generating, .repairing:
            return true
        case .ready, .failed:
            return false
        }
    }

    var progressTitle: String {
        switch self {
        case .queued: return "Queued"
        case .generating: return "Building 3D from your drawing"
        case .repairing: return "Making it printable"
        case .ready: return "Ready"
        case .failed: return "Failed"
        }
    }

    var progressDetail: String {
        switch self {
        case .queued:
            return "Waiting for the generator…"
        case .generating:
            return "Cloud image-to-3D usually takes 30 seconds to a couple of minutes."
        case .repairing:
            return "Repairing the mesh, scaling to millimetres, and sitting it on the bed."
        case .ready:
            return "Orbit the model, set size, then share a 3MF."
        case .failed:
            return "Generation did not finish. Try a tighter crop and even light."
        }
    }
}

struct JobCreateResponse: Codable {
    let id: String
    let status: JobStatusKind
    let provider: String
    let targetSizeMM: Double

    enum CodingKeys: String, CodingKey {
        case id, status, provider
        case targetSizeMM = "target_size_mm"
    }
}

struct BBoxMM: Codable {
    let x: Double
    let y: Double
    let z: Double

    var longest: Double { max(x, y, z) }
}

struct JobWarning: Codable, Identifiable {
    var id: String { code + message }
    let code: String
    let message: String
}

struct JobStatus: Codable {
    let id: String
    let status: JobStatusKind
    let provider: String
    let targetSizeMM: Double
    let preparedSizeMM: Double?
    let error: String?
    let warnings: [JobWarning]
    let bboxMM: BBoxMM?
    let minExtentMM: Double?
    let isWatertight: Bool?
    let triangleCount: Int?
    let previewAvailable: Bool
    let export3MFAvailable: Bool
    let exportSTLAvailable: Bool
    let studioNote: String?

    enum CodingKeys: String, CodingKey {
        case id, status, provider, error, warnings
        case targetSizeMM = "target_size_mm"
        case preparedSizeMM = "prepared_size_mm"
        case bboxMM = "bbox_mm"
        case minExtentMM = "min_extent_mm"
        case isWatertight = "is_watertight"
        case triangleCount = "triangle_count"
        case previewAvailable = "preview_available"
        case export3MFAvailable = "export_3mf_available"
        case exportSTLAvailable = "export_stl_available"
        case studioNote = "studio_note"
    }
}

struct PreviewMesh: Codable {
    let units: String
    let vertices: [[Double]]
    let faces: [[Int]]
}

enum APIClientError: LocalizedError {
    case badImage
    case badURL
    case http(Int, String)
    case empty

    var errorDescription: String? {
        switch self {
        case .badImage:
            return "Could not encode the photo as JPEG."
        case .badURL:
            return "The API address is not a valid URL. Check Settings."
        case .http(let code, let body):
            return "Server error (\(code)): \(body)"
        case .empty:
            return "The server returned an empty file."
        }
    }
}
