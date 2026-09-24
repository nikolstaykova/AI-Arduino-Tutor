// Detailed motors, wires, cables and consumables.
import { THREE, M, P, box, rbox, cyl, sphere, torus, at, lathe, extrude, tube, bentWire, decal, sideDecal, text,
  insulatedWire, mesh } from "./kit.js";

// ---- motors -------------------------------------------------------------------------
function servo() {
  // SG90 micro servo: translucent-blue case, mounting ears with screw holes, gear tower, white horn, 3-wire lead
  const g = new THREE.Group(), blue = new THREE.MeshPhysicalMaterial({ color: 0x2a6fd6, roughness: 0.35, transmission: 0.15, thickness: 2, clearcoat: 0.4 });
  g.add(at(rbox(23, 22.5, 12.2, 0.8, blue), 0, 11.25, 0));
  const ear = extrude([[-16.25, 0], [16.25, 0], [16.25, 2.5], [-16.25, 2.5]], 12.2, blue, { holes: [[[-14.8, 0.2], [-13, 0.2], [-13, 2.3], [-14.8, 2.3]], [[13, 0.2], [14.8, 0.2], [14.8, 2.3], [13, 2.3]]] });
  g.add(at(ear, 0, 15.9, 0));
  for (const s of [-1, 1]) { const hole = cyl(1, 1, 2.6, M.plastic(0x0c1a33, 0.9), 16); g.add(at(hole, s * 13.9, 17.2, 0)); }
  g.add(at(cyl(5.9, 5.9, 4, blue, 48), -5.8, 24.5, 0));
  g.add(at(cyl(2.8, 2.8, 3, blue, 32), 2, 23.7, 0));
  g.add(at(cyl(2.35, 2.35, 3.2, M.plastic(0xf0efe8, 0.4), 24), -5.8, 28, 0));
  // the horn: a double arm with holes, a centre screw
  const horn = new THREE.Group();
  horn.add(extrude([[-16, -2], [16, -2], [17, 0], [16, 2], [-16, 2], [-17, 0]], 1.6, M.plastic(0xf6f5f0, 0.4), { bevel: 0.2 }));
  horn.children[0].rotation.x = -Math.PI / 2;
  horn.add(at(cyl(3.5, 3.5, 3, M.plastic(0xf6f5f0, 0.4), 32), 0, -1, 0));
  for (let i = 0; i < 6; i++) for (const s of [-1, 1]) horn.add(at(cyl(0.45, 0.45, 1.8, M.plastic(0x444, 0.9), 12), s * (5.5 + i * 2), 0.1, 0));
  horn.add(at(cyl(1.2, 1.2, 0.5, M.chrome(), 16), 0, 1, 0));
  g.add(at(horn, -5.8, 30.5, 0, 0, 0.5, 0));
  g.add(at(decal(18, 10, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "TowerPro", W / 2, H * 0.3, { size: 2.2 * k }); text(ctx, "SG90", W / 2, H * 0.7, { size: 3 * k }); }, { pxPerMm: 30 }), 0, 11, 6.12, 0, 0, 0));          // the label on the side
  // the lead: brown, red, orange, into a 3-pin female plug
  [[0x6b3a1e, -1], [0xd0342c, 0], [0xe8872a, 1]].forEach(([c, i]) => g.add(tube([[11.5, 4, i * 1.1], [20, 3, i * 1.1], [30, 2, i * 1.1 + 4], [38, 2, i * 1.1 + 6]], 0.55, M.plastic(c, 0.5), { seg: 40, radial: 8 })));
  g.add(at(rbox(8, 2.8, 5.2, 0.3, M.plastic(0x141417, 0.5)), 42, 2, 6));
  return g;
}

function stepper(dual) {
  // NEMA-style can stepper: two stamped halves, the front flange with screw holes, the shaft(s) and the lead
  const g = new THREE.Group(), r = dual ? 17.5 : 14;
  const can = lathe([[0, 0], [r - 0.6, 0], [r, 0.6], [r, 8.6], [r + 0.4, 9], [r + 0.4, 10], [r, 10.4], [r, 18.4], [r - 0.6, 19], [0, 19]], M.metal(0xb9bec6, 0.35), 64);
  g.add(can);
  const flange = extrude([[-r - 7, -3.5], [-r - 3, -3.5], [-r + 1, -r * 0.35], [r - 1, -r * 0.35], [r + 3, -3.5], [r + 7, -3.5], [r + 7, 3.5], [r + 3, 3.5], [r - 1, r * 0.35], [-r + 1, r * 0.35], [-r - 3, 3.5], [-r - 7, 3.5]], 1, M.metal(0xc9ccd1, 0.3),
    { holes: [[[-r - 5.5, -1.3], [-r - 3, -1.3], [-r - 3, 1.3], [-r - 5.5, 1.3]], [[r + 3, -1.3], [r + 5.5, -1.3], [r + 5.5, 1.3], [r + 3, 1.3]]] });
  flange.rotation.x = -Math.PI / 2; g.add(at(flange, 0, 19.5, 0));
  g.add(at(cyl(4.5, 4.5, 1.6, M.plastic(0x141417, 0.5), 32), 0, 20.8, 0));
  if (dual) {
    g.add(at(cyl(3, 3, 12, M.chrome(), 32), 0, 27, 0));
    g.add(at(cyl(1.5, 1.5, 20, M.metal(0xd9b25a, 0.3), 24), 0, 31, 0));
  } else {
    const shaft = cyl(2.5, 2.5, 12, M.chrome(), 32); g.add(at(shaft, 0, 27, 0));
    g.add(at(box(3.5, 8, 0.6, M.chrome()), 0, 29, 1.9));        // the flat
  }
  g.add(at(decal(r * 1.6, r * 1.6, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, dual ? "DUAL SHAFT" : "28BYJ-48", W / 2, H * 0.4, { size: 2.2 * k, color: "#8a8e95" }); text(ctx, "5V DC", W / 2, H * 0.6, { size: 1.8 * k, color: "#8a8e95" }); }, { pxPerMm: 30 }), 0, 0.02, 0));
  g.children.at(-1).rotation.set(Math.PI / 2, 0, 0);
  // the wire exit box and the ribbon of four coloured leads
  g.add(at(box(14, 8, 6, M.plastic(0x2a6fd6, 0.4)), 0, 9, -r - 2.5));
  [0xd0342c, 0xe8c83a, 0x3a8a4a, 0x2a5ec9].forEach((c, i) => g.add(tube([[-3 + i * 2, 9, -r - 5], [-3 + i * 2, 7, -r - 18], [-6 + i * 2, 3, -r - 32], [-6 + i * 2, 2, -r - 40]], 0.6, M.plastic(c, 0.5), { seg: 40, radial: 8 })));
  g.add(at(rbox(10, 3, 6, 0.4, M.plastic(0xf2efe6, 0.4)), -3, 2, -r - 43));
  return g;
}

// ---- wires & cables -------------------------------------------------------------------------
// a Dupont jumper end: the black crimp housing with its latch window, then a pin or a socket
function dupont(kind) {
  const g = new THREE.Group();
  g.add(at(rbox(14, 2.5, 2.5, 0.25, M.plastic(0x141417, 0.5)), 0, 0, 0));
  g.add(at(box(3, 0.1, 1.2, M.plastic(0x2a2a2e, 0.9)), 1, 1.26, 0));
  if (kind === "m") {
    const pin = new THREE.Group(); pin.add(box(6, 0.64, 0.64, M.gold())); pin.add(at(mesh(new THREE.CylinderGeometry(0.1, 0.45, 0.8, 4), M.gold()), 3.4, 0, 0, 0, 0, -Math.PI / 2));
    g.add(at(pin, 10, 0, 0));
  } else {
    g.add(at(box(0.1, 1, 1, M.plastic(0x020202, 1)), 7.02, 0, 0));
  }
  return g;
}

function jumpers(list) {
  const g = new THREE.Group();
  list.forEach(([c, a, b], i) => {
    const z = -8 + i * 8, curve = [[-30, 2, z], [-15, 8 + i * 2, z + 5], [10, 7, z - 5], [30, 2, z]];
    g.add(tube(curve, 0.75, M.plastic(c, 0.45), { seg: 80, radial: 12 }));
    g.add(at(dupont(a), -37, 2, z, 0, Math.PI, 0));
    g.add(at(dupont(b), 37, 2, z));
  });
  return g;
}

function alligatorLead() {
  const g = new THREE.Group(), red = 0xd0342c;
  g.add(tube([[-34, 3, 0], [-20, 10, 12], [0, 6, 16], [20, 10, 8], [34, 3, 0]], 0.9, M.plastic(red, 0.5), { seg: 80 }));
  for (const s of [-1, 1]) {
    const c = new THREE.Group();
    const boot = lathe([[0, 0], [1.4, 0], [2.6, 3], [2.8, 10], [2.2, 11], [0, 11]], M.plastic(red, 0.45), 32); boot.rotation.z = -Math.PI / 2; c.add(boot);
    for (const t of [-1, 1]) {
      const jaw = new THREE.Group();
      jaw.add(at(extrude([[0, 0], [12, 0], [13, t * 0.6], [12, t * 1.2], [0, t * 1.4]], 3, M.steel()), 0, 0, 0));
      for (let i = 0; i < 6; i++) jaw.add(at(extrude([[0, 0], [0.8, 0], [0.4, -t * 0.7]], 3, M.steel()), 5 + i * 1.2, 0, 0));
      jaw.position.set(11, t * 0.8, 0); jaw.rotation.z = t * 0.2; c.add(jaw);
    }
    c.add(at(torus(1.2, 0.3, M.steel(), 8, 20), 13, 0, 0, Math.PI / 2));
    g.add(at(c, s * 36, 3, 0, 0, s > 0 ? 0 : Math.PI, 0));
  }
  return g;
}

function usbCable() {
  const g = new THREE.Group();
  g.add(tube([[-38, 3, 0], [-24, 3, 14], [-4, 3, 20], [12, 3, -14], [28, 3, -10], [38, 3, 0]], 2, M.plastic(0x2a2c31, 0.55), { seg: 160, radial: 16 }));
  // USB-A plug
  const a = new THREE.Group();
  a.add(at(rbox(18, 8, 16, 2, M.plastic(0x2a2c31, 0.5)), 0, 0, 0));
  a.add(at(cyl(2.4, 3.4, 8, M.plastic(0x2a2c31, 0.5), 20), 12, 0, 0, 0, 0, Math.PI / 2));
  a.add(at(box(12, 4.5, 12, M.chrome()), -15, 0, 0));
  a.add(at(box(0.3, 1.8, 10, M.plastic(0xf2efe6, 0.4)), -21.05, -0.8, 0));
  for (let i = 0; i < 4; i++) a.add(at(box(0.2, 0.4, 1.4, M.gold()), -21.1, 0.2, -3.6 + i * 2.4));
  for (const s of [-1, 1]) a.add(at(box(2, 0.1, 1.5, M.plastic(0x444, 0.9)), -18, 2.26, s * 3));
  a.add(at(decal(8, 6, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); ctx.strokeStyle = "#9a9ea6"; ctx.lineWidth = 0.4 * k; ctx.beginPath(); ctx.moveTo(1 * k, H / 2); ctx.lineTo(W - 1 * k, H / 2); ctx.moveTo(W / 2, H / 2); ctx.lineTo(W * 0.7, H * 0.2); ctx.moveTo(W / 2, H / 2); ctx.lineTo(W * 0.7, H * 0.8); ctx.stroke(); }, { pxPerMm: 30 }), 0, 4.01, 0));
  g.add(at(a, -52, 3, 0));
  // USB-B plug (the Uno end)
  const b = new THREE.Group();
  b.add(at(rbox(18, 12, 14, 2, M.plastic(0x2a2c31, 0.5)), 0, 0, 0));
  b.add(at(cyl(2.4, 3.4, 8, M.plastic(0x2a2c31, 0.5), 20), -12, 0, 0, 0, 0, Math.PI / 2));
  b.add(at(rbox(9, 10.5, 12, 1.2, M.chrome()), 13, 0, 0));
  b.add(at(box(0.3, 5, 5, M.plastic(0xf2efe6, 0.4)), 17.6, 0, 0));
  g.add(at(b, 52, 3, 0));
  return g;
}

// ---- consumables -------------------------------------------------------------------------
function solderSpool() {
  const g = new THREE.Group();
  const flange = lathe([[4, 0], [22, 0], [22.5, 0.5], [22.5, 2.5], [22, 3], [4, 3]], M.plastic(0x17181b, 0.5), 64);
  g.add(flange); g.add(at(flange.clone(), 0, 27, 0));
  g.add(at(cyl(20.5, 20.5, 24, M.metal(0xc7cbd1, 0.35), 64), 0, 15, 0));
  // wound turns catch the light
  for (let i = 0; i < 22; i++) g.add(at(torus(20.6, 0.5, M.metal(0xc7cbd1, 0.3), 8, 64), 0, 4 + i * 1.05, 0, Math.PI / 2));
  g.add(at(cyl(4, 4, 30.2, M.plastic(0x050505, 0.9), 32), 0, 15, 0));
  g.add(at(decal(40, 40, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, 19 * k, 0, 7); ctx.arc(W / 2, H / 2, 5 * k, 0, 7, true); ctx.clip();
    ctx.fillStyle = "#f2c230"; ctx.fillRect(0, 0, W, H); ctx.restore();
    text(ctx, "LEAD-FREE", W / 2, H * 0.24, { size: 3 * k, color: "#1b1b1b" }); text(ctx, "Sn99.3 Cu0.7", W / 2, H * 0.76, { size: 2.4 * k, color: "#1b1b1b" });
    text(ctx, "Ø 0.8 mm · rosin core", W / 2, H * 0.86, { size: 1.8 * k, color: "#1b1b1b", weight: "normal" });
  }, { pxPerMm: 24 }), 0, 30.02, 0));
  g.add(tube([[20.8, 20, 0], [30, 17, 8], [40, 10, 16], [46, 3, 26], [50, 1, 34]], 0.4, M.metal(0xc7cbd1, 0.3), { seg: 60, radial: 8 }));
  return g;
}

function heatShrink() {
  const g = new THREE.Group();
  [[0xd0342c, 1.2], [0x17181b, 1.6], [0x2a5ec9, 2], [0xe8c83a, 2.6], [0x3a9a4a, 3.2], [0xf2f2ee, 4]].forEach(([c, r], i) => {
    const len = 40 - i * 3;
    const t = mesh(new THREE.CylinderGeometry(r, r, len, 24, 1, true), new THREE.MeshStandardMaterial({ color: c, roughness: 0.45, side: THREE.DoubleSide }));
    t.rotation.z = Math.PI / 2; g.add(at(t, 0, r, -18 + i * 7.5));
    g.add(at(torus(r, 0.12, M.plastic(c, 0.4), 6, 24), len / 2, r, -18 + i * 7.5, 0, Math.PI / 2));
    g.add(at(torus(r, 0.12, M.plastic(c, 0.4), 6, 24), -len / 2, r, -18 + i * 7.5, 0, Math.PI / 2));
  });
  // one piece already shrunk over a soldered joint
  const joint = new THREE.Group();
  joint.add(tube([[-26, 1.2, 0], [-8, 1.2, 0]], 0.9, M.plastic(0xd0342c, 0.5), { seg: 4 }));
  joint.add(tube([[8, 1.2, 0], [26, 1.2, 0]], 0.9, M.plastic(0xd0342c, 0.5), { seg: 4 }));
  joint.add(at(cyl(1.3, 1.3, 16, M.plastic(0x17181b, 0.35), 24), 0, 1.2, 0, 0, 0, Math.PI / 2));
  g.add(at(joint, 0, 0, 30));
  return g;
}

export const WIRING = {
  "servo": servo,
  "stepper-motor": () => stepper(false),
  "biaxial-stepper": () => stepper(true),
  "jumper-wire": () => jumpers([[0x3a9a4a, "m", "m"], [0xd0342c, "m", "m"], [0x17181b, "m", "m"]]),
  "jumper-wire-mf": () => jumpers([[0xe8872a, "m", "f"], [0x2a5ec9, "m", "f"], [0x7a3ac9, "m", "f"]]),
  "alligator-clip-wire": alligatorLead,
  "usb-cable": usbCable,
  "solder": solderSpool,
  "heat-shrink": heatShrink,
};
