import Foundation

enum AppConfig {
    static let defaultSizeMM: Double = 80
    static let minSizeMM: Double = 20
    static let maxSizeMM: Double = 240
    static let apiBaseURLKey = "apiBaseURL"
    static let deviceIDKey = "deviceID"

    static var apiBaseURL: URL {
        get {
            if let stored = UserDefaults.standard.string(forKey: apiBaseURLKey),
               let url = URL(string: stored), !stored.isEmpty {
                return url
            }
            return URL(string: "http://127.0.0.1:8000")!
        }
        set {
            UserDefaults.standard.set(newValue.absoluteString, forKey: apiBaseURLKey)
        }
    }

    static var deviceID: String {
        if let existing = UserDefaults.standard.string(forKey: deviceIDKey), !existing.isEmpty {
            return existing
        }
        let created = UUID().uuidString
        UserDefaults.standard.set(created, forKey: deviceIDKey)
        return created
    }
}

enum GuidanceCopy {
    static let capture = "Fill the frame with one object. Dark ink on light paper. Even light."
    static let notAPlaque = "This app builds a 3D model of the object you drew — not a raised copy of the paper."
    static let studioRequired = "Bambu Studio on a Mac or PC is required to slice and send to the P2S. Bambu Handy cannot slice this file."
    static let studioSteps = """
    1. AirDrop or save the .3mf, then open it on a computer.
    2. Open the file in Bambu Studio. A “geometry only” warning is expected.
    3. Printer: Bambu Lab P2S, variant 0.4 nozzle.
    4. Process: 0.20 mm Standard @BBL P2S 0.4 nozzle, PLA.
    5. Enable auto tree supports. Add a brim if the footprint is tiny.
    6. Slice, then Send print (LAN or Bambu cloud) or export a sliced plate for USB.

    The P2S prints sliced .gcode.3mf, not this raw 3MF from USB.
    """
    static let mockProvider = "The backend is using the demo provider (no MESHY_API_KEY). You still get a watertight 3MF so the print path can be tested."
}
