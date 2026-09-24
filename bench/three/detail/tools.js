// Detailed tools: pliers with rubber grips, pivot bolts and springs; the
// multimeter with its dial, screen and probes; the iron on its stand …
import { THREE, M, box, rbox, cyl, sphere, torus, at, lathe, extrude, tube, bentWire, decal, sideDecal, text, mesh } from "./kit.js";

// a flat shape given in (x, z) lying on the table, extruded up by h, bottom at y0
function flat(pts, h, mat, { y0 = 0, bevel = 0.3, holes = [] } = {}) {
  const m = extrude(pts, h, mat, { bevel, holes, curveSeg: 16 });
  m.rotation.x = Math.PI / 2;           // shape y → world z; depth → world y
  m.position.y = y0 + h / 2;
  return m;
}
const curvePts = (pts, n = 40) => new THREE.CatmullRomCurve3(pts.map(([x, z]) => new THREE.Vector3(x, 0, z))).getPoints(n).map((v) => [v.x, v.z]);
// a handle half: a bent steel arm and a moulded rubber grip over it
function handle(side, colour, { len = 95, spread = 16, grip = 62 } = {}) {
  const g = new THREE.Group();
  const path = [[-4, side * 2.5], [-24, side * 6], [-60, side * (spread - 3)], [-len, side * spread]];
  g.add(tube(path.map(([x, z]) => [x, 4, z]), 2.6, M.steel(), { seg: 60, radial: 12 }));
  const gp = new THREE.CatmullRomCurve3(path.map(([x, z]) => new THREE.Vector3(x, 4, z)));
  const pts = gp.getPoints(60).filter((p) => p.x < -len + grip + 4);
  const gripMesh = mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 60, 5.2, 20), M.rubber(colour));
  gripMesh.scale.set(1, 0.72, 1); gripMesh.position.y = 4 * 0.28; g.add(gripMesh);
  // a bulb at the end and a thumb stop
  const end = sphere(5.6, M.rubber(colour), 20, 12); end.scale.set(1.1, 0.72, 1); g.add(at(end, pts.at(-1).x, 4 * 0.72 + 1.12, pts.at(-1).z));
  const stop = torus(5.4, 1.3, M.rubber(colour), 10, 24); stop.scale.set(0.72, 1, 1); g.add(at(stop, pts[0].x, 4, pts[0].z, 0, Math.PI / 2 + side * 0.15, 0));
  // moulded grip ridges
  for (let i = 4; i < pts.length - 4; i += 4) { const r = torus(5.25, 0.35, M.rubber(colour), 6, 24); r.scale.set(0.72, 1, 1); const t = gp.getTangent(0.5); r.position.set(pts[i].x, 4, pts[i].z); r.rotation.y = Math.PI / 2 + side * 0.12; g.add(r); }
  return g;
}
function pivot(r = 5) {
  const g = new THREE.Group();
  g.add(at(cyl(r, r, 7.6, M.steel(), 40), 0, 4, 0));
  g.add(at(cyl(r * 0.62, r * 0.62, 0.4, M.chrome(), 32), 0, 7.9, 0));
  g.add(at(box(r * 1.1, 0.3, 0.7, M.darkSteel()), 0, 8.05, 0));
  return g;
}
function spring() {
  // a coil return spring between the handles
  const pts = []; for (let i = 0; i <= 120; i++) { const t = i / 120, a = t * Math.PI * 14; pts.push([-10 - t * 2, 4 + Math.cos(a) * 1.8, -8 + t * 16 + Math.sin(a) * 0.4]); }
  return tube(pts, 0.35, M.chrome(), { seg: 240, radial: 6 });
}

function pliers(kind) {
  const g = new THREE.Group();
  const col = { needle: 0x2a5ec9, flush: 0xd0342c, stripper: 0xe8b83a }[kind];
  const top = new THREE.Group(), bot = new THREE.Group();
  if (kind === "needle") {
    // long tapered half-round jaws with serrations
    const jaw = (s) => flat([[0, 0], [8, s * 3.2], [30, s * 1.4], [48, s * 0.3], [49, 0]], 3.8, M.steel(), { y0: s > 0 ? 4 : 0.2 });
    top.add(jaw(1)); bot.add(jaw(-1));
    for (let i = 0; i < 14; i++) g.add(at(box(0.35, 0.3, 2.2, M.darkSteel()), 20 + i * 2, 4.1, 0));
  } else if (kind === "flush") {
    // short curved blades that meet on a flat edge
    const blade = (s) => flat(curvePts([[0, s * 7], [8, s * 8], [16, s * 5], [20, s * 0.3], [18, 0], [2, 0]], 30), 3.8, M.steel(), { y0: s > 0 ? 4 : 0.2 });
    top.add(blade(1)); bot.add(blade(-1));
    g.add(at(box(17, 0.3, 0.2, M.chrome()), 10, 4.05, 0));
  } else {
    // stripper jaws with the graded notches (AWG 10–22) and a crimp section
    const jaw = (s) => flat([[0, s * 6], [30, s * 6], [34, s * 3], [34, 0], [0, 0]], 3.8, M.steel(), { y0: s > 0 ? 4 : 0.2 });
    top.add(jaw(1)); bot.add(jaw(-1));
    for (let i = 0; i < 6; i++) g.add(at(cyl(0.4 + i * 0.18, 0.4 + i * 0.18, 8, M.plastic(0x08090a, 0.9), 16), 28 - i * 4.4, 4, 0));
    g.add(at(decal(26, 5, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); ["22", "20", "18", "16", "14", "12"].forEach((s, i) => text(ctx, s, W - (2 + i * 4.4) * k, H / 2, { size: 1.6 * k, color: "#1b1b1b" })); }, { pxPerMm: 30 }), 16, 7.85, 3.5));
    g.add(at(decal(18, 3, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "AWG  STRIP  CUT", W / 2, H / 2, { size: 1.4 * k, color: "#1b1b1b" }); }, { pxPerMm: 30 }), 14, 7.85, -3.5));
  }
  top.add(handle(1, col)); bot.add(handle(-1, col));
  // open the jaws a little
  top.rotation.y = 0.07; bot.rotation.y = -0.07;
  g.add(top, bot, pivot(kind === "needle" ? 5 : 6), spring());
  g.add(at(decal(10, 4, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, kind === "needle" ? "PRECISION" : kind === "flush" ? "FLUSH CUT" : "STRIPPER", W / 2, H / 2, { size: 1.4 * k, color: "#1b1b1b" }); }, { pxPerMm: 30 }), -12, 7.85, 0));
  return g;
}

function tweezers() {
  // stainless ESD tweezers: two flat blades welded at the back, dimpled grip, fine bent tips
  const g = new THREE.Group();
  for (const s of [-1, 1]) {
    const blade = flat([[-60, s * 1], [-20, s * 4.5], [30, s * 2.6], [52, s * 0.6], [55, s * 0.2], [55, 0.02 * s], [-60, 0.02 * s]], 1.1, M.metal(0xc9ccd1, 0.25), { bevel: 0.1 });
    blade.position.z = s * 1.3; g.add(blade);
    for (let i = 0; i < 9; i++) g.add(at(box(0.8, 0.12, 2.2, M.darkSteel()), -18 + i * 3, 1.18, s * 4.2));
  }
  g.add(at(rbox(12, 1.6, 4, 0.3, M.metal(0xc9ccd1, 0.25)), -56, 0.8, 0));
  g.add(at(decal(16, 3, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "ESD-15  ANTI-STATIC", W / 2, H / 2, { size: 1.3 * k, color: "#555" }); }, { pxPerMm: 30 }), -32, 1.2, 3.4));
  return g;
}

function screwdriverSet() {
  const g = new THREE.Group();
  // the hinged case: base tray with foam cut-outs, lid open behind
  g.add(at(rbox(120, 12, 70, 5, M.plastic(0x1f2024, 0.45)), 0, 6, 0));
  g.add(at(box(114, 0.5, 64, M.rubber(0x2a2b2f)), 0, 12.1, 0));
  const lid = rbox(120, 6, 70, 5, M.plastic(0x1f2024, 0.45)); lid.position.set(0, 42, -40); lid.rotation.x = -1.25; g.add(lid);
  const title = decal(60, 12, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "PRECISION SCREWDRIVER SET", W / 2, H / 2, { size: 3 * k, color: "#d38c63" }); }, { pxPerMm: 16 });
  title.position.set(0, 3.05, 0); lid.add(title);                   // printed on the open lid
  const colours = [0xd0342c, 0x2a5ec9, 0xe8b83a, 0x3a9a4a, 0x7a3ac9, 0xe8872a];
  const tips = ["-1.5", "-2.0", "-3.0", "+0", "+1", "T6"];
  colours.forEach((c, i) => {
    const sd = new THREE.Group();
    // handle: fluted barrel with a free-spinning cap and a colour band
    sd.add(lathe([[0, 0], [4.2, 0], [4.6, 3], [4.6, 36], [3.6, 40], [0, 40]], M.plastic(0x2a2b30, 0.4), 32));
    for (let f = 0; f < 10; f++) { const a = (f / 10) * Math.PI * 2; sd.add(at(box(0.8, 30, 0.6, M.plastic(0x1a1b1f, 0.6)), Math.cos(a) * 4.5, 19, Math.sin(a) * 4.5, 0, -a, 0)); }
    sd.add(at(cyl(4.7, 4.7, 4, M.plastic(c, 0.35), 32), 0, 6, 0));
    sd.add(at(cyl(3.6, 3.6, 1, M.chrome(), 32), 0, 40.5, 0));
    // shaft and tip
    sd.add(at(cyl(1.3, 1.3, 38, M.chrome(), 16), 0, -19, 0));
    const tip = tips[i];
    if (tip[0] === "-") sd.add(at(box(1.8, 3, 0.4, M.darkSteel()), 0, -39, 0));
    else { const p = cyl(0.2, 1.3, 3, M.darkSteel(), tip[0] === "T" ? 6 : 4); sd.add(at(p, 0, -39.5, 0)); }
    sd.add(at(decal(3, 6, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, tip, W / 2, H / 2, { size: 1.6 * k, rot: -Math.PI / 2 }); }, { pxPerMm: 40 }), 0, 6, 4.75, 0, 0, 0));
    sd.rotation.z = Math.PI / 2; sd.position.set(0, 17.5, -25 + i * 10);
    g.add(sd);
  });
  return g;
}

function solderingIron() {
  const g = new THREE.Group();
  // the stand: heavy base, the sponge tray, the brass-wool pot and the spiral holder
  g.add(at(rbox(90, 12, 70, 5, M.metal(0x3a3c42, 0.5)), 0, 6, 0));
  g.add(at(box(34, 3, 26, M.plastic(0xe8c83a, 0.5)), -22, 13.5, 14));
  g.add(at(box(30, 5, 22, M.rubber(0xf2d24a)), -22, 16, 14));
  for (let i = 0; i < 5; i++) g.add(at(box(0.6, 0.2, 18, M.rubber(0xb89a2a)), -34 + i * 6, 18.6, 14));
  const pot = lathe([[0, 0], [12, 0], [12.5, 14], [11, 14], [11, 2], [0, 2]], M.metal(0xb9bec6, 0.35), 40); g.add(at(pot, -22, 12, -16));
  const wool = mesh(new THREE.TorusKnotGeometry(6.5, 3, 160, 10, 9, 13), M.brass()); wool.scale.set(1, 0.55, 1); g.add(at(wool, -22, 23, -16, Math.PI / 2, 0, 0));
  const coil = []; for (let i = 0; i <= 300; i++) { const t = i / 300, a = t * Math.PI * 18; coil.push([22 + t * 42 * Math.cos(0.55), 14 + t * 42 * Math.sin(0.55), Math.cos(a) * (6 + t * 5)]); }
  g.add(tube(coil, 0.8, M.chrome(), { seg: 600, radial: 8 }));      // the spiral iron holder
  // the iron resting in the holder: cable, grip, heat-break, barrel and tip
  const iron = new THREE.Group();
  iron.add(lathe([[0, 0], [3, 0], [5, 6], [5.5, 10], [5.5, 30]], M.rubber(0x1b1c20), 32));
  iron.add(at(lathe([[5.5, 0], [9, 4], [9.5, 40], [8.2, 60], [7, 64], [0, 64]], M.rubber(0x1b1c20), 40), 0, 30, 0));
  for (let i = 0; i < 12; i++) iron.add(at(torus(9.4, 0.5, M.rubber(0x2a2b2f), 6, 32), 0, 36 + i * 2.6, 0, Math.PI / 2));
  iron.add(at(cyl(7, 7, 3, M.plastic(0xd0342c, 0.4), 32), 0, 95.5, 0));
  iron.add(at(cyl(4.2, 5, 36, M.chrome(), 32), 0, 115, 0));
  for (let i = 0; i < 4; i++) iron.add(at(cyl(4.6, 4.6, 0.5, M.darkSteel(), 32), 0, 102 + i * 2, 0));
  iron.add(at(lathe([[2.4, 0], [2.4, 6], [1.6, 12], [0.4, 16], [0, 16.4]], M.metal(0x7a6a5a, 0.4), 24), 0, 133, 0));
  iron.add(tube([[0, 0, 0], [0, -20, 3], [-6, -50, 20], [-20, -70, 40]], 2.4, M.rubber(0x1b1c20), { seg: 40 }));
  iron.rotation.z = -Math.PI / 2 + 0.55; iron.position.set(-8, 30, 0);
  g.add(iron);
  return g;
}

function multimeter() {
  const g = new THREE.Group();
  // the yellow rubber holster around the grey body
  g.add(at(rbox(84, 32, 166, 10, M.rubber(0xe8b83a)), 0, 16, 0));
  g.add(at(rbox(72, 4, 154, 6, M.plastic(0x3a3c42, 0.5)), 0, 31, 0));
  // the screen with its bezel and a reading
  g.add(at(rbox(60, 1.2, 34, 2, M.plastic(0x1b1c20, 0.3)), 0, 33.4, -52));
  g.add(at(decal(54, 28, (ctx, W, H, k) => {
    ctx.fillStyle = "#b9c7a8"; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#1c2418"; ctx.font = `bold ${16 * k}px "DSEG7 Classic", monospace`; ctx.textAlign = "right"; ctx.textBaseline = "middle"; ctx.fillText("4.97", W - 12 * k, H * 0.55);
    text(ctx, "V", W - 6 * k, H * 0.66, { size: 5 * k, color: "#1c2418" }); text(ctx, "DC", 6 * k, 5 * k, { size: 3 * k, color: "#1c2418" });
    text(ctx, "AUTO", 8 * k, H - 4 * k, { size: 2.6 * k, color: "#1c2418" });
  }, { pxPerMm: 16, transparent: false, rough: 0.3 }), 0, 34.05, -52));
  // the buttons row
  ["HOLD", "SEL", "RANGE", "REL"].forEach((t, i) => {
    g.add(at(rbox(12, 2.4, 7, 1.5, M.plastic(i === 0 ? 0xe8b83a : 0x5a5d63, 0.4)), -22.5 + i * 15, 34, -26));
    g.add(at(decal(11, 4, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, t, W / 2, H / 2, { size: 2.2 * k, color: i === 0 ? "#222" : "#eee" }); }, { pxPerMm: 24 }), -22.5 + i * 15, 35.25, -26));
  });
  // the rotary dial: printed ranges round it, the knob with its pointer
  g.add(at(decal(70, 70, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    const labels = ["OFF", "V~", "V⎓", "mV", "Ω", "•)))", "▶|", "Hz", "°C", "µA", "mA", "A"];
    labels.forEach((s, i) => { const a = -Math.PI / 2 - Math.PI * 0.75 + (i / (labels.length - 1)) * Math.PI * 1.5; text(ctx, s, W / 2 + Math.cos(a) * 29 * k, H / 2 + Math.sin(a) * 29 * k, { size: 3.4 * k, color: i === 2 ? "#e8b83a" : "#eee" }); });
    ctx.strokeStyle = "#8a8e95"; ctx.lineWidth = 0.4 * k; ctx.beginPath(); ctx.arc(W / 2, H / 2, 24 * k, 0, 7); ctx.stroke();
  }, { pxPerMm: 16 }), 0, 33.05, 14));
  const knob = new THREE.Group();
  knob.add(cyl(21, 21, 4, M.plastic(0x2a2b30, 0.45), 64));
  knob.add(at(rbox(40, 6, 11, 3, M.plastic(0x1b1c20, 0.4)), 0, 4, 0));
  knob.add(at(box(2, 0.3, 14, M.plastic(0xffffff, 0.4)), 0, 7.1, -12));
  knob.rotation.y = 0.55;
  g.add(at(knob, 0, 35, 14));
  // the jacks with their rings
  [["10A", 0xd0342c], ["COM", 0x1b1c20], ["VΩmA", 0xd0342c]].forEach(([t, c], i) => {
    const x = -24 + i * 24;
    g.add(at(lathe([[0, 0], [5, 0], [5, 3], [3.5, 3], [3.5, -8], [0, -8]], M.plastic(c, 0.4), 32), x, 33, 60));
    g.add(at(cyl(2, 2, 0.4, M.plastic(0x050505, 1), 24), x, 36, 60));
    g.add(at(decal(12, 4, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, t, W / 2, H / 2, { size: 2.6 * k, color: "#eee" }); }, { pxPerMm: 24 }), x, 33.05, 69));
  });
  // probes plugged in, leads curling off
  for (const [x, c, end] of [[0, 0x1b1c20, [-70, 2, 90]], [24, 0xd0342c, [80, 2, 100]]]) {
    g.add(at(lathe([[0, 0], [4, 0], [4, 12], [3.4, 14], [0, 14]], M.rubber(c), 24), x, 36, 60));
    g.add(tube([[x, 50, 60], [x, 70, 75], [end[0] * 0.5, 30, end[2] + 10], [end[0], 6, end[2]]], 1.6, M.rubber(c), { seg: 60 }));
    const probe = new THREE.Group();
    probe.add(lathe([[0, 0], [4.5, 0], [5, 50], [3.5, 60], [2, 62], [0, 62]], M.rubber(c), 24));
    probe.add(at(torus(5.5, 1.2, M.rubber(c), 8, 24), 0, 50, 0, Math.PI / 2));
    probe.add(at(cyl(0.9, 0.9, 16, M.chrome(), 12), 0, 70, 0));
    probe.add(at(cyl(0.1, 0.9, 3, M.chrome(), 12), 0, 79.5, 0));
    probe.rotation.z = end[0] < 0 ? Math.PI / 2 : -Math.PI / 2; probe.position.set(end[0], 6, end[2]);
    g.add(probe);
  }
  g.add(at(decal(40, 8, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "DIGITAL MULTIMETER", W / 2, H / 2, { size: 3 * k, color: "#ddd" }); }, { pxPerMm: 16 }), 0, 33.05, -76));
  return g;
}

function helpingHands() {
  const g = new THREE.Group();
  g.add(at(rbox(90, 14, 60, 6, M.metal(0x2a2c31, 0.5)), 0, 7, 0));
  for (const [x, z] of [[-38, -24], [38, -24], [-38, 24], [38, 24]]) g.add(at(cyl(4, 4, 1.5, M.rubber(0x1b1c20), 20), x, -0.5, z));
  g.add(at(cyl(4, 4, 60, M.chrome(), 24), 0, 44, 0));
  // the magnifier on a ball joint: a black ring holding a domed glass lens, tilted towards you
  const lens = new THREE.Group();
  lens.add(torus(34, 3.2, M.plastic(0x1b1c20, 0.4), 16, 72));
  const glass = new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.02, transmission: 0.92, thickness: 4, ior: 1.5, transparent: true, opacity: 0.3, clearcoat: 1, side: THREE.DoubleSide, depthWrite: false });
  const disc = mesh(new THREE.SphereGeometry(34, 48, 12), glass); disc.scale.set(1, 1, 0.12); lens.add(disc);
  lens.add(at(cyl(2.5, 2.5, 16, M.plastic(0x1b1c20, 0.4), 16), 0, -41, 0));
  lens.rotation.x = -0.35; lens.position.set(0, 128, -6);
  g.add(lens);
  g.add(at(sphere(5, M.chrome()), 0, 78, 0));
  g.add(tube([[0, 78, 0], [0, 84, -2], [0, 88, -4]], 2, M.chrome(), { seg: 12 }));
  // two flexible gooseneck arms ending in crocodile clips
  for (const s of [-1, 1]) {
    const pts = [[s * 6, 60, 0], [s * 28, 76, 10], [s * 50, 66, 26], [s * 62, 44, 34]];
    const curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)));
    g.add(mesh(new THREE.TubeGeometry(curve, 80, 2.6, 12), M.chrome()));
    for (let i = 1; i < 40; i++) { const p = curve.getPoint(i / 40), t = curve.getTangent(i / 40); const r = torus(2.7, 0.5, M.chrome(), 6, 16); r.position.copy(p); r.lookAt(p.clone().add(t)); g.add(r); }
    const clip = new THREE.Group();
    for (const t of [-1, 1]) { const jaw = extrude([[0, 0], [16, 0], [17, t * 0.8], [0, t * 1.8]], 4, M.chrome()); jaw.position.y = t * 0.8; jaw.rotation.z = t * 0.2; clip.add(jaw); }
    clip.add(at(torus(1.6, 0.4, M.chrome(), 8, 20), 3, 0, 0, Math.PI / 2));
    clip.position.set(s * 62, 42, 36); clip.rotation.set(0, s > 0 ? -1.2 : Math.PI + 1.2, -0.6);
    g.add(clip);
  }
  return g;
}

function desolderPump() {
  const g = new THREE.Group();
  const p = new THREE.Group();
  p.add(lathe([[0, 0], [9.5, 0], [9.5, 120], [0, 120]], M.metal(0xc9ccd1, 0.2), 48));
  p.add(at(lathe([[9.6, 0], [10, 1], [10, 32], [9.6, 33]], M.plastic(0x2a5ec9, 0.4), 48), 0, 40, 0));
  for (let i = 0; i < 10; i++) p.add(at(torus(10, 0.35, M.plastic(0x1d4aa0, 0.5), 6, 40), 0, 42 + i * 3, 0, Math.PI / 2));
  p.add(at(lathe([[0, 0], [9.4, 0], [8, 10], [3.2, 22], [3.2, 26], [0, 26]], M.plastic(0xf2efe6, 0.35), 40), 0, -26, 0));
  p.children.at(-1).rotation.x = Math.PI; p.children.at(-1).position.y = 0;
  p.add(at(cyl(2, 3.2, 10, M.plastic(0xf6f2e6, 0.3), 24), 0, -28, 0));
  // plunger rod and knob out the back, trigger button on the side
  p.add(at(cyl(2.6, 2.6, 40, M.chrome(), 24), 0, 140, 0));
  p.add(at(lathe([[0, 0], [7, 0], [8, 3], [8, 8], [6, 11], [0, 11]], M.plastic(0x1b1c20, 0.4), 32), 0, 160, 0));
  p.add(at(rbox(6, 10, 7, 2, M.plastic(0xd0342c, 0.4)), 10.5, 90, 0));
  p.rotation.z = -Math.PI / 2; p.position.y = 11;
  g.add(p);
  g.add(at(decal(40, 10, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "DESOLDERING PUMP", W / 2, H / 2, { size: 3 * k, color: "#555" }); }, { pxPerMm: 16 }), 80, 20.6, 0));
  return g;
}

function solderWick() {
  const g = new THREE.Group();
  const bob = lathe([[5, 0], [22, 0], [22, 2], [20, 2], [20, 10], [22, 10], [22, 12], [5, 12]], M.plastic(0x3a9a4a, 0.4), 48);
  g.add(bob);
  g.add(at(decal(40, 40, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, 20 * k, 0, 7); ctx.arc(W / 2, H / 2, 5 * k, 0, 7, true); ctx.clip();
    ctx.fillStyle = "#3a9a4a"; ctx.fillRect(0, 0, W, H); ctx.restore();
    text(ctx, "SOLDER WICK", W / 2, H * 0.22, { size: 3 * k }); text(ctx, "2.5 mm × 1.5 m", W / 2, H * 0.8, { size: 2.6 * k, weight: "normal" });
  }, { pxPerMm: 16 }), 0, 12.02, 0));
  // copper braid: a flat strip with a woven texture, running off the spool
  const braidTex = (ctx, W, H, k) => { ctx.fillStyle = "#b8703a"; ctx.fillRect(0, 0, W, H); ctx.strokeStyle = "#e8a066"; ctx.lineWidth = 0.25 * k; for (let x = -H; x < W; x += 0.6 * k) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + H, H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(x + H, 0); ctx.lineTo(x, H); ctx.stroke(); } };
  g.add(at(cyl(20.1, 20.1, 8, M.copper(), 48), 0, 6, 0));
  const strip = decal(50, 2.5, braidTex, { pxPerMm: 40, metal: 0.8, rough: 0.35, transparent: false });
  g.add(at(strip, 45, 0.3, 21.5));
  g.add(at(box(50, 0.5, 2.5, M.copper()), 45, 0.2, 21.5));
  // the used end, silver with solder
  g.add(at(box(8, 0.8, 2.6, M.tin()), 66, 0.4, 21.5));
  return g;
}

function heatGun() {
  const g = new THREE.Group();
  const body = new THREE.Group();
  body.add(lathe([[0, 0], [22, 0], [24, 10], [24, 70], [20, 86], [0, 88]], M.plastic(0x1f2024, 0.45), 48));
  for (let i = 0; i < 12; i++) body.add(at(box(1.4, 12, 40, M.plastic(0x0b0b0c, 0.9)), Math.cos(i * 0.52) * 24.2, 20, Math.sin(i * 0.52) * 24.2, 0, -i * 0.52, 0));
  body.add(at(lathe([[14, 0], [16, 0], [15, 50], [13, 52], [0, 52]], M.metal(0xc9ccd1, 0.3), 40), 0, 88, 0));
  body.add(at(lathe([[12, 0], [13, 0], [13, 4], [12, 4]], M.darkSteel(), 40), 0, 136, 0));
  body.rotation.z = -Math.PI / 2; body.position.set(-20, 110, 0);
  g.add(body);
  // pistol grip, trigger, the fold-out stand and the cable
  g.add(at(rbox(30, 90, 36, 12, M.plastic(0xd08a3a, 0.45)), -8, 60, 0, 0, 0, 0.18));
  g.add(at(rbox(12, 22, 16, 4, M.plastic(0x1f2024, 0.45)), 14, 70, 0, 0, 0, 0.18));
  g.add(at(rbox(40, 8, 50, 4, M.plastic(0x1f2024, 0.45)), -16, 4, 0));
  g.add(at(decal(40, 18, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "HOT AIR", W / 2, H * 0.35, { size: 5 * k, color: "#eee" }); text(ctx, "⚠ 500 °C", W / 2, H * 0.75, { size: 4 * k, color: "#e8b83a" }); }, { pxPerMm: 12 }), 20, 110, 24.1, 0, 0, 0));
  g.add(tube([[-20, 10, 0], [-40, 2, 10], [-80, 2, 30], [-110, 2, 20]], 4, M.rubber(0x1b1c20), { seg: 40 }));
  return g;
}

function safetyGlasses() {
  const g = new THREE.Group();
  const lensMat = new THREE.MeshPhysicalMaterial({ color: 0xeaf6ff, roughness: 0.03, transmission: 0.9, thickness: 1.5, transparent: true, opacity: 0.4, clearcoat: 1, side: THREE.DoubleSide, depthWrite: false });
  // a one-piece wraparound visor curving round the face (front at -z)
  const R = 80, spread = 0.8, cz = R - 6;
  const visor = mesh(new THREE.CylinderGeometry(R, R, 44, 64, 1, true, Math.PI - spread, spread * 2), lensMat);
  visor.position.set(0, 26, cz); g.add(visor);
  const arc = (y) => Array.from({ length: 33 }, (_, i) => { const t = Math.PI - spread + (i / 32) * spread * 2; return [R * Math.sin(t), y, cz + R * Math.cos(t)]; });
  g.add(tube(arc(48), 2.6, M.plastic(0xd08a3a, 0.4), { seg: 64, radial: 10 }));        // the brow bar
  g.add(tube(arc(4.5), 0.9, M.plastic(0xd08a3a, 0.4), { seg: 64, radial: 8 }));         // the bottom edge
  g.add(at(rbox(18, 10, 6, 3, M.rubber(0x2a2b30)), 0, 10, -4));                             // nose pad
  // side arms running back past the ears, with vent slots
  const endX = R * Math.sin(Math.PI - spread), endZ = cz + R * Math.cos(Math.PI - spread);
  for (const s of [-1, 1]) {
    const arm = new THREE.Group();
    arm.add(at(rbox(5, 9, 110, 2.5, M.plastic(0xd08a3a, 0.4)), 0, 0, 55));
    arm.add(at(rbox(5, 16, 22, 4, M.plastic(0xd08a3a, 0.4)), 0, -5, 108, -0.35, 0, 0));
    for (let i = 0; i < 4; i++) arm.add(at(box(5.2, 1, 6, M.plastic(0x2a2b30, 0.9)), 0, 1.5, 14 + i * 9));
    arm.position.set(s * endX, 44, endZ); arm.rotation.y = s * 0.06;
    g.add(arm);
  }
  g.add(at(sideDecal(26, 5, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "EN166 · Z87+", W / 2, H / 2, { size: 2.6 * k, color: "#333" }); }, { pxPerMm: 16 }), 0, 41, -6.2, 0, Math.PI, 0));
  return g;
}

function fluxPen() {
  const g = new THREE.Group(), p = new THREE.Group();
  p.add(lathe([[0, 0], [6, 0], [6.5, 4], [6.5, 100], [5.5, 104], [0, 104]], M.plastic(0xe8b83a, 0.35), 40));
  p.add(at(lathe([[0, 0], [6.8, 0], [6.8, 34], [6, 38], [0, 38]], M.plastic(0x1b1c20, 0.35), 40), 0, 100, 0));
  p.add(at(box(2, 30, 4, M.plastic(0x1b1c20, 0.35)), 7, 118, 0));
  p.add(at(lathe([[0, 0], [5, 0], [2.5, 8], [2, 12], [0, 12]], M.plastic(0xf6f2e6, 0.5), 32), 0, -12, 0));
  p.children.at(-1).rotation.x = Math.PI; p.children.at(-1).position.y = 0;
  p.add(at(cyl(0.8, 2, 8, M.plastic(0xd8ccb0, 0.8), 16), 0, -16, 0));
  p.add(at(sideDecal(12, 60, (ctx, W, H, k) => { ctx.fillStyle = "#e8b83a"; ctx.fillRect(0, 0, W, H); text(ctx, "NO-CLEAN FLUX", W / 2, H / 2, { size: 5 * k, color: "#1b1b1b", rot: -Math.PI / 2 }); }, { pxPerMm: 16, transparent: false }), 0, 50, 6.55));
  p.rotation.z = -Math.PI / 2; p.position.y = 7;
  g.add(p);
  return g;
}

function tipCleaner() {
  const g = new THREE.Group();
  g.add(lathe([[0, 0], [38, 0], [40, 3], [40, 12], [36, 14], [0, 14]], M.metal(0x3a3c42, 0.4), 64));
  g.add(at(lathe([[0, 0], [27, 0], [29, 24], [27, 26], [25, 26], [25, 4], [0, 4]], M.plastic(0x1b1c20, 0.45), 48), 0, 14, 0));
  const wool = mesh(new THREE.TorusKnotGeometry(13, 6, 220, 12, 11, 17), M.brass()); wool.scale.set(1, 0.55, 1); g.add(at(wool, 0, 36, 0, Math.PI / 2, 0, 0));
  const wool2 = mesh(new THREE.TorusKnotGeometry(9, 4, 160, 10, 7, 13), M.metal(0xd8b86a, 0.5)); wool2.scale.set(1, 0.6, 1); g.add(at(wool2, 3, 40, -2, Math.PI / 2, 0.3, 0));
  g.add(at(decal(50, 8, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "TIP CLEANER", W / 2, H / 2, { size: 4 * k, color: "#bbb" }); }, { pxPerMm: 12 }), 0, 14.02, 32));
  return g;
}

function glueGun() {
  const g = new THREE.Group();
  const body = new THREE.Group();
  body.add(lathe([[0, 0], [16, 0], [20, 8], [21, 60], [17, 80], [8, 88], [0, 88]], M.plastic(0x3a9a4a, 0.4), 48));
  body.add(at(lathe([[5, 0], [5, 10], [3, 22], [1.2, 28], [0, 28]], M.metal(0xd8b86a, 0.3), 32), 0, 88, 0));
  body.rotation.z = -Math.PI / 2; body.position.set(-30, 100, 0);
  g.add(body);
  g.add(at(rbox(28, 84, 32, 12, M.plastic(0x3a9a4a, 0.4)), -14, 56, 0, 0, 0, 0.22));
  g.add(at(rbox(12, 36, 14, 5, M.plastic(0xe8b83a, 0.4)), 12, 66, 0, 0, 0, 0.22));
  // the wire stand that folds down, a glue stick feeding in the back
  g.add(bentWire([[30, 90, -12], [34, 0, -18], [34, 0, 18], [30, 90, 12]], 1.2, M.chrome()));
  const stick = mesh(new THREE.CylinderGeometry(5.5, 5.5, 70, 24), new THREE.MeshPhysicalMaterial({ color: 0xf8f6ee, roughness: 0.3, transmission: 0.6, thickness: 6, transparent: true, opacity: 0.85 }));
  stick.rotation.z = Math.PI / 2; g.add(at(stick, -64, 100, 0));
  g.add(tube([[-26, 30, 0], [-40, 6, 10], [-90, 4, 30], [-120, 4, 20]], 3, M.rubber(0x1b1c20), { seg: 40 }));
  g.add(at(decal(36, 14, (ctx, W, H, k) => { ctx.clearRect(0, 0, W, H); text(ctx, "GLUE GUN", W / 2, H * 0.4, { size: 5 * k, color: "#fff" }); text(ctx, "20 W", W / 2, H * 0.8, { size: 3.4 * k, color: "#fff" }); }, { pxPerMm: 12 }), 10, 100, 21.2, 0, 0, 0));
  return g;
}

export const TOOLS = {
  "needle-nose-pliers": () => pliers("needle"),
  "flush-cutters": () => pliers("flush"),
  "wire-stripper": () => pliers("stripper"),
  "tweezers": tweezers,
  "small-screwdriver-set": screwdriverSet,
  "soldering-iron": solderingIron,
  "digital-multimeter": multimeter,
  "helping-hands": helpingHands,
  "desoldering-pump": desolderPump,
  "solder-wick": solderWick,
  "heat-gun": heatGun,
  "safety-glasses": safetyGlasses,
  "flux-pen": fluxPen,
  "tip-cleaner": tipCleaner,
  "hot-glue-gun": glueGun,
};
