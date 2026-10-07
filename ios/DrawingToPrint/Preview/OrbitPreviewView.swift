import RealityKit
import SwiftUI
import UIKit

struct OrbitPreviewView: UIViewRepresentable {
    let mesh: PreviewMesh
    let displayScale: Float

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> ARView {
        let view = ARView(frame: .zero, cameraMode: .nonAR, automaticallyConfigureSession: false)
        view.environment.background = .color(UIColor.secondarySystemBackground)
        view.renderOptions.insert(.disableMotionBlur)
        context.coordinator.installGestures(on: view)
        context.coordinator.load(mesh, into: view, scale: displayScale)
        return view
    }

    func updateUIView(_ uiView: ARView, context: Context) {
        if context.coordinator.needsReload(mesh) {
            context.coordinator.load(mesh, into: uiView, scale: displayScale)
        } else {
            context.coordinator.applyScale(displayScale)
        }
    }

    final class Coordinator {
        private var loadedVertexCount = -1
        private var model: ModelEntity?
        private var turntable: Entity?
        private var yaw: Float = 0.45
        private var pitch: Float = 0.25

        func needsReload(_ mesh: PreviewMesh) -> Bool {
            mesh.vertices.count != loadedVertexCount
        }

        func load(_ mesh: PreviewMesh, into view: ARView, scale: Float) {
            view.scene.anchors.removeAll()
            installCamera(in: view)

            let root = AnchorEntity(world: .zero)
            let turntable = Entity()
            turntable.name = "turntable"
            root.addChild(turntable)

            do {
                let resource = try Self.makeMesh(mesh)
                let material = SimpleMaterial(
                    color: UIColor(white: 0.82, alpha: 1),
                    roughness: 0.55,
                    isMetallic: false
                )
                let model = ModelEntity(mesh: resource, materials: [material])
                turntable.addChild(model)
                self.model = model
            } catch {
                loadedVertexCount = -1
                return
            }

            Self.installLights(in: view)
            view.scene.addAnchor(root)
            self.turntable = turntable
            loadedVertexCount = mesh.vertices.count
            applyScale(scale)
            applyRotation()
        }

        private static func installLights(in view: ARView) {
            let sun = DirectionalLight()
            sun.light.intensity = 1800
            sun.look(at: .zero, from: [0.2, 0.4, 0.3], relativeTo: nil)
            let fill = DirectionalLight()
            fill.light.intensity = 500
            fill.look(at: .zero, from: [-0.3, 0.1, -0.2], relativeTo: nil)
            let anchor = AnchorEntity(world: .zero)
            anchor.addChild(sun)
            anchor.addChild(fill)
            view.scene.addAnchor(anchor)
        }

        func applyScale(_ scale: Float) {
            model?.scale = SIMD3(repeating: max(scale, 0.05))
        }

        func installGestures(on view: ARView) {
            let pan = UIPanGestureRecognizer(target: self, action: #selector(handlePan(_:)))
            view.addGestureRecognizer(pan)
        }

        @objc private func handlePan(_ gesture: UIPanGestureRecognizer) {
            let translation = gesture.translation(in: gesture.view)
            yaw += Float(translation.x) * 0.008
            pitch = max(-0.9, min(0.9, pitch + Float(translation.y) * 0.006))
            gesture.setTranslation(.zero, in: gesture.view)
            applyRotation()
        }

        private func applyRotation() {
            let yawQ = simd_quatf(angle: yaw, axis: [0, 1, 0])
            let pitchQ = simd_quatf(angle: pitch, axis: [1, 0, 0])
            turntable?.orientation = yawQ * pitchQ
        }

        private func installCamera(in view: ARView) {
            let camera = PerspectiveCamera()
            camera.camera.fieldOfViewInDegrees = 40
            let anchor = AnchorEntity(world: .zero)
            let distance: Float = 0.22
            camera.look(at: [0, 0.02, 0], from: [0, 0.05, distance], relativeTo: nil)
            anchor.addChild(camera)
            view.scene.addAnchor(anchor)
        }

        static func makeMesh(_ preview: PreviewMesh) throws -> MeshResource {
            var positions: [SIMD3<Float>] = []
            positions.reserveCapacity(preview.vertices.count)
            for vertex in preview.vertices {
                guard vertex.count >= 3 else { continue }
                // Millimetres, Z-up print space → metres, Y-up RealityKit.
                let x = Float(vertex[0] / 1000.0)
                let y = Float(vertex[2] / 1000.0)
                let z = Float(-vertex[1] / 1000.0)
                positions.append(SIMD3(x, y, z))
            }

            var indices: [UInt32] = []
            indices.reserveCapacity(preview.faces.count * 3)
            for face in preview.faces {
                guard face.count >= 3 else { continue }
                indices.append(UInt32(face[0]))
                indices.append(UInt32(face[1]))
                indices.append(UInt32(face[2]))
            }

            var descriptor = MeshDescriptor(name: "drawing")
            descriptor.positions = MeshBuffers.Positions(positions)
            descriptor.primitives = .triangles(indices)
            return try MeshResource.generate(from: [descriptor])
        }
    }
}
