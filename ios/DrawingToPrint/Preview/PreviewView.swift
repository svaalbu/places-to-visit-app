import SwiftUI

struct PreviewView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            if let mesh = appState.previewMesh {
                OrbitPreviewView(mesh: mesh, displayScale: displayScale)
                    .frame(maxWidth: .infinity)
                    .frame(height: 360)
                    .background(Color(.secondarySystemBackground))
            } else {
                ContentUnavailableView("No preview", systemImage: "cube")
                    .frame(height: 360)
            }

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text("Longest edge")
                            Spacer()
                            Text("\(Int(appState.sizeMM.rounded())) mm")
                                .monospacedDigit()
                                .foregroundStyle(.secondary)
                        }
                        Slider(
                            value: $appState.sizeMM,
                            in: AppConfig.minSizeMM...AppConfig.maxSizeMM,
                            step: 1
                        )
                        Text("Default 80 mm. The P2S bed is 256 mm; we cap at 240 mm.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    if let warnings = appState.job?.warnings, !warnings.isEmpty {
                        ForEach(warnings) { warning in
                            Label(warning.message, systemImage: "exclamationmark.triangle")
                                .font(.footnote)
                                .foregroundStyle(.orange)
                        }
                    }

                    if let job = appState.job, job.provider == "stub" {
                        Text(GuidanceCopy.mockProvider)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    Text(appState.job?.studioNote ?? GuidanceCopy.studioRequired)
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    VStack(spacing: 10) {
                        Button {
                            Task { await appState.share(format: .threeMF) }
                        } label: {
                            Label("Share 3MF", systemImage: "square.and.arrow.up")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .disabled(appState.isBusy)

                        Button {
                            Task { await appState.share(format: .stl) }
                        } label: {
                            Label("Share STL instead", systemImage: "square.and.arrow.up")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                        .disabled(appState.isBusy)

                        Button("New drawing") { appState.reset() }
                    }
                }
                .padding()
            }
        }
        .overlay {
            if appState.isBusy {
                ProgressView()
                    .padding()
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
            }
        }
        .sheet(isPresented: $appState.isSharing) {
            if let url = appState.shareURL {
                ShareSheet(items: [url])
            }
        }
    }

    private var displayScale: Float {
        let prepared = appState.job?.preparedSizeMM ?? appState.job?.targetSizeMM ?? AppConfig.defaultSizeMM
        guard prepared > 0 else { return 1 }
        return Float(appState.sizeMM / prepared)
    }
}
