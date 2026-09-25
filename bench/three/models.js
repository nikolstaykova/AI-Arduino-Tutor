// Realistic 3D parts for the CircuitQuest workbench, built procedurally in
// three.js. Units are millimetres; parts sit on the XZ plane (Y is up),
// with X to the right and Z towards the viewer (breadboard rows go +Z).
//
// Every part declares its pins in PITCH units (0.1" = 2.54 mm) relative to
// its first pin, using the SAME pin names as the engine / Wokwi diagrams,
// so a leg dropped into a hole is exactly the connection the engine checks.
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { buildModel, hasModel, iconModel } from "./catalog3d.js";

export const PITCH = 2.54;
const BB_TOP = 8.5;                         // breadboard surface height

// ---------------------------------------------------------------------------
// Materials
// ---------------------------------------------------------------------------
const M = {
  ivory: new THREE.MeshStandardMaterial({ color: 0xf2eee3, roughness: 0.55 }),
  ivoryDark: new THREE.MeshStandardMaterial({ color: 0xe2dccb, roughness: 0.6 }),
  hole: new THREE.MeshStandardMaterial({ color: 0x141210, roughness: 0.9 }),
  railRed: new THREE.MeshStandardMaterial({ color: 0xd23b33, roughness: 0.5 }),
  railBlue: new THREE.MeshStandardMaterial({ color: 0x2f62c9, roughness: 0.5 }),
  metal: new THREE.MeshStandardMaterial({ color: 0xc9ccd1, metalness: 1, roughness: 0.28 }),
  tin: new THREE.MeshStandardMaterial({ color: 0xd8d9dc, metalness: 0.9, roughness: 0.35 }),
  gold: new THREE.MeshStandardMaterial({ color: 0xd9b25a, metalness: 1, roughness: 0.3 }),
  blackPlastic: new THREE.MeshStandardMaterial({ color: 0x17181b, roughness: 0.55 }),
  chip: new THREE.MeshStandardMaterial({ color: 0x1c1c1f, roughness: 0.75 }),
  pcbEdge: new THREE.MeshStandardMaterial({ color: 0x0b6f78, roughness: 0.6 }),
  blueBody: new THREE.MeshStandardMaterial({ color: 0x2166c4, roughness: 0.45 }),
  whitePlastic: new THREE.MeshStandardMaterial({ color: 0xf4f4f0, roughness: 0.4 }),
  resistorBody: new THREE.MeshStandardMaterial({ color: 0xd9c8a3, roughness: 0.5 }),
};

const BAND = { 0: 0x111111, 1: 0x7b4a1e, 2: 0xd0312d, 3: 0xf08a24, 4: 0xf3d23c, 5: 0x2f9a45, 6: 0x2b5fd0, 7: 0x8c4bc8, 8: 0x8a8a8a, 9: 0xf5f5f5, gold: 0xc9a13a };
const LED_COLOURS = { red: 0xff3b2f, green: 0x33d45a, yellow: 0xffd23a, blue: 0x3a7bff, white: 0xf4f6ff, orange: 0xff8a1f };

function mesh(geo, mat, cast = true) {
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = cast; m.receiveShadow = true;
  return m;
}
function textTexture(draw, w, h) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const ctx = c.getContext("2d"); draw(ctx, w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}
// a lead: a round wire along a path of points
function lead(points, radius = 0.25, mat = M.tin) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), false, "catmullrom", 0.05);
  return mesh(new THREE.TubeGeometry(curve, 24, radius, 8, false), mat);
}

// ---------------------------------------------------------------------------
// Breadboard — every hole is its own instance (hover/select one exact hole)
// ---------------------------------------------------------------------------
const ROWS_TOP = ["a", "b", "c", "d", "e"], ROWS_BOTTOM = ["f", "g", "h", "i", "j"];
const ROW_Z = { tp: 0, tn: 1, a: 3, b: 4, c: 5, d: 6, e: 7, f: 10, g: 11, h: 12, i: 13, j: 14, bn: 16, bp: 17 };

export function breadboardLayout(size = "half") {
  const cols = { mini: 17, half: 30, full: 63 }[size] || 30;
  const rails = size !== "mini";
  const margin = 5.2;
  const zShift = rails ? 0 : -3;              // mini: rows a..j only
  const holes = [];
  const x = (c) => margin + (c - 1) * PITCH;
  const z = (row) => margin + (ROW_Z[row] + zShift) * PITCH;
  for (let c = 1; c <= cols; c++) {
    ROWS_TOP.forEach((r) => holes.push({ name: `${c}t.${r}`, strip: `${c}t`, x: x(c), z: z(r) }));
    ROWS_BOTTOM.forEach((r) => holes.push({ name: `${c}b.${r}`, strip: `${c}b`, x: x(c), z: z(r) }));
  }
  const railCount = rails ? Math.floor((cols - 1) * 5 / 6) : 0;
  if (rails) for (const rail of ["tp", "tn", "bn", "bp"]) {
    for (let n = 1; n <= railCount; n++) {
      const col = 1 + (n - 1) + Math.floor((n - 1) / 5);
      holes.push({ name: `${rail}.${n}`, strip: rail, x: x(col), z: z(rail) });
    }
  }
  const width = x(cols) + margin;
  const depth = rails ? z("bp") + margin : z("j") + margin;
  return { cols, rails, holes, width, depth, x, z, top: BB_TOP };
}

export function makeBreadboard(size = "half") {
  const L = breadboardLayout(size);
  const g = new THREE.Group(); g.name = "breadboard";
  const body = mesh(new RoundedBoxGeometry(L.width, BB_TOP, L.depth, 3, 1.2), M.ivory);
  body.position.set(L.width / 2, BB_TOP / 2, L.depth / 2);
  g.add(body);
  // the centre gap: a groove between row e and row f
  const gapZ = (L.z("e") + L.z("f")) / 2;
  const groove = mesh(new THREE.BoxGeometry(L.width - 4, 1.4, PITCH * 1.4), M.ivoryDark, false);
  groove.position.set(L.width / 2, BB_TOP - 0.55, gapZ);
  g.add(groove);
  // rail stripes
  if (L.rails) {
    const stripe = (zPos, mat) => {
      const s = mesh(new THREE.BoxGeometry(L.x(29) - L.x(1) + 2, 0.08, 0.5), mat, false);
      s.position.set((L.x(1) + L.x(29)) / 2, BB_TOP + 0.02, zPos); g.add(s);
    };
    stripe(L.z("tp") - PITCH * 0.6, M.railRed); stripe(L.z("tn") + PITCH * 0.6, M.railBlue);
    stripe(L.z("bn") - PITCH * 0.6, M.railBlue); stripe(L.z("bp") + PITCH * 0.6, M.railRed);
  }
  // printed labels: column numbers and row letters
  const tex = textTexture((ctx, w, h) => {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#9b927c"; ctx.font = "600 22px ui-monospace, monospace"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const sx = w / L.width, sz = h / L.depth;
    for (let c = 1; c <= L.cols; c++) if (c === 1 || c % 5 === 0) {
      ctx.fillText(String(c), L.x(c) * sx, (L.z("a") - PITCH * 1.05) * sz);
      ctx.fillText(String(c), L.x(c) * sx, (L.z("j") + PITCH * 1.05) * sz);
    }
    [...ROWS_TOP, ...ROWS_BOTTOM].forEach((r) => ctx.fillText(r, (L.x(1) - PITCH * 1.1) * sx, L.z(r) * sz));
  }, 2048, Math.round(2048 * L.depth / L.width));
  const labels = mesh(new THREE.PlaneGeometry(L.width, L.depth), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }), false);
  labels.rotation.x = -Math.PI / 2; labels.position.set(L.width / 2, BB_TOP + 0.03, L.depth / 2);
  g.add(labels);
  // holes: one instance each — a dark square socket with a lighter rim
  const holeGeo = new THREE.BoxGeometry(1.05, 0.12, 1.05);
  const holes = new THREE.InstancedMesh(holeGeo, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 }), L.holes.length);
  holes.name = "holes";
  const m4 = new THREE.Matrix4();
  L.holes.forEach((h, i) => { m4.makeTranslation(h.x, BB_TOP + 0.02, h.z); holes.setMatrixAt(i, m4); holes.setColorAt(i, new THREE.Color(0x141210)); });
  holes.instanceColor.needsUpdate = true;
  holes.userData = { kind: "holes", layout: L };
  g.add(holes);
  g.userData = { layout: L };
  return g;
}

// ---------------------------------------------------------------------------
// Arduino Uno — the real Wokwi artwork on a 3D PCB, with 3D components
// ---------------------------------------------------------------------------
const PX_PER_MM = 3.7795;
const UNO_W = 68.58, UNO_D = 53.34, PCB_T = 1.6;

async function wokwiArtwork(tag, widthPx = 2048) {
  const el = document.createElement(tag);
  el.style.position = "fixed"; el.style.left = "-9999px"; document.body.appendChild(el);
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const svg = el.shadowRoot && el.shadowRoot.querySelector("svg");
  const pins = el.pinInfo || [];
  let img = null;
  if (svg) {
    const clone = svg.cloneNode(true);
    const vb = (clone.getAttribute("viewBox") || "0 0 1 1").split(/\s+/).map(Number);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.setAttribute("width", widthPx); clone.setAttribute("height", Math.round(widthPx * vb[3] / vb[2]));
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" }));
    img = await new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = url; });
    img && (img.viewBox = vb);
  }
  el.remove();
  return { img, pins };
}

export async function makeBoard(tag = "wokwi-arduino-uno") {
  if (tag !== "wokwi-arduino-uno") return makeGenericBoard(tag);
  return makeUno();
}

// any other Wokwi board: its artwork on a PCB, female headers at its real pins
async function makeGenericBoard(tag) {
  const g = new THREE.Group(); g.name = "board";
  const { img, pins } = await wokwiArtwork(tag);
  const vb = img ? img.viewBox : [0, 0, 50, 20];
  const W = vb[2], D = vb[3];
  let topMat = new THREE.MeshStandardMaterial({ color: 0x1a5f9a, roughness: 0.5 });
  if (img) {
    const c = document.createElement("canvas"); c.width = 2048; c.height = Math.round(2048 * D / W);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
    topMat = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.5 });
  }
  const pcb = mesh(new RoundedBoxGeometry(W, PCB_T, D, 2, 0.4), [M.pcbEdge, M.pcbEdge, topMat, M.pcbEdge, M.pcbEdge, M.pcbEdge]);
  pcb.position.set(W / 2, PCB_T / 2, D / 2); g.add(pcb);
  const sockets = pins.map((p) => ({ name: p.name, x: p.x / PX_PER_MM, z: p.y / PX_PER_MM }));
  const m4 = new THREE.Matrix4();
  const hdr = new THREE.InstancedMesh(new THREE.BoxGeometry(PITCH, 8.5, PITCH), M.blackPlastic, sockets.length);
  sockets.forEach((p, i) => { m4.makeTranslation(p.x, PCB_T + 4.25, p.z); hdr.setMatrixAt(i, m4); });
  hdr.castShadow = true; g.add(hdr);
  const sockMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1.0, 0.1, 1.0), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 }), sockets.length);
  sockets.forEach((p, i) => { m4.makeTranslation(p.x, PCB_T + 8.52, p.z); sockMesh.setMatrixAt(i, m4); sockMesh.setColorAt(i, new THREE.Color(0x0e0e10)); });
  sockMesh.instanceColor.needsUpdate = true; sockMesh.name = "boardPins";
  sockMesh.userData = { kind: "boardPins", pins: sockets.map((p) => p.name), positions: sockets.map((p) => [p.x, PCB_T + 8.52, p.z]) };
  g.add(sockMesh);
  g.userData = { kind: "board", width: W, depth: D };
  return g;
}

// Every physical part of the Uno, for the inspector and hover tips.
// Keys match the userData.component tags on the model's meshes.
export const UNO_COMPONENTS = {
  "usb": { name: "USB-B port", what: "Where the cable to your computer plugs in. It does three jobs: powers the board with 5 V, uploads your sketch, and carries Serial Monitor messages both ways." },
  "usbchip": { name: "ATmega16U2 (USB-to-serial chip)", what: "A small helper chip that translates USB from your computer into the serial signals the main chip understands. It's why Upload and Serial.print() just work over one cable." },
  "dc": { name: "DC barrel jack", what: "Plug a 7–12 V adapter or battery pack here to run without a computer. The voltage regulator brings it down to a steady 5 V. Don't feed it more than 12 V — the regulator gets hot." },
  "regulator": { name: "5 V voltage regulator", what: "Turns the DC-jack / VIN voltage into a clean 5 V for the board. (A second, tiny regulator makes the 3.3V pin.) When you're on USB power it isn't needed." },
  "caps": { name: "Filter capacitors", what: "Two small power reservoirs that smooth out ripples in the supply, so the chip sees a steady voltage even when something switches on." },
  "mcu": { name: "ATmega328P microcontroller", what: "The brain — this chip runs your sketch. 32 KB of flash for the program, 2 KB of RAM, running at 16 MHz. Every digital and analog pin on the headers is one of its legs. It sits in a socket, so it can be replaced. The notch/dot marks pin 1." },
  "xtal": { name: "16 MHz crystal", what: "The board's clock: it ticks 16 million times a second. delay(1000) and millis() count on it to know how long a second is." },
  "reset": { name: "Reset button", what: "Restarts your sketch from the top of setup(). It does NOT erase your program — press it any time things look stuck." },
  "icsp": { name: "ICSP header (6 pins)", what: "In-Circuit Serial Programming: an external programmer can load code or a bootloader straight into the chip through these pins. They also carry the SPI signals (MISO, MOSI, SCK = pins 12, 11, 13), 5 V, GND and RESET." },
  "led-l": { name: "L LED (pin 13)", what: "The built-in LED, wired to pin 13 (LED_BUILTIN). It lights whenever pin 13 is HIGH — handy for testing a sketch with no extra parts." },
  "led-txrx": { name: "TX / RX LEDs", what: "Blink when data travels over USB: TX when the board sends (Serial.print), RX when it receives (uploads, Serial input)." },
  "led-on": { name: "ON LED", what: "Lit whenever the board has power. If it's dark, check the USB cable or power supply first." },
  "hdr-digital": { name: "Digital header (pins 0–13, GND, AREF, SDA, SCL)", what: "Female sockets you push jumper wires into. Pins 0–13 are digital in/out (HIGH/LOW). Pins marked ~ (3, 5, 6, 9, 10, 11) can fake in-between levels with PWM (analogWrite). Pins 0 and 1 are the serial RX/TX line — avoid them while using Serial. AREF sets the top voltage for analog readings; SDA/SCL are the I²C bus." },
  "hdr-power": { name: "Power header (IOREF, RESET, 3.3V, 5V, GND, VIN)", what: "Power your breadboard from here: 5V and 3.3V are outputs, GND is the common ground every circuit must share, VIN is the raw DC-jack voltage. RESET does the same as the reset button when pulled to GND." },
  "hdr-analog": { name: "Analog inputs A0–A5", what: "Read a voltage between 0 and 5 V as a number from 0 to 1023 with analogRead() — how knobs and sensors are measured. They also work as ordinary digital pins; A4/A5 double as SDA/SCL." },
  "holes": { name: "Mounting holes", what: "Four holes for screws or standoffs, so the board can be fixed to a case or a base without touching anything metal underneath." },
  "pcb": { name: "Circuit board (PCB)", what: "Fibreglass board with copper tracks (the faint lines) that connect every part. The white print (silkscreen) labels each pin — read it before plugging in a wire." },
};

// The Uno's top face: solder mask, copper traces, white silkscreen with the
// real pin labels printed next to every header socket.
function unoSilkscreen(pins) {
  const K = 30, W = Math.round(UNO_W * K), H = Math.round(UNO_D * K);
  return textTexture((ctx) => {
    ctx.fillStyle = "#00878f"; ctx.fillRect(0, 0, W, H);
    // copper traces under the mask
    ctx.strokeStyle = "rgba(0,120,128,1)"; ctx.lineCap = "round";
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 90; i++) {
      ctx.lineWidth = (0.25 + rnd() * 0.35) * K;
      let x = rnd() * W, y = rnd() * H; ctx.beginPath(); ctx.moveTo(x, y);
      for (let k = 0; k < 3; k++) { if (rnd() < 0.5) x += (rnd() - 0.5) * 30 * K; else y += (rnd() - 0.5) * 22 * K; ctx.lineTo(x, y); }
      ctx.stroke();
    }
    for (let i = 0; i < 70; i++) { ctx.fillStyle = "#c9b27a"; ctx.beginPath(); ctx.arc(rnd() * W, rnd() * H, 0.35 * K, 0, 7); ctx.fill(); }
    const white = "#f4f7f6";
    ctx.fillStyle = white; ctx.strokeStyle = white; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    // pin labels, rotated like the real board, beside each socket
    const top = pins.filter((p) => p.z < UNO_D / 2), bottom = pins.filter((p) => p.z >= UNO_D / 2);
    ctx.font = `700 ${1.35 * K}px Arial, sans-serif`;
    for (const p of top) {
      ctx.save(); ctx.translate(p.x * K, (p.z + 3.4) * K); ctx.rotate(-Math.PI / 2);
      ctx.textAlign = "right"; ctx.fillText(p.name.replace(/\.\d+$/, ""), 0, 0); ctx.restore();
    }
    for (const p of bottom) {
      ctx.save(); ctx.translate(p.x * K, (p.z - 3.4) * K); ctx.rotate(-Math.PI / 2);
      ctx.textAlign = "left"; ctx.fillText(p.name.replace(/\.\d+$/, ""), 0, 0); ctx.restore();
    }
    const span = (arr, re) => { const xs = arr.filter((p) => re.test(p.name)).map((p) => p.x); return xs.length ? [Math.min(...xs), Math.max(...xs)] : null; };
    ctx.font = `700 ${1.6 * K}px Arial, sans-serif`; ctx.lineWidth = 0.22 * K;
    const bracket = (r, y, label, dir) => {
      if (!r) return;
      const [x0, x1] = [r[0] * K - 0.8 * K, r[1] * K + 0.8 * K];
      ctx.beginPath(); ctx.moveTo(x0, y - dir * 0.8 * K); ctx.lineTo(x0, y); ctx.lineTo(x1, y); ctx.lineTo(x1, y - dir * 0.8 * K); ctx.stroke();
      const tw = ctx.measureText(label).width + 0.8 * K;
      ctx.fillStyle = "#00878f"; ctx.fillRect((x0 + x1) / 2 - tw / 2, y - 1 * K, tw, 2 * K);
      ctx.fillStyle = white; ctx.fillText(label, (x0 + x1) / 2, y);
    };
    const topZ = top.length ? top[0].z : 2.5, botZ = bottom.length ? bottom[0].z : 50.8;
    bracket(span(top, /^\d+$/), (topZ + 7.8) * K, "DIGITAL (PWM ~)", 1);
    bracket(span(bottom, /^(IOREF|RESET|3\.3V|5V|GND|VIN)/), (botZ - 7.8) * K, "POWER", -1);
    bracket(span(bottom, /^A\d$/), (botZ - 7.8) * K, "ANALOG IN", -1);
    // logo + name
    ctx.lineWidth = 0.55 * K;
    const lx = 42 * K, ly = 21 * K;
    ctx.beginPath(); ctx.ellipse(lx - 3.2 * K, ly, 3.2 * K, 2.4 * K, 0, 0, 7); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(lx + 3.2 * K, ly, 3.2 * K, 2.4 * K, 0, 0, 7); ctx.stroke();
    ctx.font = `900 ${1.9 * K}px Arial, sans-serif`; ctx.fillText("−", lx - 3.2 * K, ly); ctx.fillText("+", lx + 3.2 * K, ly);
    ctx.font = `800 ${3 * K}px Arial, sans-serif`; ctx.textAlign = "left"; ctx.fillText("ARDUINO", 34 * K, 28 * K);
    ctx.lineWidth = 0.3 * K; ctx.strokeRect(53 * K, 15 * K, 10 * K, 5 * K);
    ctx.font = `800 ${3.4 * K}px Arial, sans-serif`; ctx.textAlign = "center"; ctx.fillText("UNO", 58 * K, 17.6 * K);
    ctx.font = `600 ${1.2 * K}px Arial, sans-serif`;
    [["L", 24.5, 11.5], ["TX", 24.5, 15], ["RX", 24.5, 17.5], ["ON", 60.5, 11], ["ICSP", 64.2, 22.8], ["RESET", 7.5, 9], ["AREF", 0, 0]]
      .forEach(([t, x, y]) => { if (x) ctx.fillText(t, x * K, y * K); });
    ctx.font = `600 ${1.05 * K}px Arial, sans-serif`; ctx.fillText("MADE IN CIRCUITQUEST", 50 * K, 33 * K);
    // mounting-hole rings and component outlines
    ctx.lineWidth = 0.25 * K;
    [[14, 2.5], [15.3, 50.8], [66.1, 7.6], [66.1, 35.5]].forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x * K, y * K, 2.6 * K, 0, 7); ctx.stroke(); });
  }, W, H);
}

export async function makeUno() {
  const g = new THREE.Group(); g.name = "uno";
  const { img, pins } = await wokwiArtwork("wokwi-arduino-uno");
  // every mesh added between mark() and tag(key) belongs to that board component
  let from = 0; const mark = () => { from = g.children.length; };
  const tag = (key) => { g.children.slice(from).forEach((o) => o.traverse((m) => { m.userData.component = key; })); mark(); };
  // PCB outline (the real Uno's cut corner), with four mounting holes
  const s = new THREE.Shape();
  s.moveTo(0, 0); s.lineTo(64.8, 0); s.lineTo(66.3, 1.5); s.lineTo(66.3, 3.6); s.lineTo(68.58, 5.9);
  s.lineTo(68.58, 37.6); s.lineTo(66.3, 39.9); s.lineTo(66.3, 51.8); s.lineTo(64.8, UNO_D); s.lineTo(0, UNO_D); s.lineTo(0, 0);
  for (const [hx, hy] of [[14, 2.5], [15.3, 50.8], [66.1, 7.6], [66.1, 35.5]]) {
    const h = new THREE.Path(); h.absarc(hx, hy, 1.6, 0, Math.PI * 2, true); s.holes.push(h);
  }
  const pcbGeo = new THREE.ExtrudeGeometry(s, { depth: PCB_T, bevelEnabled: true, bevelThickness: 0.15, bevelSize: 0.15, bevelSegments: 2 });
  // board-local mm from Wokwi pinInfo (px in the element, whose viewBox starts at -4 mm)
  const vx = img ? img.viewBox[0] : -4;
  const pinMM = pins.map((p) => ({ name: p.name, x: p.x / PX_PER_MM + vx, z: p.y / PX_PER_MM }));
  const tex = unoSilkscreen(pinMM);
  tex.repeat.set(1 / UNO_W, -1 / UNO_D); tex.offset.set(0, 1);
  const topMat = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.42, metalness: 0.08 });
  const pcb = mesh(pcbGeo, [topMat, M.pcbEdge]);
  // shape is in XY; lay it flat so shape-Y becomes +Z (towards the viewer), top face up
  pcb.rotation.x = Math.PI / 2; pcb.position.y = PCB_T;
  g.add(pcb); tag("pcb");

  const top = pinMM.filter((p) => p.z < UNO_D / 2), bottom = pinMM.filter((p) => p.z >= UNO_D / 2);
  const sockets = [];
  // female headers: one black body per contiguous run of pins, a socket hole at each pin
  for (const row of [top, bottom]) {
    const sorted = [...row].sort((a, b) => a.x - b.x);
    let run = [];
    const flush = () => {
      if (!run.length) return;
      const x0 = run[0].x - PITCH / 2, x1 = run[run.length - 1].x + PITCH / 2, zc = run[0].z;
      const body = mesh(new RoundedBoxGeometry(x1 - x0, 8.5, PITCH, 2, 0.25), M.blackPlastic);
      body.position.set((x0 + x1) / 2, PCB_T + 4.25, zc); g.add(body);
      const names = run.map((p) => p.name);
      body.userData.component = names.some((n) => /^A\d/.test(n)) ? "hdr-analog" : names.some((n) => /^(5V|VIN|IOREF)/.test(n)) ? "hdr-power" : "hdr-digital";
      run.forEach((p) => sockets.push(p));
      run = [];
    };
    sorted.forEach((p) => { if (run.length && p.x - run[run.length - 1].x > PITCH * 1.3) flush(); run.push(p); });
    flush();
  }
  const sockGeo = new THREE.BoxGeometry(1.0, 0.1, 1.0);
  const sockMesh = new THREE.InstancedMesh(sockGeo, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 }), sockets.length);
  const m4 = new THREE.Matrix4();
  sockets.forEach((p, i) => { m4.makeTranslation(p.x, PCB_T + 8.52, p.z); sockMesh.setMatrixAt(i, m4); sockMesh.setColorAt(i, new THREE.Color(0x0e0e10)); });
  sockMesh.instanceColor.needsUpdate = true;
  sockMesh.userData = { kind: "boardPins", pins: sockets.map((p) => p.name), positions: sockets.map((p) => [p.x, PCB_T + 8.52, p.z]) };
  sockMesh.name = "boardPins";
  g.add(sockMesh); mark();

  // USB-B jack (metal, hangs over the left edge)
  const usb = mesh(new RoundedBoxGeometry(16, 10.9, 12, 2, 0.6), M.metal);
  usb.position.set(1.8, PCB_T + 5.45, 15.4); g.add(usb);
  const usbMouth = mesh(new THREE.BoxGeometry(0.4, 7.6, 8.4), M.chip, false);
  usbMouth.position.set(usb.position.x - 8.01, usb.position.y, usb.position.z); g.add(usbMouth); tag("usb");
  // ATmega16U2: the USB-to-serial chip right behind the USB jack
  const u2 = mesh(new RoundedBoxGeometry(5, 0.9, 5, 2, 0.2), M.chip); u2.position.set(15.5, PCB_T + 0.45, 13.5); g.add(u2); tag("usbchip");
  // DC barrel jack
  const dc = mesh(new RoundedBoxGeometry(14, 11, 9, 2, 0.8), M.blackPlastic);
  dc.position.set(5.2, PCB_T + 5.5, 44); g.add(dc);
  const dcHole = mesh(new THREE.CylinderGeometry(3.1, 3.1, 0.5, 32), M.chip, false);
  dcHole.rotation.z = Math.PI / 2; dcHole.position.set(-1.85, PCB_T + 6, 44); g.add(dcHole); tag("dc");
  // ATmega328P in a DIP-28 socket
  const bottomY = bottom.length ? Math.min(...bottom.map((p) => p.z)) : 50;
  const chipZ = bottomY - 9.5;
  const socket = mesh(new THREE.BoxGeometry(36, 1.6, 9.2), M.blackPlastic);
  socket.position.set(49.5, PCB_T + 0.8, chipZ); g.add(socket);
  const chip = mesh(new RoundedBoxGeometry(35, 3.4, 7.2, 2, 0.35), M.chip);
  chip.position.set(49.5, PCB_T + 3.3, chipZ); g.add(chip);
  const legGeo = new THREE.BoxGeometry(0.45, 2.6, 0.9);
  const legs = new THREE.InstancedMesh(legGeo, M.tin, 28);
  for (let i = 0; i < 14; i++) for (const side of [-1, 1]) {
    m4.makeTranslation(49.5 - 16.5 + i * PITCH, PCB_T + 2.5, chipZ + side * 3.95);
    legs.setMatrixAt(i * 2 + (side > 0 ? 1 : 0), m4);
  }
  legs.castShadow = true; g.add(legs);
  const dot = mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.05, 16), M.blackPlastic, false);
  dot.position.set(33.5, PCB_T + 5.02, chipZ - 1.8); g.add(dot); tag("mcu");
  // crystal, capacitors, reset button, ICSP pins, status LEDs
  const xtal = mesh(new RoundedBoxGeometry(11, 3.8, 4.6, 3, 1.8), M.metal);
  xtal.position.set(22, PCB_T + 1.9, 25); g.add(xtal); tag("xtal");
  for (const [cx, cz] of [[17, 35], [17, 42]]) {
    const cap = mesh(new THREE.CylinderGeometry(3.1, 3.1, 5.8, 32), new THREE.MeshStandardMaterial({ color: 0x9ea3a8, metalness: 0.8, roughness: 0.35 }));
    cap.position.set(cx, PCB_T + 2.9, cz); g.add(cap);
    const band = mesh(new THREE.CylinderGeometry(3.15, 3.15, 5.2, 32, 1, true, 0, 1.1), M.blackPlastic, false);
    band.position.copy(cap.position); g.add(band);
  }
  tag("caps");
  const reg = mesh(new THREE.BoxGeometry(6.5, 1.8, 3.5), M.chip); reg.position.set(9, PCB_T + 0.9, 33); g.add(reg);
  const regTab = mesh(new THREE.BoxGeometry(3, 0.4, 3.2), M.tin); regTab.position.set(9, PCB_T + 0.2, 30.4); g.add(regTab); tag("regulator");
  const reset = mesh(new RoundedBoxGeometry(6, 2, 3.6, 2, 0.4), M.tin);
  reset.position.set(7.5, PCB_T + 1, 5.5); g.add(reset);
  const resetCap = mesh(new THREE.CylinderGeometry(1.2, 1.2, 1.4, 20), new THREE.MeshStandardMaterial({ color: 0xb8322a, roughness: 0.5 }));
  resetCap.position.set(7.5, PCB_T + 2.6, 5.5); g.add(resetCap); tag("reset");
  const icspPinGeo = new THREE.BoxGeometry(0.64, 8.5, 0.64);
  const icspBase = mesh(new THREE.BoxGeometry(PITCH * 3, 2.5, PITCH * 2), M.blackPlastic);
  icspBase.position.set(64.5, PCB_T + 1.25, 27.4); icspBase.rotation.y = Math.PI / 2; g.add(icspBase);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 2; j++) {
    const pin = mesh(icspPinGeo, M.gold); pin.position.set(63.2 + j * PITCH, PCB_T + 4.25, 24.9 + i * PITCH); g.add(pin);
  }
  tag("icsp");
  const smdLed = (x, z, colour) => {
    const l = mesh(new THREE.BoxGeometry(1.6, 0.6, 0.8), new THREE.MeshStandardMaterial({ color: colour, emissive: colour, emissiveIntensity: 0.15, roughness: 0.3 }));
    l.position.set(x, PCB_T + 0.3, z); g.add(l); return l;
  };
  g.userData.ledL = smdLed(26.5, 11.5, 0xffb13b); tag("led-l");
  smdLed(26.5, 15, 0xffb13b); smdLed(26.5, 17.5, 0xffb13b); tag("led-txrx");
  g.userData.ledOn = smdLed(58, 11, 0x3cff6a); g.userData.ledOn.material.emissiveIntensity = 1.6; tag("led-on");
  // the mounting holes: invisible pick targets over the real holes in the PCB
  for (const [hx, hz] of [[14, 2.5], [15.3, 50.8], [66.1, 7.6], [66.1, 35.5]]) {
    const ring = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.6, 0.2, 24), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }));
    ring.position.set(hx, PCB_T + 0.12, hz); g.add(ring);
  }
  tag("holes");
  g.userData = { ...g.userData, kind: "board", width: UNO_W, depth: UNO_D };
  return g;
}

// ---------------------------------------------------------------------------
// Parts
// ---------------------------------------------------------------------------
// pins: [name, dx (columns), dz (rows)] relative to the first pin
export const PART_PINS = {
  "wokwi-led": [["A", 0, 0], ["C", -1, 0]],
  "wokwi-resistor": [["1", 0, 0], ["2", 4, 0]],
  "wokwi-pushbutton": [["1.l", 0, 0], ["1.r", 0, 3], ["2.l", 2, 0], ["2.r", 2, 3]],
  "wokwi-pushbutton-6mm": [["1.l", 0, 0], ["1.r", 0, 3], ["2.l", 2, 0], ["2.r", 2, 3]],
  "wokwi-potentiometer": [["GND", 0, 0], ["SIG", 1, 0], ["VCC", 2, 0]],
  "wokwi-slide-switch": [["1", 0, 0], ["2", 1, 0], ["3", 2, 0]],
  "wokwi-buzzer": [["1", 0, 0], ["2", 3, 0]],
  "wokwi-pir-motion-sensor": [["VCC", 0, 0], ["OUT", 1, 0], ["GND", 2, 0]],
  "cq-photoresistor": [["1", 0, 0], ["2", 2, 0]],
  "cq-fsr": [["1", 0, 0], ["2", 2, 0]],
};
export const LIFT = { "cq-photoresistor": 5, "cq-fsr": 4, "wokwi-pir-motion-sensor": 8.5, "wokwi-buzzer": 0.5, "wokwi-slide-switch": 0.6, "wokwi-led": 2.2, "wokwi-resistor": 3.2, "wokwi-pushbutton": 0.4, "wokwi-pushbutton-6mm": 0.4, "wokwi-potentiometer": 1.2 };

function resistorBands(value) {
  const ohms = Math.round(Number(String(value || "1000").replace(/k/i, "e3").replace(/M/, "e6")) || 1000);
  const digits = String(ohms);
  const mult = digits.length - 2;
  return [Number(digits[0]), Number(digits[1] || 0), mult, "gold"];
}

function makeLED(attrs = {}) {
  const colour = LED_COLOURS[attrs.color] || LED_COLOURS.red;
  const g = new THREE.Group();
  const lift = LIFT["wokwi-led"];
  const cx = -PITCH / 2;                          // centred between A (0) and C (-1 col)
  const glass = new THREE.MeshPhysicalMaterial({ color: colour, roughness: 0.08, transmission: 0.55, thickness: 3, ior: 1.5,
    emissive: colour, emissiveIntensity: 0.05, clearcoat: 1, clearcoatRoughness: 0.05 });
  const prof = [];
  prof.push(new THREE.Vector2(0, 0), new THREE.Vector2(2.9, 0), new THREE.Vector2(2.9, 1), new THREE.Vector2(2.5, 1.05), new THREE.Vector2(2.5, 5.2));
  for (let a = 0; a <= 16; a++) { const t = (a / 16) * (Math.PI / 2); prof.push(new THREE.Vector2(2.5 * Math.cos(t), 5.2 + 2.5 * Math.sin(t))); }
  const dome = mesh(new THREE.LatheGeometry(prof, 48), glass);
  dome.position.set(cx, BB_TOP + lift, 0); g.add(dome);
  // inside the lens: the anode post and the cathode anvil
  const post = mesh(new THREE.BoxGeometry(0.4, 3.2, 0.5), M.tin, false); post.position.set(cx + 0.7, BB_TOP + lift + 2.2, 0); g.add(post);
  const anvil = mesh(new THREE.BoxGeometry(1.4, 1.2, 0.5), M.tin, false); anvil.position.set(cx - 0.6, BB_TOP + lift + 3.1, 0); g.add(anvil);
  // legs: the anode is the longer, kinked one
  g.add(lead([[0, BB_TOP - 1.2, 0], [0, BB_TOP + 0.6, 0], [0.25, BB_TOP + 1.3, 0], [cx + 0.9, BB_TOP + lift, 0]]));
  g.add(lead([[-PITCH, BB_TOP - 1.2, 0], [-PITCH, BB_TOP + lift, 0], [cx - 0.9, BB_TOP + lift + 0.01, 0]]));
  const light = new THREE.PointLight(colour, 0, 40, 2);
  light.position.set(cx, BB_TOP + lift + 6, 0); g.add(light);
  g.userData.setLit = (on, dim) => {
    glass.emissiveIntensity = on ? (dim ? 0.7 : 2.4) : 0.05;
    light.intensity = on ? (dim ? 6 : 28) : 0;
  };
  return g;
}

function makeResistor(attrs = {}) {
  const g = new THREE.Group();
  const lift = LIFT["wokwi-resistor"];
  const span = 4 * PITCH, cx = span / 2, bodyLen = 6.4;
  const prof = [];
  const R = 1.25;
  // a dog-bone body: bulged ends, slimmer waist
  for (let i = 0; i <= 24; i++) {
    const t = i / 24, y = -bodyLen / 2 + t * bodyLen;
    const bulge = 0.18 * (Math.exp(-Math.pow((t - 0.1) / 0.09, 2)) + Math.exp(-Math.pow((t - 0.9) / 0.09, 2)));
    const cap = Math.sin(Math.min(1, Math.min(t, 1 - t) * 14) * Math.PI / 2);
    prof.push(new THREE.Vector2((R + bulge) * cap, y));
  }
  const body = mesh(new THREE.LatheGeometry(prof, 40), M.resistorBody);
  body.rotation.z = Math.PI / 2; body.position.set(cx, BB_TOP + lift, 0); g.add(body);
  const bands = resistorBands(attrs.value);
  const bandX = [-2.0, -1.2, -0.4, 1.9];
  bands.forEach((b, i) => {
    const ring = mesh(new THREE.CylinderGeometry(R + 0.05, R + 0.05, i === 3 ? 0.55 : 0.5, 40, 1, true),
      new THREE.MeshStandardMaterial({ color: BAND[b], roughness: 0.45, metalness: b === "gold" ? 0.8 : 0, side: THREE.DoubleSide }), false);
    ring.rotation.z = Math.PI / 2; ring.position.set(cx + bandX[i], BB_TOP + lift, 0); g.add(ring);
  });
  g.add(lead([[0, BB_TOP - 1.2, 0], [0, BB_TOP + lift - 0.8, 0], [0.4, BB_TOP + lift, 0], [cx - bodyLen / 2 + 0.2, BB_TOP + lift, 0]]));
  g.add(lead([[span, BB_TOP - 1.2, 0], [span, BB_TOP + lift - 0.8, 0], [span - 0.4, BB_TOP + lift, 0], [cx + bodyLen / 2 - 0.2, BB_TOP + lift, 0]]));
  return g;
}

function makePushbutton(attrs = {}) {
  const g = new THREE.Group();
  const w = 2 * PITCH, d = 3 * PITCH, cx = w / 2, cz = d / 2;
  const y0 = BB_TOP + LIFT["wokwi-pushbutton"];
  const base = mesh(new RoundedBoxGeometry(6, 3.4, 6, 2, 0.3), M.blackPlastic);
  base.position.set(cx, y0 + 1.7, cz); g.add(base);
  const plate = mesh(new THREE.BoxGeometry(6.1, 0.3, 6.1), M.metal);
  plate.position.set(cx, y0 + 3.55, cz); g.add(plate);
  for (const [dx, dz] of [[-2.2, -2.2], [2.2, -2.2], [-2.2, 2.2], [2.2, 2.2]]) {
    const dimple = mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.1, 12), M.chip, false);
    dimple.position.set(cx + dx, y0 + 3.72, cz + dz); g.add(dimple);
  }
  const capMat = new THREE.MeshStandardMaterial({ color: attrs.color === "green" ? 0x2f9a45 : attrs.color === "blue" ? 0x2b5fd0 : 0xd8322a, roughness: 0.35 });
  const cap = mesh(new THREE.CylinderGeometry(1.75, 1.85, 1.6, 32), capMat);
  cap.position.set(cx, y0 + 4.5, cz); cap.userData.kind = "buttonCap"; g.add(cap);
  // four bent flat legs, one into each hole
  // four flat legs: out of the front/back faces, bent down into their holes
  for (const [px, pz] of [[0, 0], [0, d], [w, 0], [w, d]]) {
    const edge = pz < cz ? cz - 3 : cz + 3;
    const tab = mesh(new THREE.BoxGeometry(0.7, 0.25, Math.abs(pz - edge) + 0.35), M.tin);
    tab.position.set(px, y0 + 0.9, (pz + edge) / 2); g.add(tab);
    const leg = mesh(new THREE.BoxGeometry(0.7, y0 + 1.0 - (BB_TOP - 1.2), 0.25), M.tin);
    leg.position.set(px, (BB_TOP - 1.2 + y0 + 1.0) / 2, pz); g.add(leg);
  }
  g.userData.setPressed = (p) => { cap.position.y = y0 + (p ? 3.9 : 4.5); };
  return g;
}

function makePotentiometer() {
  const g = new THREE.Group();
  const cx = PITCH, y0 = BB_TOP + LIFT["wokwi-potentiometer"];
  const body = mesh(new RoundedBoxGeometry(9.6, 4.6, 9.6, 2, 0.6), M.blueBody);
  body.position.set(cx, y0 + 2.3, -4.2); g.add(body);
  const rotor = new THREE.Group(); rotor.position.set(cx, y0 + 4.6, -4.2); g.add(rotor);
  const disc = mesh(new THREE.CylinderGeometry(3.6, 3.8, 1.8, 40), M.whitePlastic); disc.position.y = 0.9; rotor.add(disc);
  const slot = mesh(new THREE.BoxGeometry(5.2, 0.5, 0.9), M.chip, false); slot.position.y = 1.85; rotor.add(slot);
  const pointer = mesh(new THREE.BoxGeometry(0.6, 0.12, 2.2), new THREE.MeshStandardMaterial({ color: 0xe0a458 }), false);
  pointer.position.set(0, 1.86, -2.3); rotor.add(pointer);
  rotor.userData.kind = "knob";
  disc.userData.kind = "knob"; slot.userData.kind = "knob";
  for (let i = 0; i < 3; i++) {
    g.add(lead([[i * PITCH, BB_TOP - 1.2, 0], [i * PITCH, y0 + 0.4, 0], [i * PITCH, y0 + 0.6, -1.6]], 0.3));
  }
  g.userData.setValue = (v) => { rotor.rotation.y = -((v / 1023) * 270 - 135) * Math.PI / 180; };
  g.userData.setValue(512);
  return g;
}

// pins of any part: our models' pin maps, else the Wokwi element's own pinInfo in pitches
export function pinsFor(wokwiType) {
  if (PART_PINS[wokwiType]) return PART_PINS[wokwiType];
  const el = customElements.get(wokwiType) ? document.createElement(wokwiType) : null;
  const info = (el && el.pinInfo) || [];
  if (!info.length) return [];
  const P = 9.6, x0 = info[0].x, y0 = info[0].y;
  return info.map((p) => [p.name, Math.round((p.x - x0) / P), Math.round((p.y - y0) / P)]);
}

// a part we have no hand-made model for: a neat dark module over its real pins
function makeGeneric(wokwiType) {
  const g = new THREE.Group();
  const pins = pinsFor(wokwiType);
  const xs = pins.map((p) => p[1] * PITCH), zs = pins.map((p) => p[2] * PITCH);
  const x0 = Math.min(...xs, 0) - 2, x1 = Math.max(...xs, 0) + 2, z0 = Math.min(...zs, 0) - 5, z1 = Math.max(...zs, 0) + 1.5;
  const body = mesh(new RoundedBoxGeometry(x1 - x0, 3, z1 - z0, 2, 0.6), new THREE.MeshStandardMaterial({ color: 0x23324a, roughness: 0.5 }));
  body.position.set((x0 + x1) / 2, BB_TOP + 3.5, (z0 + z1) / 2); g.add(body);
  pins.forEach(([, dx, dz]) => g.add(lead([[dx * PITCH, BB_TOP - 1.2, dz * PITCH], [dx * PITCH, BB_TOP + 2.2, dz * PITCH]], 0.3)));
  return g;
}

// A mini SPDT slide switch: black body over its three pins, a handle you
// click to slide toward pin 1 or pin 3 (it stays where you put it).
function makeSlideSwitch() {
  const g = new THREE.Group();
  const y0 = BB_TOP + LIFT["wokwi-slide-switch"];
  const body = mesh(new RoundedBoxGeometry(8.6, 3.6, 3.6, 2, 0.3), M.blackPlastic); body.position.set(PITCH, y0 + 1.8, 0); g.add(body);
  const plate = mesh(new THREE.BoxGeometry(8.7, 0.25, 3.7), M.metal); plate.position.set(PITCH, y0 + 3.7, 0); g.add(plate);
  const slot = mesh(new THREE.BoxGeometry(4.6, 0.1, 1.4), M.chip, false); slot.position.set(PITCH, y0 + 3.86, 0); g.add(slot);
  const handle = mesh(new RoundedBoxGeometry(1.8, 3, 1.3, 2, 0.3), M.blackPlastic); handle.userData.kind = "slider"; g.add(handle);
  for (let i = 0; i < 3; i++) g.add(lead([[i * PITCH, BB_TOP - 1.2, 0], [i * PITCH, y0 + 0.3, 0]], 0.3));
  g.userData.setPosition = (atPin3) => { handle.position.set(PITCH + (atPin3 ? 1.35 : -1.35), y0 + 5.2, 0); };
  g.userData.setPosition(false);
  return g;
}

// A 12 mm piezo buzzer over its two legs (7.6 mm apart), + marked on pin 2's side.
function makeBuzzer() {
  const g = new THREE.Group(), y0 = BB_TOP + LIFT["wokwi-buzzer"], cx = 1.5 * PITCH;
  const body = mesh(new THREE.CylinderGeometry(6, 6, 9.5, 40), M.blackPlastic); body.position.set(cx, y0 + 4.75, 0); g.add(body);
  const hole = mesh(new THREE.CylinderGeometry(1.2, 1.2, 0.2, 20), M.chip, false); hole.position.set(cx, y0 + 9.55, 0); g.add(hole);
  const plus = mesh(new THREE.BoxGeometry(1.6, 0.1, 0.4), M.whitePlastic, false); plus.position.set(cx + 3.6, y0 + 9.56, 0); g.add(plus);
  const plus2 = mesh(new THREE.BoxGeometry(0.4, 0.1, 1.6), M.whitePlastic, false); plus2.position.copy(plus.position); g.add(plus2);
  for (const x of [0, 3 * PITCH]) g.add(lead([[x, BB_TOP - 1.2, 0], [x, y0 + 0.3, 0]], 0.3));
  g.userData.setSounding = (on) => { body.material = on ? M.chip : M.blackPlastic; };
  return g;
}

// An HC-SR501 PIR module standing on its three header pins (VCC, OUT, GND):
// green board, white Fresnel dome you click to "wave at" it; while it sees
// motion the dome glows faintly and the board's little LED lights.
function makePIR() {
  // the board overhangs towards the breadboard's outer edge (row a), leaving rows d–e free for wires
  const g = new THREE.Group(), y0 = BB_TOP + LIFT["wokwi-pir-motion-sensor"], cx = PITCH, cz = -13;
  const board = mesh(new RoundedBoxGeometry(32.3, 1.6, 24.3, 2, 0.4), new THREE.MeshPhysicalMaterial({ color: 0x1d6b3c, roughness: 0.45, clearcoat: 0.4 }));
  board.position.set(cx, y0 + 0.8, cz); board.userData.passThrough = true; g.add(board);    // clicks reach the holes below
  const skirt = mesh(new THREE.BoxGeometry(23.5, 3, 23.5), M.whitePlastic); skirt.position.set(cx, y0 + 3.1, cz); skirt.userData.kind = "pir"; g.add(skirt);
  const domeMat = new THREE.MeshPhysicalMaterial({ color: 0xf6f5ef, roughness: 0.55, flatShading: true, emissive: 0xff5040, emissiveIntensity: 0 });
  const dome = mesh(new THREE.SphereGeometry(11.5, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), domeMat);
  dome.position.set(cx, y0 + 4.6, cz); dome.userData.kind = "pir"; g.add(dome);
  const spacer = mesh(new THREE.BoxGeometry(3 * PITCH, 2.5, PITCH), M.blackPlastic); spacer.position.set(PITCH, y0 - 1.25, 0); g.add(spacer);
  for (let i = 0; i < 3; i++) g.add(lead([[i * PITCH, BB_TOP - 1.2, 0], [i * PITCH, y0 + 1.8, 0]], 0.32, M.gold || M.tin));
  const led = mesh(new THREE.BoxGeometry(1.6, 0.6, 0.8), new THREE.MeshStandardMaterial({ color: 0x220000, emissive: 0xff2a1a, emissiveIntensity: 0 }));
  led.position.set(cx + 13, y0 + 1.9, cz + 9); g.add(led);
  g.userData.setMotion = (on) => { domeMat.emissiveIntensity = on ? 0.18 : 0; led.material.emissiveIntensity = on ? 2 : 0; };
  return g;
}

// A photoresistor: a ceramic disc with its orange zig-zag track under clear
// lacquer, on two legs. Click it to cover it with your hand (it goes dark).
function makeLDR() {
  const g = new THREE.Group(), y0 = BB_TOP + LIFT["cq-photoresistor"], cx = PITCH;
  const tex = (() => { const c = document.createElement("canvas"); c.width = c.height = 128; const ctx = c.getContext("2d");
    ctx.fillStyle = "#e6d7b0"; ctx.fillRect(0, 0, 128, 128); ctx.strokeStyle = "#b5522a"; ctx.lineWidth = 9; ctx.beginPath();
    let y = 16, dir = 1; ctx.moveTo(14, y); while (y < 116) { ctx.lineTo(dir > 0 ? 114 : 14, y); y += 14; ctx.lineTo(dir > 0 ? 114 : 14, y); dir = -dir; } ctx.stroke();
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
  const disc = mesh(new THREE.CylinderGeometry(2.6, 2.6, 1.8, 32), [M.whitePlastic, new THREE.MeshStandardMaterial({ map: tex, roughness: 0.3 }), M.whitePlastic]);
  disc.rotation.x = Math.PI / 2; disc.position.set(cx, y0 + 2.6, 0); disc.userData.kind = "ldr"; g.add(disc);
  const shade = mesh(new THREE.CylinderGeometry(3.4, 3.4, 0.6, 32), new THREE.MeshStandardMaterial({ color: 0x3a2a20, transparent: true, opacity: 0.85 }));
  shade.rotation.x = Math.PI / 2; shade.position.set(cx, y0 + 2.6, 1.6); shade.visible = false; g.add(shade);
  for (const x of [0, 2 * PITCH]) g.add(lead([[x, BB_TOP - 1.2, 0], [x, y0, 0], [cx + (x ? 0.9 : -0.9), y0 + 1.2, 0]], 0.25));
  g.userData.setCovered = (on) => { shade.visible = on; };
  return g;
}

// A force-sensitive resistor: a round pad on a flat tail ending in two pins.
// Hold the pad to press it.
function makeFSR() {
  const g = new THREE.Group(), y0 = BB_TOP + LIFT["cq-fsr"], cx = PITCH;
  const tail = mesh(new THREE.BoxGeometry(6, 0.4, 22), M.blackPlastic); tail.position.set(cx, y0 + 4, -11); g.add(tail);
  const padMat = new THREE.MeshStandardMaterial({ color: 0x2b2b30, roughness: 0.5 });
  const pad = mesh(new THREE.CylinderGeometry(9, 9, 0.6, 40), padMat); pad.position.set(cx, y0 + 4, -28); pad.userData.kind = "buttonCap"; g.add(pad);
  const ring = mesh(new THREE.TorusGeometry(7.5, 0.25, 8, 40), M.metal); ring.rotation.x = Math.PI / 2; ring.position.set(cx, y0 + 4.35, -28); g.add(ring);
  for (const x of [0, 2 * PITCH]) g.add(lead([[x, BB_TOP - 1.2, 0], [x, y0 + 4, 0], [x, y0 + 4, -2]], 0.3, M.metal));
  g.userData.setPressed = (on) => { pad.position.y = y0 + (on ? 3.5 : 4); padMat.color.setHex(on ? 0x3a3a44 : 0x2b2b30); };
  return g;
}

export function makePart(wokwiType, attrs = {}) {
  const build = { "cq-photoresistor": makeLDR, "cq-fsr": makeFSR, "wokwi-pir-motion-sensor": makePIR, "wokwi-buzzer": makeBuzzer, "wokwi-slide-switch": makeSlideSwitch, "wokwi-led": makeLED, "wokwi-resistor": makeResistor, "wokwi-pushbutton": makePushbutton,
                  "wokwi-pushbutton-6mm": makePushbutton, "wokwi-potentiometer": makePotentiometer }[wokwiType]
                || (() => makeGeneric(wokwiType));
  const g = build(attrs);
  g.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  g.userData.pins = pinsFor(wokwiType);
  g.userData.wokwiType = wokwiType;
  return g;
}

// A jumper wire: a coloured arc with a plug and pin at each end.
// An alligator clip biting a bare leg: a coloured rubber boot and two
// serrated steel jaws, opening towards the leg.
function makeClip(colour) {
  const c = new THREE.Group();
  const boot = mesh(new THREE.CylinderGeometry(1.5, 1.1, 7, 16), new THREE.MeshStandardMaterial({ color: colour, roughness: 0.55 }));
  boot.rotation.z = Math.PI / 2; boot.position.x = -6.5; c.add(boot);
  for (const side of [-1, 1]) {
    const jaw = mesh(new THREE.BoxGeometry(6.5, 0.45, 1.6), M.metal);
    jaw.position.set(-1.2, side * 0.55, 0); jaw.rotation.z = side * 0.12; c.add(jaw);
    for (let k = 0; k < 4; k++) {
      const tooth = mesh(new THREE.BoxGeometry(0.35, 0.35, 1.5), M.metal, false);
      tooth.position.set(0.6 + k * 0.7 - 2.2, side * 0.3, 0); c.add(tooth);
    }
  }
  const spring = mesh(new THREE.TorusGeometry(0.9, 0.22, 8, 16), M.metal);
  spring.position.set(-3.6, 0, 0); spring.rotation.y = Math.PI / 2; c.add(spring);
  return c;
}

// A jumper wire between two points. Each end is one of
//   "plug"    male pin + black housing pushed into a hole / socket (default)
//   "clip"    an alligator clip biting a bare leg
//   "female"  a female housing slid over a stiff pin
//   "solder"  soldered straight onto a leg: a solder blob + heat-shrink sleeve
export function makeWire(a, b, colour = 0x2f9a45, ends = {}) {
  const g = new THREE.Group();
  const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b);
  const endA = ends.a || (ends.clipA ? "clip" : "plug"), endB = ends.b || (ends.clipB ? "clip" : "plug");
  const rise = (style) => (style === "solder" ? 1.5 : style === "female" ? 7.5 : 7);
  const lift = 12 + A.distanceTo(B) * 0.18;
  const topA = A.clone().add(new THREE.Vector3(0, rise(endA), 0)), topB = B.clone().add(new THREE.Vector3(0, rise(endB), 0));
  const mid = topA.clone().lerp(topB, 0.5); mid.y = Math.max(topA.y, topB.y) + lift;
  const curve = new THREE.CatmullRomCurve3([topA, topA.clone().lerp(mid, 0.35).setY(topA.y + lift * 0.75), mid, topB.clone().lerp(mid, 0.35).setY(topB.y + lift * 0.75), topB]);
  const insulation = new THREE.MeshStandardMaterial({ color: colour, roughness: 0.45 });
  g.add(mesh(new THREE.TubeGeometry(curve, 64, 0.55, 12, false), insulation));
  for (const [P, style, other] of [[A, endA, B], [B, endB, A]]) {
    if (style === "clip") {
      const c = makeClip(colour === 0x1d1d1f ? 0x222222 : colour);
      c.position.copy(P).add(new THREE.Vector3(0, 2.5, 0));   // jaws on the bare leg
      c.rotation.y = Math.atan2(other.z - P.z, -(other.x - P.x));
      c.rotation.z = -0.9;
      g.add(c); continue;
    }
    if (style === "solder") {                    // wire soldered onto the leg
      const blob = mesh(new THREE.SphereGeometry(0.95, 16, 12), new THREE.MeshStandardMaterial({ color: 0xc9ccd1, metalness: 1, roughness: 0.18 }));
      blob.position.copy(P); blob.scale.set(1, 1.5, 1); blob.userData.solderBlob = true; g.add(blob);
      const sleeve = mesh(new THREE.CylinderGeometry(1.15, 1.15, 5, 16), new THREE.MeshStandardMaterial({ color: 0x1d1d1f, roughness: 0.6 }));
      sleeve.position.copy(P).add(new THREE.Vector3(0, 1.2, 0)); sleeve.userData.sleeve = true; g.add(sleeve);
      continue;
    }
    if (style === "female") {                    // housing slid down over a stiff pin
      const housing = mesh(new RoundedBoxGeometry(2.5, 7, 2.5, 2, 0.3), M.blackPlastic);
      housing.position.copy(P).add(new THREE.Vector3(0, 3.2, 0)); g.add(housing);
      continue;
    }
    const housing = mesh(new RoundedBoxGeometry(2.3, 6.2, 2.3, 2, 0.3), M.blackPlastic);
    housing.position.copy(P).add(new THREE.Vector3(0, 4.1, 0)); g.add(housing);
    const pin = mesh(new THREE.CylinderGeometry(0.32, 0.32, 3, 12), M.gold);
    pin.position.copy(P).add(new THREE.Vector3(0, 0.3, 0)); g.add(pin);
  }
  g.userData.kind = "wire";
  return g;
}

// What's physically there for one connection made without a breadboard.
// `leg` (A) is a bare component leg; B is a header socket or another leg.
export function makeLink(kind, leg, other, colour) {
  const A = new THREE.Vector3(...leg), B = new THREE.Vector3(...other);
  const tin = new THREE.MeshStandardMaterial({ color: 0xd4d6da, metalness: 0.9, roughness: 0.3 });
  const bend = (pts) => mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, 0.28, 8, false), tin);
  if (kind === "insert") {                       // the lead itself bent over and pushed into the socket
    const g = new THREE.Group();
    const up = Math.max(A.y, B.y) + 6;
    g.add(bend([A, A.clone().setY(up), B.clone().setY(up), B.clone().setY(B.y - 2)]));
    g.userData.kind = "wire"; return g;
  }
  if (kind === "twist" || kind === "solder") {   // two legs bent to meet
    const g = new THREE.Group();
    const M = A.clone().lerp(B, 0.5); M.y = Math.max(A.y, B.y) + 3;
    g.add(bend([A, A.clone().lerp(M, 0.5).setY(M.y - 0.5), M]));
    g.add(bend([B, B.clone().lerp(M, 0.5).setY(M.y - 0.5), M]));
    if (kind === "twist") {                      // the twisted pigtail sticking up
      for (const ph of [0, Math.PI]) {
        const pts = []; for (let t = 0; t <= 1.0001; t += 0.05) pts.push(M.clone().add(new THREE.Vector3(Math.cos(ph + t * 18) * 0.4, t * 5, Math.sin(ph + t * 18) * 0.4)));
        g.add(bend(pts));
      }
    } else {
      const blob = mesh(new THREE.SphereGeometry(1.1, 16, 12), new THREE.MeshStandardMaterial({ color: 0xc9ccd1, metalness: 1, roughness: 0.18 }));
      blob.position.copy(M); blob.scale.set(1.4, 1, 1); blob.userData.solderBlob = true; g.add(blob);
      const sleeve = mesh(new THREE.CylinderGeometry(1.3, 1.3, 5, 16), new THREE.MeshStandardMaterial({ color: 0x1d1d1f, roughness: 0.6 }));
      sleeve.position.copy(M).add(new THREE.Vector3(0, 0.4, 0)); sleeve.rotation.z = Math.PI / 2;
      sleeve.lookAt(B.clone().setY(M.y)); sleeve.rotateX(Math.PI / 2); sleeve.userData.sleeve = true; g.add(sleeve);
    }
    g.userData.kind = "wire"; return g;
  }
  const ends = { "clip-stub": { a: "clip", b: "plug" }, "solder-wire": { a: "solder", b: "plug" }, "mf-jumper": { a: "female", b: "plug" },
                 "ff-jumper": { a: "female", b: "female" }, "clip": { a: "clip", b: "clip" } }[kind] || { a: "plug", b: "plug" };
  return makeWire(leg, other, colour, ends);
}

// ---------------------------------------------------------------------------
// Thumbnails: every tray tile / picker tile is the real 3D model, rendered once
// ---------------------------------------------------------------------------
let thumbRenderer = null;
const thumbCache = new Map();
// the bench's own detailed models (they know their legs); everything else
// comes from the catalogue in catalog3d.js
const BENCH_MODELLED = new Set(["led", "resistor-220", "resistor-1k", "resistor-10k", "pushbutton", "potentiometer-10k", "slide-switch", "buzzer", "breadboard", "arduino-uno"]);

function renderThumb(obj, size, zoom = 1) {
  if (!thumbRenderer) {
    thumbRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    thumbRenderer.setPixelRatio(2); thumbRenderer.outputColorSpace = THREE.SRGBColorSpace;
    thumbRenderer.toneMapping = THREE.ACESFilmicToneMapping;
  }
  thumbRenderer.setSize(size, size);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x6b5b4a, 1.6));
  const key1 = new THREE.DirectionalLight(0xffffff, 2.4); key1.position.set(30, 60, 40); scene.add(key1);
  scene.add(obj);
  const box = new THREE.Box3().setFromObject(obj), c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3());
  const r = Math.max(s.x, s.y, s.z);
  const cam = new THREE.PerspectiveCamera(30, 1, r / 100, r * 20);
  cam.position.copy(c).add(new THREE.Vector3(r * 1.1, r * 1.05, r * 1.35).multiplyScalar(1 / zoom)); cam.lookAt(c);
  thumbRenderer.render(scene, cam);
  return thumbRenderer.domElement.toDataURL("image/png");
}

// a render of a part by its Wokwi type (bench parts, boards, generic)
export function thumbnail(wokwiType, attrs = {}, size = 160) {
  const key = wokwiType + JSON.stringify(attrs) + size;
  if (!thumbCache.has(key)) thumbCache.set(key, (async () => {
    let obj = null;
    if (/arduino-uno/.test(wokwiType || "")) obj = await makeBoard(wokwiType);
    else if (wokwiType && wokwiType.startsWith("wokwi-breadboard")) obj = makeBreadboard("mini");
    else if (wokwiType && (customElements.get(wokwiType) || PART_PINS[wokwiType])) obj = makePart(wokwiType, attrs);
    return obj ? renderThumb(obj, size) : null;
  })());
  return thumbCache.get(key);
}

// a render of any library part or tool by its id — every one has a 3D model
export function thumbnailById(id, wokwiType, attrs = {}, size = 160) {
  if (BENCH_MODELLED.has(id) || !hasModel(id)) return thumbnail(wokwiType, attrs, size);
  const key = "id:" + id + size;
  if (!thumbCache.has(key)) thumbCache.set(key, Promise.resolve().then(() => renderThumb(buildModel(id), size)));
  return thumbCache.get(key);
}

// a close-up render of a tool-switch icon (see iconModel in catalog3d.js)
export function iconThumb(name, size = 64) {
  const key = "icon:" + name + size;
  if (!thumbCache.has(key)) thumbCache.set(key, Promise.resolve().then(() => { const m = iconModel(name); return m ? renderThumb(m, size, 1.3) : null; }));
  return thumbCache.get(key);
}

// the 3D object for a library part or tool by its id (for the Parts & Tools viewer)
export async function modelById(id, wokwiType, attrs = {}) {
  if (!BENCH_MODELLED.has(id) && hasModel(id)) return buildModel(id);
  if (/arduino-uno/.test(wokwiType || "")) return makeBoard(wokwiType);
  if (wokwiType && wokwiType.startsWith("wokwi-breadboard")) return makeBreadboard("half");
  if (wokwiType && customElements.get(wokwiType)) return makePart(wokwiType, attrs);
  return null;
}
