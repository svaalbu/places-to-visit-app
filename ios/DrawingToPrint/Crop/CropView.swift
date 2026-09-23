import SwiftUI
import UIKit

struct CropView: View {
    let image: UIImage
    var onCrop: (UIImage) -> Void
    var onCancel: () -> Void

    @State private var normalizedCrop = CGRect(x: 0.08, y: 0.08, width: 0.84, height: 0.84)
    @State private var dragStart: CGRect?

    var body: some View {
        VStack(spacing: 16) {
            Text("Crop to the object. Leave a little paper around the ink.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .padding(.horizontal)

            GeometryReader { geo in
                let fitted = Self.fittedRect(imageSize: image.size, in: geo.size)
                ZStack {
                    Color.black.opacity(0.85)
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                    cropOverlay(in: fitted)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .padding(.horizontal, 8)

            HStack {
                Button("Cancel", action: onCancel)
                Spacer()
                Button("Use Crop") {
                    onCrop(Self.crop(image, normalized: normalizedCrop))
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()
        }
    }

    private func cropOverlay(in fitted: CGRect) -> some View {
        let rect = CGRect(
            x: fitted.minX + normalizedCrop.minX * fitted.width,
            y: fitted.minY + normalizedCrop.minY * fitted.height,
            width: normalizedCrop.width * fitted.width,
            height: normalizedCrop.height * fitted.height
        )

        return ZStack {
            Canvas { context, size in
                context.fill(
                    Path(CGRect(origin: .zero, size: size)),
                    with: .color(.black.opacity(0.45))
                )
                context.blendMode = .destinationOut
                context.fill(Path(roundedRect: rect, cornerRadius: 2), with: .color(.white))
            }
            .compositingGroup()
            RoundedRectangle(cornerRadius: 2)
                .stroke(Color.white, lineWidth: 2)
                .frame(width: rect.width, height: rect.height)
                .position(x: rect.midX, y: rect.midY)
                .gesture(
                    DragGesture()
                        .onChanged { value in
                            if dragStart == nil { dragStart = normalizedCrop }
                            guard let start = dragStart else { return }
                            let dx = value.translation.width / max(fitted.width, 1)
                            let dy = value.translation.height / max(fitted.height, 1)
                            var next = start
                            next.origin.x = min(max(start.minX + dx, 0), 1 - start.width)
                            next.origin.y = min(max(start.minY + dy, 0), 1 - start.height)
                            normalizedCrop = next
                        }
                        .onEnded { _ in dragStart = nil }
                )
        }
        .gesture(
            MagnificationGesture()
                .onChanged { scale in
                    let mid = CGPoint(x: normalizedCrop.midX, y: normalizedCrop.midY)
                    let newW = min(max(normalizedCrop.width * scale, 0.2), 1)
                    let newH = min(max(normalizedCrop.height * scale, 0.2), 1)
                    let x = min(max(mid.x - newW / 2, 0), 1 - newW)
                    let y = min(max(mid.y - newH / 2, 0), 1 - newH)
                    normalizedCrop = CGRect(x: x, y: y, width: newW, height: newH)
                }
        )
    }

    static func fittedRect(imageSize: CGSize, in bounds: CGSize) -> CGRect {
        guard imageSize.width > 0, imageSize.height > 0 else { return .zero }
        let scale = min(bounds.width / imageSize.width, bounds.height / imageSize.height)
        let size = CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
        return CGRect(
            x: (bounds.width - size.width) / 2,
            y: (bounds.height - size.height) / 2,
            width: size.width,
            height: size.height
        )
    }

    static func crop(_ image: UIImage, normalized: CGRect) -> UIImage {
        guard let cg = image.fixedOrientation().cgImage else { return image }
        let pixel = CGRect(
            x: normalized.minX * CGFloat(cg.width),
            y: normalized.minY * CGFloat(cg.height),
            width: normalized.width * CGFloat(cg.width),
            height: normalized.height * CGFloat(cg.height)
        ).integral
        guard let cropped = cg.cropping(to: pixel) else { return image }
        return UIImage(cgImage: cropped, scale: image.scale, orientation: .up)
    }
}

extension UIImage {
    func fixedOrientation() -> UIImage {
        if imageOrientation == .up { return self }
        let renderer = UIGraphicsImageRenderer(size: size)
        return renderer.image { _ in
            draw(in: CGRect(origin: .zero, size: size))
        }
    }
}
