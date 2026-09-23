import PhotosUI
import SwiftUI

struct CaptureView: View {
    @EnvironmentObject private var appState: AppState
    @State private var pickerItem: PhotosPickerItem?
    @State private var showingCamera = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Photograph a drawing. We’ll turn that object into a 3D model you can print on a Bambu Lab P2S Combo.")
                    .font(.body)
                    .foregroundStyle(.primary)

                Text(GuidanceCopy.notAPlaque)
                    .font(.callout)
                    .foregroundStyle(.secondary)

                Label(GuidanceCopy.capture, systemImage: "light.max")
                    .font(.callout)
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))

                VStack(spacing: 12) {
                    Button {
                        showingCamera = true
                    } label: {
                        Label("Take Photo", systemImage: "camera")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)

                    PhotosPicker(selection: $pickerItem, matching: .images) {
                        Label("Choose from Photos", systemImage: "photo.on.rectangle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)
                }

                Text(GuidanceCopy.studioRequired)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .sheet(isPresented: $showingCamera) {
            CameraPicker { image in
                showingCamera = false
                if let image {
                    appState.acceptCapture(image)
                }
            }
            .ignoresSafeArea()
        }
        .onChange(of: pickerItem) { _, item in
            guard let item else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self),
                   let image = UIImage(data: data) {
                    appState.acceptCapture(image)
                }
            }
        }
    }
}
