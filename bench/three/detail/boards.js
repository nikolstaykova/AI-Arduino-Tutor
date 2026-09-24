// Detailed microcontroller boards: every header pin with its printed name,
// the real connectors, the MCU (or the shielded Wi-Fi module with its
// antenna), crystal, regulator, LEDs, buttons and the small SMD parts.
import { THREE, M, P, box, rbox, cyl, at, group, decal, text, hex, pcb, header, headerDown, qfp, soic, sot23, sot223,
  smdR, smdC, smdLed, tantalum, elCap, crystalSMD, crystalHC49, tactSwitch, tactSMD, usb, barrelJack, silkAll, silkText, silkRect } from "./kit.js";

// scatter little SMD parts in a rectangle (deterministic)
function scatter(g, x0, z0, w, d, n, seed = 3, y = 1.6) {
  let s = seed * 7919;
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < n; i++) {
    const kind = r();
    const part = kind < 0.45 ? smdR("0603", ["103", "102", "221", "472", "000"][Math.floor(r() * 5)]) : kind < 0.85 ? smdC("0603", [0xb89a72, 0x9a8a6a, 0xc8b08a][Math.floor(r() * 3)]) : sot23("J3Y");
    part.position.set(x0 + r() * w, y, z0 + r() * d);
    part.rotation.y = r() > 0.5 ? Math.PI / 2 : 0;
    g.add(part);
  }
}
// a row of header pins soldered from below, with a gold pad ring + solder on top
function pinsDown(g, n, x, z, { dir = "x", labels = null, labelSide = 1, pitch = P, labelSize = 0.9 } = {}) {
  const h = headerDown(n); h.position.set(x, 0, z); if (dir === "z") h.rotation.y = Math.PI / 2; g.add(h);
  for (let i = 0; i < n; i++) {
    const o = -((n - 1) * pitch) / 2 + i * pitch;
    const px = dir === "x" ? x + o : x, pz = dir === "x" ? z : z + o;
    g.add(at(cyl(0.85, 0.85, 0.05, M.gold(), 20), px, 1.63, pz));
    g.add(at(cyl(0.55, 0.3, 0.7, M.tin(), 12), px, 1.95, pz));
    g.add(at(box(0.64, 0.6, 0.64, M.gold()), px, 2.2, pz));
  }
  return labels;
}
// silkscreen pin labels beside a pin row
const pinLabels = (names, x, z, { dir = "x", side = 1, pitch = P, size = 0.85, gap = 1.9 } = {}) => (ctx, mm, k) => {
  names.forEach((nm, i) => {
    if (!nm) return;
    const o = -((names.length - 1) * pitch) / 2 + i * pitch;
    const [px, py] = dir === "x" ? mm(x + o, z + side * gap) : mm(x + side * gap, z + o);
    text(ctx, nm, px, py, { size: size * k, color: "#f4f4f0", rot: dir === "x" ? -Math.PI / 2 : 0, align: dir === "x" ? (side > 0 ? "right" : "left") : side > 0 ? "left" : "right" });
  });
};
// flip "right"/"left" so the labels read away from the pins
const pinLabelsX = (names, x, z, side, size = 0.85) => (ctx, mm, k) => names.forEach((nm, i) => {
  if (!nm) return;
  const o = -((names.length - 1) * P) / 2 + i * P, [px, py] = mm(x + o, z + side * 1.6);
  text(ctx, nm, px, py, { size: size * k, color: "#f4f4f0", rot: -Math.PI / 2, align: side > 0 ? "right" : "left" });
});

// the shielded Wi-Fi module: a module PCB, a stamped can with its laser
// marking, and the meandering gold antenna trace at the free end
function wifiModule(name, lines, { w = 18, d = 25.5, can = [15.8, 17.6], antenna = 6 } = {}) {
  const g = new THREE.Group();
  const mod = pcb(w, d, 0x16171a, { holes: [], traces: 0, thick: 0.8, corner: 0.2 });
  g.add(mod);
  const shield = new THREE.Group();
  shield.add(at(rbox(can[0], 2.4, can[1], 0.35, M.metal(0xc9ccd1, 0.32)), 0, 1.2, 0));
  shield.add(at(decal(can[0] - 1, can[1] - 1, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    text(ctx, "ESPRESSIF", W / 2, 2.6 * k, { size: 1.5 * k, color: "#7b7f86" });
    lines.forEach((s, i) => text(ctx, s, W / 2, (5.4 + i * 2) * k, { size: 1.15 * k, color: "#7b7f86", weight: i ? "normal" : "bold" }));
    // FCC / CE marks and a QR-style code block
    ctx.strokeStyle = "#7b7f86"; ctx.lineWidth = 0.12 * k; ctx.strokeRect(W / 2 - 2.2 * k, H - 5.6 * k, 4.4 * k, 4.4 * k);
    for (let i = 0; i < 36; i++) if ((i * 7) % 3) { ctx.fillStyle = "#7b7f86"; ctx.fillRect(W / 2 - 2 * k + (i % 6) * 0.68 * k, H - 5.4 * k + Math.floor(i / 6) * 0.68 * k, 0.6 * k, 0.6 * k); }
  }, { pxPerMm: 60 }), 0, 2.41, 0));
  g.add(at(shield, 0, 0.8, -antenna / 2 + 0.5));
  g.add(at(decal(w - 1, antenna - 1, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H); ctx.strokeStyle = "#d9b25a"; ctx.lineWidth = 0.55 * k; ctx.lineJoin = "miter";
    ctx.beginPath(); let x = 1 * k; ctx.moveTo(x, H - 0.4 * k);
    for (let i = 0; i < 8; i++) { ctx.lineTo(x, 0.6 * k); x += 1 * k; ctx.lineTo(x, 0.6 * k); ctx.lineTo(x, H - 1.6 * k); x += 1 * k; ctx.lineTo(x, H - 1.6 * k); }
    ctx.stroke();
  }, { pxPerMm: 40 }), 0, 0.81, d / 2 - antenna / 2));
  // castellated pads down the sides
  for (let i = 0; i < 12; i++) for (const s of [-1, 1]) g.add(at(box(0.9, 0.82, 0.8, M.gold()), s * (w / 2 - 0.35), 0.41, -d / 2 + 2 + i * 1.27));
  return g;
}

function devBoard(spec) {
  const { w, d, color, pins, left, right, finish = "gold", seed = 5 } = spec;
  const rowZ = d / 2 - 1.3;
  const silk = silkAll(
    pinLabelsX(left, 0, -rowZ, 1), pinLabelsX(right, 0, rowZ, -1),
    ...(spec.silk || []),
  );
  const g = pcb(w, d, color, { holes: spec.holes ?? [], traces: 22, silk, seed, finish });
  pinsDown(g, pins, 0, -rowZ); pinsDown(g, pins, 0, rowZ);
  spec.build(g);
  return g;
}

function nano() {
  const L = ["D12", "D11", "D10", "D9", "D8", "D7", "D6", "D5", "D4", "D3", "D2", "GND", "RST", "RX0", "TX1"];
  const R = ["D13", "3V3", "REF", "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "+5V", "RST", "GND", "VIN"];
  return devBoard({ w: 43.2, d: 18, color: 0x164a8a, pins: 15, left: L.reverse(), right: R, seed: 11,
    silk: [silkText("NANO", 8, 0, 1.6), silkText("V3.0", 8, 2, 0.9), silkText("TX", -10, -4, 0.7), silkText("RX", -10, -2.6, 0.7), silkText("PWR", -10, 3, 0.7), silkText("L", -10, 4.2, 0.7)],
    build: (g) => {
      g.add(at(usb("mini"), -21.6 + 4.5 - 1, 1.6, 0));
      g.add(at(qfp(7, ["ATMEGA328P", "AU 1934"], { pins: 8 }), 6, 1.6, 0, 0, Math.PI / 4));
      g.add(at(qfp(5, ["CH340G"], { legs: false }), -8, 1.6, 0));
      g.add(at(crystalSMD(), -3, 1.6, 4.5));
      g.add(at(sot223("AMS1117"), 16, 1.6, 4.5));
      g.add(at(tactSMD(4), -2, 1.6, -4.2));
      [[0xff3a2a, -12, -4], [0xff3a2a, -12, -2.6], [0x3ae060, -12, 3], [0xffa020, -12, 4.2]].forEach(([c, x, z]) => g.add(at(smdLed(c), x, 1.6, z)));
      scatter(g, 11, -5, 7, 3, 6, 4); scatter(g, -6, 2, 6, 3, 5, 7);
    } });
}

function pico() {
  const L = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7", "GP8", "GP9", "GND", "GP10", "GP11", "GP12", "GP13", "GND", "GP14", "GP15"];
  const R = ["VBUS", "VSYS", "GND", "3V3E", "3V3", "VREF", "GP28", "GND", "GP27", "GP26", "RUN", "GP22", "GND", "GP21", "GP20", "GP19", "GP18", "GND", "GP17", "GP16"];
  return devBoard({ w: 51, d: 21, color: 0x1d6b3c, pins: 20, left: L, right: R, seed: 21, finish: "gold",
    holes: [[-23.5, -5.7, 1.05], [-23.5, 5.7, 1.05], [23.5, -5.7, 1.05], [23.5, 5.7, 1.05]],
    silk: [silkText("Raspberry Pi Pico", 6, -3.8, 1.2), silkText("©2020", 6, -2.2, 0.8), silkText("BOOTSEL", -12, 5, 0.8), silkText("LED", -18, -4.5, 0.7), silkText("DEBUG", 22.5, 0, 0.7, { rot: -Math.PI / 2 })],
    build: (g) => {
      g.add(at(usb("micro"), -25.5 + 2.8, 1.6, 0));
      g.add(at(qfp(7, ["RP2-B2", "20/21", "P64M15.00"], { legs: false }), 2, 1.6, 1));
      g.add(at(soic(8, ["W25Q16JV"], { d: 5.3 }), 13.5, 1.6, 1, 0, Math.PI / 2));
      g.add(at(crystalSMD(), -5, 1.6, 4.2));
      g.add(at(tactSMD(4), -12, 1.6, 2.8));
      g.add(at(smdLed(0x3ae060), -18, 1.6, -3.2));
      g.add(at(box(3, 1, 3, M.plastic(0x222226)), -16, 2.1, 3.5));        // the buck-boost inductor
      scatter(g, -10, -4, 8, 2.5, 7, 9); scatter(g, 17, -4, 5, 8, 6, 13);
      for (const x of [-2.54, 0, 2.54]) g.add(at(cyl(0.85, 0.85, 0.05, M.gold(), 20), 24.2, 1.63, x));
    } });
}

function bluepill() {
  const L = ["B12", "B13", "B14", "B15", "A8", "A9", "A10", "A11", "A12", "A15", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "5V", "G", "3.3"];
  const R = ["G", "G", "3.3", "R", "B11", "B10", "B1", "B0", "A7", "A6", "A5", "A4", "A3", "A2", "A1", "A0", "C15", "C14", "C13", "VB"];
  return devBoard({ w: 53, d: 22.8, color: 0x164a8a, pins: 20, left: L, right: R.reverse(), seed: 31,
    silk: [silkText("BOOT0", 12, -3.5, 0.8), silkText("BOOT1", 12, 3.5, 0.8), silkText("RESET", -12, -5, 0.8)],
    build: (g) => {
      g.add(at(usb("micro"), -26.5 + 2.8, 1.6, 0));
      g.add(at(qfp(7, ["STM32", "F103C8T6", "GH26K"], { pins: 12 }), 2, 1.6, 0, 0, Math.PI / 4));
      g.add(at(crystalHC49("8.000"), -9, 1.6, 4.5));
      g.add(at(sot223("662K"), -16, 1.6, -5));
      g.add(at(tactSMD(4), -12, 1.6, -3));
      // the two yellow boot jumpers
      for (const [z, s] of [[-2, 1], [2, -1]]) {
        const h = header(3, { rows: 1 }); h.scale.set(1, 0.8, 1); g.add(at(h, 18, 1.6, z * 1.2));
        g.add(at(box(5.1, 6, 2.5, M.plastic(0xe8c020, 0.5)), 18 + s * 1.27, 4.6, z * 1.2));
      }
      [[0xff3a2a, -18, 5], [0x3ae060, 14, -6]].forEach(([c, x, z]) => g.add(at(smdLed(c), x, 1.6, z)));
      scatter(g, -20, -2, 6, 5, 6, 17); scatter(g, 6, 3, 8, 4, 6, 19);
      // SWD header at the end
      const swd = header(4); g.add(at(swd, 25, 1.6, 0, 0, Math.PI / 2));
    } });
}

function esp32Board({ w, d, pins, name, lines, left, right, usbKind = "micro", can, antenna, second = false, rgb = false, seed = 41, color = 0x17181b }) {
  return devBoard({ w, d, color, pins, left, right, seed, finish: "gold",
    silk: [silkText(name, -w / 2 + 12, 0, 1.1), silkText("EN", -w / 2 + 5, -d / 2 + 5, 0.8), silkText("BOOT", -w / 2 + 5, d / 2 - 5, 0.8)],
    build: (g) => {
      const m = wifiModule(name, lines, { can, antenna, w: can[0] + 2.2, d: can[1] + antenna + 2 });
      m.rotation.y = -Math.PI / 2;
      g.add(at(m, w / 2 - (can[1] + antenna + 2) / 2 - 0.2, 1.6, 0));
      g.add(at(usb(usbKind), -w / 2 + 3.4, 1.6, second ? -4.5 : 0));
      if (second) g.add(at(usb(usbKind), -w / 2 + 3.4, 1.6, 4.5));
      g.add(at(tactSMD(4), -w / 2 + 6, 1.6, -d / 2 + 7.5));
      g.add(at(tactSMD(4), -w / 2 + 6, 1.6, d / 2 - 7.5));
      g.add(at(sot223("AMS1117"), -w / 2 + 14, 1.6, -4));
      g.add(at(qfp(4, ["CP2102"], { legs: false }), -w / 2 + 13, 1.6, 4));
      if (rgb) g.add(at(box(5, 1.6, 5, M.plastic(0xf8f8f4, 0.35)), -w / 2 + 19, 2.4, 0));
      g.add(at(smdLed(0xff3a2a), -w / 2 + 18, 1.6, -d / 2 + 5));
      g.add(at(smdLed(0x3a8aff), -w / 2 + 18, 1.6, d / 2 - 5));
      g.add(at(elCap(2, 4, { smd: true }), -w / 2 + 9, 1.6, 0));
      scatter(g, -w / 2 + 16, -3, 6, 6, 7, seed);
    } });
}

function mega() {
  // the Arduino Mega 2560: 101.6 × 53.3, female headers along three sides
  const w = 101.6, d = 53.3;
  const silk = silkAll(
    silkText("ARDUINO", -2, -2, 3.2, { font: "Arial Black" }), silkText("MEGA 2560", -2, 2.4, 2.4), silkText("MADE IN ITALY", 30, 12, 1.2),
    silkText("DIGITAL", 5, -17, 1.4), silkText("PWM", -26, -17, 1.4), silkText("COMMUNICATION", 32, -17, 1.2),
    silkText("POWER", -18, 17.5, 1.4), silkText("ANALOG IN", 12, 17.5, 1.4), silkText("ON", -40, -4, 1),
    silkText("L", -26, -10, 1), silkText("TX", -26, -8, 1), silkText("RX", -26, -6, 1), silkText("RESET", -44, -22, 1.1),
  );
  const g = pcb(w, d, 0x0a6a78, { holes: [[-37, -23.4, 1.6], [37, -23.4, 1.6], [-36, 24, 1.6], [46, 5, 1.6]], traces: 40, silk, seed: 51 });
  // female headers: top edge (digital), bottom (power + analog), right end (double row)
  for (const [x, n] of [[-26.5, 8], [-4.5, 8], [17.5, 8]]) g.add(at(header(n, { female: true }), x, 1.6, -d / 2 + 2.4));
  for (const [x, n] of [[-19, 8], [3, 8], [25, 8]]) g.add(at(header(n, { female: true }), x, 1.6, d / 2 - 2.4));
  g.add(at(header(18, { female: true, rows: 2 }), w / 2 - 4, 1.6, 0, 0, Math.PI / 2));
  // USB-B, barrel jack, regulators, caps, crystal, reset button
  g.add(at(usb("b"), -w / 2 + 6.5, 1.6, -12));
  g.add(at(barrelJack(), -w / 2 + 5.5, 1.6, 17));
  g.add(at(qfp(14, ["ATMEGA2560", "16AU 2019", "ATMEL"], { pins: 25 }), 12, 1.6, 2, 0, Math.PI / 4));
  g.add(at(qfp(5, ["16U2"], { legs: false }), -33, 1.6, -12));
  g.add(at(crystalHC49("16.000"), -12, 1.6, 10));
  g.add(at(sot223("1117"), -33, 1.6, 12));
  for (const [x, z] of [[-40, 8], [-40, 2]]) g.add(at(elCap(3, 6), x, 1.6, z));
  g.add(at(tactSwitch(6, { cap: 0xd0342c, h: 4.5 }), -43, 1.6, -17));
  g.add(at(header(3, { rows: 2 }), 44, 1.6, -3, 0, Math.PI / 2));     // ICSP
  g.add(at(header(3, { rows: 2 }), -30, 1.6, -3));
  [[0x3ae060, -40, -4], [0xffa020, -28, -10], [0xffa020, -28, -8], [0xffa020, -28, -6]].forEach(([c, x, z]) => g.add(at(smdLed(c), x, 1.6, z)));
  scatter(g, -24, 6, 14, 8, 14, 23); scatter(g, 26, -10, 12, 8, 10, 29); scatter(g, -40, -14, 8, 6, 6, 31);
  return g;
}

function a4988() {
  // Pololu-style purple carrier: the A4988 under a finned heatsink, current trimpot, sense resistors
  const L = ["EN", "MS1", "MS2", "MS3", "RST", "SLP", "STEP", "DIR"], R = ["VMOT", "GND", "2B", "2A", "1A", "1B", "VDD", "GND"];
  const g = pcb(20.3, 15.2, 0x5b2a9a, { holes: [], traces: 10, seed: 61, silk: silkAll(pinLabelsX(L, 0, -6.35, 1, 0.75), pinLabelsX(R, 0, 6.35, -1, 0.75)) });
  pinsDown(g, 8, 0, -6.35); pinsDown(g, 8, 0, 6.35);
  const hs = new THREE.Group();
  hs.add(at(box(9, 1, 9, M.metal(0x2d3240, 0.5)), 0, 0.5, 0));
  for (let i = 0; i < 7; i++) hs.add(at(box(0.7, 5.5, 9, M.metal(0x2d3240, 0.5)), -3.9 + i * 1.3, 3.5, 0));
  g.add(at(box(8, 0.3, 8, M.plastic(0xa8a8a8, 0.9)), 1, 1.75, 0));     // thermal pad
  g.add(at(hs, 1, 1.9, 0));
  const pot = new THREE.Group(); pot.add(cyl(1.6, 1.6, 1, M.plastic(0xeeeeee, 0.4), 24)); pot.add(at(box(2, 0.3, 0.4, M.plastic(0x444)), 0, 0.55, 0)); pot.add(at(cyl(1.3, 1.3, 0.2, M.metal(0xd9b25a, 0.3), 24), 0, 0.4, 0));
  g.add(at(pot, -7, 2.1, 0));
  g.add(at(smdR("1206", "R100"), -7, 1.6, -3.5)); g.add(at(smdR("1206", "R100"), -7, 1.6, 3.5));
  return g;
}

const ESP_L = ["3V3", "EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26", "D27", "D14", "D12", "GND", "D13"];
const ESP_R = ["GND", "D23", "D22", "TX0", "RX0", "D21", "D19", "D18", "D5", "D17", "D16", "D4", "D2", "D15", "VIN"];
const gpio = (n, pre = "IO") => Array.from({ length: n }, (_, i) => pre + i);

export const BOARDS = {
  "arduino-nano": nano,
  "arduino-mega": mega,
  "pi-pico": pico,
  "stm32-bluepill": bluepill,
  "esp32-devkit-v1": () => esp32Board({ w: 51, d: 28, pins: 15, name: "ESP32-WROOM-32", lines: ["ESP32-WROOM-32", "FCC ID 2AC7Z", "211-161007"], left: ESP_L, right: ESP_R.slice().reverse(), can: [15.8, 17.6], antenna: 6, seed: 43 }),
  "esp32-c3-devkitm1": () => esp32Board({ w: 45, d: 25.4, pins: 15, name: "ESP32-C3-MINI-1", lines: ["ESP32-C3-MINI-1", "M4N4"], left: ["GND", "3V3", "3V3", "IO2", "IO3", "GND", "RST", "GND", "IO0", "IO1", "IO10", "GND", "5V", "5V", "GND"], right: ["GND", "TX", "RX", "GND", "IO9", "IO8", "GND", "IO7", "IO6", "IO5", "IO4", "GND", "IO18", "IO19", "GND"], can: [11, 11.5], antenna: 4, rgb: true, seed: 47 }),
  "esp32-s2-devkitm1": () => esp32Board({ w: 50, d: 25.4, pins: 21, name: "ESP32-S2-MINI-1", lines: ["ESP32-S2-MINI-1", "N4"], left: gpio(21), right: gpio(21).map((s) => s.replace("IO", "IO2")), can: [11, 11.5], antenna: 4, rgb: true, seed: 53 }),
  "esp32-s3-devkitc1": () => esp32Board({ w: 63, d: 25.4, pins: 22, name: "ESP32-S3-WROOM-1", lines: ["ESP32-S3-WROOM-1", "N8R8"], left: ["3V3", "3V3", "RST", ...gpio(19).slice(4), "5V", "GND"].slice(0, 22), right: ["GND", "TX", "RX", ...gpio(19).slice(0, 19)].slice(0, 22), usbKind: "c", second: true, can: [15.8, 17.6], antenna: 6, rgb: true, seed: 59 }),
  "esp32-c6-devkitc1": () => esp32Board({ w: 58, d: 25.4, pins: 16, name: "ESP32-C6-WROOM-1", lines: ["ESP32-C6-WROOM-1", "N8"], left: ["3V3", "RST", ...gpio(14)], right: ["GND", "TX", "RX", ...gpio(14).map((s) => s.replace("IO", "IO1"))], usbKind: "c", second: true, can: [15.8, 17.6], antenna: 6, rgb: true, seed: 67 }),
  "a4988": a4988,
};
