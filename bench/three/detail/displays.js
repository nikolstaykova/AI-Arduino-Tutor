// Detailed displays and LED parts: glass panels with their bezel and
// flex cable, what they'd show when running, and the addressable LEDs,
// keypad and remote.
import { THREE, M, P, box, rbox, cyl, sphere, torus, at, lathe, extrude, tube, bentWire, decal, sideDecal, text,
  pcb, header, headerDown, soic, qfp, sot23, sot223, smdR, smdC, smdLed, elCap, silkAll, silkText } from "./kit.js";

const BLUE = 0x164a8a, BLACKPCB = 0x17181b, RED = 0xa8231b;
const labelsX = (names, z, { side = 1, size = 0.9, x0 = 0 } = {}) => (ctx, mm, k) => names.forEach((nm, i) => {
  const x = x0 - ((names.length - 1) * P) / 2 + i * P, [px, py] = mm(x, z + side * 1.6);
  text(ctx, nm, px, py, { size: size * k, color: "#f4f4f0", rot: -Math.PI / 2, align: side > 0 ? "right" : "left" });
});
const labelsZ = (names, x, { side = 1, size = 0.9 } = {}) => (ctx, mm, k) => names.forEach((nm, i) => {
  const z = -((names.length - 1) * P) / 2 + i * P, [px, py] = mm(x + side * 1.6, z);
  text(ctx, nm, px, py, { size: size * k, color: "#f4f4f0", align: side > 0 ? "left" : "right" });
});
function pinRowX(g, n, z, x0 = 0) {
  const h = headerDown(n); h.position.set(x0, 0, z); g.add(h);
  for (let i = 0; i < n; i++) { const x = x0 - ((n - 1) * P) / 2 + i * P; g.add(at(cyl(0.85, 0.85, 0.05, M.gold(), 20), x, 1.63, z)); g.add(at(cyl(0.55, 0.3, 0.7, M.tin(), 12), x, 1.95, z)); }
}
function pinRowZ(g, n, x) {
  const h = headerDown(n); h.rotation.y = Math.PI / 2; h.position.set(x, 0, 0); g.add(h);
  for (let i = 0; i < n; i++) { const z = -((n - 1) * P) / 2 + i * P; g.add(at(cyl(0.85, 0.85, 0.05, M.gold(), 20), x, 1.63, z)); g.add(at(cyl(0.55, 0.3, 0.7, M.tin(), 12), x, 1.95, z)); }
}
// a glass panel: the active area drawn by draw(ctx, W, H, k), glossy cover glass on top
function panel(w, d, activeW, activeD, draw, { glow = 0.6, frame = 0x0b0b0d, thick = 1.6, offX = 0, offZ = 0 } = {}) {
  const g = new THREE.Group();
  g.add(at(box(w, thick, d, M.plastic(frame, 0.3)), 0, thick / 2, 0));
  g.add(at(decal(activeW, activeD, draw, { pxPerMm: 16, glow, transparent: false, rough: 0.35 }), offX, thick + 0.01, offZ));
  const cover = box(w, 0.25, d, new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.02, transparent: true, opacity: 0.12, clearcoat: 1, depthWrite: false }));
  g.add(at(cover, 0, thick + 0.15, 0));
  return g;
}
// a little dashboard-style UI for the colour screens
function tftUI(ctx, W, H, k) {
  const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, "#1a2a4a"); gr.addColorStop(1, "#0c1222"); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  text(ctx, "CircuitQuest", W / 2, H * 0.12, { size: H * 0.08, color: "#ffffff" });
  ctx.fillStyle = "#d38c63"; ctx.fillRect(W * 0.08, H * 0.2, W * 0.84, H * 0.006);
  [["TEMP", "21.4°C", "#ff7a5a"], ["LIGHT", "642", "#ffd25a"], ["DIST", "38 cm", "#5ad2ff"]].forEach(([a, b, c], i) => {
    const y = H * (0.3 + i * 0.17);
    ctx.fillStyle = "rgba(255,255,255,0.07)"; ctx.beginPath(); ctx.roundRect(W * 0.08, y, W * 0.84, H * 0.13, H * 0.02); ctx.fill();
    text(ctx, a, W * 0.12, y + H * 0.065, { size: H * 0.045, color: "#aab4c8", align: "left" });
    text(ctx, b, W * 0.88, y + H * 0.065, { size: H * 0.07, color: c, align: "right" });
  });
  ctx.strokeStyle = "#5affa0"; ctx.lineWidth = H * 0.008; ctx.beginPath();
  for (let i = 0; i <= 40; i++) { const x = W * 0.08 + (i / 40) * W * 0.84, y = H * 0.88 - Math.sin(i / 3) * H * 0.04 - (i % 7) * H * 0.004; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
  ctx.stroke();
}

function tft(touch) {
  // 2.8" ILI9341 module on a red PCB with the SD slot and pin header
  const w = 86, d = 50;
  const g = pcb(w, d, RED, { holes: [[-40, -22, 1.6], [40, -22, 1.6], [-40, 22, 1.6], [40, 22, 1.6]], traces: 10, seed: 211,
    silk: silkAll(labelsZ(["VCC", "GND", "CS", "RESET", "DC", "MOSI", "SCK", "LED", "MISO"].concat(touch ? ["T_CLK", "T_CS", "T_DIN", "T_DO", "T_IRQ"] : []), -41, { side: 1, size: 0.75 }), silkText("2.8'' SPI", 30, 22, 1.2)) });
  const scr = panel(69.2, 50, 57.6, 43.2, tftUI, { offX: 2 });
  g.add(at(scr, 4, 1.6, 0));
  if (touch) g.add(at(box(69.2, 0.3, 50, new THREE.MeshPhysicalMaterial({ color: 0xd8e4f0, roughness: 0.05, transparent: true, opacity: 0.18, depthWrite: false })), 4, 3.55, 0));
  // the orange flex cable folding round the edge
  g.add(at(box(8, 0.2, 5, M.plastic(0xd98a1e, 0.4)), 40, 2.4, 0));
  const hd = headerDown(touch ? 14 : 9); hd.rotation.y = Math.PI / 2; g.add(at(hd, -42, 0, touch ? 0 : 0));
  return g;
}

function lcd1602() {
  // HD44780 16×2 with the black bezel, yellow-green backlight and the PCF8574 I²C backpack's pins
  const w = 80, d = 36;
  const g = pcb(w, d, 0x1d6b3c, { holes: [[-37.5, -15.5, 1.6], [37.5, -15.5, 1.6], [-37.5, 15.5, 1.6], [37.5, 15.5, 1.6]], traces: 8, seed: 223,
    silk: silkAll(labelsX(["VSS", "VDD", "V0", "RS", "RW", "E", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "A", "K"], -16.3, { side: 1, size: 0.6, x0: -18 })) });
  g.add(at(box(71.2, 7, 26, M.plastic(0x101012, 0.5)), 0, 5.1, 0));
  g.add(at(box(71.4, 1.6, 26.2, M.metal(0xb9bec6, 0.35)), 0, 8.4, 0));
  const lcd = decal(64.5, 16, (ctx, W, H, k) => {
    const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, "#b6d84a"); gr.addColorStop(1, "#98bf30"); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
    const rows = ["Hello, world!", "CircuitQuest :)"];
    const cw = W / 16.6, ch = H / 2.3;
    for (let r = 0; r < 2; r++) for (let c = 0; c < 16; c++) {
      const x0 = 0.3 * cw + c * cw, y0 = (0.15 + r * 1.1) * ch;
      ctx.fillStyle = "rgba(30,50,10,0.10)"; ctx.fillRect(x0, y0, cw * 0.88, ch * 0.92);
      const s = rows[r][c]; if (s && s !== " ") { ctx.fillStyle = "#1f3310"; ctx.font = `bold ${ch * 0.9}px monospace`; ctx.textBaseline = "top"; ctx.fillText(s, x0 + cw * 0.05, y0 + ch * 0.02); }
    }
  }, { pxPerMm: 24, glow: 0.35, transparent: false });
  g.add(at(lcd, 0, 9.22, 0));
  g.add(at(box(64.5, 0.2, 16, new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.02, transparent: true, opacity: 0.1, depthWrite: false })), 0, 9.3, 0));
  pinRowX(g, 16, -16.3, -18);
  // the two blobs of the controller chips-on-board under the display are hidden; show the backpack's trimpot side instead
  return g;
}

function nokia() {
  const w = 45, d = 45;
  const g = pcb(w, d, RED, { holes: [[-19.5, -19.5, 1.4], [19.5, -19.5, 1.4], [-19.5, 19.5, 1.4], [19.5, 19.5, 1.4]], traces: 6, seed: 227,
    silk: silkAll(labelsX(["RST", "CE", "DC", "DIN", "CLK", "VCC", "BL", "GND"], -20.5, { side: 1, size: 0.75 })) });
  const frame = new THREE.Group();
  frame.add(at(box(40, 4.5, 34, M.metal(0xc9ccd1, 0.3)), 0, 2.25, 0));
  for (const s of [-1, 1]) frame.add(at(box(3, 0.6, 2, M.metal(0xc9ccd1, 0.3)), s * 12, 4.7, 17.2));
  frame.add(at(box(36, 1.5, 28, M.plastic(0xf2f2ee, 0.5)), 0, 4.2, 0));
  const lcd = decal(34, 24, (ctx, W, H, k) => {
    ctx.fillStyle = "#a8c8c4"; ctx.fillRect(0, 0, W, H);
    const px = W / 84; ctx.fillStyle = "#16241f";
    ctx.font = `bold ${px * 9}px monospace`; ctx.textBaseline = "top";
    ["NOKIA 5110", "84x48 LCD", "", "CircuitQuest"].forEach((s, i) => ctx.fillText(s, px * 2, px * (2 + i * 11)));
    for (let i = 0; i < 20; i++) ctx.fillRect(px * (60 + (i % 5) * 4), px * (26 + Math.floor(i / 5) * 4), px * 3, px * 3);
  }, { pxPerMm: 24, glow: 0.2, transparent: false });
  frame.add(at(lcd, 0, 5, 1));
  g.add(at(frame, 0, 1.6, 2));
  pinRowX(g, 8, -20.5);
  return g;
}

function oled(size) {
  // 0.96" SSD1306 (128×64) or the 1.12" SH1107 (128×128)
  const sq = size === "sq";
  const w = sq ? 40 : 27.3, d = sq ? 40 : 27.8;
  const g = pcb(w, d, sq ? BLACKPCB : 0x1a1a3a, { holes: sq ? [[-17, -17, 1.4], [17, -17, 1.4], [-17, 17, 1.4], [17, 17, 1.4]] : [[-11.5, -11.8, 1], [11.5, -11.8, 1], [-11.5, 11.8, 1], [11.5, 11.8, 1]], traces: 6, seed: sq ? 229 : 233,
    silk: silkAll(labelsX(["GND", "VCC", "SCL", "SDA"], -d / 2 + 1.4, { side: 1, size: 0.75 })) });
  const glassW = sq ? 34 : 26.7, glassD = sq ? 30 : 19.3, aW = sq ? 28 : 21.7, aD = sq ? 28 : 10.9;
  const scr = panel(glassW, glassD, aW, aD, (ctx, W, H, k) => {
    ctx.fillStyle = "#020408"; ctx.fillRect(0, 0, W, H);
    const col = sq ? "#cfe8ff" : "#8fd8ff", px = W / 128;
    ctx.fillStyle = sq ? col : "#ffd84a"; if (!sq) ctx.fillRect(0, 0, W, px * 16);
    ctx.fillStyle = sq ? col : "#000"; ctx.font = `bold ${px * 12}px Arial`; ctx.textBaseline = "top";
    if (!sq) ctx.fillText("CircuitQuest", px * 4, px * 2);
    ctx.fillStyle = col; ctx.font = `bold ${px * 12}px Arial`;
    (sq ? ["CircuitQuest", "", "temp 21.4 C", "hum  48 %", ""] : ["temp 21.4 C", "hum  48 %"]).forEach((s, i) => ctx.fillText(s, px * 4, px * (sq ? 6 + i * 16 : 22 + i * 18)));
    ctx.strokeStyle = col; ctx.lineWidth = px; ctx.beginPath();
    for (let i = 0; i < 60; i++) { const x = px * (60 + i), y = px * ((sq ? 110 : 56) - Math.abs(Math.sin(i / 6)) * 10); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
    ctx.stroke();
  }, { glow: 1.1, frame: 0x0a0a0c, thick: 1.4, offZ: -1.5 });
  g.add(at(scr, 0, 1.6, 1.5));
  g.add(at(box(12, 0.15, 3, M.plastic(0xd98a1e, 0.4)), 0, 1.7, d / 2 - 3));
  pinRowX(g, 4, -d / 2 + 1.4);
  return g;
}

function epaper() {
  const w = 89.5, d = 38;
  const g = pcb(w, d, BLACKPCB, { holes: [[-42, -16, 1.5], [42, -16, 1.5], [-42, 16, 1.5], [42, 16, 1.5]], traces: 6, seed: 239,
    silk: silkAll(labelsZ(["BUSY", "RST", "DC", "CS", "CLK", "DIN", "GND", "VCC"], -41, { side: 1, size: 0.8 }), silkText("2.9inch e-Paper Module", 10, -17.2, 1.1)) });
  const scr = panel(79, 36.7, 66.9, 29.1, (ctx, W, H, k) => {
    ctx.fillStyle = "#e9e7e0"; ctx.fillRect(0, 0, W, H);
    text(ctx, "e-Paper 2.9\"", W * 0.05, H * 0.25, { size: H * 0.16, color: "#161616", align: "left" });
    text(ctx, "keeps its image with no power", W * 0.05, H * 0.5, { size: H * 0.08, color: "#161616", align: "left", weight: "normal" });
    ctx.fillStyle = "#b8261e"; ctx.fillRect(W * 0.05, H * 0.66, W * 0.3, H * 0.04);
    for (let i = 0; i < 7; i++) { ctx.fillStyle = "#161616"; ctx.fillRect(W * (0.65 + i * 0.04), H * (0.85 - (i % 4 + 1) * 0.1), W * 0.028, H * (i % 4 + 1) * 0.1); }
  }, { glow: 0, frame: 0xf2f1ec, thick: 1.2 });
  g.add(at(scr, 5, 1.6, 0));
  g.add(at(box(10, 0.15, 6, M.plastic(0xd98a1e, 0.4)), -34, 1.7, 0));
  const hd = headerDown(8); hd.rotation.y = Math.PI / 2; g.add(at(hd, -42.8, 0, 0));
  return g;
}

function palTV() {
  // a small vintage-style CRT set: wooden cabinet, curved screen showing test bars, knobs, rabbit-ear aerial
  const g = new THREE.Group();
  g.add(at(rbox(64, 48, 44, 4, M.plastic(0x8a5a36, 0.55)), 0, 24 + 4, 0));
  for (const s of [-1, 1]) for (const t of [-1, 1]) g.add(at(cyl(1.5, 1.2, 4, M.plastic(0x2a1a10)), s * 26, 2, t * 16));
  g.add(at(rbox(44, 36, 2, 4, M.plastic(0x1b1c20, 0.4)), -7, 29, 22));
  // the picture tube's face: slightly domed glass showing test bars
  const tex = (() => { const c = document.createElement("canvas"); c.width = 320; c.height = 240; const ctx = c.getContext("2d");
    ["#f0f0f0", "#d0d0d0", "#b0b0b0", "#909090", "#707070", "#505050", "#303030"].forEach((col, i) => { ctx.fillStyle = col; ctx.fillRect(i * 320 / 7, 0, 320 / 7 + 1, 170); });
    ctx.fillStyle = "#111"; ctx.fillRect(0, 170, 320, 70); ctx.fillStyle = "#eee"; ctx.font = "bold 34px Arial"; ctx.textAlign = "center"; ctx.fillText("PAL TEST", 160, 218);
    const g2 = ctx.createRadialGradient(160, 120, 60, 160, 120, 210); g2.addColorStop(0, "rgba(0,0,0,0)"); g2.addColorStop(1, "rgba(0,0,0,0.55)"); ctx.fillStyle = g2; ctx.fillRect(0, 0, 320, 240);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
  const face = new THREE.Mesh(new THREE.PlaneGeometry(40, 31, 16, 12), new THREE.MeshStandardMaterial({ map: tex, emissive: 0xffffff, emissiveMap: tex, emissiveIntensity: 0.5, roughness: 0.08 }));
  const pos = face.geometry.attributes.position;
  for (let i = 0; i < pos.count; i++) { const x = pos.getX(i) / 20, y = pos.getY(i) / 15.5; pos.setZ(i, 1.4 * (1 - x * x) * (1 - y * y)); }
  face.geometry.computeVertexNormals();
  g.add(at(face, -7, 29, 23.1));
  const knobs = [[24, 38], [24, 26]];
  for (const [x, y] of knobs) { const k = cyl(3.5, 3.5, 3, M.plastic(0xe8e2d0, 0.4), 32); k.rotation.x = Math.PI / 2; g.add(at(k, x, y, 23)); g.add(at(box(0.8, 5, 0.6, M.plastic(0x333)), x, y, 24.6)); }
  for (let i = 0; i < 6; i++) g.add(at(box(8, 0.8, 0.5, M.plastic(0x2a1a10)), 24, 12 + i * 2, 22.2));
  for (const s of [-1, 1]) g.add(bentWire([[s * 2, 52, -6], [s * 22, 88, -12]], 0.6, M.chrome()));
  g.add(at(cyl(5, 6, 3, M.plastic(0x1b1c20)), 0, 53.5, -6));
  return g;
}

function ledMatrix() {
  // an 8×8 WS2812B panel on a flexible black PCB
  const g = new THREE.Group();
  g.add(at(box(65, 0.4, 65, M.mask(BLACKPCB)), 0, 0.2, 0));
  const heart = ["01100110", "11111111", "11111111", "11111111", "01111110", "00111100", "00011000", "00000000"];
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
    const on = heart[y][x] === "1", c = on ? new THREE.Color().setHSL(0.97 - y * 0.02, 0.9, 0.55).getHex() : 0;
    const px = -28 + x * 8, pz = -28 + y * 8;
    g.add(at(box(5, 1.6, 5, M.plastic(0xf8f8f4, 0.35)), px, 1.2, pz));
    g.add(at(cyl(2.2, 2.2, 0.1, on ? M.glow(c, 1.2) : M.epoxy(0xfff2d0), 24), px, 2.05, pz));
    g.add(at(smdC("0603"), px + 3.4, 0.4, pz));
  }
  g.add(bentWire([[-32, 0.4, 30], [-38, 0.4, 30]], 0.6, M.plastic(0xd0342c)));
  g.add(bentWire([[-32, 0.4, 28], [-38, 0.4, 28]], 0.6, M.plastic(0x1b1c20)));
  g.add(bentWire([[-32, 0.4, 26], [-38, 0.4, 26]], 0.6, M.plastic(0x3ae060)));
  return g;
}

function ledRing() {
  const g = new THREE.Group(), R0 = 15.5, R1 = 22;
  const ring = new THREE.Shape(); ring.absarc(0, 0, R1, 0, Math.PI * 2, false);
  const hole = new THREE.Path(); hole.absarc(0, 0, R0, 0, Math.PI * 2, true); ring.holes.push(hole);
  const board = new THREE.Mesh(new THREE.ExtrudeGeometry(ring, { depth: 1.6, bevelEnabled: false, curveSegments: 64 }), M.mask(BLACKPCB));
  board.rotation.x = -Math.PI / 2; g.add(board);
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2, x = Math.cos(a) * 18.8, z = Math.sin(a) * 18.8;
    const c = new THREE.Color().setHSL(i / 16, 1, 0.45).getHex();
    g.add(at(box(5, 1.6, 5, M.plastic(0xf8f8f4, 0.35)), x, 2.4, z, 0, -a));
    g.add(at(cyl(2.2, 2.2, 0.1, M.glow(c, 1.2), 24), x, 3.25, z));
  }
  for (const [a, t] of [[Math.PI / 2 - 0.2, "IN"], [Math.PI / 2 + 0.2, "OUT"]]) g.add(at(cyl(0.9, 0.9, 0.05, M.gold(), 16), Math.cos(a) * 17, 1.62, Math.sin(a) * 17));
  return g;
}

function ledStrip() {
  const g = new THREE.Group(), n = 5, pitch = 16.6, L = n * pitch;
  g.add(at(box(L, 0.3, 10, M.plastic(0xf6f6f2, 0.5)), 0, 0.15, 0));
  // a silicone sleeve
  g.add(at(rbox(L, 3.4, 12, 1.4, new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.15, transparent: true, opacity: 0.22, depthWrite: false })), 0, 1.4, 0));
  for (let i = 0; i < n; i++) {
    const x = -L / 2 + pitch / 2 + i * pitch, c = new THREE.Color().setHSL(i / n, 1, 0.45).getHex();
    g.add(at(box(5, 1.6, 5, M.plastic(0xf8f8f4, 0.35)), x, 1.1, 0));
    g.add(at(cyl(2.2, 2.2, 0.1, M.glow(c, 1.2), 24), x, 1.95, 0));
    g.add(at(smdC("0603"), x + 4, 0.3, 2.5)); g.add(at(smdR("0603", "330"), x - 4, 0.3, 2.5));
    // copper cut pads between LEDs
    if (i) for (let p = 0; p < 3; p++) g.add(at(box(1.4, 0.05, 1.8, M.copper()), x - pitch / 2, 0.32, -3 + p * 3));
    g.add(at(decal(3, 1, (ctx, W, H) => { ctx.clearRect(0, 0, W, H); text(ctx, "→", W / 2, H / 2, { size: H * 0.9, color: "#333" }); }, { pxPerMm: 40 }), x, 0.32, -3.6));
  }
  return g;
}

function keypad() {
  const g = new THREE.Group();
  g.add(at(rbox(69, 0.8, 76, 1.5, M.plastic(0x141417, 0.5)), 0, 0.4, 0));
  const keys = "123A456B789C*0#D";
  for (let i = 0; i < 16; i++) {
    const x = -24 + (i % 4) * 16, z = -26 + Math.floor(i / 4) * 17.5, k = keys[i], letter = "ABCD".includes(k), sym = "*#".includes(k);
    const col = letter ? "#c9443a" : sym ? "#2c2c30" : "#2a5ec9";
    g.add(at(decal(13, 14.5, (ctx, W, H, kk) => {
      ctx.fillStyle = "#f4f3ee"; ctx.beginPath(); ctx.roundRect(0, 0, W, H, 1.2 * kk); ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.12)"; ctx.lineWidth = 0.3 * kk; ctx.stroke();
      ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(1.2 * kk, 1.2 * kk, W - 2.4 * kk, H - 2.4 * kk, 1 * kk); ctx.fill();
      text(ctx, k, W / 2, H / 2 + 0.3 * kk, { size: 7 * kk, color: "#ffffff" });
    }, { pxPerMm: 24, transparent: true, rough: 0.35 }), x, 0.82, z));
    const dome = sphere(5, new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.1, transparent: true, opacity: 0.1, depthWrite: false }), 24, 8);
    dome.scale.set(1.2, 0.08, 1.3); g.add(at(dome, x, 0.82, z));
  }
  // the flat ribbon tail with its 8-way connector
  g.add(at(box(20, 0.25, 80, M.plastic(0xd8d6cc, 0.6)), 0, 0.12, 76));
  g.add(at(box(22, 2.5, 3, M.plastic(0x141417, 0.5)), 0, 1.25, 117));
  for (let i = 0; i < 8; i++) g.add(at(box(0.9, 0.3, 80, M.plastic(0xa8a69a, 0.5)), -8.75 + i * 2.5, 0.2, 76));
  return g;
}

function irRemote() {
  const g = new THREE.Group();
  g.add(at(rbox(40, 7, 86, 3, M.plastic(0x141417, 0.5)), 0, 3.5, 0));
  g.add(at(rbox(38, 1, 84, 2.5, M.plastic(0x1f2024, 0.35)), 0, 7, 0));
  const labels = ["⏻", "MENU", "🔇", "MODE", "+", "↺", "◀◀", "▶", "▶▶", "EQ", "–", "U/SD", "0", "100+", "200+", "1", "2", "3", "4", "5", "6", "7", "8", "9"];
  labels.forEach((t, i) => {
    const x = -12.5 + (i % 3) * 12.5, z = -34 + Math.floor(i / 3) * 9.4;
    const red = i === 0, b = rbox(9.5, 1.6, 6.8, 2.2, M.rubber(red ? 0xc9443a : 0x3a3c42));
    g.add(at(b, x, 7.8, z));
    g.add(at(decal(8.5, 6, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, t, W / 2, H / 2, { size: (t.length > 3 ? 1.8 : 2.8) * k, color: "#ececec" }); }, { pxPerMm: 30 }), x, 8.62, z));
  });
  const lens = sphere(3, M.epoxy(0x3a2020), 24, 12); lens.scale.set(1, 0.6, 0.6); g.add(at(lens, 0, 4, -43));
  g.add(at(decal(30, 6, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "CAR MP3", W / 2, H / 2, { size: 3 * k, color: "#c8c8c8" }); }, { pxPerMm: 30 }), 0, 7.52, 38));
  return g;
}

export const DISPLAYS = {
  "ili9341-lcd": () => tft(false),
  "ili9341-touch-lcd": () => tft(true),
  "lcd1602": lcd1602,
  "nokia-5110-screen": nokia,
  "oled-ssd1306": () => oled("wide"),
  "sh1107-oled": () => oled("sq"),
  "epaper-2in9": epaper,
  "pal-tv": palTV,
  "led-matrix": ledMatrix,
  "led-ring": ledRing,
  "led-strip": ledStrip,
  "membrane-keypad": keypad,
  "ir-remote": irRemote,
};
