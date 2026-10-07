import Foundation

struct APIClient {
    var session: URLSession = .shared

    func createJob(imageJPEG: Data, targetSizeMM: Double) async throws -> JobCreateResponse {
        var request = URLRequest(url: Self.url(path: "v1/jobs"))
        request.httpMethod = "POST"
        request.setValue(AppConfig.deviceID, forHTTPHeaderField: "X-Device-Id")
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = Self.multipartBody(
            boundary: boundary,
            filename: "drawing.jpg",
            mime: "image/jpeg",
            file: imageJPEG,
            fields: ["target_size_mm": String(format: "%.1f", targetSizeMM)]
        )
        return try await decode(JobCreateResponse.self, request: request)
    }

    func job(id: String) async throws -> JobStatus {
        var request = URLRequest(url: Self.url(path: "v1/jobs/\(id)"))
        request.setValue(AppConfig.deviceID, forHTTPHeaderField: "X-Device-Id")
        return try await decode(JobStatus.self, request: request)
    }

    func previewMesh(jobID: String, sizeMM: Double) async throws -> PreviewMesh {
        var request = URLRequest(url: endpoint("v1/jobs/\(jobID)/preview.mesh.json", sizeMM: sizeMM))
        request.setValue(AppConfig.deviceID, forHTTPHeaderField: "X-Device-Id")
        return try await decode(PreviewMesh.self, request: request)
    }

    func export3MF(jobID: String, sizeMM: Double) async throws -> Data {
        try await download(path: "v1/jobs/\(jobID)/export.3mf", sizeMM: sizeMM)
    }

    func exportSTL(jobID: String, sizeMM: Double) async throws -> Data {
        try await download(path: "v1/jobs/\(jobID)/export.stl", sizeMM: sizeMM)
    }

    private static func url(path: String) -> URL {
        let base = AppConfig.apiBaseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let trimmed = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        return URL(string: "\(base)/\(trimmed)")!
    }

    private func endpoint(_ path: String, sizeMM: Double) -> URL {
        var components = URLComponents(url: Self.url(path: path), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "size_mm", value: String(format: "%.1f", sizeMM))]
        return components.url!
    }

    private func download(path: String, sizeMM: Double) async throws -> Data {
        var request = URLRequest(url: endpoint(path, sizeMM: sizeMM))
        request.setValue(AppConfig.deviceID, forHTTPHeaderField: "X-Device-Id")
        let (data, response) = try await session.data(for: request)
        try Self.throwIfNeeded(response, data: data)
        if data.isEmpty { throw APIClientError.empty }
        return data
    }

    private func decode<T: Decodable>(_ type: T.Type, request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        try Self.throwIfNeeded(response, data: data)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private static func throwIfNeeded(_ response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIClientError.http(http.statusCode, String(body.prefix(280)))
        }
    }

    private static func multipartBody(
        boundary: String,
        filename: String,
        mime: String,
        file: Data,
        fields: [String: String]
    ) -> Data {
        var body = Data()
        for (name, value) in fields {
            body.append("--\(boundary)\r\n")
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            body.append("\(value)\r\n")
        }
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"image\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: \(mime)\r\n\r\n")
        body.append(file)
        body.append("\r\n")
        body.append("--\(boundary)--\r\n")
        return body
    }
}

private extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}
