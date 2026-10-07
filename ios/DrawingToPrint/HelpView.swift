import SwiftUI

struct HelpView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("What this app does")
                        .font(.headline)
                    Text(GuidanceCopy.notAPlaque)

                    Text("Capture tips")
                        .font(.headline)
                    Text(GuidanceCopy.capture)

                    Text("Print on a Bambu Lab P2S Combo")
                        .font(.headline)
                    Text(GuidanceCopy.studioRequired)
                    Text(GuidanceCopy.studioSteps)
                        .font(.callout)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
            }
            .navigationTitle("How to print")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
