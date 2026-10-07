# Drawing to Print

Photograph a 2D drawing on iPhone, generate a **3D model of the depicted object** (not a plaque or extrusion), and export a watertight **3MF** to open in **Bambu Studio** for a **Bambu Lab P2S Combo**.

v1 does **not** send jobs to the printer. Bambu Handy is not a slicer for this file.

```
ios/        SwiftUI app (iOS 17+)
backend/   FastAPI service (image-to-3D adapter + print prep)
```

## Run the backend

Python **3.9 or newer** (macOS Command Line Tools 3.9 is fine). You do not need to upgrade to 3.10+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set MESHY_API_KEY if you have one
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- With `MESHY_API_KEY` set, jobs call [Meshy Image to 3D](https://docs.meshy.ai/en/api/image-to-3d), copy the GLB immediately, then repair/scale/ground and write 3MF in millimetres.
- Without a key, a **stub provider** still runs the full pipeline (watertight demo mesh) so capture → preview → share can be tested.

```bash
cd backend
source .venv/bin/activate
pytest
```

OpenAPI UI: `http://127.0.0.1:8000/docs`

### Environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `MESHY_API_KEY` | No | Meshy bearer token. Empty → stub provider. **Server only.** |
| `MESHY_BASE_URL` | No | Default `https://api.meshy.ai` |
| `JOB_DIR` | No | Job file store (images, meshes, 3MF) |

Vendor keys must never ship in the IPA. The iOS app talks only to this API.

## Open the iOS app

1. Open `ios/DrawingToPrint.xcodeproj` in Xcode 15+ (iOS 17 SDK).
2. Select an iPhone simulator or device. Set your Development Team for signing.
3. Settings → Backend URL:
   - Simulator: `http://127.0.0.1:8000`
   - Device: `http://<your-mac-lan-ip>:8000` (local HTTP is allowed)
4. Run. Camera and Photos need the usage prompts.

Flow: photo or library → crop → generate (poll) → RealityKit orbit preview → size slider (default **80 mm** longest edge, 20–240 mm) → Share Sheet `.3mf` (STL fallback).

## API contract

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/v1/jobs` | multipart `image` (JPEG/PNG) + optional `target_size_mm`. Header `X-Device-Id` (anonymous). Returns `{id, status, provider, target_size_mm}`. |
| `GET` | `/v1/jobs/{id}` | `status`: `queued` \| `generating` \| `repairing` \| `ready` \| `failed`. Includes watertight flag, bbox mm, warnings, Studio note. |
| `GET` | `/v1/jobs/{id}/preview.mesh.json` | Vertices/faces in millimetres for RealityKit. `?size_mm=` |
| `GET` | `/v1/jobs/{id}/preview.glb` | Optional GLB preview. `?size_mm=` |
| `GET` | `/v1/jobs/{id}/export.3mf` | Core 3MF, `unit="millimeter"`. `?size_mm=` |
| `GET` | `/v1/jobs/{id}/export.stl` | Share fallback. `?size_mm=` |
| `GET` | `/health` | `{status, provider}` |

Statuses match the product plan. Export is geometry-only 3MF; Studio will warn that the file is not from Bambu Lab.

## Slice on a computer (P2S 0.4 mm)

1. AirDrop or save the `.3mf` and open it in **Bambu Studio** (Mac / Windows / Linux).
2. Accept the geometry-only warning if it appears.
3. Printer: **Bambu Lab P2S**, variant **0.4 nozzle**.
4. Process: **0.20 mm Standard @BBL P2S 0.4 nozzle**, filament **PLA**.
5. Enable auto tree supports. Add a brim if the footprint is tiny.
6. Slice, then **Send print** (LAN or Bambu cloud) or export a sliced plate for USB.

The P2S prints sliced `.gcode.3mf`, not this raw 3MF from USB. Handy cannot slice this file.
