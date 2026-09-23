import SwiftUI

struct GenerateView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        VStack(spacing: 24) {
            if let image = appState.croppedImage {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .frame(maxHeight: 240)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .padding(.horizontal)
            }

            ProgressView()
                .controlSize(.large)

            VStack(spacing: 8) {
                Text(appState.job?.status.progressTitle ?? "Starting…")
                    .font(.title3.weight(.semibold))
                Text(appState.job?.status.progressDetail ?? "Uploading the drawing to the generator.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }

            if appState.job?.provider == "stub" {
                Text(GuidanceCopy.mockProvider)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal)
            }

            if let error = appState.errorMessage {
                Text(error)
                    .font(.callout)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                Button("Try again") {
                    Task { await appState.generate() }
                }
                .buttonStyle(.borderedProminent)
                Button("Start over") { appState.reset() }
            }

            Spacer()
        }
        .padding(.top, 24)
    }
}
