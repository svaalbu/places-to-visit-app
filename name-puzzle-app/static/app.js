import * as THREE from "three";
import { OrbitControls } from "/vendor/OrbitControls.js";

const form = document.querySelector("#form");
const nameInput = document.querySelector("#name");
const makeButton = document.querySelector("#make");
const statusNode = document.querySelector("#status");
const stage = document.querySelector("#stage");
const empty = document.querySelector("#empty");
const hint = document.querySelector("#hint");
const details = document.querySelector("#details");
const puzzleName = document.querySelector("#puzzle-name");
const sizeNode = document.querySelector("#size");
const scaleNote = document.querySelector("#scale-note");
const chips = document.querySelector("#chips");
const warnings = document.querySelector("#warnings");
const download = document.querySelector("#download");
const canvas = document.querySelector("#canvas");

const view = createView(canvas);
let pollToken = 0;

nameInput.focus();

form.addEventListener("submit", (event) => {
  event.preventDefault();
  startPuzzle(nameInput.value);
});

canvas.addEventListener("pointerdown", () => {
  hint.hidden = true;
}, { once: true });

async function startPuzzle(rawName) {
  const token = ++pollToken;
  setBusy(true);
  hidePuzzle();
  setStatus("Starting…");
  let response;
  try {
    response = await fetch("/api/puzzles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: rawName }),
    });
  } catch {
    fail(token, "The app could not be reached.");
    return;
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    fail(token, payload.detail || "That name did not work.");
    return;
  }
  setStatus(`Building ${payload.name}. ${payload.message}`);
  poll(payload.id, token);
}

async function poll(id, token) {
  if (token !== pollToken) return;
  let response;
  try {
    response = await fetch(`/api/puzzles/${id}`);
  } catch {
    window.setTimeout(() => poll(id, token), 1500);
    return;
  }
  const job = await response.json().catch(() => null);
  if (!response.ok || !job) {
    fail(token, "That puzzle could not be found.");
    return;
  }
  if (job.status === "running") {
    setStatus(`Building ${job.name}. ${job.message}`);
    window.setTimeout(() => poll(id, token), 1500);
    return;
  }
  if (job.status === "error") {
    fail(token, job.error || "That puzzle could not be built.");
    return;
  }
  setStatus(`Building ${job.name}. Loading the preview…`);
  if (job.summary) showSummary(job.summary, id);
  try {
    const modelResponse = await fetch(`/api/puzzles/${id}/model`);
    if (!modelResponse.ok) throw new Error("preview missing");
    const model = await modelResponse.json();
    if (token !== pollToken) return;
    showSummary(model, id);
    view.show(model);
    empty.hidden = true;
    hint.hidden = false;
    setStatus("Ready. Drag the board to look around, then download the 3MF.");
    setBusy(false);
  } catch {
    if (token !== pollToken) return;
    setStatus("The preview did not load. The 3MF is still ready to download.");
    setBusy(false);
  }
}

function showSummary(summary, id) {
  stage.classList.remove("solo");
  details.hidden = false;
  puzzleName.textContent = summary.name;
  sizeNode.textContent = `${formatMm(summary.width)} × ${formatMm(summary.depth)} × ${formatMm(summary.height)} mm`;
  scaleNote.textContent = summary.scaled
    ? `Scaled to ${Math.round(summary.scale * 100)}% so the board fits the printer. The letters stay ${formatMm(summary.letter_thickness)} mm thick, and each slot is 0.40 mm larger than its letter.`
    : `Same letter size as the printed FINN puzzle. The letters are ${formatMm(summary.letter_thickness)} mm thick, and each slot is 0.40 mm larger than its letter.`;
  chips.replaceChildren();
  for (const letter of summary.letters) {
    const item = document.createElement("li");
    item.textContent = letter.char;
    item.style.background = safeColor(letter.color);
    chips.append(item);
  }
  if (summary.warnings && summary.warnings.length) {
    warnings.hidden = false;
    warnings.textContent = summary.warnings.join(" ");
  } else {
    warnings.hidden = true;
    warnings.textContent = "";
  }
  download.href = `/api/puzzles/${id}/puzzle.3mf`;
  download.setAttribute("download", `${summary.name}_name_puzzle.3mf`);
}

function hidePuzzle() {
  details.hidden = true;
  stage.classList.add("solo");
  empty.hidden = false;
  hint.hidden = true;
  view.clear();
}

function fail(token, message) {
  if (token !== pollToken) return;
  setStatus(message);
  setBusy(false);
}

function setBusy(busy) {
  makeButton.disabled = busy;
  nameInput.disabled = busy;
  makeButton.textContent = busy ? "Making…" : "Make puzzle";
}

function setStatus(message) {
  statusNode.textContent = message;
}

function formatMm(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function safeColor(value) {
  return /^#[0-9A-Fa-f]{6}$/.test(value) ? value : "#888888";
}

function createView(canvasElement) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvasElement, antialias: true });
  } catch {
    empty.textContent = "This browser cannot show the 3D view. You can still download the file.";
    return { show() {}, clear() {} };
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.setClearColor(0xf4eadc, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 5000);
  camera.position.set(80, 90, 160);

  const controls = new OrbitControls(camera, canvasElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 6, 0);

  scene.add(new THREE.HemisphereLight(0xfff7ec, 0xd9c3a0, 0.95));
  const key = new THREE.DirectionalLight(0xffffff, 1.35);
  key.position.set(60, 120, 80);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xffe2c4, 0.45);
  fill.position.set(-70, 40, -30);
  scene.add(fill);

  const group = new THREE.Group();
  scene.add(group);
  const frameCenter = new THREE.Vector3();
  const frameSize = new THREE.Vector3();
  let framed = false;

  function placeCamera() {
    if (!framed) return;
    const vFov = THREE.MathUtils.degToRad(camera.fov);
    const aspect = Math.max(camera.aspect, 0.35);
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * aspect);
    const distW = (frameSize.x * 1.2) / (2 * Math.tan(hFov / 2));
    const distH = (frameSize.z * 1.05) / (2 * Math.tan(vFov / 2));
    const dist = Math.max(distW, distH, 40);
    const direction = new THREE.Vector3(0.35, 0.85, 1.35).normalize();
    controls.target.copy(frameCenter);
    camera.position.copy(frameCenter).addScaledVector(direction, dist);
    camera.near = Math.max(0.1, dist / 100);
    camera.far = dist * 20;
    camera.updateProjectionMatrix();
    controls.update();
  }

  function resize() {
    const width = canvasElement.clientWidth || 1;
    const height = canvasElement.clientHeight || 1;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    placeCamera();
  }

  const observer = new ResizeObserver(resize);
  observer.observe(canvasElement.parentElement);
  resize();

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  function clear() {
    framed = false;
    for (const child of [...group.children]) {
      child.geometry.dispose();
      child.material.dispose();
      group.remove(child);
    }
  }

  function addMesh(data, color) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(data.positions, 3));
    geometry.setIndex(data.indices);
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({
      color: safeColor(color),
      roughness: color === "#E8C794" ? 0.62 : 0.42,
      metalness: 0.02,
      flatShading: true,
      side: THREE.DoubleSide,
    });
    group.add(new THREE.Mesh(geometry, material));
  }

  function show(model) {
    clear();
    addMesh(model.board, model.board_color || "#E8C794");
    for (const letter of model.letters) {
      addMesh(letter, letter.color);
    }
    const box = new THREE.Box3().setFromObject(group);
    box.getCenter(frameCenter);
    box.getSize(frameSize);
    framed = true;
    placeCamera();
  }

  return { show, clear };
}
