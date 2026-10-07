import CoreImage
import CoreImage.CIFilterBuiltins
import UIKit
import Vision

enum ImagePrep {
    static func enhance(_ image: UIImage) -> UIImage {
        let upright = image.fixedOrientation()
        let flattened = flattenDocument(upright) ?? upright
        let contrasted = boostContrast(flattened)
        return liftSubject(contrasted) ?? contrasted
    }

    private static func flattenDocument(_ image: UIImage) -> UIImage? {
        guard let cg = image.cgImage else { return nil }
        let request = VNDetectRectanglesRequest()
        request.maximumObservations = 1
        request.minimumConfidence = 0.7
        request.minimumAspectRatio = 0.3
        let handler = VNImageRequestHandler(cgImage: cg, orientation: .up)
        try? handler.perform([request])
        guard let observation = request.results?.first else { return nil }

        let ci = CIImage(cgImage: cg)
        let size = ci.extent.size
        let filter = CIFilter.perspectiveCorrection()
        filter.inputImage = ci
        filter.topLeft = observation.topLeft.scaled(to: size)
        filter.topRight = observation.topRight.scaled(to: size)
        filter.bottomLeft = observation.bottomLeft.scaled(to: size)
        filter.bottomRight = observation.bottomRight.scaled(to: size)
        return render(filter.outputImage)
    }

    private static func boostContrast(_ image: UIImage) -> UIImage {
        guard let cg = image.cgImage else { return image }
        let ci = CIImage(cgImage: cg)
        let filter = CIFilter.colorControls()
        filter.inputImage = ci
        filter.contrast = 1.25
        filter.saturation = 0.85
        filter.brightness = 0.02
        return render(filter.outputImage) ?? image
    }

    private static func liftSubject(_ image: UIImage) -> UIImage? {
        guard let cg = image.cgImage else { return nil }
        let request = VNGenerateForegroundInstanceMaskRequest()
        let handler = VNImageRequestHandler(cgImage: cg, orientation: .up)
        try? handler.perform([request])
        guard let result = request.results?.first,
              let maskBuffer = try? result.generateScaledMaskForImage(forInstances: result.allInstances, from: handler)
        else {
            return nil
        }

        let color = CIImage(cgImage: cg)
        let mask = CIImage(cvPixelBuffer: maskBuffer)
        let background = CIImage(color: CIColor(red: 0.96, green: 0.96, blue: 0.96))
            .cropped(to: color.extent)
        let scaledMask = mask.transformed(
            by: CGAffineTransform(
                scaleX: color.extent.width / mask.extent.width,
                y: color.extent.height / mask.extent.height
            )
        )
        let blend = color.applyingFilter(
            "CIBlendWithMask",
            parameters: [
                kCIInputBackgroundImageKey: background,
                kCIInputMaskImageKey: scaledMask,
            ]
        )
        return render(blend)
    }

    private static func render(_ image: CIImage?) -> UIImage? {
        guard let image else { return nil }
        let context = CIContext(options: nil)
        guard let cg = context.createCGImage(image, from: image.extent) else { return nil }
        return UIImage(cgImage: cg)
    }
}

private extension CGPoint {
    func scaled(to size: CGSize) -> CGPoint {
        CGPoint(x: x * size.width, y: y * size.height)
    }
}
