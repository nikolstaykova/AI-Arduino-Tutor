// The Learn overworld: a small low-poly 3D world (three.js) you travel
// through. Sparky drives a little car along one winding road; every level is
// a checkpoint flag on it; each world is a themed zone the road runs through
// (Lighthouse Bay, Button Arcade, Dial Desert, Motor Moon, AI Lab ...).
// Levels are never locked. Flags are coloured by what you own: green READY,
// blue STAND-IN, white NEEDS n, gold done.
//
// Same interface as the old flat map: createWorldMap(host, {onOpen, onCreate,
// lessonIcon}) -> {render(worlds, matches), celebrate(id), updateMatches(m),
// walkTo(id), tiles()}.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const FLAG = { done: 0xd9b35c, ready: 0x6fbf8e, sub: 0x6fa8c7, need: 0xe9e9e6, open: 0xd08a5c, soon: 0xa4a8b0, create: 0x5fae99 };

// ---------------------------------------------------------------------------
// Low-poly building blocks
// ---------------------------------------------------------------------------
const matCache = new Map();
function mat(color, extra = {}) {
  const key = color + JSON.stringify(extra);
  if (!matCache.has(key)) matCache.set(key, new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 0.8, ...extra }));
  return matCache.get(key);
}
function m(geo, color, extra) {
  const o = new THREE.Mesh(geo, typeof color === "object" ? color : mat(color, extra));
  o.castShadow = true; o.receiveShadow = true;
  return o;
}
function at(o, x, y, z, s = 1) { o.position.set(x, y, z); if (s !== 1) o.scale.setScalar(s); return o; }

function tree(x, z, s = 1) {
  const g = new THREE.Group();
  g.add(at(m(new THREE.CylinderGeometry(0.8, 1.1, 5, 6), 0x8a6a50), 0, 2.5, 0));
  g.add(at(m(new THREE.IcosahedronGeometry(3.9, 0), 0x7fa37a), 0, 7.4, 0));
  g.add(at(m(new THREE.IcosahedronGeometry(2.7, 0), 0x93b48c), 1.4, 9.6, 0.6));
  g.add(at(m(new THREE.IcosahedronGeometry(2.2, 0), 0x86a97f), -1.6, 8.8, -0.8));
  g.rotation.y = x * 0.37;
  return at(g, x, 0, z, s);
}

// ---------------------------------------------------------------------------
// The countryside between the worlds: hills, grass, cottages, LED mushrooms,
// grazing sheep, a winding river and a few lakes.
// ---------------------------------------------------------------------------
const WATER = () => new THREE.MeshStandardMaterial({ color: 0x8fb8c8, roughness: 0.25, metalness: 0.05, flatShading: true });
function house(s = 1) {
  const g = new THREE.Group();
  const wall = [0xece4d4, 0xe3d6c2, 0xd9cdb8][Math.floor(Math.random() * 3)];
  g.add(at(m(new THREE.BoxGeometry(7, 5, 6), wall), 0, 2.5, 0));
  const roof = m(new THREE.CylinderGeometry(0.01, 5.4, 4, 4, 1), [0xb86b52, 0x8e6f5a, 0x7f95a8][Math.floor(Math.random() * 3)]);
  roof.rotation.y = Math.PI / 4; roof.scale.set(1.05, 1, 0.92); roof.position.y = 7; g.add(roof);
  g.add(at(m(new THREE.BoxGeometry(1.6, 2.8, 0.2), 0x7a5a40), 0, 1.4, 3.05));
  for (const x of [-2.2, 2.2]) g.add(at(m(new THREE.BoxGeometry(1.3, 1.2, 0.2), 0xbfd4dc, { emissive: 0xffe2a0, emissiveIntensity: 0.15 }), x, 3.2, 3.05));
  g.add(at(m(new THREE.BoxGeometry(1, 3, 1), 0x8a8580), 2.2, 8.2, -1));
  g.scale.setScalar(s);
  return g;
}
function ledMushroom(color, s = 1) {       // an LED for a cap, its two legs for a stem
  const g = new THREE.Group();
  const cap = m(new THREE.SphereGeometry(1.2, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), color, { emissive: color, emissiveIntensity: 0.35, transparent: true, opacity: 0.9, roughness: 0.2 });
  cap.position.y = 3; g.add(cap);
  g.add(at(m(new THREE.CylinderGeometry(1.2, 1.2, 1.3, 16), color, { emissive: color, emissiveIntensity: 0.35, transparent: true, opacity: 0.9, roughness: 0.2 }), 0, 2.4, 0));
  g.add(at(m(new THREE.CylinderGeometry(1.35, 1.35, 0.3, 16), color), 0, 1.7, 0));
  g.add(at(m(new THREE.CylinderGeometry(0.12, 0.12, 1.7, 6), 0xd4d6da, { metalness: 0.2, roughness: 0.4 }), -0.4, 0.85, 0));
  g.add(at(m(new THREE.CylinderGeometry(0.12, 0.12, 2.1, 6), 0xd4d6da, { metalness: 0.2, roughness: 0.4 }), 0.4, 1.05, 0));
  // a little face
  for (const k of [-1, 1]) { g.add(at(m(new THREE.SphereGeometry(0.16, 8, 6), 0x1c1d21), 1.12, 2.5, k * 0.35)); g.add(at(m(new THREE.SphereGeometry(0.05, 6, 4), 0xffffff), 1.26, 2.56, k * 0.35 + 0.04)); }
  const smile = m(new THREE.TorusGeometry(0.22, 0.04, 6, 12, Math.PI), 0x1c1d21); smile.position.set(1.18, 2.22, 0); smile.rotation.set(0, Math.PI / 2, Math.PI); g.add(smile);
  g.userData.cap = cap; g.scale.setScalar(s);
  return g;
}
function sheep() {
  const g = new THREE.Group(), body = new THREE.Group();
  for (const [x, y, z, r] of [[0, 1.9, 0, 1.3], [1, 2, 0.3, 1], [-1, 2, -0.2, 1], [0.3, 2.6, 0, 1], [-0.5, 2.4, 0.5, 0.9], [0.6, 2.3, -0.6, 0.9]])
    body.add(at(m(new THREE.IcosahedronGeometry(r, 0), 0xf2f0ea), x, y, z));
  g.add(body);
  for (const [x, z] of [[0.8, 0.5], [0.8, -0.5], [-0.8, 0.5], [-0.8, -0.5]]) g.add(at(m(new THREE.CylinderGeometry(0.16, 0.16, 1.2, 5), 0x3a3a3a), x, 0.6, z));
  const head = new THREE.Group(); head.position.set(1.8, 2.1, 0);
  head.add(at(m(new THREE.BoxGeometry(1, 0.8, 0.8), 0x2f2f33), 0.3, 0, 0));
  head.add(at(m(new THREE.BoxGeometry(0.2, 0.35, 0.5), 0x2f2f33), -0.1, 0.35, 0.45));
  head.add(at(m(new THREE.BoxGeometry(0.2, 0.35, 0.5), 0x2f2f33), -0.1, 0.35, -0.45));
  eyes(head, 0.72, 0.15, 0, 0.8, 0.28);
  g.add(head); g.userData.head = head;
  return g;
}
// ---- cute critters ------------------------------------------------------------
function eyes(g, x, y, z, s = 1, spread = 0.35, dir = "x") {   // two shiny eyes looking along +x (or +z)
  for (const k of [-1, 1]) {
    const e = new THREE.Group();
    e.add(m(new THREE.SphereGeometry(0.22 * s, 10, 8), 0xffffff));
    e.add(at(m(new THREE.SphereGeometry(0.13 * s, 8, 6), 0x1c1d21), dir === "x" ? 0.12 * s : 0, 0.02 * s, dir === "x" ? 0 : 0.12 * s));
    e.position.set(x + (dir === "x" ? 0 : k * spread * s), y, z + (dir === "x" ? k * spread * s : 0));
    g.add(e);
  }
}
function bunny(color = 0xf2f0ea) {
  const g = new THREE.Group();
  const body = m(new THREE.SphereGeometry(1, 12, 10), color); body.scale.set(1.2, 0.95, 0.9); body.position.y = 1; g.add(body);
  g.add(at(m(new THREE.SphereGeometry(0.7, 12, 10), color), 1, 1.8, 0));
  for (const k of [-1, 1]) { const ear = m(new THREE.CylinderGeometry(0.18, 0.25, 1.6, 8), color); ear.position.set(0.8, 2.9, k * 0.3); ear.rotation.x = k * 0.2; ear.scale.z = 0.5; g.add(ear);
    const inner = m(new THREE.CylinderGeometry(0.1, 0.14, 1.2, 8), 0xe8b4b0); inner.position.set(0.86, 2.9, k * 0.3); inner.rotation.x = k * 0.2; inner.scale.z = 0.4; g.add(inner); }
  g.add(at(m(new THREE.SphereGeometry(0.35, 8, 6), 0xffffff), -1.2, 1.2, 0));
  g.add(at(m(new THREE.SphereGeometry(0.1, 6, 4), 0xe8a0a0), 1.68, 1.8, 0));
  eyes(g, 1.5, 2, 0, 1, 0.33);
  return g;
}
function chicken() {
  const g = new THREE.Group();
  const body = m(new THREE.SphereGeometry(0.9, 12, 10), 0xf6f2e8); body.scale.set(1.1, 1, 0.9); body.position.y = 1.3; g.add(body);
  const head = new THREE.Group(); head.position.set(0.8, 2.2, 0); g.add(head);
  head.add(m(new THREE.SphereGeometry(0.5, 10, 8), 0xf6f2e8));
  head.add(at(m(new THREE.BoxGeometry(0.4, 0.35, 0.15), 0xd9443a), 0, 0.5, 0));
  const beak = m(new THREE.ConeGeometry(0.15, 0.4, 6), 0xe8a040); beak.rotation.z = -Math.PI / 2; beak.position.set(0.55, 0, 0); head.add(beak);
  eyes(head, 0.35, 0.12, 0, 0.7, 0.3);
  for (const k of [-1, 1]) g.add(at(m(new THREE.CylinderGeometry(0.06, 0.06, 0.6, 4), 0xe8a040), 0, 0.3, k * 0.3));
  g.add(at(m(new THREE.ConeGeometry(0.4, 0.8, 5), 0xf6f2e8), -0.9, 1.7, 0));
  g.userData.head = head;
  return g;
}
function cow() {
  const g = new THREE.Group();
  g.add(at(m(new RoundedBoxGeometry(4, 2.2, 2, 2, 0.5), 0xf4f1ea), 0, 2.4, 0));
  for (const [x, y, z, w] of [[0.6, 2.9, 1.02, 1], [-1, 2.2, 1.02, 0.8], [-0.4, 2.6, -1.02, 1.1], [1.2, 1.9, -1.02, 0.6]]) g.add(at(m(new THREE.BoxGeometry(w, w * 0.8, 0.05), 0x2f2f33), x, y, z));
  for (const [x, z] of [[1.4, 0.7], [1.4, -0.7], [-1.4, 0.7], [-1.4, -0.7]]) g.add(at(m(new THREE.CylinderGeometry(0.25, 0.22, 1.4, 6), 0xf4f1ea), x, 0.7, z));
  const head = new THREE.Group(); head.position.set(2.4, 3, 0); g.add(head);
  head.add(m(new RoundedBoxGeometry(1.4, 1.3, 1.3, 2, 0.35), 0xf4f1ea));
  head.add(at(m(new RoundedBoxGeometry(0.5, 0.8, 1.1, 2, 0.2), 0xe8b4b0), 0.7, -0.25, 0));
  for (const k of [-1, 1]) { head.add(at(m(new THREE.ConeGeometry(0.15, 0.6, 6), 0xe8e0c8), -0.1, 0.85, k * 0.45)); }
  eyes(head, 0.62, 0.25, 0, 0.9, 0.38);
  g.userData.head = head;
  return g;
}
function butterfly(color) {
  const g = new THREE.Group();
  const wingMat = new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide, roughness: 0.5 });
  const wings = [-1, 1].map((k) => { const w = new THREE.Mesh(new THREE.CircleGeometry(0.9, 12), wingMat); w.scale.set(1, 0.75, 1); const pivot = new THREE.Group(); w.position.z = k * 0.85; w.rotation.x = Math.PI / 2; pivot.add(w); g.add(pivot); return pivot; });
  g.add(m(new THREE.CylinderGeometry(0.1, 0.1, 1.2, 6), 0x3a3a3a)).children.at(-1).rotation.z = Math.PI / 2;
  g.userData.wings = wings;
  return g;
}
function bird() {
  const g = new THREE.Group();
  for (const k of [-1, 1]) { const w = m(new THREE.BoxGeometry(0.8, 0.1, 2.2), 0x5b5f6a); w.position.z = k * 1.1; w.rotation.x = k * 0.3; g.add(w); }
  g.add(m(new THREE.SphereGeometry(0.45, 8, 6), 0x5b5f6a));
  return g;
}
function frog() {
  const g = new THREE.Group();
  const pad = m(new THREE.CircleGeometry(2, 16), 0x7fa06c); pad.rotation.x = -Math.PI / 2; pad.position.y = 0.12; g.add(pad);
  const f = new THREE.Group(); g.add(f); g.userData.body = f;
  const body = m(new THREE.SphereGeometry(0.8, 12, 10), 0x8cc07a); body.scale.set(1, 0.7, 1.1); body.position.y = 0.6; f.add(body);
  for (const k of [-1, 1]) { f.add(at(m(new THREE.SphereGeometry(0.3, 10, 8), 0x8cc07a), 0.35, 1.1, k * 0.4)); f.add(at(m(new THREE.SphereGeometry(0.2, 8, 6), 0xffffff), 0.5, 1.2, k * 0.4)); f.add(at(m(new THREE.SphereGeometry(0.11, 6, 4), 0x1c1d21), 0.66, 1.22, k * 0.4)); }
  return g;
}
function fish() {
  const g = new THREE.Group();
  const b = m(new THREE.SphereGeometry(0.8, 12, 8), 0xe8904a); b.scale.set(1.5, 0.8, 0.55); g.add(b);
  const tail = m(new THREE.ConeGeometry(0.6, 0.9, 4), 0xe8904a); tail.rotation.z = Math.PI / 2; tail.position.x = -1.5; g.add(tail);
  eyes(g, 0.8, 0.2, 0, 0.6, 0.3);
  return g;
}
export function robot(color = 0x7fa8d4) {                   // a cute boxy robot with a screen face
  const g = new THREE.Group();
  g.add(at(m(new RoundedBoxGeometry(2.4, 2.6, 2, 2, 0.4), color), 0, 2.3, 0));
  for (const k of [-1, 1]) { const wh = m(new THREE.CylinderGeometry(0.6, 0.6, 0.4, 14), 0x3a3c42); wh.rotation.x = Math.PI / 2; wh.position.set(0, 0.6, k * 1.05); g.add(wh); }
  const head = new THREE.Group(); head.position.y = 4.4; g.add(head);
  head.add(m(new RoundedBoxGeometry(2.2, 1.7, 1.8, 2, 0.4), 0xe8e8e2));
  head.add(at(m(new RoundedBoxGeometry(0.1, 1.1, 1.4, 1, 0.05), 0x2b2e33), 1.1, 0, 0));
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x9fe0ff, emissive: 0x9fe0ff, emissiveIntensity: 1.2 });
  for (const k of [-1, 1]) head.add(at(new THREE.Mesh(new THREE.SphereGeometry(0.2, 8, 6), eyeMat), 1.18, 0.12, k * 0.35));
  head.add(at(new THREE.Mesh(new THREE.TorusGeometry(0.25, 0.05, 6, 12, Math.PI), eyeMat), 1.18, -0.25, 0)).children.at(-1).rotation.set(0, Math.PI / 2, Math.PI);
  head.add(at(m(new THREE.CylinderGeometry(0.06, 0.06, 1, 6), 0x9aa0a8), 0, 1.3, 0));
  const bulb = m(new THREE.SphereGeometry(0.25, 8, 6), 0xd9776a, { emissive: 0xd9776a, emissiveIntensity: 1 }); bulb.position.y = 1.85; head.add(bulb);
  const arms = [-1, 1].map((k) => { const a = new THREE.Group(); a.position.set(0, 3.2, k * 1.25); a.add(at(m(new THREE.CylinderGeometry(0.18, 0.18, 1.6, 6), 0x9aa0a8), 0, -0.8, 0)); a.add(at(m(new THREE.SphereGeometry(0.3, 8, 6), 0x9aa0a8), 0, -1.6, 0)); g.add(a); return a; });
  g.userData = { head, bulb, arms };
  return g;
}
function ghost(color) {
  const g = new THREE.Group();
  const mm = { color, emissive: color, emissiveIntensity: 0.25, transparent: true, opacity: 0.92 };
  g.add(at(m(new THREE.SphereGeometry(1.4, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), color, mm), 0, 2, 0));
  g.add(at(m(new THREE.CylinderGeometry(1.4, 1.4, 1.6, 16, 1, true), color, { ...mm, side: THREE.DoubleSide }), 0, 1.2, 0));
  for (let k = 0; k < 6; k++) { const a = (k / 6) * Math.PI * 2; g.add(at(m(new THREE.ConeGeometry(0.45, 0.6, 4), color, mm), Math.cos(a) * 1.05, 0.15, Math.sin(a) * 1.05)).children.at(-1).rotation.x = Math.PI; }
  eyes(g, 1.2, 2, 0, 1.4, 0.35);
  return g;
}
function camel() {
  const g = new THREE.Group(), c = 0xd9b98a;
  g.add(at(m(new RoundedBoxGeometry(4, 2, 1.8, 2, 0.6), c), 0, 3.5, 0));
  g.add(at(m(new THREE.SphereGeometry(1.1, 10, 8), c), -0.3, 4.6, 0));
  for (const [x, z] of [[1.4, 0.6], [1.4, -0.6], [-1.4, 0.6], [-1.4, -0.6]]) g.add(at(m(new THREE.CylinderGeometry(0.25, 0.2, 2.6, 6), c), x, 1.3, z));
  const neck = m(new THREE.CylinderGeometry(0.4, 0.5, 2.4, 8), c); neck.position.set(2.3, 4.6, 0); neck.rotation.z = -0.6; g.add(neck);
  const head = new THREE.Group(); head.position.set(3.2, 5.6, 0); g.add(head);
  head.add(m(new RoundedBoxGeometry(1.4, 0.8, 0.8, 2, 0.3), c)); eyes(head, 0.4, 0.3, 0, 0.8, 0.4);
  g.userData.head = head;
  return g;
}
function crab() {
  const g = new THREE.Group();
  const body = m(new THREE.SphereGeometry(1, 12, 8), 0xd9776a); body.scale.set(1, 0.5, 1.3); body.position.y = 0.8; g.add(body);
  for (const k of [-1, 1]) {
    g.add(at(m(new THREE.CylinderGeometry(0.08, 0.08, 0.7, 5), 0xd9776a), 0.4, 1.4, k * 0.35)); g.add(at(m(new THREE.SphereGeometry(0.18, 8, 6), 0xffffff), 0.4, 1.8, k * 0.35)); g.add(at(m(new THREE.SphereGeometry(0.1, 6, 4), 0x1c1d21), 0.52, 1.82, k * 0.35));
    g.add(at(m(new THREE.SphereGeometry(0.4, 8, 6), 0xd9776a), 1, 0.9, k * 1.3));
    for (let j = 0; j < 3; j++) { const leg = m(new THREE.CylinderGeometry(0.06, 0.06, 0.9, 4), 0xd9776a); leg.position.set(-0.3 + j * 0.3, 0.45, k * 1.2); leg.rotation.x = k * 0.8; g.add(leg); }
  }
  return g;
}
function cat() {
  const g = new THREE.Group(), c = 0xe8a86a;
  const body = m(new THREE.SphereGeometry(1, 12, 10), c); body.scale.set(1.3, 1, 0.9); body.position.y = 1; g.add(body);
  g.add(at(m(new THREE.SphereGeometry(0.75, 12, 10), c), 0.9, 2, 0));
  for (const k of [-1, 1]) g.add(at(m(new THREE.ConeGeometry(0.28, 0.5, 4), c), 0.9, 2.75, k * 0.4));
  eyes(g, 1.55, 2.1, 0, 0.8, 0.35);
  const tail = new THREE.Group(); tail.position.set(-1.2, 1, 0); g.add(tail);
  tail.add(at(m(new THREE.CylinderGeometry(0.15, 0.12, 1.8, 6), c), 0, 0.9, 0));
  g.userData.tail = tail;
  return g;
}
function deer() {
  const g = new THREE.Group(), c = 0xb98a5a;
  g.add(at(m(new RoundedBoxGeometry(3, 1.6, 1.3, 2, 0.5), c), 0, 3, 0));
  for (const [x, z] of [[1, 0.4], [1, -0.4], [-1, 0.4], [-1, -0.4]]) g.add(at(m(new THREE.CylinderGeometry(0.15, 0.12, 2.4, 6), c), x, 1.2, z));
  const head = new THREE.Group(); head.position.set(1.7, 4.1, 0); g.add(head);
  head.add(m(new RoundedBoxGeometry(1.1, 0.9, 0.8, 2, 0.3), c));
  for (const k of [-1, 1]) { const a = m(new THREE.CylinderGeometry(0.06, 0.08, 1.2, 4), 0x8a6a50); a.position.set(-0.1, 0.9, k * 0.3); a.rotation.x = k * 0.4; head.add(a); }
  eyes(head, 0.4, 0.15, 0, 0.8, 0.35);
  g.add(at(m(new THREE.SphereGeometry(0.25, 6, 4), 0xf2f0ea), -1.55, 3.3, 0));
  g.userData.head = head;
  return g;
}
function owl(glasses = false) {
  const g = new THREE.Group();
  const body = m(new THREE.SphereGeometry(1.2, 12, 10), 0x9a7a5a); body.scale.set(1, 1.3, 1); body.position.y = 1.5; g.add(body);
  g.add(at(m(new THREE.SphereGeometry(0.8, 12, 10), 0xd9c9a0), 0.6, 1.3, 0));
  const lids = [];
  for (const k of [-1, 1]) {
    g.add(at(m(new THREE.SphereGeometry(0.42, 12, 10), 0xffffff), 0.95, 2.2, k * 0.45)); g.add(at(m(new THREE.SphereGeometry(0.22, 8, 6), 0x1c1d21), 1.3, 2.2, k * 0.45));
    const lid = m(new THREE.SphereGeometry(0.44, 12, 10, 0, Math.PI * 2, 0, Math.PI / 2), 0x9a7a5a); lid.position.set(0.95, 2.2, k * 0.45); lid.rotation.z = -Math.PI / 2; lid.scale.y = 0.05; g.add(lid); lids.push(lid);
    if (glasses) { const r = m(new THREE.TorusGeometry(0.5, 0.06, 6, 16), 0x3a3a3a); r.position.set(1.3, 2.2, k * 0.45); r.rotation.y = Math.PI / 2; g.add(r); }
    g.add(at(m(new THREE.ConeGeometry(0.2, 0.5, 4), 0x9a7a5a), 0.3, 3.2, k * 0.55));
  }
  const beak = m(new THREE.ConeGeometry(0.15, 0.4, 4), 0xe8a040); beak.rotation.z = -Math.PI / 2; beak.position.set(1.25, 1.85, 0); g.add(beak);
  g.userData.lids = lids;
  return g;
}
function mouseCritter() {
  const g = new THREE.Group(), c = 0xb8bcc4;
  const body = m(new THREE.SphereGeometry(0.8, 12, 10), c); body.scale.set(1.4, 0.8, 0.9); body.position.y = 0.7; g.add(body);
  g.add(at(m(new THREE.SphereGeometry(0.5, 10, 8), c), 1, 1, 0));
  for (const k of [-1, 1]) { const ear = m(new THREE.CylinderGeometry(0.4, 0.4, 0.08, 14), 0xe8b4b0); ear.rotation.x = Math.PI / 2; ear.position.set(0.9, 1.5, k * 0.35); g.add(ear); }
  eyes(g, 1.38, 1.1, 0, 0.6, 0.3);
  g.add(cable3([[-1.1, 0.6, 0], [-2, 0.3, 0.5], [-2.8, 0.2, -0.3]], 0.07, 0xe8b4b0));
  return g;
}
function cable3(points, r, c) { return m(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p))), 16, r, 6), c); }

// walk a critter round a small loop: position + facing, with an optional hop
function wander(o, cx, cz, rad, speed, phase, hop = 0) {
  return (t) => {
    const a = t * speed + phase;
    o.position.set(cx + Math.cos(a) * rad, hop ? Math.abs(Math.sin(t * 5 + phase)) * hop : 0, cz + Math.sin(a * 1.3) * rad * 0.8);
    o.rotation.y = -Math.atan2(Math.cos(a * 1.3) * 1.3 * 0.8, -Math.sin(a)) + Math.PI / 2;
  };
}

function countryside({ z0, z1, clear, zones: zs, seed = 7 }) {
  const g = new THREE.Group(), ticks = [];
  let rnd = seed * 7919 + 13;
  const R = () => ((rnd = (rnd * 9301 + 49297) % 233280) / 233280);
  const riverX = (z) => -112 + Math.sin(z / 95) * 26 + Math.sin(z / 37) * 6;
  const inZone = (x, z, pad = 0) => zs.some((d) => (d.center.x - x) ** 2 + (d.center.z - z) ** 2 < (d.radius * 0.95 + pad) ** 2);
  const lakes = [];
  const free = (x, z, room) => clear(x, z, room) && !inZone(x, z, room * 0.3) && Math.abs(x - riverX(z)) > 10 + room
    && lakes.every((l) => (l.x - x) ** 2 + (l.z - z) ** 2 > (l.r + room) ** 2);
  const spot = (room, xmin = -175, xmax = 175) => {
    for (let k = 0; k < 30; k++) {
      const x = xmin + R() * (xmax - xmin), z = z1 + R() * (z0 - z1);
      if (free(x, z, room)) return [x, z];
    }
    return null;
  };
  const water = WATER();
  // the river, winding alongside the whole road on the left
  const rpts = []; for (let z = z0 + 40; z > z1 - 40; z -= 12) rpts.push(new THREE.Vector3(riverX(z), 0.06, z));
  const rcurve = new THREE.CatmullRomCurve3(rpts), rs = rcurve.getPoints(rpts.length * 4), up = new THREE.Vector3(0, 1, 0);
  const verts = [], bank = [];
  rs.forEach((p, i) => {
    const tan = rcurve.getTangent(i / (rs.length - 1)), side = new THREE.Vector3().crossVectors(up, tan).normalize(), w = 6 + Math.sin(i / 7) * 1.5;
    verts.push(p.clone().addScaledVector(side, w), p.clone().addScaledVector(side, -w));
    bank.push(p.clone().addScaledVector(side, w + 2).setY(0.03), p.clone().addScaledVector(side, -w - 2).setY(0.03));
  });
  const strip = (pts, material) => { const idx = []; for (let i = 0; i < pts.length / 2 - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } const geo = new THREE.BufferGeometry().setFromPoints(pts); geo.setIndex(idx); geo.computeVertexNormals(); const mm = new THREE.Mesh(geo, material); mm.receiveShadow = true; return mm; };
  g.add(strip(bank, new THREE.MeshStandardMaterial({ color: 0xd8c9a0, roughness: 1, side: THREE.DoubleSide })));
  g.add(strip(verts, Object.assign(water, { side: THREE.DoubleSide })));
  // lakes on the right, with a sandy shore and reeds
  for (let i = 0; i < 9; i++) {
    const r = 12 + R() * 12, x = 70 + R() * 90, z = z1 + R() * (z0 - z1);
    if (!clear(x, z, r + 14) || inZone(x, z, r)) continue;
    lakes.push({ x, z, r });
    const shape = new THREE.Shape();
    // a smooth, natural outline: a couple of slow wobbles, not spikes
    for (let k = 0; k <= 48; k++) { const a = (k / 48) * Math.PI * 2, rr = r * (0.9 + 0.08 * Math.sin(a * 2 + i) + 0.05 * Math.sin(a * 3 + i * 2)); k ? shape.lineTo(Math.cos(a) * rr * 1.3, Math.sin(a) * rr) : shape.moveTo(Math.cos(a) * rr * 1.3, Math.sin(a) * rr); }
    const shore = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshStandardMaterial({ color: 0xd8c9a0, roughness: 1 })); shore.rotation.x = -Math.PI / 2; shore.scale.setScalar(1.18); shore.position.set(x, 0.03, z); g.add(shore);
    const lake = new THREE.Mesh(new THREE.ShapeGeometry(shape), water); lake.rotation.x = -Math.PI / 2; lake.position.set(x, 0.07, z); g.add(lake);
    for (let k = 0; k < 10; k++) { const a = R() * Math.PI * 2; g.add(at(m(new THREE.CylinderGeometry(0.12, 0.2, 2 + R() * 2, 4), 0x7f9a6a), x + Math.cos(a) * r * 1.02, 1, z + Math.sin(a) * r * 1.02)); }
    if (R() < 0.6) { const duck = new THREE.Group(); duck.add(at(m(new THREE.SphereGeometry(0.7, 8, 6), 0xf2f0ea), 0, 0.4, 0)); duck.add(at(m(new THREE.SphereGeometry(0.4, 8, 6), 0x5f7f5c), 0.6, 0.9, 0)); g.add(duck);
      const ph = R() * 6; ticks.push((t) => { const a = t * 0.15 + ph; duck.position.set(x + Math.cos(a) * r * 0.5, 0.1, z + Math.sin(a) * r * 0.5); duck.rotation.y = -a; }); }
  }
  const wc = new THREE.Color(0x8fb8c8), wh = new THREE.Color(0xa6c8d4);
  ticks.push((t) => water.color.copy(wc).lerp(wh, (Math.sin(t * 0.8) + 1) * 0.3));
  // rolling hills
  const hillCols = [0x8fae78, 0x86a770, 0x97b582, 0x7fa06c];
  for (let i = 0; i < 70; i++) {
    const r = 14 + R() * 26, p = spot(r * 0.8 + 8, -190, 190); if (!p) continue;
    const h = m(new THREE.IcosahedronGeometry(r, 1), hillCols[i % 4]); h.scale.y = 0.22 + R() * 0.18; h.position.set(p[0], 0, p[1]); h.rotation.y = R() * 3; h.castShadow = false; g.add(h);
  }
  // woods
  for (let i = 0; i < 110; i++) { const p = spot(6); if (p) g.add(tree(p[0], p[1], 0.8 + R() * 0.6)); }
  // hamlets of cottages (with chickens pecking about)
  for (let hmt = 0; hmt < 9; hmt++) {
    const c = spot(22, -150, 160); if (!c) continue;
    for (let k = 0; k < 3; k++) {
      const ch = chicken(); ch.scale.setScalar(1.2); g.add(ch);
      const walk = wander(ch, c[0] + (R() - 0.5) * 14, c[1] + (R() - 0.5) * 14, 2 + R() * 2, 0.12 + R() * 0.1, R() * 9), ph = R() * 5;
      ticks.push((t) => { walk(t); const peck = Math.max(0, Math.sin(t * 3 + ph)); ch.userData.head.position.y = 2.2 - peck * 0.9; ch.userData.head.rotation.z = -peck * 0.8; });
    }
    for (let k = 0; k < 3; k++) { const x = c[0] + (R() - 0.5) * 26, z = c[1] + (R() - 0.5) * 26; if (!free(x, z, 7)) continue; const hs = house(0.9 + R() * 0.3); hs.position.set(x, 0, z); hs.rotation.y = R() * Math.PI * 2; g.add(hs); }
  }
  // LED mushrooms, in little rings
  const ledCols = [0xd9776a, 0x7fbf8e, 0xe0c86a, 0x7fa8d4, 0xc49ad6];
  for (let i = 0; i < 26; i++) {
    const c = spot(6); if (!c) continue;
    for (let k = 0; k < 3 + Math.floor(R() * 3); k++) {
      const a = R() * Math.PI * 2, d = 2.5 + R() * 5, mu = ledMushroom(ledCols[(i + k) % 5], 1.5 + R() * 1.1);
      mu.position.set(c[0] + Math.cos(a) * d, 0, c[1] + Math.sin(a) * d); g.add(mu);
      const ph = R() * 6; ticks.push((t) => { mu.userData.cap.material.emissiveIntensity = 0.25 + (Math.sin(t * 1.3 + ph) + 1) * 0.2; });
    }
  }
  // sheep, grazing and pottering about
  for (let f = 0; f < 9; f++) {
    const c = spot(14); if (!c) continue;
    for (let k = 0; k < 2 + Math.floor(R() * 3); k++) {
      const sh = sheep(); sh.scale.setScalar(1.7); g.add(sh);
      const cx = c[0] + (R() - 0.5) * 16, cz = c[1] + (R() - 0.5) * 16, ph = R() * 10, sp = 0.05 + R() * 0.05;
      ticks.push((t) => {
        const a = t * sp + ph;
        sh.position.set(cx + Math.cos(a) * 4, 0, cz + Math.sin(a * 1.3) * 4);
        sh.rotation.y = -Math.atan2(Math.cos(a * 1.3) * 1.3, -Math.sin(a)) + Math.PI / 2;
        const graze = (Math.sin(t * 0.7 + ph) + 1) / 2;                   // head down to the grass, then up
        sh.userData.head.rotation.z = -graze * 0.9; sh.userData.head.position.y = 2.1 - graze * 0.9;
      });
    }
  }
  // bunnies, hopping in pairs
  const fur = [0xf2f0ea, 0xc9a07a, 0xd9d4ca];
  for (let i = 0; i < 14; i++) {
    const c = spot(8); if (!c) continue;
    for (let k = 0; k < 2; k++) { const b = bunny(fur[(i + k) % 3]); b.scale.setScalar(1.3); g.add(b); ticks.push(wander(b, c[0] + k * 3, c[1], 3 + R() * 3, 0.25 + R() * 0.15, R() * 9, 1.4)); }
  }
  // cows, grazing
  for (let i = 0; i < 6; i++) {
    const c = spot(16); if (!c) continue;
    for (let k = 0; k < 2 + Math.floor(R() * 2); k++) {
      const cw = cow(); cw.scale.setScalar(1.3); g.add(cw);
      const walk = wander(cw, c[0] + (R() - 0.5) * 16, c[1] + (R() - 0.5) * 16, 2.5, 0.03 + R() * 0.03, R() * 9), ph = R() * 9;
      ticks.push((t) => { walk(t); const graze = (Math.sin(t * 0.5 + ph) + 1) / 2; cw.userData.head.position.y = 3 - graze * 1.6; cw.userData.head.rotation.z = -graze * 0.6; });
    }
  }
  // butterflies over the grass
  const wingCols = [0xf2c4d0, 0xf6e0a0, 0xbfd8f2, 0xd8c4f0, 0xf6c89a];
  for (let i = 0; i < 40; i++) {
    const c = spot(4); if (!c) continue;
    const bf = butterfly(wingCols[i % 5]); g.add(bf);
    const ph = R() * 9, rad = 3 + R() * 5, h = 3 + R() * 4;
    ticks.push((t) => {
      const a = t * 0.5 + ph;
      bf.position.set(c[0] + Math.cos(a) * rad, h + Math.sin(t * 2 + ph) * 1.2, c[1] + Math.sin(a * 1.4) * rad);
      bf.rotation.y = -a; const flap = Math.sin(t * 16 + ph) * 0.9; bf.userData.wings[0].rotation.x = flap; bf.userData.wings[1].rotation.x = -flap;
    });
  }
  // birds flying over in little V flocks
  for (let f = 0; f < 5; f++) {
    const x0 = -120 + R() * 240, h = 38 + R() * 14, sp = 6 + R() * 5, ph = R() * 1000;
    for (let k = 0; k < 5; k++) {
      const bd = bird(); g.add(bd); const off = [[0, 0], [-3, 3], [-3, -3], [-6, 6], [-6, -6]][k];
      ticks.push((t) => { const z = z0 - ((t * sp + ph) % (z0 - z1 + 200)); bd.position.set(x0 + off[1], h + Math.sin(t * 2 + k) * 0.6, z - off[0]); bd.rotation.y = Math.PI / 2; bd.children.slice(0, 2).forEach((w, j) => (w.rotation.x = (j ? 1 : -1) * (0.3 + Math.sin(t * 7 + k) * 0.4))); });
    }
  }
  // on the lakes: frogs on lily pads, fish that leap
  lakes.forEach((l, i) => {
    const fr = frog(); fr.scale.setScalar(1.3); fr.position.set(l.x + l.r * 0.4, 0, l.z - l.r * 0.3); g.add(fr);
    const ph = R() * 9; ticks.push((t) => { const hop = Math.max(0, Math.sin(t * 1.5 + ph)); fr.userData.body.position.y = hop > 0.9 ? (hop - 0.9) * 18 : 0; });
    const fs = fish(); fs.scale.setScalar(1.2); g.add(fs);
    const fph = R() * 9, fx = l.x - l.r * 0.3, fz = l.z + l.r * 0.2;
    ticks.push((t) => { const k = ((t + fph) % 5) / 1.2; if (k > 1) { fs.visible = false; return; } fs.visible = true; fs.position.set(fx + (k - 0.5) * 6, Math.sin(k * Math.PI) * 4, fz); fs.rotation.z = Math.cos(k * Math.PI) * 0.9; });
  });
  // grass tufts
  const tuftGeo = new THREE.ConeGeometry(0.35, 1.6, 3), tufts = new THREE.InstancedMesh(tuftGeo, mat(0x86a97f), 1600), mm = new THREE.Matrix4();
  let n = 0;
  for (let i = 0; i < 4000 && n < 1600; i++) { const x = -185 + R() * 370, z = z1 + R() * (z0 - z1); if (!free(x, z, 3)) continue; mm.makeRotationY(R() * 3); mm.setPosition(x, 0.8, z); tufts.setMatrixAt(n++, mm); }
  tufts.count = n; g.add(tufts);
  return { group: g, tick: (t) => ticks.forEach((f) => f(t)) };
}
function palm(x, z, s = 1) {
  const g = new THREE.Group();
  for (let i = 0; i < 5; i++) g.add(at(m(new THREE.CylinderGeometry(0.45 - i * 0.04, 0.5 - i * 0.04, 1.6, 6), i % 2 ? 0x9c6b3f : 0x8a5a36), i * 0.25, 0.8 + i * 1.5, 0));
  for (let k = 0; k < 6; k++) {
    const leaf = m(new THREE.ConeGeometry(0.9, 4.2, 4), 0x7fa37a);
    leaf.position.set(1.25, 8, 0); leaf.rotation.set(0, (k / 6) * Math.PI * 2, 1.9); g.add(leaf);
  }
  return at(g, x, 0, z, s);
}
function rock(x, z, s = 1, color = 0x9aa0a6) { const r = m(new THREE.DodecahedronGeometry(1.4, 0), color); r.rotation.set(Math.random(), Math.random(), 0); return at(r, x, 0.6 * s, z, s); }
function crate(x, z, s = 1) { return at(m(new THREE.BoxGeometry(2.4, 2.4, 2.4), 0xb07a45), x, 1.2 * s, z, s); }

function label(text, { size = 64, color = "#fff", bg = "rgba(0,0,0,0)" } = {}) {
  const c = document.createElement("canvas"); const ctx = c.getContext("2d");
  ctx.font = `800 ${size}px Sora, Arial, sans-serif`; c.width = Math.ceil(ctx.measureText(text).width + size); c.height = Math.ceil(size * 1.5);
  ctx.fillStyle = bg; ctx.fillRect(0, 0, c.width, c.height);
  ctx.font = `800 ${size}px Sora, Arial, sans-serif`; ctx.fillStyle = color; ctx.textBaseline = "middle"; ctx.textAlign = "center";
  ctx.fillText(text, c.width / 2, c.height / 2);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(c.width / c.height * 3, 3), new THREE.MeshBasicMaterial({ map: t, transparent: true }));
  return mesh;
}

// ---------------------------------------------------------------------------
// Themed zones: ground patch + scenery. Each returns {group, tick(t)}.
// ---------------------------------------------------------------------------
// A calm, muted palette — soft enough that the level flags stand out.
const P = {
  grass: 0xa8bf96, sky: 0xdbe6ea, trunk: 0x8a6a50, leaf: 0x7fa37a, leaf2: 0x93b48c, stone: 0xa9aca8,
  basics: 0xc9d6a8, arcade: 0x55506a, desert: 0xdcc7a0, dune: 0xd2b98e, sand: 0xe3d6b4, sea: 0x86b4c4,
  rail: 0xbcb1a0, forest: 0x93ad84, city: 0xbfc2c6, library: 0xd8cbb4, desk: 0xc9b79c, factory: 0xb0b0aa,
  lab: 0xa9cfc4, workshop: 0xc4a984, space: 0xbfc2c8,
};
function zone(theme, center, radius, seed, clear = () => true, landmark = false) {
  const g = new THREE.Group(); g.position.copy(center);
  const ticks = [];
  let rnd = seed * 9301 + 49297;
  const R = () => ((rnd = (rnd * 9301 + 49297) % 233280) / 233280);
  const spot = (min = 0.45, max = 0.95, room = 7) => {
    let best = null;
    for (let k = 0; k < 24; k++) {               // re-roll until it's off the road
      const a = R() * Math.PI * 2, d = radius * (min + R() * (max - min));
      best = [Math.cos(a) * d, Math.sin(a) * d];
      if (clear(center.x + best[0], center.z + best[1], room)) break;
    }
    return best;
  };
  const put = (o, min, max, room) => { const [x, z] = spot(min, max, room); o.position.x = x; o.position.z = z; g.add(o); return o; };
  const ground = (color, r = radius) => { const p = m(new THREE.CircleGeometry(r, 36), color); p.rotation.x = -Math.PI / 2; p.position.y = 0.05; p.castShadow = false; g.add(p); return p; };
  const box = (w, h, d, c, x = 0, y = h / 2, z = 0, extra) => at(m(new THREE.BoxGeometry(w, h, d), c, extra), x, y, z);

  if (theme === "basics") {
    // a quiet garden workshop: a shed, a fence, a giant LED sculpture that slowly breathes
    ground(P.basics);
    const shed = new THREE.Group();
    shed.add(box(8, 5, 6, 0xd8cfc0)); const roof = m(new THREE.ConeGeometry(6.2, 3, 4), 0x8e6f5a); roof.position.y = 6.5; roof.rotation.y = Math.PI / 4; shed.add(roof);
    shed.add(box(1.8, 3, 0.2, 0x8a6a50, 0, 1.5, 3.05));
    put(shed, 0.55, 0.75, 9);
    const led = new THREE.Group();
    const lens = m(new THREE.CylinderGeometry(1.6, 1.6, 3, 16), 0xd98a7a, { emissive: 0xd98a7a, emissiveIntensity: 0.2 }); lens.position.y = 4.5; led.add(lens);
    const dome = m(new THREE.SphereGeometry(1.6, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), 0xd98a7a, { emissive: 0xd98a7a, emissiveIntensity: 0.2 }); dome.position.y = 6; led.add(dome);
    led.add(box(0.25, 3, 0.25, 0xb9b9b9, -0.6, 1.5)); led.add(box(0.25, 3.6, 0.25, 0xb9b9b9, 0.6, 1.8));
    put(led, 0.4, 0.6, 8);
    ticks.push((t) => { const k = 0.2 + (Math.sin(t * 1.2) + 1) * 0.35; lens.material.emissiveIntensity = k; dome.material.emissiveIntensity = k; });
    for (let i = 0; i < 8; i++) { const f = m(new THREE.IcosahedronGeometry(0.5, 0), [0xd9a7a0, 0xe0cf8a, 0xb7a6cf][i % 3]); put(at(f, 0, 0.5, 0), 0.3, 0.9, 5); }
  } else if (theme === "arcade") {
    const c = document.createElement("canvas"); c.width = c.height = 256; const ctx = c.getContext("2d");
    ctx.fillStyle = "#55506a"; ctx.fillRect(0, 0, 256, 256); ctx.strokeStyle = "#8c83a8"; ctx.lineWidth = 2;
    for (let i = 0; i <= 256; i += 32) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 256); ctx.moveTo(0, i); ctx.lineTo(256, i); ctx.stroke(); }
    const tex = new THREE.CanvasTexture(c); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.repeat.set(radius / 6, radius / 6); tex.colorSpace = THREE.SRGBColorSpace;
    ground(new THREE.MeshStandardMaterial({ map: tex, roughness: 0.8 }));
    const tones = [0xc98fb5, 0x8fb7c9, 0xd6c98a, 0x9cc79a];
    for (let i = 0; i < 6; i++) {
      const cab = new THREE.Group(), col = tones[i % 4];
      cab.add(box(2.4, 5, 2.2, 0x3e3a4c));
      const scr = m(new THREE.PlaneGeometry(1.8, 1.4), col, { emissive: col, emissiveIntensity: 0.5 }); scr.position.set(0, 3.6, 1.12); cab.add(scr);
      cab.add(at(m(new THREE.SphereGeometry(0.28, 8, 6), 0xc46a6a), 0.4, 2.6, 1.3));
      put(cab, 0.5, 0.9); cab.lookAt(0, 0, 0);
      ticks.push((t) => { scr.material.emissiveIntensity = 0.35 + Math.sin(t * 3 + i) * 0.15; });
    }
    const arch = m(new THREE.TorusGeometry(7, 0.45, 8, 32, Math.PI), 0xb88aa8, { emissive: 0xb88aa8, emissiveIntensity: 0.35 }); put(arch, 0.35, 0.45, 9);
  } else if (theme === "desert") {
    ground(P.desert);
    for (let i = 0; i < 6; i++) { const d = m(new THREE.SphereGeometry(4 + R() * 3, 8, 6), P.dune); d.scale.y = 0.3; put(d, 0.55, 1.05, 8); }
    for (let i = 0; i < 7; i++) {
      const c = new THREE.Group();
      c.add(at(m(new THREE.CylinderGeometry(0.6, 0.7, 5, 7), 0x7f9f78), 0, 2.5, 0));
      c.add(at(m(new THREE.CylinderGeometry(0.4, 0.4, 2, 7), 0x7f9f78), 1.1, 3, 0));
      c.add(at(m(new THREE.CylinderGeometry(0.4, 0.4, 1.6, 7), 0x7f9f78), -1, 2.2, 0));
      c.scale.setScalar(0.7 + R() * 0.5); put(c, 0.4, 0.9, 5);
    }
    const tower = new THREE.Group();
    for (let k = 0; k < 3; k++) { const leg = m(new THREE.CylinderGeometry(0.15, 0.3, 20, 5), 0xc7c9cc); const a = (k / 3) * Math.PI * 2; leg.position.set(Math.cos(a) * 1.2, 10, Math.sin(a) * 1.2); tower.add(leg); }
    const bulb = m(new THREE.SphereGeometry(0.5, 8, 6), 0xc46a6a, { emissive: 0xc46a6a, emissiveIntensity: 1 }); bulb.position.y = 20.4; tower.add(bulb);
    ticks.push((t) => { bulb.material.emissiveIntensity = Math.sin(t * 3) > 0 ? 1.2 : 0.1; });
    put(tower, 0.6, 0.72, 8);
    const tw = m(new THREE.IcosahedronGeometry(0.9, 0), 0xb09a78); g.add(tw);
    ticks.push((t) => { const k = (t * 0.1) % 1; tw.position.set(-radius + k * radius * 2, 0.9 + Math.abs(Math.sin(t * 4)) * 0.6, radius * 0.5); tw.rotation.z = -t * 3; });
  } else if (theme === "ocean") {
    ground(P.sand, radius * 0.95);
    const sea = new THREE.Mesh(new THREE.RingGeometry(radius * 0.9, radius * 1.6, 48, 6), new THREE.MeshStandardMaterial({ color: P.sea, flatShading: true, roughness: 0.35, transparent: true, opacity: 0.95 }));
    sea.rotation.x = -Math.PI / 2; sea.position.y = 0.02; sea.receiveShadow = true; g.add(sea);   // flat, always under the road
    const seaCol = new THREE.Color(P.sea), seaHi = new THREE.Color(0x9cc6d3);
    ticks.push((t) => { sea.material.color.copy(seaCol).lerp(seaHi, (Math.sin(t * 0.9) + 1) * 0.25); });
    const lh = new THREE.Group();
    for (let i = 0; i < 5; i++) lh.add(at(m(new THREE.CylinderGeometry(1.9 - i * 0.18, 2.1 - i * 0.18, 2.4, 10), i % 2 ? 0xeeeeea : 0xb8665e), 0, 1.2 + i * 2.4, 0));
    lh.add(at(m(new THREE.CylinderGeometry(1.4, 1.4, 1.8, 10), 0xf1e6bf, { emissive: 0xe8d28a, emissiveIntensity: 0.6 }), 0, 13.2, 0));
    lh.add(at(m(new THREE.ConeGeometry(1.8, 1.8, 10), 0x4a5058), 0, 15, 0));
    const beam = new THREE.Mesh(new THREE.ConeGeometry(4, 26, 16, 1, true), new THREE.MeshBasicMaterial({ color: 0xfff4c8, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false }));
    beam.rotation.z = Math.PI / 2; beam.position.set(13, 0, 0);
    const pivot = new THREE.Group(); pivot.position.y = 13.2; pivot.add(beam); lh.add(pivot);
    ticks.push((t) => { pivot.rotation.y = t * 0.7; });
    put(lh, 0.62, 0.75, 8);
    const boat = new THREE.Group();
    boat.add(box(5, 1.2, 2.2, 0x8a6a58, 0, 0.6)); const sail = m(new THREE.ConeGeometry(1.8, 4.5, 3), 0xeeeeea); sail.position.set(0, 3.4, 0); sail.rotation.y = Math.PI / 2; boat.add(sail);
    boat.position.set(radius * 1.25, 0.2, radius * 0.2); g.add(boat);
    ticks.push((t) => { boat.position.y = 0.2 + Math.sin(t * 1.6) * 0.25; boat.rotation.z = Math.sin(t * 1.2) * 0.06; });
    for (let i = 0; i < 6; i++) put(palm(0, 0, 0.8 + R() * 0.4), 0.5, 0.85);
  } else if (theme === "rail") {
    // a train loops a track: loops and switches
    ground(P.rail);
    const r = radius * 0.62, cx = -radius * 0.05;
    const track = m(new THREE.TorusGeometry(r, 0.35, 4, 64), 0x6d6259); track.rotation.x = -Math.PI / 2; track.position.set(cx, 0.3, 0); g.add(track);
    const track2 = m(new THREE.TorusGeometry(r - 1.6, 0.35, 4, 64), 0x6d6259); track2.rotation.x = -Math.PI / 2; track2.position.set(cx, 0.3, 0); g.add(track2);
    for (let i = 0; i < 48; i++) { const a = (i / 48) * Math.PI * 2; const s = box(3, 0.3, 0.6, 0x8a6a50, cx + Math.cos(a) * (r - 0.8), 0.15, Math.sin(a) * (r - 0.8)); s.rotation.y = -a; g.add(s); }
    const train = new THREE.Group();
    const cars = [0x7f95a8, 0xb8665e, 0xd6c28a];
    cars.forEach((c, k) => { const w = new THREE.Group(); w.add(box(2.4, 2, 4, c, 0, 1.4)); if (!k) w.add(at(m(new THREE.CylinderGeometry(0.4, 0.5, 1.4, 8), 0x4a5058), 0, 3, 1)); w.userData.k = k; train.add(w); });
    g.add(train);
    ticks.push((t) => train.children.forEach((w) => { const a = t * 0.25 - w.userData.k * 0.16; w.position.set(cx + Math.cos(a) * (r - 0.8), 0, Math.sin(a) * (r - 0.8)); w.rotation.y = -a; }));
    const sig = new THREE.Group(); sig.add(box(0.3, 5, 0.3, 0x4a5058)); const lamp = m(new THREE.SphereGeometry(0.45, 8, 6), 0x7fbf8e, { emissive: 0x7fbf8e, emissiveIntensity: 0.8 }); lamp.position.y = 5; sig.add(lamp);
    put(sig, 0.8, 0.9, 5);
    ticks.push((t) => { const on = Math.sin(t * 0.8) > 0; lamp.material.color.setHex(on ? 0x7fbf8e : 0xc46a6a); lamp.material.emissive.setHex(on ? 0x7fbf8e : 0xc46a6a); });
  } else if (theme === "forest") {
    ground(P.forest);
    for (let i = 0; i < 14; i++) {
      const pine = new THREE.Group(); pine.add(at(m(new THREE.CylinderGeometry(0.4, 0.5, 2, 6), P.trunk), 0, 1, 0));
      for (let k = 0; k < 3; k++) pine.add(at(m(new THREE.ConeGeometry(2.4 - k * 0.6, 3, 7), k % 2 ? 0x6f8f6a : 0x5f7f5c), 0, 3 + k * 1.6, 0));
      pine.scale.setScalar(0.8 + R() * 0.6); put(pine, 0.4, 1.0, 5);
    }
    // a little weather station: spinning cups, a sensor box
    const ws = new THREE.Group(); ws.add(box(0.3, 7, 0.3, 0xc7c9cc, 0, 3.5)); ws.add(box(1.6, 1.2, 1, 0xeeeeea, 0, 4));
    const cups = new THREE.Group(); cups.position.y = 7.2;
    for (let k = 0; k < 3; k++) { const a = (k / 3) * Math.PI * 2; cups.add(box(1.4, 0.12, 0.12, 0xc7c9cc, Math.cos(a) * 0.7, 0, Math.sin(a) * 0.7)).children.at(-1).rotation.y = -a; cups.add(at(m(new THREE.SphereGeometry(0.3, 6, 4), 0xc7c9cc), Math.cos(a) * 1.4, 0, Math.sin(a) * 1.4)); }
    ws.add(cups); put(ws, 0.35, 0.5, 8);
    ticks.push((t) => { cups.rotation.y = t * 2.5; });
  } else if (theme === "city") {
    ground(P.city);
    for (let i = 0; i < 9; i++) {
      const h = 6 + R() * 12, b = new THREE.Group();
      b.add(box(5, h, 5, [0xcfd2d6, 0xb9bdc3, 0xd9d3c7][i % 3]));
      // an LED-matrix billboard on some buildings
      if (i % 3 === 0) {
        const c = document.createElement("canvas"); c.width = c.height = 64; const ctx = c.getContext("2d");
        const tex = new THREE.CanvasTexture(c); tex.magFilter = THREE.NearestFilter; tex.colorSpace = THREE.SRGBColorSpace;
        const bb = m(new THREE.PlaneGeometry(4, 4), new THREE.MeshBasicMaterial({ map: tex })); bb.position.set(0, h - 2.5, 2.52); b.add(bb);
        let last = -1;
        ticks.push((t) => {
          const f = Math.floor(t * 3); if (f === last) return; last = f;
          ctx.fillStyle = "#2b2e33"; ctx.fillRect(0, 0, 64, 64);
          for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { const on = (x + y + f) % 4 === 0 || y === (f % 8); ctx.fillStyle = on ? "#e0b86a" : "#3d4148"; ctx.beginPath(); ctx.arc(4 + x * 8, 4 + y * 8, 3, 0, 7); ctx.fill(); }
          tex.needsUpdate = true;
        });
      }
      put(b, 0.45, 0.95, 7); b.lookAt(0, b.position.y, 0);
    }
  } else if (theme === "library") {
    ground(P.library);
    const books = [0xa8756a, 0x7f95a8, 0x9cae8a, 0xc9b27a, 0x8f7fa3];
    for (let i = 0; i < 8; i++) {
      const st = new THREE.Group(); let y = 0;
      for (let k = 0; k < 3 + Math.floor(R() * 4); k++) { const hgt = 0.8 + R() * 0.5; const bk = box(3.2 + R(), hgt, 2.4, books[(i + k) % 5], 0, y + hgt / 2); bk.rotation.y = (R() - 0.5) * 0.4; st.add(bk); y += hgt; }
      put(st, 0.4, 0.9, 5);
    }
    // letters floating over an open book
    const open = new THREE.Group(); open.add(box(3, 0.4, 4, 0xeeeae0, -1.6, 0.4)); open.add(box(3, 0.4, 4, 0xeeeae0, 1.6, 0.4)); open.children.forEach((p, k) => (p.rotation.z = k ? -0.12 : 0.12));
    const letters = ["A", "b", "c", "?", "42"].map((ch, k) => { const l = label(ch, { size: 48, color: "#5b5f6a" }); l.userData.k = k; open.add(l); return l; });
    put(open, 0.35, 0.5, 8);
    ticks.push((t) => letters.forEach((l) => { const k = l.userData.k; l.position.set(Math.sin(t * 0.6 + k * 1.3) * 2.5, 3 + ((t * 0.5 + k * 0.4) % 2.5), Math.cos(t * 0.6 + k) * 1.2); l.rotation.y = Math.sin(t + k) * 0.4; }));
  } else if (theme === "desk") {
    ground(P.desk);
    // a giant keyboard and a mouse lying in the cove
    const kb = new THREE.Group(); kb.add(box(16, 1, 6, 0x5b5f6a, 0, 0.5));
    const keys = [];
    for (let r = 0; r < 4; r++) for (let c = 0; c < 12; c++) { const k = box(1, 0.5, 1, 0xe7e5df, -6.6 + c * 1.2, 1.25, -1.8 + r * 1.2); kb.add(k); keys.push(k); }
    put(kb, 0.4, 0.6, 12);
    ticks.push((t) => { keys.forEach((k, i) => { k.position.y = ((Math.floor(t * 4) * 7) % keys.length) === i ? 1.05 : 1.25; }); });
    const mouse = new THREE.Group(); const body = m(new THREE.SphereGeometry(2, 12, 8), 0xe7e5df); body.scale.set(1, 0.55, 1.5); body.position.y = 1; mouse.add(body);
    const cable = m(new THREE.TorusGeometry(4, 0.15, 4, 24, Math.PI), 0x5b5f6a); cable.rotation.x = -Math.PI / 2; cable.position.set(0, 0.2, -4); mouse.add(cable);
    put(mouse, 0.55, 0.8, 8);
  } else if (theme === "factory") {
    ground(P.factory);
    const hall = new THREE.Group(); hall.add(box(12, 6, 8, 0xc9c6bd));
    for (let k = 0; k < 3; k++) { const roof = box(4, 1.5, 8, 0x8f8a80, -4 + k * 4, 6.75); roof.rotation.z = 0.3; hall.add(roof); }
    const chim = at(m(new THREE.CylinderGeometry(0.9, 1.1, 10, 10), 0xa8665e), 5, 5, -2.5); hall.add(chim);
    put(hall, 0.6, 0.75, 12);
    const puffs = [0, 1, 2, 3].map((k) => { const p = m(new THREE.IcosahedronGeometry(1, 0), 0xe6e6e2, { transparent: true, opacity: 0.8 }); hall.add(p); return p; });
    ticks.push((t) => puffs.forEach((p, k) => { const s = (t * 0.4 + k * 0.25) % 1; p.position.set(5 + s * 2, 10.5 + s * 6, -2.5); p.scale.setScalar(0.6 + s * 1.2); p.material.opacity = 0.8 * (1 - s); }));
    // a conveyor carrying chips (DIP ICs)
    const conv = new THREE.Group(); conv.add(box(14, 1, 2.4, 0x5b5f6a, 0, 0.8));
    const chips = [0, 1, 2, 3, 4].map((k) => { const c = new THREE.Group(); c.add(box(1.6, 0.4, 0.9, 0x2e3035, 0, 0)); for (let j = 0; j < 4; j++) for (const s of [-1, 1]) c.add(box(0.1, 0.25, 0.25, 0xc7c9cc, -0.6 + j * 0.4, -0.1, s * 0.55)); conv.add(c); return c; });
    put(conv, 0.35, 0.5, 9);
    ticks.push((t) => chips.forEach((c, k) => { const s = ((t * 0.12 + k / 5) % 1); c.position.set(-6.5 + s * 13, 1.5, 0); }));
  } else if (theme === "lab") {
    ground(P.lab);
    const dome = m(new THREE.SphereGeometry(6, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2), 0xe3f2ee, { transparent: true, opacity: 0.6, roughness: 0.1 });
    put(dome, 0.6, 0.7, 9);
    for (let i = 0; i < 5; i++) {
      const prof = [new THREE.Vector2(0, 0), new THREE.Vector2(1.4, 0), new THREE.Vector2(1.4, 0.3), new THREE.Vector2(0.5, 2.4), new THREE.Vector2(0.5, 3.4), new THREE.Vector2(0, 3.4)];
      const col = [0x9f8fc4, 0x8fbf9c, 0xc49aaf, 0x8fb4c9, 0xd6c28a][i];
      const flask = m(new THREE.LatheGeometry(prof, 10), col, { transparent: true, opacity: 0.85 });
      const [x, z] = spot(0.45, 0.9); g.add(at(flask, x, 0, z));
      const bubble = m(new THREE.SphereGeometry(0.3, 6, 4), 0xffffff, { transparent: true, opacity: 0.7 }); g.add(bubble);
      ticks.push((t) => { const k = (t * 0.5 + i * 0.3) % 1; bubble.position.set(x, 3.6 + k * 5, z); bubble.material.opacity = 0.7 * (1 - k); });
    }
  } else {
    ground(P[theme] || P.workshop);
    for (let i = 0; i < 6; i++) put(crate(0, 0, 0.6 + R() * 0.6), 0.4, 0.9, 5);
  }
  // themed critters in every patch of a world
  const crit = (o, room = 6) => { const [x, z] = spot(0.3, 0.9, room); o.position.set(x, 0, z); g.add(o); return [x, z]; };
  if (theme === "basics") for (let k = 0; k < 2; k++) { const b = bunny(k ? 0xc9a07a : 0xf2f0ea); b.scale.setScalar(1.3); const [x, z] = crit(b); ticks.push(wander(b, x, z, 3, 0.3, k * 2, 1.4)); }
  if (theme === "arcade") [0xf2a0b8, 0x9fd8f2, 0xf6d88a].forEach((c, k) => { const gh = ghost(c); const [x, z] = crit(gh); ticks.push((t) => { gh.position.set(x + Math.sin(t * 0.6 + k) * 3, 1 + Math.sin(t * 2 + k) * 0.6, z + Math.cos(t * 0.5 + k) * 3); gh.rotation.y = t * 0.6 + k; }); });
  if (theme === "ocean") for (let k = 0; k < 2; k++) { const cr = crab(); cr.scale.setScalar(1.3); const [x, z] = crit(cr); ticks.push((t) => { cr.position.z = z + Math.sin(t * 0.8 + k * 2) * 4; cr.rotation.y = Math.sin(t * 6) * 0.08; }); }
  if (theme === "city") [0x7fa8d4, 0x9cc79a, 0xd9a0b8].forEach((c, k) => {
    const rb = robot(c); rb.scale.setScalar(1.2); const [x, z] = crit(rb, 8), walk = wander(rb, x, z, 5, 0.18, k * 2.1);
    ticks.push((t) => { walk(t); rb.userData.head.rotation.y = Math.sin(t * 1.2 + k) * 0.5; rb.userData.bulb.material.emissiveIntensity = Math.sin(t * 5 + k) > 0 ? 1.5 : 0.1; rb.userData.arms[0].rotation.z = Math.sin(t * 3 + k) > 0.3 ? -2.4 + Math.sin(t * 12) * 0.4 : 0; });
  });
  if (theme === "factory") for (let k = 0; k < 2; k++) {
    const rb = robot(0xe0b85a); rb.scale.setScalar(1.2); rb.userData.arms.forEach((a) => (a.rotation.z = -1.3));
    rb.add(at(m(new THREE.BoxGeometry(1.8, 1.4, 2.2), 0xb07a45), 2.2, 3.1, 0));
    const [x, z] = crit(rb, 8); ticks.push(wander(rb, x, z, 6, 0.15, k * 3));
  }
  if (theme === "lab") { const rb = robot(0x9fd8c4); rb.scale.setScalar(1.3); crit(rb, 8); ticks.push((t) => { rb.userData.arms[1].rotation.z = -2.6 + Math.sin(t * 6) * 0.5; rb.userData.bulb.material.emissiveIntensity = Math.sin(t * 4) > 0 ? 1.5 : 0.1; }); }
  if (landmark && theme === "desert") { const cm = camel(); cm.scale.setScalar(1.2); const [x, z] = crit(cm, 10); const walk = wander(cm, x, z, 6, 0.06, 0); ticks.push((t) => { walk(t); cm.userData.head.rotation.z = Math.sin(t * 1.5) * 0.15; }); }
  if (landmark && theme === "rail") { const ct = cat(); ct.scale.setScalar(1.2); crit(ct, 6); ticks.push((t) => { ct.userData.tail.rotation.x = Math.sin(t * 2.5) * 0.7; }); }
  if (landmark && (theme === "forest" || theme === "library")) {
    const ow = owl(theme === "library"); ow.scale.setScalar(1.3); crit(ow, 6);
    ticks.push((t) => { const blink = (t % 4) < 0.15 ? 1 : 0.05; ow.userData.lids.forEach((l) => (l.scale.y = blink)); ow.rotation.y = Math.sin(t * 0.4) * 0.6; });
  }
  if (theme === "forest") { const dr = deer(); dr.scale.setScalar(1.2); const [x, z] = crit(dr, 8); const walk = wander(dr, x, z, 3, 0.04, 1); ticks.push((t) => { walk(t); const graze = (Math.sin(t * 0.6) + 1) / 2; dr.userData.head.position.y = 4.1 - graze * 1.8; }); }
  if (landmark && theme === "desk") { const ms = mouseCritter(); ms.scale.setScalar(1.6); const [x, z] = crit(ms, 5); ticks.push((t) => { ms.position.x = x + Math.sin(t * 0.9) * 2; ms.rotation.y = Math.cos(t * 0.9) > 0 ? 0 : Math.PI; }); }

  // one landmark per world, in its first patch
  if (landmark) {
    const L = new THREE.Group();
    if (theme === "basics") {                                   // a windmill
      L.add(at(m(new THREE.CylinderGeometry(2.2, 3.4, 12, 8), 0xe3d6c2), 0, 6, 0));
      L.add(at(m(new THREE.ConeGeometry(3, 3.5, 8), 0x8e6f5a), 0, 13.7, 0));
      const hub = new THREE.Group(); hub.position.set(0, 12, 2.6); L.add(hub);
      for (let k = 0; k < 4; k++) { const blade = m(new THREE.BoxGeometry(1.4, 9, 0.2), 0xf2f0ea); blade.position.y = 4.8; const arm = new THREE.Group(); arm.rotation.z = k * Math.PI / 2; arm.add(blade); hub.add(arm); }
      ticks.push((t) => { hub.rotation.z = t * 0.8; });
    } else if (theme === "arcade") {                            // a giant joystick
      L.add(at(m(new THREE.BoxGeometry(8, 3, 8), 0x3e3a4c), 0, 1.5, 0));
      const stick = new THREE.Group(); stick.position.y = 3; L.add(stick);
      stick.add(at(m(new THREE.CylinderGeometry(0.6, 0.6, 7, 10), 0x2a2a30), 0, 3.5, 0));
      stick.add(at(m(new THREE.SphereGeometry(2, 16, 12), 0xc46a6a), 0, 7.6, 0));
      ticks.push((t) => { stick.rotation.z = Math.sin(t * 1.1) * 0.3; stick.rotation.x = Math.cos(t * 0.8) * 0.25; });
    } else if (theme === "desert") {                            // an oasis
      const pond = new THREE.Mesh(new THREE.CircleGeometry(5, 20), WATER()); pond.rotation.x = -Math.PI / 2; pond.position.y = 0.1; L.add(pond);
      L.add(palm(4, 3, 0.9)); L.add(palm(-4, -2, 1.1)); L.add(palm(1, -5, 0.8));
    } else if (theme === "ocean") {                             // seagulls circling the lighthouse
      for (let k = 0; k < 4; k++) {
        const gull = new THREE.Group();
        for (const s2 of [-1, 1]) { const w = m(new THREE.BoxGeometry(2.4, 0.12, 0.8), 0xf2f0ea); w.position.x = s2 * 1.1; w.rotation.z = s2 * 0.35; gull.add(w); }
        L.add(gull);
        ticks.push((t) => { const a = t * 0.35 + k * 1.6; gull.position.set(Math.cos(a) * (10 + k * 2), 18 + Math.sin(t * 2 + k) * 1.5, Math.sin(a) * (10 + k * 2)); gull.rotation.y = -a; gull.children.forEach((w, j) => (w.rotation.z = (j ? 1 : -1) * (0.35 + Math.sin(t * 6 + k) * 0.25))); });
      }
    } else if (theme === "rail") {                              // a little station
      L.add(at(m(new THREE.BoxGeometry(12, 1, 5), 0xa9aca8), 0, 0.5, 0));
      L.add(at(m(new THREE.BoxGeometry(7, 5, 4), 0xd9cdb8), 0, 3.5, -0.2));
      L.add(at(m(new THREE.BoxGeometry(13, 0.5, 6), 0x8e6f5a), 0, 6.2, 0));
      const clock2 = m(new THREE.CylinderGeometry(0.8, 0.8, 0.2, 16), 0xf2f0ea); clock2.rotation.x = Math.PI / 2; clock2.position.set(0, 4.6, 1.85); L.add(clock2);
    } else if (theme === "forest") {                            // a campfire
      for (let k = 0; k < 5; k++) { const lg = m(new THREE.CylinderGeometry(0.35, 0.35, 3.4, 6), 0x7a5a40); lg.rotation.z = Math.PI / 2 - 0.35; lg.rotation.y = k * 1.25; lg.position.y = 0.7; L.add(lg); }
      const flame = m(new THREE.ConeGeometry(1.1, 3, 7), 0xe8a050, { emissive: 0xe8903a, emissiveIntensity: 1.2 }); flame.position.y = 2; L.add(flame);
      const fire = new THREE.PointLight(0xffa050, 10, 20, 2); fire.position.y = 3; L.add(fire);
      ticks.push((t) => { const f = 0.85 + Math.sin(t * 13) * 0.08 + Math.sin(t * 7.3) * 0.07; flame.scale.set(f, f * 1.1, f); fire.intensity = 8 + f * 5; });
    } else if (theme === "city") {                              // traffic lights
      for (const sx of [-5, 5]) {
        const tl = new THREE.Group(); tl.add(at(m(new THREE.CylinderGeometry(0.25, 0.25, 7, 6), 0x4a5058), 0, 3.5, 0)); tl.add(at(m(new THREE.BoxGeometry(1.4, 3.6, 1.2), 0x2e3035), 0, 8, 0));
        const lamps = [0xc46a6a, 0xd6c28a, 0x7fbf8e].map((c, k) => { const l = m(new THREE.SphereGeometry(0.4, 10, 8), c, { emissive: c, emissiveIntensity: 0 }); l.position.set(0, 9 - k * 1.1, 0.62); tl.add(l); return l; });
        tl.position.x = sx; L.add(tl);
        ticks.push((t) => { const on = Math.floor((t + (sx > 0 ? 3 : 0)) / 2) % 3; lamps.forEach((l, k) => (l.material.emissiveIntensity = k === on ? 1.4 : 0.05)); });
      }
    } else if (theme === "library") {                           // a giant pencil
      const pen = new THREE.Group();
      pen.add(at(m(new THREE.CylinderGeometry(1.2, 1.2, 14, 6), 0xe0c86a), 0, 0, 0));
      pen.add(at(m(new THREE.ConeGeometry(1.2, 3, 6), 0xe8d8b8), 0, -8.5, 0)); pen.add(at(m(new THREE.ConeGeometry(0.4, 1, 6), 0x3a3a3a), 0, -9.8, 0));
      pen.add(at(m(new THREE.CylinderGeometry(1.25, 1.25, 1.2, 6), 0xc7c9cc), 0, 7.6, 0)); pen.add(at(m(new THREE.CylinderGeometry(1.2, 1.2, 1.4, 6), 0xd98a8a), 0, 8.9, 0));
      pen.rotation.z = 1.25; pen.position.y = 3.5; L.add(pen);
    } else if (theme === "desk") {                              // a steaming mug
      L.add(at(m(new THREE.CylinderGeometry(3, 2.8, 6, 20), 0xd98a7a), 0, 3, 0));
      const handle = m(new THREE.TorusGeometry(1.6, 0.45, 8, 16, Math.PI), 0xd98a7a); handle.rotation.z = -Math.PI / 2; handle.position.set(3, 3, 0); L.add(handle);
      L.add(at(m(new THREE.CylinderGeometry(2.7, 2.7, 0.2, 20), 0x6b4a36), 0, 5.8, 0));
      const puffs = [0, 1, 2].map((k) => { const pf = m(new THREE.SphereGeometry(0.8, 8, 6), 0xf2f2ee, { transparent: true, opacity: 0.6 }); L.add(pf); return pf; });
      ticks.push((t) => puffs.forEach((pf, k) => { const q = (t * 0.35 + k / 3) % 1; pf.position.set(Math.sin(t + k) * 0.6, 6.5 + q * 6, 0); pf.scale.setScalar(0.6 + q); pf.material.opacity = 0.55 * (1 - q); }));
    } else if (theme === "factory") {                           // a robot arm
      L.add(at(m(new THREE.CylinderGeometry(2.4, 2.8, 1.6, 12), 0xd6a84a), 0, 0.8, 0));
      const base = new THREE.Group(); base.position.y = 1.6; L.add(base);
      const lower = new THREE.Group(); base.add(lower); lower.add(at(m(new THREE.BoxGeometry(1.4, 7, 1.4), 0xe0b85a), 0, 3.5, 0));
      const upper = new THREE.Group(); upper.position.y = 7; lower.add(upper); upper.add(at(m(new THREE.BoxGeometry(1.2, 6, 1.2), 0xe0b85a), 0, 3, 0)); upper.add(at(m(new THREE.BoxGeometry(2, 0.8, 1.6), 0x4a5058), 0, 6.2, 0));
      ticks.push((t) => { base.rotation.y = Math.sin(t * 0.5) * 1.2; lower.rotation.z = 0.35 + Math.sin(t * 0.9) * 0.2; upper.rotation.z = -0.9 + Math.sin(t * 1.3) * 0.35; });
    } else if (theme === "lab") {                               // a tesla coil
      L.add(at(m(new THREE.CylinderGeometry(2.4, 3, 2, 16), 0x4a5058), 0, 1, 0));
      L.add(at(m(new THREE.CylinderGeometry(1, 1, 10, 16), 0xb87a4a, { metalness: 0.6, roughness: 0.35 }), 0, 7, 0));
      const top = m(new THREE.TorusGeometry(2.4, 0.9, 10, 24), 0xc7c9cc, { metalness: 0.9, roughness: 0.25 }); top.rotation.x = Math.PI / 2; top.position.y = 12.5; L.add(top);
      const spark = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xbfe0ff })); L.add(spark);
      ticks.push((t) => {
        const pts = []; if (Math.sin(t * 9) > 0.2) for (let k = 0; k < 3; k++) { let x = 0, y = 12.5, z = 0; const a = Math.random() * Math.PI * 2; for (let j = 0; j < 5; j++) { const nx = x + Math.cos(a) * 1.4 + (Math.random() - 0.5), ny = y + (Math.random() - 0.3) * 1.4, nz = z + Math.sin(a) * 1.4 + (Math.random() - 0.5); pts.push(new THREE.Vector3(x, y, z), new THREE.Vector3(nx, ny, nz)); x = nx; y = ny; z = nz; } }
        spark.geometry.setFromPoints(pts);
      });
    }
    if (L.children.length) { const [lx, lz] = spot(0.35, 0.55, 12); L.position.set(lx, 0, lz); g.add(L); }
  }
  // trees around the zone's edge
  if (!["arcade", "city", "factory", "desk"].includes(theme)) for (let i = 0; i < 5; i++) { const [x, z] = spot(1.05, 1.35, 5); g.add(theme === "ocean" ? palm(x, z) : tree(x, z, 0.8 + R() * 0.5)); }
  return { group: g, tick: (t) => ticks.forEach((f) => f(t)) };
}

// Sparky's car: a chunky little buggy with Sparky (an LED) in the seat
function car() {
  const g = new THREE.Group();
  g.add(at(m(new THREE.BoxGeometry(3.2, 1.2, 4.6), 0xc27b53), 0, 1.3, 0));
  g.add(at(m(new THREE.BoxGeometry(3.0, 0.6, 1.6), 0x333a44), 0, 2.1, -1.4));
  const wheels = [];
  for (const [x, z] of [[-1.7, 1.5], [1.7, 1.5], [-1.7, -1.5], [1.7, -1.5]]) {
    const w = m(new THREE.CylinderGeometry(0.75, 0.75, 0.6, 12), 0x222222); w.rotation.z = Math.PI / 2; w.position.set(x, 0.75, z); g.add(w); wheels.push(w);
  }
  const sparky = new THREE.Group();
  sparky.add(at(m(new THREE.CylinderGeometry(1, 1, 1.4, 14), 0xdf9563, { emissive: 0xdf9563, emissiveIntensity: 0.25 }), 0, 0.7, 0));
  sparky.add(at(m(new THREE.SphereGeometry(1, 14, 10, 0, Math.PI * 2, 0, Math.PI / 2), 0xe8ad84, { emissive: 0xdf9563, emissiveIntensity: 0.25 }), 0, 1.4, 0));
  sparky.add(at(m(new THREE.SphereGeometry(0.16, 6, 4), 0x2b1a0c), -0.35, 1.3, 0.92)); sparky.add(at(m(new THREE.SphereGeometry(0.16, 6, 4), 0x2b1a0c), 0.35, 1.3, 0.92));
  sparky.position.set(0, 1.9, 0.4); g.add(sparky);
  const glow = new THREE.PointLight(0xffa640, 6, 14, 2); glow.position.set(0, 4.5, 0.4); g.add(glow);
  g.userData = { wheels, sparky };
  return g;
}

// A checkpoint: a round pad on the road with a flag on a pole
function checkpoint(state) {
  const g = new THREE.Group();
  const pad = m(new THREE.CylinderGeometry(3.4, 3.8, 0.6, 20), 0xffffff); pad.position.y = 0.3; g.add(pad);
  const ring = m(new THREE.TorusGeometry(3.5, 0.28, 6, 24), FLAG[state] ?? FLAG.open); ring.rotation.x = Math.PI / 2; ring.position.y = 0.65; g.add(ring);
  const pole = m(new THREE.CylinderGeometry(0.16, 0.16, 7, 6), 0xdadada); pole.position.set(2.6, 3.5, -1.2); g.add(pole);
  const flag = m(new THREE.BoxGeometry(2.6, 1.6, 0.12, 6, 1, 1), FLAG[state] ?? FLAG.open); flag.position.set(3.9, 6.2, -1.2); g.add(flag);
  const fpos = flag.geometry.attributes.position, fbase = fpos.array.slice();
  g.userData = {
    pad, ring, flag,
    setState(s) { const c = FLAG[s] ?? FLAG.open; flag.material = mat(c); ring.material = mat(c, s === "ready" || s === "done" ? { emissive: c, emissiveIntensity: 0.6 } : {}); },
    tick(t, i) { for (let k = 0; k < fpos.count; k++) { const x = fbase[k * 3] + 1.3; fpos.array[k * 3 + 2] = fbase[k * 3 + 2] + Math.sin(t * 5 + x * 2 + i) * 0.12 * x; } fpos.needsUpdate = true; },
  };
  g.userData.setState(state);
  return g;
}

// ---------------------------------------------------------------------------
export function createWorldMap(host, { onOpen, onCreate, onSoon, lessonIcon = () => null }) {
  const load = (k) => { try { return JSON.parse(localStorage.getItem("cq." + k)); } catch { return null; } };
  const save = (k, v) => { try { localStorage.setItem("cq." + k, JSON.stringify(v)); } catch { /* ignore */ } };
  const M = { at: load("mapAt"), tiles: [], cur: 0, busy: false, matches: {} };
  host.classList.add("overworld");
  host.innerHTML = `<div class="ow-labels"></div>
    <div class="ow-hud"><button class="btn" data-hud="prev">◀ Back</button><button class="btn" data-hud="home">📍 Sparky</button><button class="btn btn-primary" data-hud="next">Next ▶</button></div>
    <div class="ow-hint">drag to look around · scroll to zoom · click a flag to drive there</div>`;
  const labels = host.querySelector(".ow-labels");

  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.className = "ow-canvas";
  host.prepend(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xdbe6ea); scene.fog = new THREE.Fog(0xdbe6ea, 130, 300);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a9a80, 1.3));
  const sun = new THREE.DirectionalLight(0xfff6ea, 1.8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -90, right: 90, top: 90, bottom: -90, near: 1, far: 300 });
  scene.add(sun, sun.target);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.5, 1000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.minDistance = 25; controls.maxDistance = 160; controls.maxPolarAngle = Math.PI * 0.42; controls.enablePan = false;
  let world = null, carObj = null, curve = null, zones = [], cps = [], tParam = [], carT = 0, followPrev = null, clock = new THREE.Clock(), ambient = null;

  function resize() {
    const w = host.clientWidth || 800, h = host.clientHeight || 500;
    renderer.setSize(w, h, false); renderer.domElement.style.width = "100%"; renderer.domElement.style.height = "100%";
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host);

  // ---- build the world from the worlds list -----------------------------
  function render(worlds, matches = {}) {
    M.matches = matches;
    if (world) scene.remove(world);
    world = new THREE.Group(); scene.add(world);
    const grass = new THREE.Mesh(new THREE.PlaneGeometry(1000, 6000), mat(0xa8bf96)); grass.rotation.x = -Math.PI / 2; grass.position.z = -2400; grass.receiveShadow = true; world.add(grass);

    // lay the road out: worlds one after another, winding away from the camera
    const tiles = [], pts = [], zoneDefs = [];
    let z = 0, side = 1;
    pts.push(new THREE.Vector3(-10, 0, 22));
    worlds.forEach((w, wi) => {
      const levels = w.id === "ai-lab" ? [...w.levels, { create: true }] : w.levels.length ? w.levels : [{ soon: true, title: "Coming soon" }];
      const first = tiles.length;
      levels.forEach((lv, i) => {
        const x = side * (8 + (i % 2) * 10) * (i % 2 ? -1 : 1);
        const p = new THREE.Vector3(x, 0, z);
        pts.push(new THREE.Vector3((pts.at(-1).x + x) / 2 + side * 12, 0, z + 14));       // a bend between checkpoints
        pts.push(p);
        tiles.push({ ...lv, world: w, pos: p, ctrl: pts.length - 1 });
        z -= 30;
      });
      // scenery in patches of ~3 checkpoints, so long worlds stay full, not one huge empty disc
      const mine = tiles.slice(first);
      for (let k = 0; k < mine.length; k += 3) {
        const chunk = mine.slice(k, k + 3), c = new THREE.Vector3();
        chunk.forEach((t) => c.add(t.pos)); c.divideScalar(chunk.length); c.x *= 0.4;
        zoneDefs.push({ theme: w.theme, center: c, radius: 30 + chunk.length * 6, world: w, sign: k === 0 ? mine[0] : null });
      }
      z -= 26; side = -side;
    });
    pts.push(new THREE.Vector3(0, 0, z + 10));
    curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.4);
    const N = pts.length - 1;
    tParam = tiles.map((t) => t.ctrl / N);

    const samples = curve.getPoints(N * 24), up = new THREE.Vector3(0, 1, 0);
    // scenery keeps clear of the road and the checkpoints
    const clear = (x, z, room) => samples.every((p) => (p.x - x) ** 2 + (p.z - z) ** 2 > room * room)
      && tiles.every((t) => (t.pos.x - x) ** 2 + (t.pos.z - z) ** 2 > (room + 5) ** 2);
    zones = zoneDefs.map((d, i) => { const zn = zone(d.theme, d.center, d.radius, i + 3, clear, !!d.sign); world.add(zn.group); return { ...d, ...zn }; });
    const land = countryside({ z0: 40, z1: z - 20, clear, zones: zoneDefs });
    world.add(land.group); ambient = land.tick;
    // the road: a flat ribbon with a dashed centre line
    const road = [], dash = [];
    samples.forEach((p, i) => {
      const tan = curve.getTangent(i / (samples.length - 1)), side = new THREE.Vector3().crossVectors(up, tan).normalize();
      road.push(p.clone().addScaledVector(side, 3.4).setY(0.12), p.clone().addScaledVector(side, -3.4).setY(0.12));
      dash.push(p.clone().setY(0.16));
    });
    const idx = []; for (let i = 0; i < samples.length - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    const rg = new THREE.BufferGeometry().setFromPoints(road); rg.setIndex(idx); rg.computeVertexNormals();
    const roadMesh = new THREE.Mesh(rg, new THREE.MeshStandardMaterial({ color: 0x5b5f6a, roughness: 0.95, side: THREE.DoubleSide })); roadMesh.receiveShadow = true; world.add(roadMesh);
    const kerbL = [], kerbR = [];
    for (let i = 0; i < road.length; i += 2) { kerbL.push(road[i].clone().setY(0.2)); kerbR.push(road[i + 1].clone().setY(0.2)); }
    for (const k of [kerbL, kerbR]) world.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(k), samples.length, 0.35, 4), mat(0xf4f4f4)));
    const dl = new THREE.Line(new THREE.BufferGeometry().setFromPoints(dash), new THREE.LineDashedMaterial({ color: 0xffe27a, dashSize: 1.6, gapSize: 1.6 }));
    dl.computeLineDistances(); world.add(dl);

    // checkpoints
    cps = tiles.map((t, i) => {
      const cp = checkpoint(stateOf(t)); cp.position.copy(t.pos); cp.userData.index = i;
      cp.traverse((o) => { o.userData.cp = i; });
      world.add(cp); return cp;
    });
    M.tiles = tiles;
    // DOM labels (crisp text, clickable) + world signs
    labels.innerHTML = tiles.map((t, i) => labelHtml(t, i)).join("") +
      zones.map((zn, i) => {
        if (!zn.sign) return "";
        const real = zn.world.levels.filter((l) => !l.soon), earned = real.reduce((s, l) => s + (l.stars || 0), 0);
        return `<div class="ow-sign" data-zone="${i}"><span class="wnum">WORLD ${zn.world.number} · ${esc((zn.world.group || "").toUpperCase())}</span><b>${esc(zn.world.name)}</b>${real.length ? `<span class="wstars">★ ${earned}/${real.length * 3}</span>` : ""}</div>`;
      }).join("");
    labels.querySelectorAll(".tile").forEach((el) => (el.onclick = () => clickTile(+el.dataset.i)));
    updateMatches(matches);

    // Sparky's car at the current checkpoint
    carObj = car(); world.add(carObj);
    const start = indexOf(M.at) ?? suggestedIndex() ?? 0;
    M.cur = start; carT = tParam[start] ?? 0; placeCar(carT);
    const c = carObj.position;
    controls.target.copy(c); camera.position.set(c.x + 18, 58, c.z + 62); followPrev = c.clone();
    resize();
  }

  const stateOf = (t) => t.soon ? "soon" : t.create ? "create" : t.completed ? "done" : "open";
  function labelHtml(t, i) {
    if (t.soon) return `<button class="tile soon" data-i="${i}" title="Coming soon"><b class="lv">${esc(t.level || "")}</b><span class="nm">${esc(t.title || "Coming soon")}</span><span class="soon-tag">soon</span></button>`;
    if (t.create) return `<button class="tile create" data-i="${i}"><b class="lv">＋</b><span class="nm">Invent a level</span></button>`;
    const stars = [1, 2, 3].map((k) => `<i class="st${k <= (t.stars || 0) ? " on" : ""}">★</i>`).join("");
    return `<button class="tile${t.completed ? " done" : ""}" data-i="${i}" data-id="${esc(t.id)}">
      ${!t.prereqs_done && !t.completed ? `<i class="bdg tip" title="Builds on an earlier level — you can still play it">!</i>` : ""}
      ${lessonIcon(t.id) ? `<img class="ico" src="${lessonIcon(t.id)}" alt="">` : ""}<b class="lv">${esc(t.level)}</b><span class="nm">${esc(t.title)}</span><span class="stars">${stars}</span></button>`;
  }

  function placeCar(t) {
    const p = curve.getPoint(Math.min(1, Math.max(0, t))), tan = curve.getTangent(Math.min(0.999, Math.max(0.001, t)));
    carObj.position.set(p.x, 0.15, p.z);
    carObj.lookAt(p.x + tan.x, 0.15, p.z + tan.z);
  }
  const indexOf = (id) => { const i = M.tiles.findIndex((t) => t.id && t.id === id); return i < 0 ? null : i; };
  function suggestedIndex() { const i = M.tiles.findIndex((t) => t.id && !t.completed && t.prereqs_done); return i < 0 ? null : i; }

  // ---- driving -------------------------------------------------------------
  async function walkTo(target) {
    if (target === M.cur || !curve) return;
    const t0 = carT, t1 = tParam[target], dist = Math.abs(t1 - t0);
    const dur = Math.min(4200, 900 + dist * 9000), s = performance.now();
    host.classList.add("driving");
    await new Promise((res) => {
      const step = (now) => {
        const k = Math.min(1, (now - s) / dur), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        carT = t0 + (t1 - t0) * e;
        placeCar(carT);
        if (t1 < t0) carObj.rotateY(Math.PI);          // reversing: face the way it's going
        carObj.userData.wheels.forEach((w) => (w.rotation.x += (t1 > t0 ? 1 : -1) * 0.5));
        carObj.userData.sparky.position.y = 1.9 + Math.abs(Math.sin(now / 90)) * 0.35;
        if (k < 1) requestAnimationFrame(step); else res();
      };
      requestAnimationFrame(step);
    });
    host.classList.remove("driving");
    carObj.userData.sparky.position.y = 1.9;
    M.cur = target;
  }
  async function clickTile(i) {
    if (M.busy) return;
    const t = M.tiles[i];
    if (!t) return;
    M.busy = true;
    try {
      await walkTo(i);
      if (t.soon) { onSoon && onSoon(t); return; }
      if (t.create) { onCreate && onCreate(); return; }
      M.at = t.id; save("mapAt", t.id);
      onOpen && onOpen(t.id, t);
    } finally { M.busy = false; }
  }
  host.querySelector(".ow-hud").onclick = async (e) => {
    const b = e.target.closest("[data-hud]"); if (!b || M.busy) return;
    const dir = b.dataset.hud;
    if (dir === "home") { followPrev = null; return; }
    let i = M.cur;
    do { i += dir === "next" ? 1 : -1; } while (M.tiles[i] && M.tiles[i].soon);
    if (!M.tiles[i]) return;
    M.busy = true;
    try { await walkTo(i); if (M.tiles[i].id) { M.at = M.tiles[i].id; save("mapAt", M.at); } } finally { M.busy = false; }
  };

  // clicking a flag / pad in 3D
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  let downAt = null;
  renderer.domElement.addEventListener("pointerdown", (e) => { downAt = { x: e.clientX, y: e.clientY }; });
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!downAt || Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 5) return;
    const hit = pickCp(e); if (hit !== null) clickTile(hit);
  });
  renderer.domElement.addEventListener("pointermove", (e) => {
    const hit = pickCp(e);
    renderer.domElement.style.cursor = hit !== null ? "pointer" : "grab";
    labels.querySelectorAll(".tile").forEach((el) => el.classList.toggle("hover", +el.dataset.i === hit));
  });
  function pickCp(e) {
    if (!cps.length) return null;
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const h = ray.intersectObjects(cps, true)[0];
    return h ? h.object.userData.cp : null;
  }

  // ---- what you own: flag colours + ribbons ----------------------------------
  function updateMatches(matches = {}) {
    M.matches = matches;
    labels.querySelectorAll(".tile[data-id]").forEach((el) => {
      const i = +el.dataset.i, t = M.tiles[i], m = matches[el.dataset.id];
      el.classList.remove("ready", "sub", "need");
      el.querySelector(".ribbon") && el.querySelector(".ribbon").remove();
      let state = t.completed ? "done" : "open";
      if (m) {
        const nobb = m.build && m.build.method === "no-breadboard";
        const [cls, text] = m.status === "ready" ? ["ready", nobb ? "READY · NO BREADBOARD" : "READY!"]
          : m.status === "substitute" ? ["sub", nobb ? "STAND-IN · NO BREADBOARD" : "STAND-IN"]
          : ["need", `NEEDS ${m.missing.length}`];
        if (!t.completed) { el.classList.add(cls); state = cls; }
        const r = document.createElement("span"); r.className = `ribbon ${cls}`; r.textContent = text;
        if (m.status === "missing") r.title = "Still needs: " + m.missing.join(", ");
        el.prepend(r);
      }
      cps[i] && cps[i].userData.setState(state);
    });
  }

  // ---- a win: fireworks over the flag, it turns gold, then drive on ----------
  function fireworks(pos) {
    const n = 140, geo = new THREE.BufferGeometry(), p = new Float32Array(n * 3), v = [], col = new Float32Array(n * 3);
    const palette = [new THREE.Color(0xffc53d), new THREE.Color(0xff5ca8), new THREE.Color(0x3ddc84), new THREE.Color(0x35b9e8)];
    for (let i = 0; i < n; i++) {
      p.set([pos.x, 9, pos.z], i * 3);
      const d = new THREE.Vector3(Math.random() - 0.5, Math.random() * 0.9 + 0.2, Math.random() - 0.5).normalize().multiplyScalar(8 + Math.random() * 10);
      v.push(d); palette[i % 4].toArray(col, i * 3);
    }
    geo.setAttribute("position", new THREE.BufferAttribute(p, 3)); geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const pts = new THREE.Points(geo, new THREE.PointsMaterial({ size: 0.9, vertexColors: true, transparent: true }));
    world.add(pts);
    const s = performance.now();
    const step = (now) => {
      const k = (now - s) / 1600, dt = 1 / 60;
      for (let i = 0; i < n; i++) { v[i].y -= 14 * dt; p[i * 3] += v[i].x * dt; p[i * 3 + 1] += v[i].y * dt; p[i * 3 + 2] += v[i].z * dt; }
      geo.attributes.position.needsUpdate = true; pts.material.opacity = Math.max(0, 1 - k);
      if (k < 1) requestAnimationFrame(step); else world.remove(pts);
    };
    requestAnimationFrame(step);
  }
  async function celebrate(id) {
    const i = indexOf(id);
    if (i === null) return;
    await sleep(400);
    followPrev = null;                        // camera swings back to the car
    const cp = cps[i], el = labels.querySelector(`.tile[data-i="${i}"]`);
    fireworks(cp.position); cp.userData.setState("done");
    const s = performance.now();
    const pop = (now) => { const k = Math.min(1, (now - s) / 700); cp.scale.setScalar(1 + Math.sin(k * Math.PI) * 0.35); if (k < 1) requestAnimationFrame(pop); };
    requestAnimationFrame(pop);
    if (el) {
      el.classList.add("won", "done");
      const stars = [...el.querySelectorAll(".st.on")];
      stars.forEach((st) => st.classList.remove("on"));
      for (const st of stars) { await sleep(300); st.classList.add("on", "pop"); }
    }
    await sleep(700);
    const next = M.tiles.findIndex((t, k) => k > i && t.id && !t.completed);
    const target = next >= 0 ? next : suggestedIndex();
    if (target !== null && target >= 0) {
      M.cur = i; carT = tParam[i]; placeCar(carT);
      await walkTo(target);
      M.at = M.tiles[target].id; save("mapAt", M.at);
      const tEl = labels.querySelector(`.tile[data-i="${target}"]`);
      tEl && tEl.classList.add("beckon");
    }
  }

  // ---- the frame loop: scenery, camera follow, labels ------------------------
  const v = new THREE.Vector3();
  function frame() {
    requestAnimationFrame(frame);
    if (!host.offsetParent || !world) return;
    const t = clock.getElapsedTime();
    zones.forEach((zn) => zn.tick(t));
    ambient && ambient(t);
    cps.forEach((cp, i) => cp.userData.tick(t, i));
    if (carObj) {
      // the camera keeps its angle but travels with the car
      const c = carObj.position;
      if (!followPrev) { followPrev = controls.target.clone(); }
      const d = new THREE.Vector3(c.x, 0, c.z).sub(followPrev).multiplyScalar(0.08);
      controls.target.add(d); camera.position.add(d); followPrev.add(d);
      sun.position.set(c.x - 40, 90, c.z + 50); sun.target.position.set(c.x, 0, c.z);
    }
    controls.update();
    renderer.render(scene, camera);
    // project labels
    const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
    labels.querySelectorAll(".tile").forEach((el) => {
      const cp = cps[+el.dataset.i]; if (!cp) return;
      v.copy(cp.position).setY(8.6).project(camera);
      const dist = camera.position.distanceTo(cp.position), vis = v.z < 1 && Math.abs(v.x) < 1.2 && Math.abs(v.y) < 1.2 && dist < 190;
      el.style.display = vis ? "" : "none";
      el.style.transform = `translate(${(v.x + 1) / 2 * w}px, ${(1 - v.y) / 2 * h}px) translate(-50%, -100%) scale(${Math.max(0.55, Math.min(1.1, 70 / dist))})`;
      el.style.zIndex = String(1000 - Math.round(dist));
    });
    labels.querySelectorAll(".ow-sign").forEach((el) => {
      const zn = zones[+el.dataset.zone]; if (!zn) return;
      v.copy(zn.sign.pos).add(new THREE.Vector3(zn.sign.pos.x > 0 ? -16 : 16, 14, 6)).project(camera);
      const vis = v.z < 1 && Math.abs(v.x) < 1.3 && Math.abs(v.y) < 1.3;
      el.style.display = vis ? "" : "none";
      el.style.transform = `translate(${(v.x + 1) / 2 * w}px, ${(1 - v.y) / 2 * h}px) translate(-50%, -50%)`;
    });
  }
  frame();

  return {
    render, celebrate, updateMatches,
    walkTo: (id) => { const i = indexOf(id); return i === null ? null : walkTo(i); },
    tiles: () => M.tiles,
    _debug: { scene, camera, controls, cps, tParam: () => tParam },
  };
}
