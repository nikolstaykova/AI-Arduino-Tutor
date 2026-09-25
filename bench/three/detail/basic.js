// Detailed discrete parts: LEDs, resistors, buttons, knobs, switches, the
// buzzer and the through-hole chips.
import { THREE, M, P, box, rbox, cyl, sphere, torus, at, group, lathe, extrude, tube, bentWire, decal, sideDecal, text,
  dip, resistorBody, to92, knurledShaft } from "./kit.js";

// a 5 mm LED: tinted epoxy dome with its flat (cathode) side, the anvil and
// post inside, and the two legs (anode longer, with the classic bend)
function led5(color, { lit = true, diffused = false } = {}) {
  const g = new THREE.Group();
  const pts = [[0, 1.0], [2.5, 1.0], [2.5, 5.6]];
  for (let k = 1; k <= 14; k++) { const a = (k / 14) * Math.PI / 2; pts.push([2.5 * Math.cos(a), 5.6 + 2.5 * Math.sin(a)]); }
  const lensMat = new THREE.MeshPhysicalMaterial({ color, roughness: diffused ? 0.55 : 0.06, transmission: diffused ? 0.2 : 0.75, thickness: 3, ior: 1.5,
    transparent: true, opacity: diffused ? 0.95 : 0.8, clearcoat: 1, emissive: color, emissiveIntensity: lit ? 0.35 : 0 });
  const lens = lathe(pts, lensMat, 64); lens.position.y = 1; g.add(lens);
  // the rim, with its flat side = the cathode
  const cut = Math.acos(2.6 / 2.95), rim = new THREE.Shape();
  rim.absarc(0, 0, 2.95, cut, Math.PI * 2 - cut, false); rim.closePath();
  const flange = new THREE.Mesh(new THREE.ExtrudeGeometry(rim, { depth: 1, bevelEnabled: false, curveSegments: 48 }), lensMat);
  flange.rotation.x = -Math.PI / 2; flange.position.y = 1; g.add(flange);
  // the inside: anvil (cathode, bigger) and post (anode) with the die and bond wire
  const inner = M.metal(0xc9ccd1, 0.35);
  g.add(at(box(0.5, 4, 1.4, inner), 0.9, 3.2, 0));
  g.add(at(box(1.6, 0.5, 1.4, inner), 0.4, 5.2, 0));
  g.add(at(box(0.5, 3.4, 0.6, inner), -0.9, 3.0, 0));
  g.add(at(box(0.4, 0.25, 0.4, M.glow(color, lit ? 3 : 0.2)), 0.35, 5.55, 0));
  g.add(tube([[0.35, 5.7, 0], [-0.2, 6.4, 0], [-0.9, 4.8, 0]], 0.04, M.gold(), { seg: 16, radial: 4 }));
  // legs: anode (long, bent) at -x, cathode (short) at +x
  g.add(bentWire([[-1.27, 1.2, 0], [-1.27, -1.2, 0], [-1.9, -2.2, 0], [-1.9, -13, 0]], 0.25, M.tin()));
  g.add(bentWire([[1.27, 1.2, 0], [1.27, -10, 0]], 0.25, M.tin()));
  if (lit) { const l = new THREE.PointLight(color, 2, 30); l.position.set(0, 6, 0); g.add(l); }
  return g;
}

// an axial resistor with its legs bent down 90°, ready for a breadboard
function resistor(ohms) {
  const g = new THREE.Group();
  const body = resistorBody(ohms); body.position.y = 8; g.add(body);
  for (const s of [-1, 1]) g.add(bentWire([[s * 3.1, 8, 0], [s * 4.9, 8, 0], [s * 5.08, 7.6, 0], [s * 5.08, 1, 0]], 0.3, M.tin()));
  return g;
}

function pushbutton() {
  // a 12 mm tactile switch with a round cap
  const g = new THREE.Group();
  g.add(at(rbox(12, 3.8, 12, 0.3, M.plastic(0x18191c, 0.5)), 0, 1.9, 0));
  const plate = rbox(12.1, 0.35, 12.1, 0.15, M.steel()); g.add(at(plate, 0, 3.9, 0));
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    g.add(at(cyl(0.6, 0.6, 0.4, M.plastic(0x0c0c0e, 0.8), 16), x * 4.6, 4.15, z * 4.6));
    g.add(at(box(1.8, 0.4, 0.8, M.steel()), x * 6.2, 3.3, z * 4.2));
  }
  g.add(at(cyl(3.6, 3.6, 1.2, M.plastic(0x18191c, 0.5), 40), 0, 4.6, 0));
  const cap = lathe([[0, 0], [5.8, 0], [6, 0.3], [6, 3.4], [5.7, 3.9], [4.8, 4.2], [0, 4.3]], M.plastic(0xd33a2c, 0.35), 64);
  g.add(at(cap, 0, 5.1, 0));
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) g.add(bentWire([[x * 6.2, 3, z * 2.5], [x * 6.6, 0.4, z * 2.5], [x * 6.35, -1.4, z * 2.5], [x * 6.6, -4.5, z * 2.5]], 0.35, M.tin()));
  return g;
}

function potentiometer() {
  // a 16 mm panel pot: steel can, threaded bushing and nut, knurled shaft, three solder lugs
  const g = new THREE.Group();
  g.add(at(cyl(8, 8, 7, M.steel(), 64), 0, 3.5, 0));
  g.add(at(cyl(8.1, 8.1, 0.6, M.metal(0xa9aeb6, 0.3), 64), 0, 7, 0));
  for (let i = 0; i < 4; i++) { const a = (i / 4) * Math.PI * 2 + 0.4; g.add(at(box(1.6, 1.4, 0.4, M.steel()), Math.cos(a) * 8.1, 6.3, Math.sin(a) * 8.1, 0, -a + Math.PI / 2)); }
  const bush = new THREE.Group();
  bush.add(cyl(3.5, 3.5, 7, M.brass(), 40));
  for (let i = 0; i < 12; i++) bush.add(at(torus(3.52, 0.12, M.brass(), 6, 40), 0, -3 + i * 0.55, 0, Math.PI / 2));
  g.add(at(bush, 0, 10.8, 0));
  const nut = cyl(5.5, 5.5, 2, M.chrome(), 6); g.add(at(nut, 0, 8.3, 0));
  g.add(at(knurledShaft(3, 9, M.metal(0xdfe2e6, 0.3), 24), 0, 18.8, 0));
  for (const x of [-5, 0, 5]) {
    g.add(at(extrude([[-1.4, 0], [1.4, 0], [1.4, -6], [0.6, -8], [-0.6, -8], [-1.4, -6]], 0.3, M.tin(), { holes: [[[-0.5, -4.2], [0.5, -4.2], [0.5, -5.4], [-0.5, -5.4]]] }), x, -1, 5.2));
  }
  return g;
}

function slideSwitch() {
  const g = new THREE.Group();
  g.add(at(rbox(8.6, 3.6, 3.6, 0.15, M.plastic(0x18191c, 0.5)), 0, 1.8, 0));
  const frame = new THREE.Group();
  frame.add(at(box(8.8, 0.3, 3.8, M.steel()), 0, 3.75, 0));
  for (const s of [-1, 1]) { frame.add(at(box(0.3, 3.6, 3.8, M.steel()), s * 4.45, 2, 0)); frame.add(at(box(1, 0.3, 1.2, M.steel()), s * 4.45, -0.2, 0)); }
  g.add(frame);
  g.add(at(box(4.2, 0.1, 1.4, M.plastic(0x050505, 0.9)), 0, 3.91, 0));
  const knob = rbox(1.6, 3.2, 1.3, 0.2, M.plastic(0x18191c, 0.5)); g.add(at(knob, 1.3, 5.3, 0));
  for (let i = 0; i < 3; i++) g.add(at(box(1.62, 0.1, 1.32, M.plastic(0x0d0d0f, 0.7)), 1.3, 5.9 + i * 0.45, 0));
  for (const x of [-P, 0, P]) g.add(at(box(0.8, 4.5, 0.3, M.tin()), x, -2.2, 0));
  return g;
}

function buzzer() {
  const g = new THREE.Group();
  g.add(at(lathe([[0, 0], [5.9, 0], [6, 0.3], [6, 9.2], [5.7, 9.5], [0, 9.5]], M.plastic(0x17181b, 0.45), 64), 0, 0, 0));
  g.add(at(lathe([[0, 0], [1.2, 0], [1.2, -0.8], [0, -0.8]], M.plastic(0x040404, 1), 32), 0, 9.52, 0));
  g.add(at(decal(12, 12, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    text(ctx, "+", W * 0.24, H * 0.5, { size: 3 * k, color: "#e8e8e8" });
    ctx.fillStyle = "#e8e8e8"; ctx.beginPath(); ctx.arc(W / 2, H / 2, 4.8 * k, 0, 7); ctx.lineWidth = 0.1 * k; ctx.strokeStyle = "#555"; ctx.stroke();
    text(ctx, "TMB12A05", W / 2, H * 0.78, { size: 1 * k, color: "#bbb", weight: "normal" });
  }, { pxPerMm: 60 }), 0, 9.52, 0));
  g.add(at(decal(8, 3, (ctx, W, H, k) => { ctx.fillStyle = "#f2f2ee"; ctx.fillRect(0, 0, W, H); text(ctx, "REMOVE SEAL", W / 2, H / 2, { size: 1.1 * k, color: "#222" }); }, { pxPerMm: 60, transparent: false }), 0, 9.55, -1.2));
  g.add(at(box(0.8, 0.02, 1.6, M.plastic(0xffffff, 0.5)), -2.4, 9.56, 1));
  g.add(bentWire([[-3.8, 0.1, 0], [-3.8, -7, 0]], 0.3, M.tin()));
  g.add(bentWire([[3.8, 0.1, 0], [3.8, -5.5, 0]], 0.3, M.tin()));
  return g;
}

function rgbLed() {
  const g = new THREE.Group();
  const pts = [[0, 0], [2.95, 0], [2.95, 1.0], [2.5, 1.05], [2.5, 5.6]];
  for (let k = 1; k <= 14; k++) { const a = (k / 14) * Math.PI / 2; pts.push([2.5 * Math.cos(a), 5.6 + 2.5 * Math.sin(a)]); }
  const mat = new THREE.MeshPhysicalMaterial({ color: 0xf6f6f6, roughness: 0.55, transmission: 0.3, thickness: 3, transparent: true, opacity: 0.93, clearcoat: 1 });
  g.add(at(lathe(pts, mat, 64), 0, 1, 0));
  [[0xff3030, -0.5], [0x30ff60, 0], [0x3060ff, 0.5]].forEach(([c, x]) => g.add(at(box(0.3, 0.2, 0.3, M.glow(c, 3)), x, 5.6, 0)));
  const L = [[-1.9, -10], [-0.63, -13], [0.63, -11.5], [1.9, -10]];
  L.forEach(([x, y]) => g.add(bentWire([[x * 0.7, 1.2, 0], [x, -1.5, 0], [x, y, 0]], 0.22, M.tin())));
  const l = new THREE.PointLight(0xc0a0ff, 1.5, 30); l.position.set(0, 6, 0); g.add(l);
  return g;
}

function dipSwitch() {
  const g = new THREE.Group(), L = 8 * P + 0.6;
  g.add(at(rbox(L, 5, 9.8, 0.3, M.plastic(0xd0342c, 0.45)), 0, 2.5 + 0.6, 0));
  g.add(at(decal(L, 9.8, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    text(ctx, "ON", 1.6 * k, 1.2 * k, { size: 1.2 * k, color: "#fff", align: "left" });
    for (let i = 0; i < 8; i++) text(ctx, String(i + 1), (0.3 + P / 2 + i * P) * k, H - 1 * k, { size: 1.2 * k, color: "#fff" });
  }, { pxPerMm: 50 }), 0, 5.62, 0));
  for (let i = 0; i < 8; i++) {
    const x = -L / 2 + 0.3 + P / 2 + i * P;
    g.add(at(box(1.5, 0.3, 5.4, M.plastic(0x3a100e, 0.8)), x, 5.5, 0));
    g.add(at(rbox(1.3, 1.4, 2.1, 0.2, M.plastic(0xf5f3ee, 0.4)), x, 6, [1, 0, 1, 1, 0, 0, 1, 0][i] ? -1.4 : 1.4));
    for (const s of [-1, 1]) g.add(at(box(0.5, 4.5, 0.3, M.tin()), x, -1.1, s * 3.81));
  }
  return g;
}

function irReceiver() {
  // a VS1838B: black epoxy with the dome lens, on three legs
  const g = new THREE.Group();
  g.add(at(rbox(6, 7, 3, 0.4, M.plastic(0x141417, 0.25)), 0, 16.5, 0));
  const dome = sphere(2.3, M.plastic(0x141417, 0.15), 32, 16); dome.scale.set(1, 1, 0.55); g.add(at(dome, 0, 17, 1.4));
  g.add(at(box(6.02, 1.4, 3.02, M.plastic(0x141417, 0.25)), 0, 13.6, 0));
  for (const x of [-P, 0, P]) g.add(bentWire([[x, 13, 0], [x, 10, 0], [x, 5, 0]], 0.25, M.tin()));
  g.add(at(sideDecal(4, 1.2, (ctx, W, H) => text(ctx, "1838", W / 2, H / 2, { size: H * 0.7, color: "#777" }), { pxPerMm: 60 }), 0, 13.6, 1.52));
  return g;
}

function sevenSegment() {
  const g = new THREE.Group();
  g.add(at(box(12.7, 8, 19, M.plastic(0xf4f3ef, 0.6)), 0, 4, 0));
  g.add(at(decal(12.2, 18.5, (ctx, W, H, k) => {
    ctx.fillStyle = "#17181b"; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.translate(W / 2 + 0.3 * k, H / 2); ctx.transform(1, 0, -0.1, 1, 0, 0);
    const s = 5 * k, t = 1.1 * k, on = [1, 1, 1, 1, 1, 1, 1];     // segments a-g, all lit: an "8"
    const seg = (x, y, w, h, i) => { ctx.fillStyle = on[i] ? "#ff4a30" : "#3a2020"; ctx.beginPath(); ctx.roundRect(x, y, w, h, t / 2); ctx.fill(); };
    seg(-s / 2, -s - t * 1.5, s, t, 0); seg(s / 2, -s - t, t, s, 1); seg(s / 2, t / 2, t, s, 2); seg(-s / 2, s + t / 2, s, t, 3); seg(-s / 2 - t, t / 2, t, s, 4); seg(-s / 2 - t, -s - t, t, s, 5); seg(-s / 2, -t / 2, s, t, 6);
    ctx.fillStyle = "#3a2020"; ctx.beginPath(); ctx.arc(s / 2 + 2.2 * t, s + t, t * 0.6, 0, 7); ctx.fill();
    ctx.restore();
  }, { pxPerMm: 40, glow: 0.25, transparent: false }), 0, 8.01, 0));
  for (let i = 0; i < 5; i++) for (const s of [-1, 1]) g.add(at(box(0.5, 6, 0.25, M.tin()), -5.08 + i * P, -3, s * 7.62));
  return g;
}

function barGraph() {
  const g = new THREE.Group();
  g.add(at(box(25.4, 8, 10.1, M.plastic(0x17181b, 0.5)), 0, 4, 0));
  for (let i = 0; i < 10; i++) {
    const c = i < 7 ? 0x50e050 : i < 9 ? 0xf0d020 : 0xff3a2a;
    g.add(at(box(1.7, 0.08, 5.2, i < 7 ? M.glow(c, 0.9) : M.epoxy(c)), -11.43 + i * P, 8.04, 0));
    for (const s of [-1, 1]) g.add(at(box(0.5, 6, 0.25, M.tin()), -11.43 + i * P, -3, s * 3.81));
  }
  g.add(at(decal(25, 2, (ctx, W, H, k) => text(ctx, "LTA-1000", W / 2, H / 2, { size: 1.2 * k, color: "#777" }), { pxPerMm: 40 }), 0, 8.01, 4));
  return g;
}

function neopixel() {
  // one WS2812B on a tiny round breakout
  const g = new THREE.Group();
  g.add(at(cyl(5, 5, 1.6, M.mask(0x17181b), 48), 0, 0.8, 0));
  g.add(at(box(5, 1.6, 5, M.plastic(0xf8f8f4, 0.35)), 0, 2.4, 0));
  g.add(at(cyl(1.9, 1.9, 0.1, M.epoxy(0xfff2d0), 32), 0, 3.25, 0));
  [[0xff3030, -0.6], [0x30ff60, 0], [0x3060ff, 0.6]].forEach(([c, x]) => g.add(at(box(0.35, 0.15, 0.35, M.glow(c, 2)), x, 3.2, 0.4)));
  g.add(at(box(0.9, 0.15, 0.6, M.plastic(0x222)), 0, 3.2, -0.6));
  for (const [x, z, t] of [[-3.6, 0, "DI"], [3.6, 0, "DO"], [0, -3.6, "5V"], [0, 3.6, "GND"]]) {
    g.add(at(cyl(0.7, 0.7, 0.05, M.gold(), 16), x, 1.62, z));
  }
  const l = new THREE.PointLight(0xa8ffc0, 1.5, 20); l.position.set(0, 5, 0); g.add(l);
  return g;
}

function relayKS2E() {
  const g = new THREE.Group();
  g.add(at(rbox(20, 10, 10, 0.4, M.plastic(0x1d1e22, 0.35)), 0, 5, 0));
  g.add(at(decal(18, 8.5, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    text(ctx, "KEMET", W / 2, 1.5 * k, { size: 1.4 * k, color: "#d8d8d8" });
    text(ctx, "KS2E-M-DC5", W / 2, 3.6 * k, { size: 1.5 * k, color: "#d8d8d8" });
    text(ctx, "2A 30VDC  0.5A 125VAC", W / 2, 5.6 * k, { size: 0.9 * k, color: "#bbb", weight: "normal" });
    ctx.strokeStyle = "#ccc"; ctx.lineWidth = 0.15 * k; ctx.strokeRect(1 * k, 6.6 * k, 5 * k, 1.4 * k);
  }, { pxPerMm: 50 }), 0, 10.01, 0));
  for (let i = 0; i < 5; i++) for (const s of [-1, 1]) if (i !== 2) g.add(at(box(0.5, 3.5, 0.3, M.tin()), -7.62 + i * 3.81, -1.7, s * 3.81));
  return g;
}

function photoresistor() {
  // GL5528-style LDR: ceramic disc, orange cadmium-sulphide track, clear lacquer, two long legs
  const g = new THREE.Group();
  const disc = cyl(2.6, 2.6, 2, M.ceramic(0xe6d7b0), 48); disc.rotation.x = Math.PI / 2; g.add(at(disc, 0, 6, 0));
  g.add(at(sideDecal(4.8, 4.8, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, W / 2, 0, 7); ctx.clip(); ctx.fillStyle = "#e6d7b0"; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "#b5522a"; ctx.lineWidth = 0.42 * k; ctx.beginPath(); let y = 0.6 * k, dir = 1; ctx.moveTo(0.4 * k, y);
    while (y < H - 0.6 * k) { ctx.lineTo(dir > 0 ? W - 0.4 * k : 0.4 * k, y); y += 0.62 * k; ctx.lineTo(dir > 0 ? W - 0.4 * k : 0.4 * k, y); dir = -dir; }
    ctx.stroke(); ctx.fillStyle = "#c9ccd1"; ctx.fillRect(0, 0, 0.7 * k, H); ctx.fillRect(W - 0.7 * k, 0, 0.7 * k, H); ctx.restore();
  }, { pxPerMm: 80 }), 0, 6, 1.02));
  g.add(at(cyl(2.65, 2.65, 0.25, M.glass(0xfff8e0, 0.3), 48), 0, 6, 1.1, Math.PI / 2, 0, 0));
  for (const x of [-1.7, 1.7]) g.add(bentWire([[x * 0.6, 3.8, 0], [x, 2.6, 0], [x, -14, 0]], 0.25, M.tin()));
  return g;
}

function fsr() {
  // Interlink FSR 402: a round black sensing pad on a flat tail, two crimped pins
  const g = new THREE.Group();
  g.add(at(cyl(9, 9, 0.5, M.plastic(0x1f2024, 0.45), 64), 0, 0.25, -28));
  g.add(at(decal(15, 15, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, W / 2, 0, 7); ctx.clip();
    ctx.fillStyle = "#2c2d33"; ctx.fillRect(0, 0, W, H); ctx.strokeStyle = "#51535c"; ctx.lineWidth = 0.35 * k;
    for (let i = 1; i < 12; i++) { ctx.beginPath(); ctx.arc(W / 2, H / 2, i * 0.62 * k, 0, 7); ctx.stroke(); }
    ctx.restore();
  }, { pxPerMm: 50 }), 0, 0.52, -28));
  g.add(at(box(6.5, 0.4, 20, M.plastic(0x1f2024, 0.45)), 0, 0.2, -10));
  g.add(at(decal(5.5, 18, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); ctx.strokeStyle = "#c9a45a"; ctx.lineWidth = 0.5 * k;
    for (const x of [1.6, 3.9]) { ctx.beginPath(); ctx.moveTo(x * k, 0); ctx.lineTo(x * k, H); ctx.stroke(); } }, { pxPerMm: 40 }), 0, 0.42, -10));
  g.add(at(box(7, 1.6, 4, M.plastic(0xd8d8d0, 0.4)), 0, 0.8, 1));
  for (const x of [-1.27, 1.27]) g.add(bentWire([[x, 0.8, 2.5], [x, 0.8, 4], [x, -8, 4]], 0.32, M.tin()));
  return g;
}

const OHMS = { "resistor-100": 100, "resistor-150": 150, "resistor-220": 220, "resistor-330": 330, "resistor-470": 470, "resistor-680": 680,
  "resistor-1k": 1000, "resistor-2k2": 2200, "resistor-4k7": 4700, "resistor-10k": 10000, "resistor-22k": 22000, "resistor-47k": 47000, "resistor-100k": 100000 };

export const BASIC = {
  "led": () => led5(0xff2a1a),
  "photoresistor": photoresistor,
  "fsr": fsr,
  "rgb-led": rgbLed,
  "pushbutton": pushbutton,
  "potentiometer-10k": potentiometer,
  "slide-switch": slideSwitch,
  "buzzer": buzzer,
  "dip-switch-8": dipSwitch,
  "ir-receiver": irReceiver,
  "ds18b20": () => to92(["DALLAS", "18B20"], { legLen: 8 }),
  "seven-segment": sevenSegment,
  "led-bar-graph": barGraph,
  "neopixel": neopixel,
  "dpdt-relay": relayKS2E,
  "attiny85": () => dip(8, ["ATTINY85", "20PU"]),
  "74hc165": () => dip(16, ["SN74HC165N", "TEXAS INSTR."]),
  "74hc595": () => dip(16, ["SN74HC595N", "TEXAS INSTR."]),
  "nlsf595": () => dip(16, ["NLSF595", "ON SEMI"]),
  ...Object.fromEntries(Object.entries(OHMS).map(([id, o]) => [id, () => resistor(o)])),
};
