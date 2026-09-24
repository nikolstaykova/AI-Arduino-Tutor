// 3D models for every part and tool in the library — built procedurally in
// the same style (and roughly real millimetre size) as the bench's hand-made
// LED / resistor / button / knob. Used for the parts picker, the tray, lesson
// icons and the inspector. buildModel(libraryId) -> THREE.Group | null.
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

const P = 2.54;
const mats = new Map();
const mat = (color, o = {}) => {
  const k = color + JSON.stringify(o);
  if (!mats.has(k)) mats.set(k, new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0, ...o }));
  return mats.get(k);
};
const METAL = { metalness: 0.9, roughness: 0.3 }, GOLD = 0xd9b25a, TIN = 0xd4d6da, BLACK = 0x1c1d21;
function mesh(geo, color, o) { const m = new THREE.Mesh(geo, typeof color === "object" ? color : mat(color, o)); m.castShadow = true; m.receiveShadow = true; return m; }
const box = (w, h, d, c, o) => mesh(new THREE.BoxGeometry(w, h, d), c, o);
const rbox = (w, h, d, r, c, o) => mesh(new RoundedBoxGeometry(w, h, d, 2, Math.min(r, w / 2, h / 2, d / 2)), c, o);
const cyl = (rt, rb, h, c, o, seg = 24) => mesh(new THREE.CylinderGeometry(rt, rb, h, seg), c, o);
const at = (o, x, y, z) => { o.position.set(x, y, z); return o; };
const add = (g, ...objs) => { objs.forEach((o) => g.add(o)); return g; };

function canvasTex(w, h, draw) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return t;
}
// a flat printed / glowing face lying on top of something
function face(w, d, draw, { glow = 0, px = 256 } = {}) {
  const t = canvasTex(px, Math.max(8, Math.round(px * d / w)), draw);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshStandardMaterial({ map: t, roughness: 0.4, emissive: glow ? 0xffffff : 0, emissiveMap: glow ? t : null, emissiveIntensity: glow }));
  m.rotation.x = -Math.PI / 2;
  return m;
}
const label = (text, color = "#e8e8e8", bg = null, font = "bold 44px Arial") => (ctx, w, h) => {
  if (bg) { ctx.fillStyle = bg; ctx.fillRect(0, 0, w, h); }
  ctx.fillStyle = color; ctx.font = font; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(text, w / 2, h / 2);
};

// ---- common building blocks -------------------------------------------------
function pcb(w, d, color = 0x2a5ea8, holes = true) {
  const g = new THREE.Group();
  g.add(at(rbox(w, 1.6, d, 0.6, color), 0, 0.8, 0));
  if (holes) for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) if (w > 18 && d > 14) g.add(at(cyl(1.2, 1.2, 1.7, 0xd9c28a, METAL, 16), sx * (w / 2 - 2.4), 0.8, sz * (d / 2 - 2.4)));
  return g;
}
// a row of male header pins (black strip + gold pins), along x, pins up (or down)
function pinRow(n, { x = 0, y = 1.6, z = 0, up = true, dir = "x", female = false } = {}) {
  const g = new THREE.Group();
  const len = n * P;
  if (female) g.add(at(box(dir === "x" ? len : P, 8.5, dir === "x" ? P : len, BLACK), 0, 4.25, 0));
  else g.add(at(box(dir === "x" ? len : P, 2.5, dir === "x" ? P : len, BLACK), 0, 1.25, 0));
  for (let i = 0; i < n; i++) {
    const o = -len / 2 + P / 2 + i * P;
    if (female) { g.add(at(box(1, 0.1, 1, 0x050505), dir === "x" ? o : 0, 8.52, dir === "x" ? 0 : o)); continue; }
    g.add(at(box(0.64, up ? 11.5 : 6, 0.64, GOLD, METAL), dir === "x" ? o : 0, up ? 3.2 : -1.8, dir === "x" ? 0 : o));
  }
  return at(g, x, y, z);
}
function chipQFP(s, text = "", color = BLACK) {
  const g = new THREE.Group();
  g.add(at(box(s, 1.2, s, color), 0, 0.6, 0));
  const leg = new THREE.BoxGeometry(0.25, 0.2, 0.9), n = Math.max(4, Math.round(s / 0.8));
  for (let i = 0; i < n; i++) {
    const o = -s / 2 + 0.5 + i * ((s - 1) / (n - 1));
    for (const [x, z, r] of [[o, -s / 2 - 0.35, 0], [o, s / 2 + 0.35, 0], [-s / 2 - 0.35, o, 1], [s / 2 + 0.35, o, 1]]) { const l = mesh(leg, TIN, METAL); l.position.set(x, 0.2, z); l.rotation.y = r * Math.PI / 2; g.add(l); }
  }
  if (text) g.add(at(face(s * 0.8, s * 0.3, label(text, "#9aa0a8", "#1c1d21", "bold 60px Arial")), 0, 1.21, 0));
  return g;
}
function dip(n, text) {
  const g = new THREE.Group(), half = n / 2, L = half * P;
  g.add(at(rbox(L + 0.6, 3.3, 6.4, 0.3, BLACK), 0, 2.8, 0));
  g.add(at(cyl(0.6, 0.6, 0.1, 0x333333), -L / 2 + 1.2, 4.46, -1.8));
  g.add(at(face(L - 1, 2.4, label(text, "#b8bcc4", "#1c1d21", "bold 54px Arial")), 0, 4.46, 0.6));
  for (let i = 0; i < half; i++) for (const s of [-1, 1]) {
    g.add(at(box(0.5, 1.0, 1.4, TIN, METAL), -L / 2 + P / 2 + i * P, 1.5, s * 3.6));
    g.add(at(box(0.5, 3.4, 0.3, TIN, METAL), -L / 2 + P / 2 + i * P, -0.2, s * 3.9));
  }
  return g;
}
const smd = (w, d, c = 0x3a3a3a) => at(box(w, 0.6, d, c), 0, 1.9, 0);
const cap = (r, h, c = 0x2a4a8a) => { const g = new THREE.Group(); g.add(at(cyl(r, r, h, c), 0, 1.6 + h / 2, 0)); g.add(at(cyl(r * 0.98, r * 0.98, 0.1, 0xb8bcc4, METAL), 0, 1.6 + h + 0.05, 0)); return g; };
function trimpot() { const g = new THREE.Group(); g.add(at(box(6.5, 4.5, 6.5, 0x2a5ea8), 0, 1.6 + 2.25, 0)); g.add(at(cyl(2.2, 2.2, 0.8, 0xe8e8e2), 0, 6.3, 0)); g.add(at(box(3, 0.5, 0.6, 0x555555), 0, 6.75, 0)); return g; }
function smdLed(c) { return at(box(1.6, 0.6, 0.8, c, { emissive: c, emissiveIntensity: 0.6 }), 0, 1.9, 0); }
function leads(n, { pitch = P, len = 14, x0 = null, z = 0, y = 0, color = TIN } = {}) {
  const g = new THREE.Group(), s = x0 ?? -((n - 1) * pitch) / 2;
  for (let i = 0; i < n; i++) g.add(at(cyl(0.25, 0.25, len, color, METAL, 6), s + i * pitch, y - len / 2, z));
  return g;
}
function screen(w, d, draw, glow = 0.6) { const g = new THREE.Group(); g.add(at(box(w + 1, 1.2, d + 1, 0x111214), 0, 0.6, 0)); g.add(at(face(w, d, draw, { glow, px: 320 }), 0, 1.22, 0)); return g; }
function cable(points, r, c) { return mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p))), 64, r, 10), c); }

// ---- boards -------------------------------------------------------------------
function devBoard({ w, d, color, pins, pinsRows = 2, chipText, chipSize = 7, usb = "micro", can = false, antenna = false, buttons = 2, extra }) {
  const g = pcb(w, d, color);
  const rowZ = d / 2 - 1.4;
  for (let r = 0; r < pinsRows; r++) g.add(pinRow(pins, { z: r ? rowZ : -rowZ, y: 0, up: false }));
  if (can) {
    const c = new THREE.Group(); c.add(at(box(18, 3, 16, 0xc9ccd1, METAL), 0, 3.1, 0)); c.add(at(face(14, 5, label(chipText, "#555", "#c9ccd1", "bold 48px Arial")), 0, 4.62, 0));
    g.add(at(c, w / 2 - 12, 0, 0));
    if (antenna) g.add(at(face(6, 16, (ctx, W, H) => { ctx.fillStyle = "#1c1d21"; ctx.fillRect(0, 0, W, H); ctx.strokeStyle = "#c9a45a"; ctx.lineWidth = 8; ctx.beginPath(); for (let y = 10; y < H - 10; y += 26) { ctx.moveTo(10, y); ctx.lineTo(W - 10, y); ctx.lineTo(W - 10, y + 13); ctx.lineTo(10, y + 13); } ctx.stroke(); }), w / 2 - 2.2, 1.62, 0));
  } else g.add(at(chipQFP(chipSize, chipText), 0, 1.6, 0));
  const u = usb === "micro" ? box(7.5, 2.6, 5.6, 0xc9ccd1, METAL) : usb === "c" ? rbox(9, 3.2, 7.4, 1.4, 0xc9ccd1, METAL) : box(8, 4, 9, 0xc9ccd1, METAL);
  g.add(at(u, -w / 2 + 3.2, 1.6 + (usb === "c" ? 1.6 : 1.3), 0));
  for (let b = 0; b < buttons; b++) { const bt = new THREE.Group(); bt.add(at(box(3.5, 1.4, 3, TIN, METAL), 0, 2.3, 0)); bt.add(at(cyl(0.8, 0.8, 0.8, 0x1c1d21), 0, 3.3, 0)); g.add(at(bt, -w / 2 + 12 + b * 6, 0, (b ? 1 : -1) * (d / 2 - 5))); }
  g.add(at(smdLed(0xff4040), -w / 2 + 10, 0, 0));
  extra && extra(g);
  return g;
}

// ---- the catalogue -----------------------------------------------------------------
const B = {
  "74hc165": () => dip(16, "74HC165"),
  "74hc595": () => dip(16, "74HC595"),
  "nlsf595": () => dip(16, "NLSF595"),
  "attiny85": () => dip(8, "ATTINY85"),
  "a4988": () => {
    const g = pcb(20, 15.2, 0x6b3fa0, false); g.add(pinRow(8, { z: -6.35, y: 0, up: false })); g.add(pinRow(8, { z: 6.35, y: 0, up: false }));
    const hs = new THREE.Group(); hs.add(at(box(9, 1, 9, 0x3a4150, METAL), 0, 0.5, 0)); for (let i = 0; i < 6; i++) hs.add(at(box(0.8, 5, 9, 0x3a4150, METAL), -3.6 + i * 1.44, 3, 0));
    g.add(at(hs, 0, 2.2, 0)); g.add(at(cyl(1.2, 1.2, 1, 0xd9c28a, METAL), -7, 2.1, 0)); return g;
  },
  "alligator-clip-wire": () => { const g = new THREE.Group(); g.add(cable([[-30, 4, 0], [-10, 14, 8], [10, 10, -8], [30, 4, 0]], 0.9, 0xc9443a)); for (const s of [-1, 1]) g.add(at(clip(0xc9443a, s), s * 36, 4, 0)); return g; },
  "analog-joystick": () => {
    const g = pcb(34, 26, 0x1c1d21); g.add(pinRow(5, { x: 0, z: 11.5, y: 0, up: false }));
    g.add(at(box(16, 10, 16, 0xe8e8e2), 0, 6.6, -1)); g.add(at(cyl(4, 4, 6, 0x1c1d21), 0, 13, -1)); g.add(at(cyl(8, 7, 3.5, 0x1c1d21), 0, 16.5, -1)); return g;
  },
  "arduino-nano": () => devBoard({ w: 43, d: 18, color: 0x2a6fa8, pins: 15, chipText: "ATMEGA328P", usb: "mini" }),
  "arduino-mega": () => {
    const g = pcb(101.6, 53.3, 0x1a8a96);
    g.add(pinRow(8, { x: -18, z: -24.5, female: true, y: 0 })); g.add(pinRow(8, { x: 4, z: -24.5, female: true, y: 0 })); g.add(pinRow(8, { x: 26, z: -24.5, female: true, y: 0 }));
    g.add(pinRow(8, { x: -18, z: 24.5, female: true, y: 0 })); g.add(pinRow(8, { x: 4, z: 24.5, female: true, y: 0 })); g.add(pinRow(8, { x: 26, z: 24.5, female: true, y: 0 }));
    g.add(pinRow(18, { x: 46.5, z: 0, female: true, dir: "z", y: 0 })); g.add(pinRow(18, { x: 44, z: 0, female: true, dir: "z", y: 0 }));
    g.add(at(box(16, 11, 12, 0xc9ccd1, METAL), -48, 7, -12)); g.add(at(box(14, 11, 9, BLACK), -46, 7, 16)); g.add(at(chipQFP(14, "ATMEGA2560"), 10, 1.6, 2)); return g;
  },
  "arduino-uno": null,  // the bench's detailed Uno (models.js)
  "pi-pico": () => devBoard({ w: 51, d: 21, color: 0x2f7d4a, pins: 20, chipText: "RP2040", usb: "micro", buttons: 1 }),
  "stm32-bluepill": () => devBoard({ w: 53, d: 22.8, color: 0x2a5ea8, pins: 20, chipText: "STM32F103", usb: "micro", buttons: 1, extra: (g) => { for (let i = 0; i < 2; i++) g.add(pinRow(3, { x: -10 + i * 6, z: 0, dir: "z", y: 0 })); } }),
  "esp32-devkit-v1": () => devBoard({ w: 51, d: 28, color: 0x1c1d21, pins: 15, chipText: "ESP32-WROOM-32", can: true, antenna: true }),
  "esp32-c3-devkitm1": () => devBoard({ w: 45, d: 25.4, color: 0x1c1d21, pins: 15, chipText: "ESP32-C3-MINI", can: true, usb: "micro" }),
  "esp32-s2-devkitm1": () => devBoard({ w: 50, d: 25.4, color: 0x1c1d21, pins: 21, chipText: "ESP32-S2-MINI", can: true, usb: "micro" }),
  "esp32-s3-devkitc1": () => devBoard({ w: 63, d: 25.4, color: 0x1c1d21, pins: 22, chipText: "ESP32-S3-WROOM", can: true, antenna: true, usb: "c" }),
  "esp32-c6-devkitc1": () => devBoard({ w: 58, d: 25.4, color: 0x1c1d21, pins: 16, chipText: "ESP32-C6-WROOM", can: true, antenna: true, usb: "c" }),
  "biaxial-stepper": () => stepper(true),
  "stepper-motor": () => stepper(false),
  "bmp180": () => { const g = pcb(13, 10, 0x6b3fa0, false); g.add(pinRow(4, { z: 3.6, y: 0, up: false })); g.add(at(box(3.6, 1, 3.6, 0xc9ccd1, METAL), 0, 2.1, -1.5)); g.add(at(cyl(0.5, 0.5, 0.1, 0x222222), 0.8, 2.65, -1.5)); return g; },
  "buzzer": () => { const g = new THREE.Group(); g.add(at(cyl(6, 6, 9.5, BLACK, {}, 36), 0, 4.75, 0)); g.add(at(cyl(1.2, 1.2, 0.2, 0x050505), 0, 9.55, 0)); g.add(at(face(3, 3, label("+", "#ddd", null, "bold 200px Arial")), -3.6, 9.56, 0)); g.add(leads(2, { pitch: 7.6, len: 8 })); return g; },
  "dht22": () => {
    const g = new THREE.Group(); g.add(at(rbox(15.1, 7.7, 25, 0.8, 0xeeeeea), 0, 3.85, 0));
    g.add(at(face(12, 16, (ctx, W, H) => { ctx.fillStyle = "#eeeeea"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#b8b8b0"; for (let y = 10; y < H - 6; y += 22) for (let x = 12; x < W - 6; x += 30) ctx.fillRect(x, y, 20, 12); }), 0, 7.72, -2));
    g.add(leads(4, { z: 12, len: 10, y: 1 })); return g;
  },
  "dip-switch-8": () => { const g = new THREE.Group(); g.add(at(box(21, 5, 9.8, 0xc9443a), 0, 2.5, 0)); for (let i = 0; i < 8; i++) { g.add(at(box(1.4, 0.6, 5, 0x5a2a26), -8.9 + i * P, 5.01, 0)); g.add(at(box(1.3, 1.2, 1.8, 0xf2f2ee), -8.9 + i * P, 5.3, i % 3 ? -1.2 : 1.2)); } g.add(leads(8, { z: -3.8, len: 4 })); g.add(leads(8, { z: 3.8, len: 4 })); return g; },
  "dpdt-relay": () => { const g = new THREE.Group(); g.add(at(rbox(20, 10, 10, 0.5, 0x2b2b30), 0, 5, 0)); g.add(at(face(16, 7, label("KS2E-M-DC5", "#ccc", "#2b2b30", "bold 36px Arial")), 0, 10.02, 0)); for (let i = 0; i < 4; i++) g.add(leads(2, { x0: -7.6 + i * 5, pitch: 0, z: 0, len: 4 })); return g; },
  "ds1307-rtc": () => { const g = pcb(27, 28, 0x2a5ea8); g.add(pinRow(7, { x: 0, z: 12, y: 0, up: false })); const bat = new THREE.Group(); bat.add(at(cyl(10.5, 10.5, 3.2, 0xc9ccd1, METAL, 40), 0, 3.2, 0)); bat.add(at(face(12, 4, label("CR2032", "#555", "#c9ccd1")), 0, 4.82, 0)); g.add(at(bat, 0, 0, -2)); g.add(at(chipQFP(4, ""), 9, 1.6, 8)); return g; },
  "ds18b20": () => to92("DS18B20"),
  "ir-receiver": () => { const g = to92(""); g.add(at(new THREE.Mesh(new THREE.SphereGeometry(1.6, 16, 10), mat(0x2b2b30)), 0, 4.2, 2.6)); return g; },
  "epaper-2in9": () => { const g = pcb(89.5, 38, 0x1c1d21); g.add(at(screen(67, 29, (ctx, W, H) => { ctx.fillStyle = "#e8e6df"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#222"; ctx.font = "bold 44px Arial"; ctx.fillText("e-Paper 2.9\"", 20, H / 2 + 14); }, 0), 3, 1.6, 0)); g.add(pinRow(8, { x: -40, z: 0, dir: "z", y: 0, up: false })); return g; },
  "gas-sensor": () => { const g = pcb(32, 22, 0x2a5ea8); g.add(pinRow(4, { z: 9.5, y: 0, up: false })); const s = new THREE.Group(); s.add(at(cyl(9.5, 9.5, 2, 0xd08a3a), 0, 2.6, 0)); s.add(at(cyl(9, 9, 7, 0xb8bcc4, { ...METAL, wireframe: false }), 0, 7, 0)); s.add(at(cyl(9.05, 9.05, 7, 0x888c94, { wireframe: true }), 0, 7, 0)); g.add(at(s, -3, 0, -1)); g.add(at(trimpot(), 10, 0, -2)); return g; },
  "hc-sr04": () => { const g = pcb(45, 20, 0x2a5ea8); g.add(pinRow(4, { z: 8.6, y: 0, up: false })); for (const x of [-13, 13]) { const t = new THREE.Group(); t.add(at(cyl(8, 8, 12, 0xc9ccd1, METAL, 36), 0, 7.6, 0)); t.add(at(cyl(7.2, 7.2, 0.3, 0x2b2b30, { wireframe: true }), 0, 13.7, 0)); t.add(at(cyl(7.1, 7.1, 0.2, 0x1c1d21), 0, 13.6, 0)); g.add(at(t, x, 0, -1)); } g.add(at(box(11, 3.5, 4.6, 0xc9ccd1, METAL), 0, 3.3, -6)); return g; },
  "hx711": () => { const g = pcb(34, 20, 0x2f7d4a); g.add(pinRow(4, { x: -15, z: 0, dir: "z", y: 0, up: false })); g.add(pinRow(6, { x: 15, z: 0, dir: "z", y: 0, up: false })); g.add(at(chipQFP(6, "HX711"), 0, 1.6, 0)); return g; },
  "ili9341-lcd": () => tft(false),
  "ili9341-touch-lcd": () => tft(true),
  "ir-remote": () => {
    const g = new THREE.Group(); g.add(at(rbox(40, 7, 86, 3, 0x1c1d21), 0, 3.5, 0));
    g.add(at(face(36, 80, (ctx, W, H) => { ctx.fillStyle = "#1c1d21"; ctx.fillRect(0, 0, W, H); const k = ["⏻", "MENU", "", "+", "", "◀", "▶", "▶", "", "–", "", "0", "↺", "C", "1", "2", "3", "4", "5", "6", "7", "8", "9"]; k.forEach((t, i) => { const x = 22 + (i % 3) * 38, y = 26 + Math.floor(i / 3) * 29; ctx.fillStyle = i === 0 ? "#c9443a" : "#3a3c42"; ctx.beginPath(); ctx.arc(x + 8, y, 12, 0, 7); ctx.fill(); ctx.fillStyle = "#ddd"; ctx.font = "bold 12px Arial"; ctx.textAlign = "center"; ctx.fillText(t, x + 8, y + 4); }); }, { px: 128 }), 0, 7.02, 0));
    return g;
  },
  "jumper-wire": () => jumpers([[0x4d8a64, "m", "m"], [0xc9443a, "m", "m"], [0x2b2b30, "m", "m"]]),
  "jumper-wire-mf": () => jumpers([[0xd08a3a, "m", "f"], [0x2a5ea8, "m", "f"], [0x6b3fa0, "m", "f"]]),
  "ky-040": () => { const g = pcb(32, 19, 0x2a5ea8); g.add(pinRow(5, { x: -14.5, z: 0, dir: "z", y: 0, up: false })); const e = new THREE.Group(); e.add(at(box(12, 6.5, 13, 0xc9ccd1, METAL), 0, 4.8, 0)); e.add(at(cyl(3.5, 3.5, 5, 0xc9ccd1, METAL), 0, 10.5, 0)); e.add(at(cyl(3, 3, 12, 0xd9d9d9, METAL, 18), 0, 19, 0)); g.add(at(e, 3, 0, 0)); return g; },
  "lcd1602": () => { const g = pcb(80, 36, 0x2f7d4a); g.add(at(box(71, 7, 24, BLACK), 0, 5.1, 0)); g.add(at(face(64.5, 16, (ctx, W, H) => { ctx.fillStyle = "#a9c64a"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#1f2a10"; ctx.font = "bold 52px monospace"; ctx.fillText("Hello, world!", 16, H / 2 - 4); ctx.fillText("CircuitQuest", 16, H - 12); }, { glow: 0.35, px: 512 }), 0, 8.62, 0)); g.add(pinRow(16, { x: -18, z: -16, y: 0, up: false })); return g; },
  "led-bar-graph": () => { const g = new THREE.Group(); g.add(at(box(25.4, 8, 10.1, BLACK), 0, 4, 0)); for (let i = 0; i < 10; i++) g.add(at(box(1.6, 0.1, 5, 0xc9443a, { emissive: 0xc9443a, emissiveIntensity: i < 6 ? 0.9 : 0.1 }), -11.4 + i * P, 8.05, 0)); g.add(leads(10, { z: -3.8, len: 5 })); g.add(leads(10, { z: 3.8, len: 5 })); return g; },
  "led-matrix": () => { const g = pcb(65, 65, BLACK, false); const cols = [0xff5a5a, 0x5aff8a, 0x5a9aff, 0xffd25a]; for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { const c = (x + y) % 5 === 0 ? cols[(x * y) % 4] : 0xf2f2ee; g.add(at(box(5, 1.4, 5, c, { emissive: c === 0xf2f2ee ? 0 : c, emissiveIntensity: 0.8 }), -28 + x * 8, 2.3, -28 + y * 8)); } return g; },
  "led-ring": () => { const g = new THREE.Group(); g.add(at(mesh(new THREE.RingGeometry(14, 22, 48), BLACK), 0, 0, 0)); g.children[0].rotation.x = -Math.PI / 2; g.add(at(mesh(new THREE.CylinderGeometry(22, 22, 1.6, 48, 1, true), BLACK), 0, 0.8, 0)); for (let i = 0; i < 16; i++) { const a = (i / 16) * Math.PI * 2, c = new THREE.Color().setHSL(i / 16, 0.6, 0.6).getHex(); const l = box(5, 1.4, 5, c, { emissive: c, emissiveIntensity: 0.7 }); l.position.set(Math.cos(a) * 18, 1.6, Math.sin(a) * 18); l.rotation.y = -a; g.add(l); } const base = mesh(new THREE.RingGeometry(14, 22, 48), BLACK); base.rotation.x = -Math.PI / 2; base.position.y = 0.9; g.add(base); return g; },
  "led-strip": () => { const g = new THREE.Group(); g.add(at(box(50, 0.4, 10, 0xf2f2ee), 0, 0.2, 0)); for (let i = 0; i < 3; i++) { const c = new THREE.Color().setHSL(i / 6, 0.6, 0.6).getHex(); g.add(at(box(5, 1.6, 5, 0xf8f8f4), -16.6 + i * 16.6, 1.2, 0)); g.add(at(box(3.4, 0.1, 3.4, c, { emissive: c, emissiveIntensity: 0.9 }), -16.6 + i * 16.6, 2.05, 0)); g.add(at(box(1.6, 0.6, 0.8, 0x3a3a3a), -8.3 + i * 16.6, 0.7, 2.5)); } for (const x of [-25, 25]) g.add(at(box(2, 0.5, 9, 0xd9b25a, METAL), x, 0.45, 0)); return g; },
  "logic-analyzer": () => { const g = new THREE.Group(); g.add(at(rbox(55, 12, 25, 2, 0x2b2b30, METAL), 0, 6, 0)); g.add(at(face(40, 8, label("LOGIC 8CH · 24MHz", "#bbb", "#2b2b30", "bold 30px Arial")), 0, 12.02, -4)); g.add(pinRow(10, { x: 0, y: 3, z: 12.5, up: false })); g.children.at(-1).rotation.x = Math.PI / 2; g.add(at(box(8, 3, 3, 0xc9ccd1, METAL), -27.5, 6, 0)); return g; },
  "max7219-matrix": () => { const g = pcb(32, 32, 0x2a5ea8); g.add(at(box(32, 7, 32, 0x1c1d21), 0, 5.1, 0)); for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) g.add(at(cyl(1.3, 1.3, 0.2, 0xc9443a, { emissive: 0xc9443a, emissiveIntensity: (x ^ y) & 1 ? 0.9 : 0.05 }, 12), -14 + x * 4, 8.65, -14 + y * 4)); g.add(pinRow(5, { x: -17, z: 0, dir: "z", y: 0, up: false })); return g; },
  "membrane-keypad": () => { const g = new THREE.Group(); g.add(at(rbox(69, 0.8, 76, 1, 0x1c1d21), 0, 0.4, 0)); const k = "123A456B789C*0#D"; for (let i = 0; i < 16; i++) { const x = -24 + (i % 4) * 16, z = -26 + Math.floor(i / 4) * 17, c = "ABCD".includes(k[i]) ? "#c9443a" : "#2a5ea8"; const key = new THREE.Group(); key.add(at(rbox(13, 0.6, 14, 1, 0xe8e8e2), 0, 0.3, 0)); key.add(at(face(8, 8, label(k[i], c, null, "bold 180px Arial")), 0, 0.62, 0)); g.add(at(key, x, 0.8, z)); } g.add(at(box(18, 0.3, 40, 0xd9c9a0), 0, 0.2, 57)); return g; },
  "mfrc522": () => { const g = pcb(60, 40, 0x2a5ea8); g.add(at(face(56, 36, (ctx, W, H) => { ctx.clearRect(0, 0, W, H); ctx.strokeStyle = "#d9b25a"; ctx.lineWidth = 7; for (let i = 0; i < 4; i++) { const m = 16 + i * 12; ctx.strokeRect(m + 60, m, W - 2 * m - 60, H - 2 * m); } }, { px: 512 }), 0, 1.62, 0)); g.children.at(-1).material.transparent = true; g.add(pinRow(8, { x: -28, z: 0, dir: "z", y: 0, up: false })); g.add(at(chipQFP(5, ""), -18, 1.6, 0)); g.add(at(box(4, 1.2, 1.6, 0xc9ccd1, METAL), -18, 2.2, 8)); return g; },
  "microsd-card": () => { const g = pcb(42, 24, 0x2a5ea8); g.add(pinRow(6, { x: -19, z: 0, dir: "z", y: 0, up: false })); g.add(at(box(15, 2, 15, 0xc9ccd1, METAL), 8, 2.6, 0)); g.add(at(box(11, 0.8, 15, 0x1c1d21), 10, 3.1, 3)); g.add(at(chipQFP(4, ""), -8, 1.6, 0)); return g; },
  "mpu6050": () => { const g = pcb(21, 16, 0x2a5ea8, false); g.add(pinRow(8, { z: 6.6, y: 0, up: false })); g.add(at(chipQFP(4, "MPU"), 0, 1.6, -1.5)); return g; },
  "neopixel": () => { const g = new THREE.Group(); g.add(at(cyl(6, 6, 1.6, BLACK, {}, 32), 0, 0.8, 0)); g.add(at(box(5, 1.6, 5, 0xf8f8f4), 0, 2.4, 0)); g.add(at(cyl(2, 2, 0.1, 0x7fbf8e, { emissive: 0x7fbf8e, emissiveIntensity: 1 }), 0, 3.25, 0)); return g; },
  "nokia-5110-screen": () => { const g = pcb(45, 45, 0xc9443a); g.add(at(box(40, 5, 34, 0xc9ccd1, METAL), 0, 4.1, 2)); g.add(at(face(34, 24, (ctx, W, H) => { ctx.fillStyle = "#9cc4c9"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#1c2a2a"; ctx.font = "bold 40px monospace"; ctx.fillText("NOKIA", 30, 80); ctx.fillText("5110", 30, 130); }, { glow: 0.3 }), 0, 6.62, 2)); g.add(pinRow(8, { z: -20, y: 0, up: false })); return g; },
  "ntc-temperature-sensor": () => { const g = pcb(30, 15, 0x2a5ea8, false); g.add(pinRow(3, { x: -13, z: 0, dir: "z", y: 0, up: false })); g.add(at(new THREE.Mesh(new THREE.SphereGeometry(1.6, 12, 8), mat(0x1c1d21)), 12, 4, 0)); g.add(at(cyl(0.2, 0.2, 5, TIN, METAL, 6), 11.4, 2.5, 0)); g.add(at(cyl(0.2, 0.2, 5, TIN, METAL, 6), 12.6, 2.5, 0)); g.add(at(box(3.2, 1.6, 1.6, 0x3a3a3a), 0, 2.4, 0)); return g; },
  "oled-ssd1306": () => oled(27, 27, 0x1c1d21, "#eaf6ff"),
  "sh1107-oled": () => oled(40, 20, 0x1c1d21, "#cfe8ff"),
  "pal-tv": () => { const g = new THREE.Group(); g.add(at(rbox(60, 46, 42, 4, 0x8a6a50), 0, 23, 0)); g.add(at(rbox(40, 32, 2, 3, 0x2a2e33), -5, 25, 21)); g.add(at(new THREE.Mesh(new THREE.PlaneGeometry(36, 28), new THREE.MeshStandardMaterial({ map: canvasTex(128, 100, (ctx, W, H) => { const bars = ["#e8e8e8", "#e8e05a", "#5ae8e8", "#5ae85a", "#e85ae8", "#e85a5a", "#5a5ae8"]; bars.forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(i * W / 7, 0, W / 7 + 1, H); }); }), emissive: 0xffffff, emissiveIntensity: 0.25 })), -5, 25, 22.1)); for (let i = 0; i < 2; i++) g.add(at(cyl(1.6, 1.6, 2, 0xc9ccd1, METAL), 21, 34 - i * 10, 21.5)).children.at(-1).rotation.x = Math.PI / 2; for (const s of [-1, 1]) { const a = cyl(0.4, 0.4, 36, 0xc9ccd1, METAL, 8); a.position.set(s * 8, 58, -5); a.rotation.z = s * 0.5; g.add(a); } return g; },
  "photoresistor-sensor": () => { const g = pcb(32, 14, 0x2a5ea8, false); g.add(pinRow(4, { x: -14, z: 0, dir: "z", y: 0, up: false })); const ldr = new THREE.Group(); ldr.add(at(cyl(2.5, 2.5, 2, 0xd9c9a0), 0, 5, 0)); ldr.add(at(face(4, 4, (ctx, W, H) => { ctx.fillStyle = "#d9c9a0"; ctx.fillRect(0, 0, W, H); ctx.strokeStyle = "#b8552a"; ctx.lineWidth = 16; ctx.beginPath(); for (let i = 0; i < 6; i++) { ctx.moveTo(40, 30 + i * 36); ctx.lineTo(W - 40, 30 + i * 36); } ctx.stroke(); }), 0, 6.02, 0)); ldr.add(at(cyl(0.25, 0.25, 4, TIN, METAL, 6), -1, 2.5, 0)); ldr.add(at(cyl(0.25, 0.25, 4, TIN, METAL, 6), 1, 2.5, 0)); g.add(at(ldr, 12, 0, 0)); g.add(at(trimpot(), 2, 0, 0)); g.add(at(smdLed(0x7fbf8e), -6, 0, 4)); return g; },
  "pir-motion-sensor": () => { const g = pcb(32, 24, 0x2f7d4a); const dome = mesh(new THREE.SphereGeometry(11.5, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), 0xf2f2ee, { flatShading: true, roughness: 0.3, transparent: true, opacity: 0.95 }); dome.position.y = 1.6; g.add(dome); g.add(at(pinRow(3, { up: false, y: 0 }), 0, 0, 0)); g.children.at(-1).position.y = -2; return g; },
  "relay-module": () => { const g = pcb(50, 26, 0x2a5ea8); g.add(pinRow(3, { x: -23, z: 0, dir: "z", y: 0, up: false })); const r = new THREE.Group(); r.add(at(box(19, 15.5, 15.5, 0x2a6fd6), 0, 9.3, 0)); r.add(at(face(16, 12, label("SRD-05VDC", "#fff", "#2a6fd6", "bold 34px Arial")), 0, 17.06, 0)); g.add(at(r, 4, 0, 0)); const t = new THREE.Group(); t.add(at(box(8, 10, 15, 0x4a9a6a), 0, 6.6, 0)); for (let i = 0; i < 3; i++) t.add(at(cyl(1.4, 1.4, 0.6, 0xc9ccd1, METAL), 0, 11.8, -5 + i * 5)); g.add(at(t, 20, 0, 0)); g.add(at(smdLed(0xc9443a), -12, 0, 8)); return g; },
  "rgb-led": () => { const g = new THREE.Group(); const lens = mesh(new THREE.LatheGeometry([new THREE.Vector2(0, 0), new THREE.Vector2(2.9, 0), new THREE.Vector2(2.9, 1), new THREE.Vector2(2.5, 1), new THREE.Vector2(2.5, 5.2), ...Array.from({ length: 12 }, (_, k) => { const a = (k / 11) * Math.PI / 2; return new THREE.Vector2(2.5 * Math.cos(a), 5.2 + 2.5 * Math.sin(a)); })], 36), new THREE.MeshPhysicalMaterial({ color: 0xf4f4f8, roughness: 0.15, transmission: 0.4, thickness: 2, clearcoat: 1 })); g.add(lens); g.add(at(box(0.5, 1.2, 0.5, 0xff5a5a, { emissive: 0xff5a5a, emissiveIntensity: 0.6 }), -0.8, 3, 0)); g.add(at(box(0.5, 1.2, 0.5, 0x5aff8a, { emissive: 0x5aff8a, emissiveIntensity: 0.6 }), 0, 3, 0)); g.add(at(box(0.5, 1.2, 0.5, 0x5a9aff, { emissive: 0x5a9aff, emissiveIntensity: 0.6 }), 0.8, 3, 0)); [16, 18, 16, 16].forEach((l, i) => g.add(at(cyl(0.25, 0.25, l, TIN, METAL, 6), -1.9 + i * 1.27, -l / 2, 0))); return g; },
  "servo": () => { const g = new THREE.Group(); g.add(at(rbox(23, 22.5, 12.2, 0.8, 0x2a6fd6), 0, 11.25, 0)); g.add(at(box(32.5, 2.5, 12.2, 0x2a6fd6), 0, 16, 0)); g.add(at(cyl(5.9, 5.9, 4, 0x2a6fd6), -5.8, 24.5, 0)); g.add(at(cyl(2.4, 2.4, 3, 0xf2f2ee), -5.8, 27.5, 0)); const horn = new THREE.Group(); horn.add(at(rbox(30, 1.6, 5, 2, 0xf2f2ee), 0, 0, 0)); for (let i = 0; i < 4; i++) horn.add(at(cyl(0.5, 0.5, 1.7, 0x999999), -12 + i * 4, 0, 0)); g.add(at(horn, -5.8, 29.5, 0)); g.children.at(-1).rotation.y = 0.5; [0x8a5a3a, 0xc9443a, 0xe8943a].forEach((c, i) => g.add(cable([[11.5, 3, -1 + i], [22, 2, -1 + i], [34, 1, -1 + i * 1.2]], 0.5, c))); return g; },
  "seven-segment": () => { const g = new THREE.Group(); g.add(at(box(12.7, 8, 19, 0xf2f2ee), 0, 4, 0)); g.add(at(face(11, 17, (ctx, W, H) => { ctx.fillStyle = "#1c1d21"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#e0463a"; ctx.save(); ctx.translate(W / 2, H / 2); ctx.transform(1, 0, -0.12, 1, 0, 0); const s = W * 0.34, t = W * 0.07; const bar = (x, y, w, h) => ctx.fillRect(x, y, w, h); bar(-s / 2, -s * 1.1, s, t); bar(-s / 2, -t / 2, s, t); bar(-s / 2, s * 1.1 - t, s, t); bar(-s / 2 - t, -s * 1.05, t, s); bar(s / 2, -s * 1.05, t, s); bar(-s / 2 - t, t / 2, t, s); bar(s / 2, t / 2, t, s); ctx.restore(); ctx.beginPath(); ctx.arc(W * 0.85, H * 0.88, t * 0.7, 0, 7); ctx.fill(); }, { glow: 0.6, px: 128 }), 0, 8.02, 0)); g.add(leads(5, { z: -7.6, len: 5 })); g.add(leads(5, { z: 7.6, len: 5 })); return g; },
  "slide-switch": () => { const g = new THREE.Group(); g.add(at(box(8.5, 3.6, 3.5, BLACK), 0, 1.8, 0)); g.add(at(box(8.6, 0.3, 3.6, TIN, METAL), 0, 3.7, 0)); g.add(at(box(2, 3, 1.4, BLACK), 1.5, 5, 0)); g.add(leads(3, { len: 4 })); return g; },
  "tm1637-7segment": () => { const g = pcb(42, 24, 0x2a5ea8); g.add(pinRow(4, { x: 20, z: 0, dir: "z", y: 0, up: false })); g.add(at(box(30, 7, 14, 0x1c1d21), -2, 5.1, 0)); g.add(at(face(28, 12, (ctx, W, H) => { ctx.fillStyle = "#1c1d21"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#e0463a"; ctx.font = "bold 150px monospace"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("12:34", W / 2, H / 2 + 6); }, { glow: 0.7, px: 512 }), -2, 8.62, 0)); return g; },
  "usb-cable": () => { const g = new THREE.Group(); g.add(cable([[-40, 3, 0], [-20, 3, 18], [10, 3, 22], [30, 3, 6], [20, 3, -12], [-5, 3, -10], [-20, 3, -2], [40, 3, 0]], 1.8, 0x2b2b30)); g.add(at(box(14, 6, 9, 0x2b2b30), -48, 3, 0)); g.add(at(box(12, 4.5, 8, 0xc9ccd1, METAL), -60, 3, 0)); g.add(at(box(14, 10, 12, 0x2b2b30), 48, 5, 0)); g.add(at(box(8, 8, 9, 0xc9ccd1, METAL), 58, 5, 0)); return g; },
  "heat-shrink": () => { const g = new THREE.Group(); [0xc9443a, 0x1c1d21, 0x2a5ea8, 0xe8c83a, 0x4a9a6a].forEach((c, i) => { const t = mesh(new THREE.CylinderGeometry(1.6 + i * 0.4, 1.6 + i * 0.4, 36 - i * 3, 16, 1, true), c, { side: THREE.DoubleSide }); t.rotation.z = Math.PI / 2; t.position.set(0, 2 + i * 0.2, -10 + i * 5); g.add(t); }); return g; },
  "solder": () => { const g = new THREE.Group(); g.add(at(cyl(22, 22, 3, 0x2b2b30), 0, 1.5, 0)); g.add(at(cyl(20, 20, 22, 0xb8bcc4, METAL), 0, 14, 0)); g.add(at(cyl(22, 22, 3, 0x2b2b30), 0, 26.5, 0)); g.add(at(cyl(8, 8, 28.2, 0xd9d0bc), 0, 14, 0)); g.add(cable([[20, 16, 0], [34, 12, 10], [44, 4, 26]], 0.6, 0xb8bcc4)); return g; },
  // tools
  "digital-multimeter": () => { const g = new THREE.Group(); g.add(at(rbox(80, 30, 160, 8, 0xe8b83a), 0, 15, 0)); g.add(at(rbox(66, 4, 146, 4, 0x2b2b30), 0, 29, 0)); g.add(at(face(52, 30, (ctx, W, H) => { ctx.fillStyle = "#b9c7a8"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#1c2418"; ctx.font = "bold 90px monospace"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("4.97 V", W / 2, H / 2 + 4); }, { px: 400 }), 0, 31.1, -40)); g.add(at(cyl(24, 24, 4, 0x3a3c42), 0, 32, 20)); g.add(at(box(4, 1.5, 34, 0xe8e8e2), 0, 34.5, 20)); [[-20, 0x2b2b30], [0, 0x2b2b30], [20, 0xc9443a]].forEach(([x, c]) => g.add(at(cyl(3.5, 3.5, 3, c), x, 31.5, 64))); g.add(cable([[20, 33, 64], [40, 30, 110], [30, 10, 170]], 1.2, 0xc9443a)); g.add(cable([[0, 33, 64], [-20, 30, 110], [-30, 10, 170]], 1.2, 0x2b2b30)); return g; },
  "flush-cutters": () => pliers(0xc9443a, 22, true),
  "needle-nose-pliers": () => pliers(0x2a5ea8, 48, false),
  "wire-stripper": () => { const g = pliers(0xe8b83a, 30, true); for (let i = 0; i < 5; i++) g.add(at(cyl(0.3 + i * 0.12, 0.3 + i * 0.12, 3, 0x1c1d21, {}, 10), 60 - i * 4, 5, 0)); return g; },
  "small-screwdriver-set": () => { const g = new THREE.Group(); g.add(at(rbox(110, 14, 60, 4, 0x2b2b30), 0, 7, 0)); [0xc9443a, 0x2a5ea8, 0xe8b83a, 0x4a9a6a, 0x6b3fa0, 0xd08a3a].forEach((c, i) => { const s = new THREE.Group(); s.add(at(cyl(4, 4.5, 40, c, {}, 12), 0, 0, 0)); s.add(at(cyl(1, 1, 38, 0xc9ccd1, METAL, 10), 0, -39, 0)); s.rotation.z = Math.PI / 2; s.position.set(0, 16, -22 + i * 9); g.add(s); }); return g; },
  "soldering-iron": () => { const g = new THREE.Group(); const iron = new THREE.Group(); iron.add(at(cyl(9, 8, 70, 0x2b2b30, {}, 20), 0, 0, 0)); iron.add(at(cyl(6, 9, 10, 0xc9443a, {}, 20), 0, 40, 0)); iron.add(at(cyl(3.5, 5, 40, 0xc9ccd1, METAL, 16), 0, 65, 0)); iron.add(at(cyl(0.6, 2.5, 18, 0x8a6a50, METAL, 12), 0, 94, 0)); iron.add(cable([[0, -35, 0], [0, -60, 10], [20, -80, 30]], 2.5, 0x2b2b30)); iron.rotation.z = -Math.PI / 2.4; iron.position.y = 30; g.add(iron); const stand = new THREE.Group(); stand.add(at(rbox(70, 10, 60, 4, 0x3a3c42, METAL), 0, 5, 0)); stand.add(at(cyl(18, 22, 12, 0xe8c83a), -18, 16, 0)); g.add(at(stand, 10, 0, 30)); return g; },
  "tweezers": () => { const g = new THREE.Group(); for (const s of [-1, 1]) { const arm = box(110, 2, 8, 0xc9ccd1, METAL); arm.position.set(0, 6, s * 5); arm.rotation.y = s * 0.05; g.add(arm); } g.add(at(box(14, 6, 16, 0xc9ccd1, METAL), -56, 6, 0)); return g; },
};

// ---- helpers used by several entries ----------------------------------------------
function clip(color, side = 1) {
  const c = new THREE.Group();
  const boot = cyl(1.8, 1.3, 9, color); boot.rotation.z = Math.PI / 2; boot.position.x = -side * 7; c.add(boot);
  for (const s of [-1, 1]) { const jaw = box(8, 0.6, 2, 0xc9ccd1, METAL); jaw.position.set(side * 1, s * 0.7, 0); jaw.rotation.z = s * side * 0.12; c.add(jaw); }
  return c;
}
function to92(text) {
  const g = new THREE.Group();
  const body = mesh(new THREE.CylinderGeometry(2.4, 2.4, 5, 24, 1, false, 0, Math.PI), BLACK); body.rotation.y = Math.PI / 2; body.position.y = 3.5; g.add(body);
  g.add(at(box(4.8, 5, 0.2, BLACK), 0, 3.5, 0));
  if (text) { const f = new THREE.Mesh(new THREE.PlaneGeometry(4.4, 1.4), new THREE.MeshStandardMaterial({ map: canvasTex(256, 80, label(text, "#bbb", "#1c1d21")) })); f.position.set(0, 4, -0.11); f.rotation.y = Math.PI; g.add(f); }
  g.add(leads(3, { pitch: 1.27, len: 12, y: 1 }));
  return g;
}
function stepper(dual) {
  const g = new THREE.Group();
  g.add(at(rbox(42.3, 40, 42.3, 3, 0x1c1d21), 0, 20, 0));
  for (const y of [4, 36]) g.add(at(rbox(42.5, 8, 42.5, 3, 0x9aa0a8, METAL), 0, y, 0));
  g.add(at(cyl(11, 11, 2, 0x9aa0a8, METAL), 0, 41, 0));
  g.add(at(cyl(2.5, 2.5, 22, 0xd4d6da, METAL), 0, 51, 0));
  if (dual) g.add(at(cyl(4, 4, 10, 0xb8bcc4, METAL), 0, 45, 0));
  [0xc9443a, 0x2a5ea8, 0x4a9a6a, 0x1c1d21].forEach((c, i) => g.add(cable([[21, 8, -3 + i * 2], [36, 6, -4 + i * 2.5], [52, 2, -6 + i * 4]], 0.7, c)));
  return g;
}
function tft(touch) {
  const g = pcb(86, 50, 0xc9443a);
  g.add(at(screen(58, 43, (ctx, W, H) => { const gr = ctx.createLinearGradient(0, 0, W, H); gr.addColorStop(0, "#2a5ea8"); gr.addColorStop(1, "#6b3fa0"); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#fff"; ctx.font = "bold 36px Arial"; ctx.fillText(touch ? "ILI9341 + touch" : "ILI9341  320×240", 20, H / 2); }), 6, 1.6, 0));
  g.add(pinRow(touch ? 13 : 9, { x: -38, z: 0, dir: "z", y: 0, up: false }));
  if (touch) g.add(at(box(60, 0.3, 45, 0xffffff, { transparent: true, opacity: 0.15 }), 6, 3.1, 0));
  return g;
}
function oled(w, d, pcbc, textColor) {
  const g = pcb(w, d, pcbc);
  g.add(at(screen(w - 4, d * 0.62, (ctx, W, H) => { ctx.fillStyle = "#050608"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = textColor; ctx.font = "bold 40px monospace"; ctx.fillText("CircuitQuest", 12, H / 2 - 6); ctx.fillText("temp 21.4 C", 12, H / 2 + 38); }, 0.8), 0, 1.6, 1.5));
  g.add(pinRow(4, { z: -d / 2 + 1.6, y: 0, up: false }));
  return g;
}
function pliers(color, jaw, cutter) {
  const g = new THREE.Group();
  for (const s of [-1, 1]) {
    const h = new THREE.Group();
    h.add(at(cyl(4, 5, 70, color, {}, 12), 0, 0, 0)); h.children[0].rotation.z = Math.PI / 2;
    const j = box(jaw, 3, cutter ? 5 : 2.6, 0x9aa0a8, METAL); j.position.x = 35 + jaw / 2; h.add(j);
    h.rotation.y = s * 0.12; h.position.set(-15, 6, s * 4); g.add(h);
  }
  g.add(at(cyl(4, 4, 8, 0x9aa0a8, METAL), 20, 6, 0));
  return g;
}
function jumpers(list) {
  const g = new THREE.Group();
  list.forEach(([c, a, b], i) => {
    const z = -8 + i * 8;
    g.add(cable([[-38, 4, z], [-14, 10, z + 4], [14, 10, z - 4], [38, 4, z]], 0.7, c));
    for (const [x, kind, dir] of [[-42, a, -1], [42, b, 1]]) {
      g.add(at(rbox(8, 2.6, 2.6, 0.3, BLACK), x, 4, z));
      if (kind === "m") { const pin = cyl(0.32, 0.32, 5, GOLD, METAL, 8); pin.rotation.z = Math.PI / 2; pin.position.set(x + dir * 6.5, 4, z); g.add(pin); }
    }
  });
  return g;
}

export function hasModel(id) { return !!B[id]; }
export function buildModel(id) {
  const f = B[id];
  if (!f) return null;
  const g = f();
  g.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return g;
}
