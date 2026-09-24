// Parts & Tools: browse every part and tool in the library — what it is, how
// to use it, its pins, the levels that use it, a 3D model you can turn round,
// and a video wherever one is available.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { thumbnailById, modelById } from "./three/models.js";
import { buildDetailed } from "./three/detail/index.js";
import { fitCamera } from "./three/detail/kit.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const L = { items: null, kind: "part", category: "All", query: "", viewer: null };

// the detailed model for an id (the bench's own Uno / breadboard where there's no detailed one)
async function detailModel(it) {
  return buildDetailed(it.id) || (await modelById(it.id, it.wokwi_type, it.attrs).catch(() => null));
}
// studio lighting: a room reflection map (so metal and gloss look real) plus a key light
function studio(renderer) {
  const scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x6b5b4a, 0.6));
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(30, 60, 40); scene.add(key);
  return scene;
}
// free a model's own geometry and printed textures (shared materials stay cached)
function dispose(obj) {
  obj.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); if (o.material.map) { o.material.map.dispose(); o.material.dispose(); } } });
}
// grid thumbnails: one shared renderer, rendered one at a time, cached per id
const thumbs = new Map();
let thumbR = null, thumbScene = null, queue = Promise.resolve();
function detailThumb(it, size = 200) {
  if (thumbs.has(it.id)) return thumbs.get(it.id);
  const p = (queue = queue.then(async () => {
    if (!thumbR) {
      thumbR = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
      thumbR.setPixelRatio(2); thumbR.setSize(size, size * 0.75);
      thumbR.outputColorSpace = THREE.SRGBColorSpace; thumbR.toneMapping = THREE.ACESFilmicToneMapping;
      thumbScene = studio(thumbR);
    }
    const obj = await detailModel(it);
    if (!obj) return null;
    thumbScene.add(obj);
    const cam = new THREE.PerspectiveCamera(30, 4 / 3, 1, 1000); fitCamera(cam, obj, undefined, 1.02);
    thumbR.render(thumbScene, cam);
    thumbScene.remove(obj); dispose(obj);
    return thumbR.domElement.toDataURL("image/png");
  }).catch(() => null));
  thumbs.set(it.id, p);
  return p;
}

async function load() {
  if (L.items) return;
  const r = await fetch("/api/library", { method: "POST", body: "{}" }).then((x) => x.json());
  L.items = r.items || [];
}

export async function renderLibrary(onPlay) {
  L.onPlay = onPlay;
  $("libGrid").innerHTML = `<p class="muted">Loading…</p>`;
  await load();
  $("libTabs").querySelectorAll("button").forEach((b) => (b.onclick = () => { L.kind = b.dataset.kind; L.category = "All"; draw(); }));
  $("libSearch").oninput = (e) => { L.query = e.target.value.trim().toLowerCase(); draw(); };
  draw();
}

function visible() {
  return L.items.filter((it) => it.kind === L.kind
    && (L.category === "All" || it.category === L.category)
    && (!L.query || [it.name, it.description, ...it.aliases].join(" ").toLowerCase().includes(L.query)));
}

function draw() {
  const ofKind = L.items.filter((it) => it.kind === L.kind);
  $("libTabs").querySelectorAll("button").forEach((b) => {
    b.setAttribute("aria-pressed", b.dataset.kind === L.kind);
    b.querySelector("small").textContent = L.items.filter((it) => it.kind === b.dataset.kind).length;
  });
  const cats = ["All", ...new Set(ofKind.map((it) => it.category))];
  $("libCats").innerHTML = cats.length > 2 ? cats.map((c) => `<button class="lib-chip" data-cat="${esc(c)}" aria-pressed="${c === L.category}">${esc(c)}</button>`).join("") : "";
  $("libCats").querySelectorAll("button").forEach((b) => (b.onclick = () => { L.category = b.dataset.cat; draw(); }));
  const list = visible();
  $("libGrid").innerHTML = list.length ? "" : `<p class="muted">Nothing matches “${esc(L.query)}”.</p>`;
  for (const it of list) {
    const t = document.createElement("button");
    t.className = "lib-tile"; t.dataset.id = it.id;
    t.innerHTML = `<div class="art"></div><div class="nm">${esc(it.name)}</div>${it.video ? `<span class="lib-badge" title="Has a video">▶</span>` : ""}`;
    t.onclick = () => openItem(it.id);
    $("libGrid").appendChild(t);
    detailThumb(it).then((url) => url || thumbnailById(it.id, it.wokwi_type, it.attrs, 160)).then((url) => { if (url) t.querySelector(".art").innerHTML = `<img src="${url}" alt="">`; }).catch(() => {});
  }
}

function videoBlock(it) {
  if (it.video) return `<video class="lib-video" src="${esc(it.video)}" controls preload="metadata" playsinline></video>`;
  const q = encodeURIComponent(`how to use ${it.name}${it.kind === "part" ? " arduino" : " electronics"}`);
  return `<a class="btn ghost lib-yt" href="https://www.youtube.com/results?search_query=${q}" target="_blank" rel="noopener">▶ Find a video on YouTube ↗</a>`;
}

async function openItem(id) {
  const it = L.items.find((x) => x.id === id); if (!it) return;
  const pins = Array.isArray(it.pins) ? it.pins.map((p) => [p, ""]) : Object.entries(it.pins || {});
  $("libDetailCard").innerHTML = `
    <button class="lib-close" data-close aria-label="Close">✕</button>
    <div class="lib-view" id="libView"><span class="lib-drag">drag to turn · scroll to zoom in</span></div>
    <div class="lib-body">
      <div class="pop-level">${esc(it.kind === "tool" ? "Tool" : it.category)}${it.polarized ? " · has a + and − side" : ""}</div>
      <h2>${esc(it.name)}</h2>
      <p>${esc(it.description)}</p>
      ${it.how_to_use ? `<div class="seg-label">How to use it</div><p class="lib-how">${esc(it.how_to_use)}</p>` : ""}
      ${pins.length ? `<div class="seg-label">Pins</div><dl class="lib-pins">${pins.map(([p, what]) => `<dt>${esc(p)}</dt><dd>${esc(what)}</dd>`).join("")}</dl>` : ""}
      <div class="seg-label">Video</div>${videoBlock(it)}
      ${it.used_in.length ? `<div class="seg-label">Used in</div><div class="lib-used">${it.used_in.map((l) => `<button class="lib-chip" data-lesson="${esc(l.id)}">${esc(l.title)}</button>`).join("")}</div>` : ""}
    </div>`;
  $("libDetail").hidden = false;
  const close = () => { $("libDetail").hidden = true; stopViewer(); const v = $("libDetailCard").querySelector("video"); if (v) v.pause(); };
  $("libDetailCard").querySelectorAll("[data-close]").forEach((b) => (b.onclick = close));
  $("libDetail").onclick = (e) => { if (e.target === $("libDetail")) close(); };
  $("libDetailCard").querySelectorAll("[data-lesson]").forEach((b) => (b.onclick = () => { close(); L.onPlay && L.onPlay(b.dataset.lesson); }));
  startViewer($("libView"), await detailModel(it));
}

// a turntable: the detailed model, slowly spinning; drag to turn, zoom right in on the details
function startViewer(host, obj) {
  stopViewer();
  if (!obj || !host) return;
  const w = host.clientWidth || 520, h = host.clientHeight || 340;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, devicePixelRatio)); renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
  host.prepend(renderer.domElement);
  const scene = studio(renderer);
  scene.add(obj);
  const cam = new THREE.PerspectiveCamera(32, w / h, 1, 1000);
  const { center, dist } = fitCamera(cam, obj);
  cam.near = dist / 400; cam.updateProjectionMatrix();
  const ctl = new OrbitControls(cam, renderer.domElement);
  ctl.target.copy(center);
  ctl.enableDamping = true; ctl.autoRotate = true; ctl.autoRotateSpeed = 1.4; ctl.screenSpacePanning = true;
  ctl.minDistance = dist * 0.08; ctl.maxDistance = dist * 3; ctl.zoomSpeed = 1.2;
  ctl.addEventListener("start", () => (ctl.autoRotate = false));
  let raf = 0;
  const loop = () => { ctl.update(); renderer.render(scene, cam); raf = requestAnimationFrame(loop); };
  loop();
  L.viewer = { stop: () => { cancelAnimationFrame(raf); ctl.dispose(); dispose(obj); renderer.dispose(); renderer.domElement.remove(); } };
  window.__libViewer = { ok: true, cam, ctl };
}
function stopViewer() { if (L.viewer) { L.viewer.stop(); L.viewer = null; } }
