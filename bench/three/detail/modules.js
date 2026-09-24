// Detailed sensor and breakout modules — each on its real board colour, with
// the pin names printed next to the header, and the parts you'd see on the
// real thing (trimpots, comparator chips, indicator LEDs, domes, cans …).
import { THREE, M, P, box, rbox, cyl, sphere, torus, at, group, lathe, extrude, tube, bentWire, decal, sideDecal, text,
  pcb, header, headerDown, qfp, soic, sot23, sot223, smdR, smdC, smdLed, elCap, crystalSMD, crystalHC49, tactSMD, trimpot3362,
  screwTerminal, jst, to92, knurledShaft, silkAll, silkText, silkRect, insulatedWire, dip, usb } from "./kit.js";

const labelsZ = (names, x, { side = 1, size = 0.9, z0 = 0 } = {}) => (ctx, mm, k) => names.forEach((nm, i) => {
  const z = z0 - ((names.length - 1) * P) / 2 + i * P, [px, py] = mm(x + side * 1.6, z);
  text(ctx, nm, px, py, { size: size * k, color: "#f4f4f0", align: side > 0 ? "left" : "right" });
});
const labelsX = (names, z, { side = 1, size = 0.9, x0 = 0 } = {}) => (ctx, mm, k) => names.forEach((nm, i) => {
  const x = x0 - ((names.length - 1) * P) / 2 + i * P, [px, py] = mm(x, z + side * 1.6);
  text(ctx, nm, px, py, { size: size * k, color: "#f4f4f0", rot: -Math.PI / 2, align: side > 0 ? "right" : "left" });
});
function rowPins(g, n, z, x0 = 0) {
  const h = headerDown(n); h.position.set(x0, 0, z); g.add(h);
  for (let i = 0; i < n; i++) { const x = x0 - ((n - 1) * P) / 2 + i * P; g.add(at(cyl(0.85, 0.85, 0.05, M.gold(), 20), x, 1.63, z)); g.add(at(cyl(0.55, 0.3, 0.7, M.tin(), 12), x, 1.95, z)); }
}
const BLUE = 0x164a8a, GREEN = 0x1d6b3c, PURPLE = 0x5b2a9a, BLACKPCB = 0x17181b, RED = 0xb8261e;

// the typical "sensor with a comparator" module: LM393, trimpot, power + signal LEDs
function comparatorBits(g, x, z) {
  g.add(at(soic(8, ["LM393"]), x, 1.6, z));
  g.add(at(trimpot3362(), x - 8, 1.6, z));
  g.add(at(smdLed(0xff3a2a), x + 5, 1.6, z - 3)); g.add(at(smdLed(0x3ae060), x + 5, 1.6, z + 3));
  for (let i = 0; i < 4; i++) g.add(at(smdR("0603", "103"), x + 1 - i * 1.6, 1.6, z + 4, 0, Math.PI / 2));
}

function hcsr04() {
  const w = 45, d = 20;
  const g = pcb(w, d, BLUE, { holes: [[-20.5, -8, 1], [20.5, -8, 1], [-20.5, 8, 1], [20.5, 8, 1]], traces: 16, seed: 71,
    silk: silkAll(silkText("HC-SR04", 0, -7.4, 1.6), silkText("T", -13, -8.4, 1.2), silkText("R", 13, -8.4, 1.2), labelsX(["Vcc", "Trig", "Echo", "Gnd"], 8.9, { side: -1 })) });
  for (const x of [-13, 13]) {
    const t = new THREE.Group();
    t.add(lathe([[0, 0], [8, 0], [8, 12], [7.4, 12.2], [7.4, 11.4], [0, 11.4]], M.metal(0xd4d7dc, 0.25), 64));
    t.add(at(cyl(7.3, 7.3, 0.1, M.plastic(0x101012, 0.9), 48), 0, 11.5, 0));
    // the fine mesh: a grid decal
    t.add(at(decal(14.6, 14.6, (ctx, W, H, k) => {
      ctx.clearRect(0, 0, W, H); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, W / 2, 0, 7); ctx.clip();
      ctx.fillStyle = "#1a1b1f"; ctx.fillRect(0, 0, W, H); ctx.strokeStyle = "#5a5d63"; ctx.lineWidth = 0.1 * k;
      for (let i = 0; i < W; i += 0.55 * k) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke(); }
      ctx.restore();
    }, { pxPerMm: 40 }), 0, 11.6, 0));
    g.add(at(t, x, 1.6, -1));
  }
  g.add(at(crystalHC49("4.000"), 0, 1.6, -1, 0, Math.PI / 2));
  rowPins(g, 4, 8.9);
  return g;
}

function dht22() {
  const g = new THREE.Group();
  g.add(at(rbox(15.1, 7.7, 25.1, 0.8, M.plastic(0xf2f1ec, 0.55)), 0, 3.85, 0));
  // the grille: a grid of rectangular slots
  for (let r = 0; r < 6; r++) for (let c = 0; c < 4; c++) g.add(at(box(2.3, 0.4, 1.6, M.plastic(0x2a2a2c, 0.9)), -4.8 + c * 3.2, 7.55, -8 + r * 2.6));
  g.add(at(decal(12, 4, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "AM2302", W / 2, H / 2, { size: 1.6 * k, color: "#555" }); }, { pxPerMm: 50 }), 0, 7.71, 9.5));
  g.add(at(cyl(1.6, 1.6, 7.8, M.plastic(0xf2f1ec)), 0, 3.85, -13.4));
  g.add(at(cyl(1.3, 1.3, 7.9, M.plastic(0x101010, 1)), 0, 3.85, -13.4));
  for (let i = 0; i < 4; i++) g.add(bentWire([[-3.81 + i * P, 1.5, 12.5], [-3.81 + i * P, 1.5, 15], [-3.81 + i * P, -6, 15]], 0.3, M.tin()));
  return g;
}

function bmp180() {
  const g = pcb(13, 10, PURPLE, { holes: [[-4.5, -2.5, 1.2]], traces: 6, seed: 73, silk: silkAll(silkText("GY-68", 2, -3, 1), labelsX(["VIN", "GND", "SCL", "SDA"], 3.8, { side: -1, size: 0.7 })) });
  g.add(at(box(3.6, 0.9, 3.6, M.metal(0xc9ccd1, 0.35)), 1.5, 2.05, -1.5));
  g.add(at(cyl(0.4, 0.4, 0.06, M.plastic(0x111)), 2.3, 2.52, -1.5));
  g.add(at(sot23("662K"), -2, 1.6, -1.2));
  g.add(at(smdC("0603"), 4.5, 1.6, -1)); g.add(at(smdR("0603", "472"), 4.5, 1.6, 0.6)); g.add(at(smdR("0603", "472"), -4.5, 1.6, 0.5));
  rowPins(g, 4, 3.8);
  return g;
}

function mpu6050() {
  const g = pcb(21, 16, BLUE, { holes: [[-8.5, -5.5, 1.5], [8.5, -5.5, 1.5]], traces: 10, seed: 79,
    silk: silkAll(silkText("GY-521", 0, -5.5, 1.1), labelsX(["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"], 6.6, { side: -1, size: 0.65 }),
      (ctx, mm, k) => { const [x, y] = mm(-6, -1); ctx.lineWidth = 0.15 * k; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 3 * k, y); ctx.moveTo(x, y); ctx.lineTo(x, y - 3 * k); ctx.stroke(); text(ctx, "X", x + 3.6 * k, y, { size: 0.8 * k }); text(ctx, "Y", x, y - 3.6 * k, { size: 0.8 * k }); }) });
  g.add(at(qfp(4, ["MPU-6050", "C3417"], { legs: false }), 1, 1.6, -0.5));
  g.add(at(sot23("LDO"), 6.5, 1.6, -3)); g.add(at(smdLed(0x3ae060), -7, 1.6, 2));
  for (let i = 0; i < 5; i++) g.add(at(smdC("0603"), -3 + i * 1.6, 1.6, 3.2, 0, Math.PI / 2));
  rowPins(g, 8, 6.6);
  return g;
}

function ds1307() {
  const g = pcb(27, 28, BLUE, { holes: [[-10.5, -11, 1.5], [10.5, -11, 1.5]], traces: 12, seed: 83,
    silk: silkAll(silkText("Tiny RTC", 0, -11, 1.4), labelsZ(["SQ", "DS", "SCL", "SDA", "VCC", "GND", "BAT"], -11.5, { side: 1, size: 0.8 })) });
  const bat = new THREE.Group();
  bat.add(at(box(22, 1, 22, M.plastic(0x17181b)), 0, 0.5, 0));
  bat.add(at(lathe([[0, 0], [10, 0], [10, 3.2], [9.6, 3.2], [9.6, 2.9], [0, 2.9]], M.metal(0xd4d7dc, 0.22), 64), 0, 1, 0));
  bat.add(at(decal(16, 8, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "CR2032", W / 2, H * 0.35, { size: 2 * k, color: "#6d7178" }); text(ctx, "3V  LITHIUM", W / 2, H * 0.72, { size: 1.2 * k, color: "#6d7178" }); }, { pxPerMm: 40 }), 0, 4.21, 0));
  bat.add(at(box(6, 0.4, 3, M.steel()), 0, 4.4, -9));
  g.add(at(bat, 3, 1.6, 2, 0, Math.PI));
  g.add(at(soic(8, ["DS1307", "Z+"]), -4, 1.6, -6));
  g.add(at(soic(8, ["AT24C32"]), 6, 1.6, -7));
  g.add(at(crystalSMD(), -9, 1.6, -3));
  const h = headerDown(7); h.rotation.y = Math.PI / 2; g.add(at(h, -12.3, 0, 0));
  return g;
}

function hx711() {
  const g = pcb(34, 20, GREEN, { holes: [], traces: 12, seed: 89,
    silk: silkAll(silkText("HX711", 0, -7.5, 1.4), labelsZ(["E+", "E-", "A-", "A+", "B-", "B+"], 15, { side: -1, size: 0.8 }), labelsZ(["GND", "DT", "SCK", "VCC"], -15, { side: 1, size: 0.8 })) });
  g.add(at(soic(16, ["HX711", "AVIA"]), 1, 1.6, 0));
  g.add(at(sot23("S8050"), -7, 1.6, 4)); g.add(at(elCap(2, 3.5, { smd: true }), 8, 1.6, 5));
  for (let i = 0; i < 6; i++) g.add(at(smdR("0603", "102"), -6 + i * 2, 1.6, -4.5, 0, Math.PI / 2));
  const L = headerDown(4); L.rotation.y = Math.PI / 2; g.add(at(L, -15.5, 0, 0));
  const R = headerDown(6); R.rotation.y = Math.PI / 2; g.add(at(R, 15.5, 0, 0));
  return g;
}

function mfrc522() {
  const g = pcb(60, 40, BLUE, { holes: [[-25, -15, 1.6], [25, -15, 1.6], [-19, 15, 1.6], [19, 15, 1.6]], traces: 6, seed: 97,
    silk: silkAll(silkText("RFID-RC522", 10, -8, 1.8), labelsX(["SDA", "SCK", "MOSI", "MISO", "IRQ", "GND", "RST", "3.3V"], 17.5, { side: -1, size: 0.8 })) });
  // the coil antenna: 4 turns of gold trace around the free half
  g.add(at(decal(56, 24, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H); ctx.strokeStyle = "#e0bd72"; ctx.lineWidth = 0.9 * k;
    for (let i = 0; i < 4; i++) { const m = (1 + i * 1.7) * k; ctx.beginPath(); ctx.roundRect(m, m, W - 2 * m, H - 2 * m, 2 * k); ctx.stroke(); }
  }, { pxPerMm: 30, metal: 0.6, rough: 0.35 }), 0, 1.62, -6));
  g.add(at(qfp(5, ["MFRC522", "NXP"], { legs: false }), -10, 1.6, 8));
  g.add(at(crystalSMD("27.12"), -3, 1.6, 9));
  for (let i = 0; i < 6; i++) g.add(at(smdC("0603"), -18 + i * 2, 1.6, 12, 0, Math.PI / 2));
  g.add(at(smdLed(0xff3a2a), 18, 1.6, 10));
  const h = header(8, { rightAngle: true }); g.add(at(h, 0, 1.6, 17.5));
  return g;
}

function microsd() {
  const g = pcb(42, 24, BLUE, { holes: [[-18, -9, 1.5], [18, -9, 1.5], [-18, 9, 1.5], [18, 9, 1.5]], traces: 10, seed: 101,
    silk: silkAll(silkText("MicroSD Card Adapter", 6, -9.5, 1.1), labelsZ(["GND", "VCC", "MISO", "MOSI", "SCK", "CS"], -19, { side: 1, size: 0.8 })) });
  const slot = new THREE.Group();
  slot.add(at(rbox(15, 1.8, 15, 0.3, M.metal(0xd0d3d8, 0.3)), 0, 0.9, 0));
  for (let i = 0; i < 6; i++) slot.add(at(box(0.8, 0.05, 2, M.plastic(0x222)), -4 + i * 1.6, 1.82, -5));
  const card = new THREE.Group(); card.add(rbox(11, 0.8, 15, 0.4, M.plastic(0x1b1c20, 0.5)));
  card.add(at(decal(10, 6, (ctx, W, H, k) => { ctx.fillStyle = "#c9443a"; ctx.fillRect(0, 0, W, H); text(ctx, "microSD", W / 2, H * 0.4, { size: 1.8 * k }); text(ctx, "16GB", W / 2, H * 0.78, { size: 1.4 * k }); }, { pxPerMm: 40, transparent: false }), 0, 0.41, 2));
  slot.add(at(card, 0, 2.3, 5));
  g.add(at(slot, 8, 1.6, -1));
  g.add(at(sot223("AMS1117"), -8, 1.6, -4)); g.add(at(soic(14, ["LVC125A"]), -8, 1.6, 4));
  const h = headerDown(6); h.rotation.y = Math.PI / 2; g.add(at(h, -19.5, 0, 0));
  return g;
}

function gasSensor() {
  const g = pcb(32, 22, BLUE, { holes: [[-13, -8, 1.5], [13, -8, 1.5]], traces: 10, seed: 103, silk: silkAll(silkText("MQ-2", -11, 8, 1.1), labelsX(["VCC", "GND", "DO", "AO"], 9.5, { side: -1, size: 0.8 })) });
  const s = new THREE.Group();
  s.add(lathe([[0, 0], [10, 0], [10, 1.2], [9.4, 1.4], [9.4, 3], [0, 3]], M.plastic(0xd9a13a, 0.4), 64));
  s.add(at(cyl(9.2, 9.2, 8, M.metal(0xc9ccd1, 0.3), 64), 0, 7, 0));
  // stainless mesh top: a woven texture on the can
  const meshTex = decal(18, 18, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, W / 2, 0, 7); ctx.clip();
    ctx.fillStyle = "#6a6e75"; ctx.fillRect(0, 0, W, H); ctx.strokeStyle = "#d6d8dc"; ctx.lineWidth = 0.18 * k;
    for (let i = 0; i < W; i += 0.45 * k) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke(); }
    ctx.restore();
  }, { pxPerMm: 40, metal: 0.8, rough: 0.4 });
  s.add(at(meshTex, 0, 11.02, 0));
  g.add(at(s, -3, 1.6, -1));
  g.add(at(soic(8, ["LM393"]), 11, 1.6, -2, 0, Math.PI / 2));
  g.add(at(trimpot3362(), 10, 1.6, 4.5));
  g.add(at(smdLed(0xff3a2a), 5, 1.6, 7)); g.add(at(smdLed(0x3ae060), 1, 1.6, 7));
  rowPins(g, 4, 9.5);
  return g;
}

function sensorWithProbe(kind) {
  // NTC thermistor / LDR on a KY-style 3- or 4-pin module
  const pins = kind === "ntc" ? ["GND", "VCC", "OUT"] : ["VCC", "GND", "DO", "AO"];
  const w = kind === "ntc" ? 30 : 32, d = kind === "ntc" ? 15 : 14;
  const g = pcb(w, d, BLUE, { holes: [[w / 2 - 3, 0, 1.5]], traces: 8, seed: kind === "ntc" ? 107 : 109,
    silk: silkAll(silkText(kind === "ntc" ? "NTC" : "LDR", -2, -4.5, 1.1), labelsZ(pins, -w / 2 + 1.5, { side: 1, size: 0.75 })) });
  const h = headerDown(pins.length); h.rotation.y = Math.PI / 2; g.add(at(h, -w / 2 + 1.3, 0, 0));
  if (kind === "ntc") {
    const bead = sphere(1.4, M.gloss(0x1c1d21), 24, 16); bead.scale.set(1, 1.3, 1); g.add(at(bead, w / 2 - 7, 6.5, 0));
    for (const s of [-0.5, 0.5]) g.add(bentWire([[w / 2 - 7 + s, 5.2, 0], [w / 2 - 7 + s * 2.54, 3, 0], [w / 2 - 7 + s * 2.54, 1.6, 0]], 0.18, M.tin()));
    g.add(at(smdR("0805", "103"), 0, 1.6, 3)); g.add(at(soic(8, ["LM393"]), 2, 1.6, -1));
  } else {
    const ldr = new THREE.Group();
    ldr.add(cyl(2.6, 2.6, 1.8, M.ceramic(0xe6d7b0), 32));
    ldr.add(at(decal(4.8, 4.8, (ctx, W, H, k) => {
      ctx.clearRect(0, 0, W, H); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, W / 2, 0, 7); ctx.clip(); ctx.fillStyle = "#e6d7b0"; ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "#b5522a"; ctx.lineWidth = 0.45 * k; ctx.beginPath(); let y = 0.6 * k, dir = 1; ctx.moveTo(0.4 * k, y);
      while (y < H - 0.6 * k) { ctx.lineTo(dir > 0 ? W - 0.4 * k : 0.4 * k, y); y += 0.7 * k; ctx.lineTo(dir > 0 ? W - 0.4 * k : 0.4 * k, y); dir = -dir; }
      ctx.stroke(); ctx.restore();
    }, { pxPerMm: 60 }), 0, 0.91, 0));
    ldr.add(at(cyl(2.62, 2.62, 0.3, M.glass(0xffffff, 0.3), 32), 0, 1, 0));
    g.add(at(ldr, w / 2 - 6, 7, 0));
    for (const s of [-1, 1]) g.add(bentWire([[w / 2 - 6 + s * 1.7, 6, 0], [w / 2 - 6 + s * 1.7, 1.6, 0]], 0.2, M.tin()));
    comparatorBits(g, -2, 0);
  }
  return g;
}

function pir() {
  const g = pcb(32.3, 24.3, GREEN, { holes: [[-14, -10, 1], [14, -10, 1], [-14, 10, 1], [14, 10, 1]], traces: 10, seed: 113 });
  // the white Fresnel dome with its faceted lens
  const dome = new THREE.Group();
  const facets = new THREE.SphereGeometry(11.5, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2);
  dome.add(mesh2(facets, new THREE.MeshPhysicalMaterial({ color: 0xf6f5ef, roughness: 0.55, flatShading: true, transmission: 0.15, thickness: 1 })));
  dome.add(at(box(24, 3, 24, M.plastic(0xf6f5ef, 0.5)), 0, -1.5, 0));
  g.add(at(dome, 0, 4.6, 0));
  // underside: the BISS0001 chip, two orange trimpots, the jumper
  const under = new THREE.Group();
  under.add(at(soic(16, ["BISS0001"]), 0, 0, 0));
  for (const x of [-9, 9]) { const p = trimpot3362({ color: 0xe07a1e }); p.scale.setScalar(0.8); under.add(at(p, x, 0, 6)); }
  under.add(at(header(3), -10, 0, -7));
  under.rotation.x = Math.PI; under.position.y = -0.02; g.add(under);
  const pins = header(3, { dir: "down" }); pins.rotation.x = Math.PI; g.add(at(pins, 0, 0, 10.5));
  return g;
}
const mesh2 = (geo, mat) => { const m = new THREE.Mesh(geo, mat); m.castShadow = m.receiveShadow = true; return m; };

function relayModule() {
  const g = pcb(50, 26, BLUE, { holes: [[-22, -10, 1.5], [22, -10, 1.5], [-22, 10, 1.5], [22, 10, 1.5]], traces: 10, seed: 127,
    silk: silkAll(silkText("1 Relay Module", -8, -10.5, 1.2), labelsZ(["DC+", "DC-", "IN"], -23, { side: 1, size: 0.8 }), silkText("NO", 23, -5, 0.9), silkText("COM", 23, 0, 0.9), silkText("NC", 23, 5, 0.9),
      silkText("High/Low Level Trigger", -6, 10.5, 0.9)) });
  const relay = new THREE.Group();
  relay.add(at(rbox(19, 15.5, 15.5, 0.3, M.plastic(0x1f5fd0, 0.4)), 0, 7.75, 0));
  relay.add(at(decal(17, 13.5, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    text(ctx, "SONGLE", W / 2, 1.8 * k, { size: 1.8 * k });
    ["10A 250VAC  10A 125VAC", "10A 30VDC   10A 28VDC"].forEach((s, i) => text(ctx, s, W / 2, (4.4 + i * 1.6) * k, { size: 1 * k, weight: "normal" }));
    text(ctx, "SRD-05VDC-SL-C", W / 2, 8.4 * k, { size: 1.4 * k });
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 0.15 * k; ctx.strokeRect(1 * k, 9.8 * k, 5 * k, 2.8 * k); text(ctx, "CE", 3.5 * k, 11.2 * k, { size: 1.6 * k });
  }, { pxPerMm: 40 }), 0, 15.51, 0));
  g.add(at(relay, 2, 1.6, 0));
  g.add(at(screwTerminal(3), 20, 1.6, 0, 0, -Math.PI / 2));
  g.add(at(to92("S8050"), -12, 1.6, -4));
  g.children.at(-1).scale.setScalar(0.5);
  g.add(at(sot23("M7"), -12, 1.6, 4));
  g.add(at(smdLed(0xff3a2a), -16, 1.6, -6)); g.add(at(smdLed(0x3ae060), -16, 1.6, 6));
  const h = headerDown(3); h.rotation.y = Math.PI / 2; g.add(at(h, -23.5, 0, 0));
  return g;
}

function ky040() {
  const g = pcb(32, 19, BLACKPCB, { holes: [[9, -7, 1.3], [9, 7, 1.3]], traces: 6, seed: 131, silk: silkAll(labelsZ(["GND", "+", "SW", "DT", "CLK"], -14, { side: 1, size: 0.8 }), silkText("KY-040", 10, 0, 1, { rot: -Math.PI / 2 })) });
  const enc = new THREE.Group();
  enc.add(at(box(12, 6.5, 13.2, M.metal(0xc9ccd1, 0.3)), 0, 3.25, 0));
  enc.add(at(box(12.4, 6.6, 1, M.plastic(0x1b1c20)), 0, 3.3, 0));
  for (const s of [-1, 1]) enc.add(at(box(2, 5, 0.5, M.metal(0xc9ccd1, 0.3)), s * 6.2, 2, 0));
  const bush = cyl(3.5, 3.5, 5, M.chrome(), 40); enc.add(at(bush, 0, 9, 0));
  for (let i = 0; i < 8; i++) enc.add(at(torus(3.52, 0.1, M.chrome(), 6, 40), 0, 7 + i * 0.55, 0, Math.PI / 2));
  const shaft = new THREE.Group(); shaft.add(cyl(3, 3, 12, M.metal(0xe0e3e7, 0.3), 32)); shaft.add(at(box(6.2, 7, 1.2, M.plastic(0x222)), 0, 2.6, 0));
  for (let i = 0; i < 20; i++) { const a = (i / 20) * Math.PI * 2; shaft.add(at(box(0.3, 7, 0.3, M.metal(0xe0e3e7, 0.3)), Math.cos(a) * 3, 2.6, Math.sin(a) * 3)); }
  enc.add(at(shaft, 0, 17.5, 0));
  g.add(at(enc, 3, 1.6, 0));
  g.add(at(smdR("0603", "103"), -8, 1.6, -5)); g.add(at(smdR("0603", "103"), -8, 1.6, 0)); g.add(at(smdR("0603", "103"), -8, 1.6, 5));
  const h = header(5, { rightAngle: true }); g.add(at(h, -14.5, 1.6, 0, 0, -Math.PI / 2));
  return g;
}

function joystick() {
  const g = pcb(34, 26, BLACKPCB, { holes: [[-14, -10, 1.6], [14, -10, 1.6], [-14, 10, 1.6], [14, 10, 1.6]], traces: 6, seed: 137, silk: silkAll(labelsX(["GND", "+5V", "VRx", "VRy", "SW"], 11.5, { side: -1, size: 0.8 })) });
  const j = new THREE.Group();
  j.add(at(box(16, 9, 16, M.plastic(0x1b1c20, 0.6)), 0, 4.5, 0));
  for (const [x, z, ry] of [[9.5, 0, 0], [0, 9.5, Math.PI / 2]]) { const pot = new THREE.Group(); pot.add(box(3, 8, 9, M.plastic(0x1f5fd0, 0.5))); pot.add(at(box(1, 6, 7, M.metal(0xc9ccd1, 0.3)), 1.8, 0, 0)); j.add(at(pot, x, 4.5, z, 0, ry)); }
  j.add(at(box(16.2, 1, 16.2, M.metal(0xc9ccd1, 0.3)), 0, 9.3, 0));
  const dome = sphere(7, M.plastic(0x1b1c20, 0.5), 40, 20); dome.scale.set(1, 0.45, 1); j.add(at(dome, 0, 9.8, 0));
  j.add(at(cyl(2.3, 2.3, 8, M.plastic(0x1b1c20, 0.5)), 0, 13, 0));
  const cap = lathe([[0, 0], [2.4, 0], [8.5, 1], [9.3, 2], [9.3, 4], [8.4, 5.4], [6, 5.8], [0, 5.3]], M.rubber(0x202124), 64);
  j.add(at(cap, 0, 16, 0));
  for (let i = 0; i < 24; i++) { const a = (i / 24) * Math.PI * 2; j.add(at(box(0.6, 1.8, 0.8, M.rubber(0x2c2d30)), Math.cos(a) * 9.1, 19, Math.sin(a) * 9.1, 0, -a)); }
  g.add(at(j, 0, 1.6, -1.5));
  const h = header(5, { rightAngle: true }); g.add(at(h, 0, 1.6, 11.5));
  return g;
}

function tm1637() {
  const g = pcb(42, 24, BLUE, { holes: [[-19, -9.5, 1.3], [19, -9.5, 1.3], [-19, 9.5, 1.3], [19, 9.5, 1.3]], traces: 6, seed: 139, silk: silkAll(labelsZ(["CLK", "DIO", "VCC", "GND"], 19.5, { side: -1, size: 0.8 })) });
  const disp = new THREE.Group();
  disp.add(at(box(30, 7.5, 14, M.plastic(0xf4f3ef, 0.6)), 0, 3.75, 0));
  disp.add(at(decal(29.6, 13.6, (ctx, W, H, k) => {
    ctx.fillStyle = "#141417"; ctx.fillRect(0, 0, W, H);
    const digits = ["1", "2", "3", "4"], on = { "1": [0, 1, 1, 0, 0, 0, 0], "2": [1, 1, 0, 1, 1, 0, 1], "3": [1, 1, 1, 1, 0, 0, 1], "4": [0, 1, 1, 0, 0, 1, 1] };
    digits.forEach((dg, i) => {
      ctx.save(); ctx.translate((3.6 + i * 7.1 + (i > 1 ? 0.8 : 0)) * k, H / 2); ctx.transform(1, 0, -0.1, 1, 0, 0);
      const s = 3.2 * k, t = 0.7 * k, o = on[dg];
      const seg = (x, y, w, h, n) => { ctx.fillStyle = o[n] ? "#ff4a30" : "#34201e"; ctx.beginPath(); ctx.roundRect(x, y, w, h, t / 2); ctx.fill(); };
      seg(-s / 2, -s - t * 1.5, s, t, 0); seg(s / 2, -s - t, t, s, 1); seg(s / 2, t / 2, t, s, 2); seg(-s / 2, s + t / 2, s, t, 3); seg(-s / 2 - t, t / 2, t, s, 4); seg(-s / 2 - t, -s - t, t, s, 5); seg(-s / 2, -t / 2, s, t, 6);
      ctx.restore();
    });
    ctx.fillStyle = "#ff4a30"; ctx.beginPath(); ctx.arc(W / 2 + 0.3 * k, H / 2 - 1.3 * k, 0.45 * k, 0, 7); ctx.arc(W / 2 - 0.1 * k, H / 2 + 1.5 * k, 0.45 * k, 0, 7); ctx.fill();
  }, { pxPerMm: 40, glow: 0.3, transparent: false }), 0, 7.51, 0));
  g.add(at(disp, -2, 1.6, 0));
  const h = header(4, { rightAngle: true }); g.add(at(h, 19.5, 1.6, 0, 0, Math.PI / 2));
  return g;
}

function max7219() {
  const g = pcb(32, 32, BLUE, { holes: [], traces: 4, seed: 149 });
  const mat = new THREE.Group();
  mat.add(at(box(32, 7.5, 32, M.plastic(0x141417, 0.5)), 0, 3.75, 0));
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
    const on = [[0, 1, 1, 0, 0, 1, 1, 0], [1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 0], [0, 0, 1, 1, 1, 1, 0, 0], [0, 0, 0, 1, 1, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]][y][x];
    const dot = cyl(1.5, 1.5, 0.3, on ? M.glow(0xff3a2a, 1.3) : M.epoxy(0x5a1a14), 20);
    mat.add(at(dot, -14 + x * 4, 7.55, -14 + y * 4));
  }
  g.add(at(mat, 0, 1.6, 0));
  // the driver board underneath sticks out with its pins
  const under = pcb(32, 38, BLUE, { holes: [], traces: 8, seed: 151 });
  under.add(at(dip(24, ["MAX7219CNG"]), 0, 1.6, 0));
  g.add(at(under, 0, -9, 3));
  for (const s of [-1, 1]) { const h = header(5, { rightAngle: true }); g.add(at(h, 0, -7.4, s * 20, 0, s > 0 ? 0 : Math.PI)); }
  return g;
}

function logicAnalyzer() {
  const g = new THREE.Group();
  const body = rbox(54, 12, 26, 3, M.metal(0x2a2c31, 0.45)); g.add(at(body, 0, 6, 0));
  g.add(at(decal(40, 18, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    text(ctx, "USB LOGIC ANALYZER", W / 2, 3 * k, { size: 2.2 * k, color: "#dfe2e6" });
    text(ctx, "24MHz  8CH", W / 2, 6.5 * k, { size: 1.8 * k, color: "#aab0b8" });
    ["CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8", "CLK", "GND"].forEach((s, i) => text(ctx, s, (2 + i * 4) * k, H - 2 * k, { size: 1.1 * k, color: "#dfe2e6", rot: -Math.PI / 2 }));
  }, { pxPerMm: 40 }), 0, 12.01, 0));
  const h = header(10, { rows: 2 }); g.add(at(h, 0, 3.5, 13, Math.PI / 2, 0, 0));
  g.add(at(usb("mini"), -27, 3.5, 0, 0, 0, 0));
  g.add(at(box(0.4, 3, 3, M.glow(0x3ae060, 1)), 27.1, 8, 7));
  return g;
}

export const MODULES = {
  "hc-sr04": hcsr04,
  "dht22": dht22,
  "bmp180": bmp180,
  "mpu6050": mpu6050,
  "ds1307-rtc": ds1307,
  "hx711": hx711,
  "mfrc522": mfrc522,
  "microsd-card": microsd,
  "gas-sensor": gasSensor,
  "ntc-temperature-sensor": () => sensorWithProbe("ntc"),
  "photoresistor-sensor": () => sensorWithProbe("ldr"),
  "pir-motion-sensor": pir,
  "relay-module": relayModule,
  "ky-040": ky040,
  "analog-joystick": joystick,
  "tm1637-7segment": tm1637,
  "max7219-matrix": max7219,
  "logic-analyzer": logicAnalyzer,
};
