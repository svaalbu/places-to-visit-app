import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var urlString = AppConfig.apiBaseURL.absoluteString

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("http://127.0.0.1:8000", text: $urlString)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("Simulator can use localhost. On a device, use your Mac’s LAN IP running the backend, or an HTTPS tunnel.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                } header: {
                    Text("Backend")
                }

                Section {
                    Text("Vendor image-to-3D keys stay on the server. They are never stored in this app.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    Text("Device id \(AppConfig.deviceID)")
                        .font(.footnote.monospaced())
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                } header: {
                    Text("Privacy")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        if let url = URL(string: urlString.trimmingCharacters(in: .whitespacesAndNewlines)),
                           url.scheme != nil {
                            AppConfig.apiBaseURL = url
                        }
                        dismiss()
                    }
                }
            }
        }
    }
}
