import SwiftUI

struct RootView: View {
    @EnvironmentObject private var appState: AppState
    @State private var showingHelp = false
    @State private var showingSettings = false

    var body: some View {
        NavigationStack {
            Group {
                switch appState.step {
                case .capture:
                    CaptureView()
                case .crop:
                    if let image = appState.capturedImage {
                        CropView(
                            image: image,
                            onCrop: { appState.acceptCrop($0) },
                            onCancel: { appState.reset() }
                        )
                    } else {
                        CaptureView()
                    }
                case .generate:
                    GenerateView()
                case .preview:
                    PreviewView()
                }
            }
            .navigationTitle("Drawing to Print")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Help") { showingHelp = true }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Settings") { showingSettings = true }
                }
            }
            .sheet(isPresented: $showingHelp) { HelpView() }
            .sheet(isPresented: $showingSettings) { SettingsView() }
            .alert("Something went wrong", isPresented: errorBinding) {
                Button("OK", role: .cancel) { appState.errorMessage = nil }
            } message: {
                Text(appState.errorMessage ?? "")
            }
        }
    }

    private var errorBinding: Binding<Bool> {
        Binding(
            get: { appState.errorMessage != nil && appState.step != .generate },
            set: { if !$0 { appState.errorMessage = nil } }
        )
    }
}
