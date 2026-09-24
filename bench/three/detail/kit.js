// The detailed-model kit: real-looking materials, printed circuit boards
// with traces and silkscreen, and the small standard components (headers,
// chips, SMD resistors, capacitors, crystals, connectors …) that the
// Parts & Tools models are assembled from. Millimetres, y up.
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

export { THREE };
export const P = 2.54;

// ---- materials ------------------------------------------------------------------
const cache = new Map();
const std = (key, make) => { if (!cache.has(key)) cache.set(key, make()); return cache.get(key); };
export const M = {
  plastic: (c, rough = 0.55) => std(`p${c}${rough}`, () => new THREE.MeshStandardMaterial({ color: c, roughness: rough, metalness: 0 })),
  gloss: (c) => std(`g${c}`, () => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.3, clearcoat: 0.6, clearcoatRoughness: 0.2 })),
  rubber: (c) => std(`r${c}`, () => new THREE.MeshStandardMaterial({ color: c, roughness: 0.92 })),
  metal: (c = 0xd6d8dc, rough = 0.28) => std(`m${c}${rough}`, () => new THREE.MeshStandardMaterial({ color: c, roughness: rough, metalness: 1 })),
  tin: () => M.metal(0xd9dbde, 0.3),
  gold: () => M.metal(0xe3b964, 0.22),
  copper: () => M.metal(0xd08a55, 0.3),
  brass: () => M.metal(0xc9a95a, 0.35),
  steel: () => M.metal(0xb9bec6, 0.35),
  chrome: () => M.metal(0xeef0f3, 0.08),
  darkSteel: () => M.metal(0x4a4f57, 0.45),
  mask: (c) => std(`k${c}`, () => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.42, clearcoat: 0.5, clearcoatRoughness: 0.35 })),
  glass: (c = 0xffffff, opacity = 0.35) => std(`gl${c}${opacity}`, () => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.05, metalness: 0, transparent: true, opacity, clearcoat: 1, side: THREE.DoubleSide, depthWrite: false })),
  epoxy: (c, glow = 0) => std(`e${c}${glow}`, () => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.12, transmission: 0.35, thickness: 2, transparent: true, opacity: 0.9, clearcoat: 1, emissive: c, emissiveIntensity: glow })),
  // a lit LED: only its own light (a diffuse colour would wash it pastel under the room lighting)
  glow: (c, k = 1) => std(`w${c}${k}`, () => new THREE.MeshStandardMaterial({ color: 0x000000, emissive: c, emissiveIntensity: k, roughness: 0.6 })),
  black: () => M.plastic(0x1b1c20, 0.6),
  ceramic: (c) => std(`c${c}`, () => new THREE.MeshStandardMaterial({ color: c, roughness: 0.75 })),
};
const asMat = (m) => (m && m.isMaterial ? m : M.plastic(m ?? 0x888888));

// ---- primitives -----------------------------------------------------------------
export function mesh(geo, mat) { const m = new THREE.Mesh(geo, asMat(mat)); m.castShadow = true; m.receiveShadow = true; return m; }
export const box = (w, h, d, mat) => mesh(new THREE.BoxGeometry(w, h, d), mat);
export const rbox = (w, h, d, r, mat, seg = 3) => mesh(new RoundedBoxGeometry(w, h, d, seg, Math.max(0.01, Math.min(r, w / 2 - 0.01, h / 2 - 0.01, d / 2 - 0.01))), mat);
export const cyl = (rt, rb, h, mat, seg = 32) => mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat);
export const sphere = (r, mat, ws = 24, hs = 16) => mesh(new THREE.SphereGeometry(r, ws, hs), mat);
export const torus = (r, t, mat, rs = 12, ts = 32, arc = Math.PI * 2) => mesh(new THREE.TorusGeometry(r, t, rs, ts, arc), mat);
// place (and, only when given, turn) an object — a decal keeps its own lie-flat rotation
export function at(o, x = 0, y = 0, z = 0, rx, ry, rz) { o.position.set(x, y, z); if (rx !== undefined || ry !== undefined || rz !== undefined) o.rotation.set(rx || 0, ry || 0, rz || 0); return o; }
export function group(...kids) { const g = new THREE.Group(); kids.flat().forEach((k) => k && g.add(k)); return g; }
// a lathe from [radius, y] pairs
export const lathe = (pts, mat, seg = 48) => mesh(new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(Math.max(0, r), y)), seg), mat);
// an extruded 2D outline ([x, y] pairs, in the xy plane), depth along z, centred on z
export function extrude(pts, depth, mat, { bevel = 0, holes = [], curveSeg = 12 } = {}) {
  const s = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
  holes.forEach((h) => s.holes.push(new THREE.Path(h.map(([x, y]) => new THREE.Vector2(x, y)))));
  const geo = new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: bevel > 0, bevelSize: bevel, bevelThickness: bevel, bevelSegments: 3, curveSegments: curveSeg });
  geo.translate(0, 0, -depth / 2);
  return mesh(geo, mat);
}
export function shapeMesh(shape, depth, mat, bevel = 0) {
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: bevel > 0, bevelSize: bevel, bevelThickness: bevel, bevelSegments: 3, curveSegments: 24 });
  geo.translate(0, 0, -depth / 2);
  return mesh(geo, mat);
}
export function tube(points, r, mat, { seg = 96, radial = 12, tension = 0.5 } = {}) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), false, "catmullrom", tension);
  return mesh(new THREE.TubeGeometry(curve, seg, r, radial), mat);
}
// a wire bent through straight segments with small round bends
export function bentWire(points, r, mat) {
  const g = new THREE.Group();
  const V = points.map((p) => new THREE.Vector3(...p));
  for (let i = 0; i < V.length - 1; i++) {
    const a = V[i], b = V[i + 1], len = a.distanceTo(b);
    const c = cyl(r, r, len, mat, 10);
    c.position.copy(a).add(b).multiplyScalar(0.5);
    c.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    g.add(c);
    if (i > 0) g.add(at(sphere(r, mat, 10, 8), a.x, a.y, a.z));
  }
  return g;
}

// ---- canvas textures ---------------------------------------------------------------
export function canvasTex(w, h, draw) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}
// a flat printed face lying on +y, size w × d mm; draw(ctx, W, H, k) with k = px per mm
export function decal(w, d, draw, { pxPerMm = 24, glow = 0, transparent = true, rough = 0.5, metal = 0 } = {}) {
  const k = Math.min(pxPerMm, 2048 / Math.max(w, d));
  const t = canvasTex(Math.max(8, Math.round(w * k)), Math.max(8, Math.round(d * k)), (ctx, W, H) => draw(ctx, W, H, k));
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshStandardMaterial({
    map: t, transparent, roughness: rough, metalness: metal, polygonOffset: true, polygonOffsetFactor: -2,
    emissive: glow ? 0xffffff : 0x000000, emissiveMap: glow ? t : null, emissiveIntensity: glow }));
  m.rotation.x = -Math.PI / 2; m.receiveShadow = true;
  return m;
}
// a decal standing on a vertical face (facing +z)
export function sideDecal(w, h, draw, opts) { const m = decal(w, h, draw, opts); m.rotation.x = 0; return m; }
export function text(ctx, s, x, y, { size = 20, color = "#fff", font = "Arial", weight = "bold", align = "center", base = "middle", rot = 0 } = {}) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
  ctx.fillStyle = color; ctx.font = `${weight} ${size}px ${font}`; ctx.textAlign = align; ctx.textBaseline = base; ctx.fillText(s, 0, 0);
  ctx.restore();
}
export function hex(c) { return "#" + new THREE.Color(c).getHexString(); }
const shade = (c, k) => { const col = new THREE.Color(c); col.multiplyScalar(k); return "#" + col.getHexString(); };

// ---- PCBs ---------------------------------------------------------------------------
// A board w × d (x × z), 1.6 thick, top at y = 1.6. Options:
//   holes:   [[x, z, r]] plated mounting holes
//   pads:    [[x, z]] round plated through-holes (for pins that go through)
//   traces:  number of random-looking copper traces, or [[x1,z1,x2,z2,...]] polylines
//   silk:    (ctx, mm) => draw white silkscreen, mm(x, z) → canvas px
//   corner:  corner radius
export function pcb(w, d, color, { holes = "corners", pads = [], traces = 14, silk = null, corner = 1, seed = 1, thick = 1.6, finish = "gold" } = {}) {
  const g = new THREE.Group();
  const core = rbox(w, thick, d, Math.min(corner, thick / 2 - 0.01) || 0.2, M.mask(color), 2);
  g.add(at(core, 0, thick / 2, 0));
  if (holes === "corners") holes = w > 16 && d > 14 ? [[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([a, b]) => [a * (w / 2 - 2.6), b * (d / 2 - 2.6), 1.5]) : [];
  let rnd = seed * 9301 + 49297;
  const rand = () => ((rnd = (rnd * 9301 + 49297) % 233280) / 233280);
  const pad = finish === "gold" ? "#e3c07a" : "#d8d9db";
  const top = decal(w, d, (ctx, W, H, k) => {
    const mm = (x, z) => [(x + w / 2) * k, (z + d / 2) * k];
    // board edge darkening
    ctx.fillStyle = hex(color); ctx.fillRect(0, 0, W, H);
    const gr = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.2, W / 2, H / 2, Math.max(W, H) * 0.75);
    gr.addColorStop(0, "rgba(255,255,255,0.04)"); gr.addColorStop(1, "rgba(0,0,0,0.12)"); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
    // copper traces under the mask: slightly lighter lines with vias
    ctx.strokeStyle = shade(color, 1.35); ctx.lineCap = "round"; ctx.lineJoin = "round";
    const lines = Array.isArray(traces) ? traces : Array.from({ length: traces }, () => {
      const x0 = (rand() - 0.5) * w * 0.9, z0 = (rand() - 0.5) * d * 0.9;
      const x1 = x0 + (rand() - 0.5) * w * 0.6, z1 = z0 + (rand() - 0.5) * d * 0.6;
      const mid = rand() > 0.5 ? [x1, z0] : [x0, z1];
      return [x0, z0, ...mid, x1, z1];
    });
    for (const L of lines) {
      ctx.lineWidth = Math.max(1, (0.25 + rand() * 0.3) * k); ctx.beginPath();
      for (let i = 0; i < L.length; i += 2) { const [x, y] = mm(L[i], L[i + 1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
      ctx.stroke();
      const [ex, ey] = mm(L[L.length - 2], L[L.length - 1]);
      ctx.fillStyle = pad; ctx.beginPath(); ctx.arc(ex, ey, 0.35 * k, 0, 7); ctx.fill();
      ctx.fillStyle = "#111"; ctx.beginPath(); ctx.arc(ex, ey, 0.15 * k, 0, 7); ctx.fill();
    }
    for (const [x, z] of pads) {
      const [px, py] = mm(x, z);
      ctx.fillStyle = pad; ctx.beginPath(); ctx.arc(px, py, 0.85 * k, 0, 7); ctx.fill();
    }
    for (const [x, z, r] of holes) {
      const [px, py] = mm(x, z);
      ctx.fillStyle = pad; ctx.beginPath(); ctx.arc(px, py, (r + 0.8) * k, 0, 7); ctx.fill();
    }
    if (silk) { ctx.fillStyle = ctx.strokeStyle = "#f4f4f0"; ctx.lineWidth = 0.18 * k; silk(ctx, mm, k); }
  }, { rough: 0.4 });
  g.add(at(top, 0, thick + 0.01, 0, -Math.PI / 2));
  // plated holes: a dark hole with a gold ring
  for (const [x, z, r] of holes) {
    g.add(at(cyl(r, r, thick + 0.06, M.plastic(0x08090a, 0.9), 24), x, thick / 2, z));
    g.add(at(torus(r + 0.35, 0.3, finish === "gold" ? M.gold() : M.tin(), 8, 28), x, thick + 0.02, z, Math.PI / 2));
  }
  g.userData.top = thick;
  return g;
}
// silkscreen helpers for pcb({silk})
export const silkText = (s, x, z, size = 1.2, opts = {}) => (ctx, mm, k) => { const [px, py] = mm(x, z); text(ctx, s, px, py, { size: size * k, color: opts.color || "#f4f4f0", rot: opts.rot || 0, align: opts.align || "center", weight: opts.weight || "bold", font: opts.font || "Arial" }); };
export const silkRect = (x, z, w, d) => (ctx, mm, k) => { const [px, py] = mm(x - w / 2, z - d / 2); ctx.strokeRect(px, py, w * k, d * k); };
export const silkAll = (...fs) => (ctx, mm, k) => fs.forEach((f) => f(ctx, mm, k));

// ---- solder, pins, headers -------------------------------------------------------------
export const solderJoint = (r = 0.9, h = 0.9) => lathe([[0, 0], [r, 0], [r * 0.8, h * 0.3], [r * 0.45, h * 0.75], [0.33, h]], M.tin(), 20);

// one square header pin (0.64 mm) with pointed ends, length L, centred on y = 0
function pinGeo(L) {
  const g = new THREE.Group();
  g.add(box(0.64, L - 1.2, 0.64, M.gold()));
  for (const s of [-1, 1]) { const tip = mesh(new THREE.CylinderGeometry(0.12, 0.45, 0.6, 4), M.gold()); tip.rotation.y = Math.PI / 4; tip.position.y = s * (L / 2 - 0.3); if (s < 0) tip.rotation.x = Math.PI; g.add(tip); }
  return g;
}
// a header strip along x: n pins × rows, male ("up" out of the top, or "down" through a board) or female
export function header(n, { rows = 1, female = false, dir = "up", color = 0x141518, pitch = P, pinLen = 11.5, bodyH = 2.5, rightAngle = false } = {}) {
  const g = new THREE.Group();
  const L = n * pitch, Wd = rows * pitch;
  const body = new THREE.Group();
  if (female) {
    body.add(at(rbox(L, 8.5, Wd, 0.25, M.plastic(color, 0.5)), 0, 4.25, 0));
    for (let i = 0; i < n; i++) for (let r = 0; r < rows; r++) {
      const x = -L / 2 + pitch / 2 + i * pitch, z = -Wd / 2 + pitch / 2 + r * pitch;
      body.add(at(box(1.05, 0.05, 1.05, M.plastic(0x020202, 1)), x, 8.51, z));
      body.add(at(mesh(new THREE.CylinderGeometry(0.75, 0.52, 0.5, 4), M.plastic(0x050505, 0.9)), x, 8.3, z, 0, Math.PI / 4));
      body.add(at(box(0.64, 3, 0.64, M.gold()), x, -1.5, z));    // tail through the board
    }
    g.add(body);
    return g;
  }
  // male: plastic spacer with chamfered cells, pins through it
  for (let i = 0; i < n; i++) for (let r = 0; r < rows; r++) {
    const x = -L / 2 + pitch / 2 + i * pitch, z = -Wd / 2 + pitch / 2 + r * pitch;
    body.add(at(rbox(pitch - 0.08, bodyH, pitch - 0.08, 0.3, M.plastic(color, 0.5), 2), x, bodyH / 2, z));
    if (rightAngle) {
      body.add(bentWire([[x, -3, z], [x, bodyH / 2, z], [x, bodyH / 2, z + 8]], 0.33, M.gold()));
    } else {
      // up: 3 mm below the spacer (into a board), the rest standing up. down (the strip is then flipped
      // under a board): a short stub pokes 1 mm out of the board's top, the long end hangs below
      const pin = pinGeo(pinLen); pin.position.set(x, dir === "up" ? pinLen / 2 - 3 : pinLen / 2 - 2.6, z); body.add(pin);
    }
  }
  g.add(body);
  return g;
}
// a header soldered into a board from below (pins sticking down) — the common module style
export function headerDown(n, opts = {}) { const h = header(n, { ...opts, dir: "down" }); h.rotation.x = Math.PI; return h; }

// ---- chips ------------------------------------------------------------------------------
function chipTop(w, d, lines, { color = "#c9ccd1", size = 1.1, logo = null, dot = true } = {}) {
  return decal(w, d, (ctx, W, H, k) => {
    ctx.clearRect(0, 0, W, H);
    lines.forEach((s, i) => text(ctx, s, W / 2, H / 2 + (i - (lines.length - 1) / 2) * size * 1.35 * k, { size: size * k, color, font: "Arial", weight: i ? "normal" : "bold" }));
    if (dot) { ctx.fillStyle = "rgba(255,255,255,0.18)"; ctx.beginPath(); ctx.arc(0.9 * k, H - 0.9 * k, 0.45 * k, 0, 7); ctx.fill(); }
  }, { pxPerMm: 60 });
}
// DIP package, n pins, body along x, legs down (seated on y = 0, legs below)
export function dip(n, lines, { color = 0x17181b } = {}) {
  const g = new THREE.Group(), half = n / 2, L = half * P;
  const body = rbox(L + 0.5, 3.3, 6.35, 0.35, M.plastic(color, 0.55)); g.add(at(body, 0, 2.4 + 1.65, 0));
  // pin-1 notch and dimple
  g.add(at(cyl(0.8, 0.8, 0.4, M.plastic(0x0c0c0e, 0.7), 20), -L / 2 - 0.25, 5.55, 0, 0, 0, 0));
  g.add(at(cyl(0.45, 0.45, 0.08, M.plastic(0x2a2b30, 0.3), 16), -L / 2 + 1.3, 5.72, 1.9));
  g.add(at(chipTop(L - 1.5, 4.8, [].concat(lines), { size: 1.05, dot: false }), 0, 5.72, -0.3));
  for (let i = 0; i < half; i++) for (const s of [-1, 1]) {
    const x = -L / 2 + P / 2 + i * P;
    g.add(at(box(1.2, 0.25, 0.8, M.tin()), x, 3.0, s * 3.5));               // out of the body
    g.add(at(box(1.2, 1.6, 0.25, M.tin()), x, 2.3, s * 3.85));              // the wide shoulder
    g.add(at(mesh(new THREE.CylinderGeometry(0.25, 0.6, 0.5, 4), M.tin()), x, 1.25, s * 3.85, 0, Math.PI / 4));
    g.add(at(box(0.46, 3.2, 0.25, M.tin()), x, -0.6, s * 3.85));            // narrow leg into the hole
  }
  return g;
}
// SOIC / TSSOP gull-wing package on a board top (y = 0 is the board surface)
export function soic(n, lines, { w = null, d = 3.9, pitch = 1.27, color = 0x17181b } = {}) {
  const g = new THREE.Group(), half = n / 2, L = w ?? half * pitch + 0.4;
  g.add(at(rbox(L, 1.5, d, 0.15, M.plastic(color, 0.5)), 0, 0.85, 0));
  g.add(at(chipTop(L - 0.4, d - 0.6, [].concat(lines), { size: Math.min(0.75, d / 4) }), 0, 1.61, 0));
  for (let i = 0; i < half; i++) for (const s of [-1, 1]) {
    const x = -((half - 1) * pitch) / 2 + i * pitch;
    g.add(bentWire([[x, 0.9, s * (d / 2)], [x, 0.9, s * (d / 2 + 0.35)], [x, 0.12, s * (d / 2 + 0.6)], [x, 0.12, s * (d / 2 + 1.1)]], 0.13, M.tin()));
  }
  return g;
}
// QFP: legs on all 4 sides; QFN when legs = false
export function qfp(s, lines, { pins = null, legs = true, color = 0x17181b, h = 1.2 } = {}) {
  const g = new THREE.Group(), n = pins ?? Math.max(6, Math.round(s / 0.5) - 2);
  g.add(at(rbox(s, h, s, 0.1, M.plastic(color, 0.5)), 0, h / 2 + 0.1, 0));
  g.add(at(chipTop(s * 0.9, s * 0.9, [].concat(lines), { size: s / 9 }), 0, h + 0.11, 0));
  const step = (s - 1) / (n - 1);
  for (let i = 0; i < n; i++) {
    const o = -s / 2 + 0.5 + i * step;
    for (const [x, z, ry] of [[o, -1, 0], [o, 1, 0], [-1, o, 1], [1, o, 1]]) {
      const px = Math.abs(x) === 1 ? x * (s / 2) : x, pz = Math.abs(z) === 1 ? z * (s / 2) : z;
      if (legs) {
        const L = bentWire([[0, 0.55, 0], [0, 0.55, 0.3], [0, 0.1, 0.55], [0, 0.1, 0.95]], 0.09, M.tin());
        L.position.set(px, 0, pz);
        L.rotation.y = ry ? (x > 0 ? Math.PI / 2 : -Math.PI / 2) : (z > 0 ? 0 : Math.PI);
        g.add(L);
      } else g.add(at(box(ry ? 0.3 : 0.2, 0.2, ry ? 0.2 : 0.3, M.tin()), px + (ry ? x * 0.05 : 0), 0.1, pz + (ry ? 0 : z * 0.05)));
    }
  }
  return g;
}
export function sot23(lines = "", { pins = 3 } = {}) {
  const g = new THREE.Group();
  g.add(at(rbox(2.9, 1.0, 1.4, 0.1, M.plastic(0x17181b, 0.5)), 0, 0.6, 0));
  if (lines) g.add(at(chipTop(2.4, 1.0, [lines], { size: 0.55, dot: false }), 0, 1.11, 0));
  const xs = pins === 3 ? [[-0.95, -1], [0.95, -1], [0, 1]] : pins === 5 ? [[-0.95, -1], [0, -1], [0.95, -1], [-0.95, 1], [0.95, 1]] : [[-0.95, -1], [0, -1], [0.95, -1], [-0.95, 1], [0, 1], [0.95, 1]];
  for (const [x, s] of xs) g.add(bentWire([[x, 0.6, s * 0.7], [x, 0.6, s * 0.95], [x, 0.1, s * 1.15], [x, 0.1, s * 1.45]], 0.1, M.tin()));
  return g;
}
export function sot223(lines = "") {
  const g = new THREE.Group();
  g.add(at(rbox(6.5, 1.7, 3.5, 0.15, M.plastic(0x17181b, 0.5)), 0, 0.95, 0));
  g.add(at(chipTop(5.6, 2.6, [lines], { size: 0.7, dot: false }), 0, 1.81, 0));
  g.add(at(box(3, 0.2, 2, M.tin()), 0, 0.1, -2.9));
  for (const x of [-2.3, 0, 2.3]) g.add(bentWire([[x, 0.9, 1.75], [x, 0.9, 2.05], [x, 0.1, 2.4], [x, 0.1, 3.3]], 0.2, M.tin()));
  return g;
}

// ---- passives -----------------------------------------------------------------------------
const SMD = { "0402": [1, 0.5, 0.35], "0603": [1.6, 0.8, 0.45], "0805": [2, 1.25, 0.5], "1206": [3.2, 1.6, 0.55] };
export function smdR(code = "0603", mark = "103") {
  const [l, w, h] = SMD[code] || SMD["0603"], g = new THREE.Group();
  g.add(at(box(l * 0.7, h, w, M.plastic(0x141414, 0.6)), 0, h / 2 + 0.03, 0));
  for (const s of [-1, 1]) g.add(at(box(l * 0.17, h + 0.04, w + 0.02, M.tin()), s * l * 0.42, h / 2 + 0.03, 0));
  if (mark && l >= 1.6) g.add(at(decal(l * 0.6, w * 0.8, (ctx, W, H) => text(ctx, mark, W / 2, H / 2, { size: H * 0.7, color: "#e8e8e8", weight: "normal" }), { pxPerMm: 80 }), 0, h + 0.035, 0));
  return g;
}
export function smdC(code = "0603", color = 0xb89a72) {
  const [l, w, h] = SMD[code] || SMD["0603"], g = new THREE.Group();
  g.add(at(box(l * 0.7, h * 1.1, w, M.ceramic(color)), 0, h * 0.55 + 0.03, 0));
  for (const s of [-1, 1]) g.add(at(box(l * 0.17, h * 1.1 + 0.02, w + 0.02, M.tin()), s * l * 0.42, h * 0.55 + 0.03, 0));
  return g;
}
export function smdLed(color = 0xff3030, lit = true) {
  const g = new THREE.Group();
  g.add(at(box(1.6, 0.35, 0.8, M.plastic(0xf0efe9, 0.4)), 0, 0.2, 0));
  g.add(at(box(1.1, 0.12, 0.6, lit ? M.glow(color, 1.4) : M.epoxy(color)), 0, 0.43, 0));
  for (const s of [-1, 1]) g.add(at(box(0.25, 0.37, 0.82, M.tin()), s * 0.72, 0.2, 0));
  return g;
}
export function tantalum(mark = "106") {
  const g = new THREE.Group();
  g.add(at(rbox(2.4, 1.6, 1.6, 0.15, M.plastic(0xd6a22c, 0.45)), 0, 0.85, 0));
  g.add(at(box(0.5, 0.02, 1.4, M.plastic(0x7a5410, 0.6)), -0.8, 1.66, 0));
  for (const s of [-1, 1]) g.add(at(box(0.5, 0.9, 1.2, M.tin()), s * 1.35, 0.45, 0));
  g.add(at(decal(1.2, 0.9, (ctx, W, H) => text(ctx, mark, W / 2, H / 2, { size: H * 0.7, color: "#3a2a08" }), { pxPerMm: 80 }), 0.25, 1.67, 0));
  return g;
}
// electrolytic can capacitor, standing on y = 0
export function elCap(r, h, { color = 0x1f2a6e, stripe = 0xb8c0d8, text: label = "", smd = false } = {}) {
  const g = new THREE.Group();
  const pts = [[0, 0], [r * 0.92, 0], [r, 0.25], [r, h - 0.6], [r * 0.93, h - 0.35], [r * 0.93, h - 0.15], [r * 0.9, h], [0, h]];
  const sleeve = lathe(pts, M.gloss(color), 48);
  g.add(sleeve);
  // negative stripe: a wedge of the sleeve drawn on a thin shell
  const stripeGeo = new THREE.CylinderGeometry(r + 0.02, r + 0.02, h - 1, 24, 1, true, -0.35, 0.7);
  g.add(at(mesh(stripeGeo, M.gloss(stripe)), 0, (h - 1) / 2 + 0.3, 0));
  g.add(at(cyl(r * 0.88, r * 0.88, 0.05, M.metal(0xc7cbd1, 0.35), 40), 0, h - 0.02, 0));
  const vent = new THREE.Group(); vent.add(box(r * 1.4, 0.06, 0.18, M.metal(0x8c9098, 0.5))); vent.add(box(0.18, 0.06, r * 1.4, M.metal(0x8c9098, 0.5)));
  g.add(at(vent, 0, h + 0.02, 0));
  if (label) g.add(at(sideDecal(r * 1.2, h * 0.6, (ctx, W, H) => { ctx.clearRect(0, 0, W, H); text(ctx, label, W / 2, H / 2, { size: H * 0.28, color: "#dfe3ee", rot: -Math.PI / 2 }); }, { pxPerMm: 40 }), 0, h * 0.5, r + 0.03));
  if (smd) { g.add(at(box(r * 2.1, 0.7, r * 2.1, M.plastic(0x222222, 0.6)), 0, 0.35, 0)); g.children[0].position.y = 0.7; }
  return g;
}
export function ceramicDisc(r = 2.5, color = 0xd08a2a, mark = "104") {
  const g = new THREE.Group();
  const disc = sphere(r, M.ceramic(color), 24, 16); disc.scale.set(1, 1, 0.35); g.add(at(disc, 0, r + 2.5, 0));
  g.add(at(sideDecal(r * 1.2, r * 0.7, (ctx, W, H) => { ctx.clearRect(0, 0, W, H); text(ctx, mark, W / 2, H / 2, { size: H * 0.7, color: "#3a2a10" }); }, { pxPerMm: 50 }), 0, r + 2.5, r * 0.36));
  for (const s of [-1, 1]) g.add(at(cyl(0.25, 0.25, r + 5, M.tin(), 8), s * 1.27, (r + 5) / 2 - 2.5, 0));
  return g;
}
export function crystalHC49(label = "16.000") {
  const g = new THREE.Group();
  g.add(at(rbox(11, 3.6, 4.6, 1.2, M.chrome()), 0, 1.8 + 0.4, 0));
  g.add(at(rbox(11.6, 0.4, 5, 0.2, M.chrome()), 0, 0.2, 0));
  g.add(at(decal(8, 2.5, (ctx, W, H) => text(ctx, label, W / 2, H / 2, { size: H * 0.6, color: "#666a72" }), { pxPerMm: 60 }), 0, 4.01, 0));
  return g;
}
export function crystalSMD(label = "16.000") {
  const g = new THREE.Group();
  g.add(at(box(3.2, 0.5, 2.5, M.ceramic(0xe8e4dc)), 0, 0.25, 0));
  g.add(at(rbox(2.8, 0.35, 2.1, 0.15, M.chrome()), 0, 0.65, 0));
  return g;
}
// through-hole resistor body with correct colour bands, axis along x, centred
const BAND = ["#1a1a1a", "#7a4a26", "#d0312d", "#e8742a", "#f2d23a", "#3a9a4a", "#2a5ec9", "#7a3ac9", "#8a8a8a", "#f4f4f4"];
export function resistorBody(ohms, { body = 0xd9c7a0, len = 6.3, r = 1.25 } = {}) {
  const g = new THREE.Group();
  const pts = [[0, -len / 2], [r * 0.55, -len / 2], [r, -len / 2 + 0.55], [r, -len / 2 + 1.5], [r * 0.86, -len / 2 + 1.9], [r * 0.86, len / 2 - 1.9], [r, len / 2 - 1.5], [r, len / 2 - 0.55], [r * 0.55, len / 2], [0, len / 2]];
  const bodyM = lathe(pts, M.gloss(body), 40); bodyM.rotation.z = Math.PI / 2; g.add(bodyM);
  let v = Math.max(1, Math.round(ohms)), exp = 0; while (v >= 100) { v = Math.round(v / 10); exp++; }
  const digits = String(v).padStart(2, "0").split("").map(Number);
  const bands = [[-len / 2 + 0.95, digits[0]], [-len / 2 + 1.75, digits[1]], [-0.3, exp], [len / 2 - 0.95, "gold"]];
  for (const [x, c] of bands) {
    const rr = Math.abs(x) > len / 2 - 2 ? r + 0.015 : r * 0.86 + 0.015;
    const band = cyl(rr, rr, 0.45, c === "gold" ? M.metal(0xc9a24a, 0.4) : M.gloss(BAND[c]), 40); band.rotation.z = Math.PI / 2; band.position.x = x; g.add(band);
  }
  return g;
}

// ---- switches & connectors ---------------------------------------------------------------
export function tactSwitch(size = 6, { cap = 0x1b1c20, h = 5 } = {}) {
  const g = new THREE.Group();
  g.add(at(box(size, 3.4, size, M.plastic(0x1b1c20, 0.55)), 0, 1.7, 0));
  g.add(at(box(size + 0.02, 0.3, size + 0.02, M.steel()), 0, 3.5, 0));
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) g.add(at(cyl(0.35, 0.35, 0.3, M.plastic(0x0c0c0c), 10), x * (size / 2 - 0.8), 3.7, z * (size / 2 - 0.8)));
  g.add(at(cyl(1.75, 1.75, h - 3.4, M.plastic(cap, 0.5), 32), 0, 3.4 + (h - 3.4) / 2, 0));
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) g.add(bentWire([[x * (size / 2 + 0.2), 0.8, z * 2.25], [x * (size / 2 + 0.5), 0.3, z * 2.25], [x * (size / 2 + 0.5), -3, z * 2.25]], 0.25, M.tin()));
  return g;
}
export function tactSMD(size = 4) {
  const g = new THREE.Group();
  g.add(at(box(size, 1.2, size * 0.75, M.plastic(0xf1efe8, 0.5)), 0, 0.6, 0));
  g.add(at(box(size + 0.02, 0.2, size * 0.75 + 0.02, M.steel()), 0, 1.3, 0));
  g.add(at(cyl(0.8, 0.8, 0.5, M.plastic(0x1b1c20), 24), 0, 1.6, 0));
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) g.add(at(box(0.8, 0.2, 0.6, M.tin()), x * (size / 2 + 0.2), 0.1, z * size * 0.28));
  return g;
}
// USB receptacles facing -x (the plug goes in from -x)
export function usb(kind = "micro") {
  const g = new THREE.Group();
  const spec = { micro: [5, 2.6, 7.5, 0.9], mini: [7.7, 3.9, 9, 0.9], c: [7.4, 3.2, 8.9, 1.5], b: [12, 11, 16, 0.4], a: [12.5, 5.5, 14, 0.3] }[kind];
  const [w, h, l, rad] = spec;
  const shell = rbox(l, h, w, Math.min(rad, h / 2 - 0.05), M.chrome(), 4);
  g.add(at(shell, 0, h / 2, 0));
  // the opening: a dark mouth with the tongue inside
  const mouth = rbox(0.3, h * 0.75, w * 0.85, Math.min(rad * 0.8, h * 0.3), M.plastic(0x050505, 0.9), 3);
  g.add(at(mouth, -l / 2 - 0.02, h / 2, 0));
  const tongue = box(0.32, h * 0.2, w * 0.6, kind === "b" || kind === "a" ? M.plastic(0x2a5ec9, 0.5) : M.plastic(0x1b1c20, 0.5));
  g.add(at(tongue, -l / 2 - 0.05, h * (kind === "a" ? 0.6 : 0.5), 0));
  if (kind === "b") { g.children[0].material = M.metal(0xc9ccd1, 0.3); }
  for (const s of [-1, 1]) g.add(at(box(1.2, 0.3, 1, M.chrome()), l / 4, 0.15, s * (w / 2 + 0.4)));
  return g;
}
export function barrelJack() {
  const g = new THREE.Group();
  g.add(at(box(14, 11, 9, M.plastic(0x141518, 0.55)), 0, 5.5, 0));
  const hole = cyl(3.2, 3.2, 0.4, M.plastic(0x020202, 1), 32); hole.rotation.z = Math.PI / 2; g.add(at(hole, -7.02, 6, 0));
  const pin = cyl(1, 1, 0.5, M.chrome(), 16); pin.rotation.z = Math.PI / 2; g.add(at(pin, -7.1, 6, 0));
  return g;
}
export function screwTerminal(n, { color = 0x2e7fd0, pitch = 5.08 } = {}) {
  const g = new THREE.Group(), L = n * pitch;
  g.add(at(extrude([[-4, 0], [4, 0], [4, 6], [1.5, 10], [-4, 10]], L, M.plastic(color, 0.5), { bevel: 0.15 }), 0, 0, 0, 0, Math.PI / 2));
  for (let i = 0; i < n; i++) {
    const x = -L / 2 + pitch / 2 + i * pitch;
    const screw = new THREE.Group();
    screw.add(cyl(1.4, 1.4, 1, M.chrome(), 24));
    screw.add(at(box(2.8, 0.4, 0.45, M.plastic(0x2a2b30, 0.8)), 0, 0.35, 0, 0, 0.6));
    const well = cyl(1.7, 1.7, 0.2, M.plastic(0x050505), 24);
    g.add(at(well, x, 9.95, -1.2)); g.add(at(screw, x, 9.6, -1.2));
    const mouth = box(0.2, 3.2, 3.4, M.plastic(0x050505)); g.add(at(mouth, x, 3.5, 4.02, 0, Math.PI / 2));
    g.add(at(box(3, 2.4, 0.2, M.chrome()), x, 3.5, 4.05));
  }
  return g;
}
export function jst(n, { color = 0xf2efe6, pitch = 2 } = {}) {
  const g = new THREE.Group(), L = n * pitch + 1.5;
  g.add(at(box(L, 4.2, 4.5, M.plastic(color, 0.45)), 0, 2.1, 0));
  g.add(at(box(L - 1, 3.5, 0.2, M.plastic(0x2a2a2a, 0.9)), 0, 2.4, 2.26));
  for (let i = 0; i < n; i++) g.add(at(box(0.5, 3, 0.5, M.tin()), -((n - 1) * pitch) / 2 + i * pitch, 2.2, 1));
  return g;
}
export function trimpot3362({ color = 0x2e6fd0 } = {}) {
  const g = new THREE.Group();
  g.add(at(box(6.8, 4.8, 6.8, M.plastic(color, 0.45)), 0, 2.4, 0));
  g.add(at(cyl(2.8, 2.8, 0.6, M.metal(0xd8b86a, 0.35), 32), 0, 5.1, 0));
  const slot = new THREE.Group(); slot.add(box(3.8, 0.4, 0.6, M.plastic(0x5a4a2a, 0.8))); slot.add(box(0.6, 0.4, 3.8, M.plastic(0x5a4a2a, 0.8)));
  g.add(at(slot, 0, 5.3, 0, 0, 0.5));
  g.add(at(decal(5, 1.2, (ctx, W, H) => text(ctx, "103", W / 2, H / 2, { size: H * 0.8, color: "#ffffff" }), { pxPerMm: 60 }), 0, 4.81, 2.6));
  return g;
}
export function to92(lines = "", { color = 0x17181b, legLen = 14 } = {}) {
  // the classic half-round transistor body: flat marked face towards +z, three legs down
  const g = new THREE.Group(), body = new THREE.Group();
  body.add(mesh(new THREE.CylinderGeometry(2.4, 2.4, 4.8, 40, 1, false, Math.PI / 2, Math.PI), M.plastic(color, 0.5)));
  body.add(box(4.8, 4.8, 0.05, M.plastic(color, 0.5)));
  if (lines) body.add(at(sideDecal(4.2, 3.6, (ctx, W, H) => { [].concat(lines).forEach((s, i, a) => text(ctx, s, W / 2, H / 2 + (i - (a.length - 1) / 2) * H * 0.3, { size: H * 0.24, color: "#cfd2d8" })); }, { pxPerMm: 70 }), 0, 0, 0.04));
  g.add(at(body, 0, legLen + 2.4, 0));
  for (const x of [-1.27, 0, 1.27]) g.add(bentWire([[x, legLen, 0], [x, 2, 0], [x, 0, 0]], 0.22, M.tin()));
  return g;
}
export function mountHoleScrew(r = 1.5) {
  const g = new THREE.Group();
  g.add(cyl(r * 1.8, r * 1.8, 1, M.chrome(), 32));
  g.add(at(box(r * 2.4, 0.3, 0.45, M.plastic(0x222)), 0, 0.4, 0, 0, 0.7));
  return g;
}
// wire with insulation, stripped tinned end; points in mm
export function insulatedWire(points, color, { r = 0.8, strip = 0 } = {}) {
  const g = new THREE.Group();
  g.add(tube(points, r, M.plastic(color, 0.5)));
  if (strip) {
    const [a, b] = [points.at(-2), points.at(-1)].map((p) => new THREE.Vector3(...p));
    const dir = b.clone().sub(a).normalize(), end = b.clone().add(dir.multiplyScalar(strip));
    g.add(tube([b.toArray(), end.toArray()], r * 0.45, M.copper(), { seg: 4, radial: 8 }));
  }
  return g;
}
// knurled round knob (a pot / encoder shaft top)
export function knurledShaft(r, h, mat = M.metal(0xd9dce1, 0.35), teeth = 18) {
  const g = new THREE.Group();
  g.add(cyl(r, r, h, mat, teeth * 2));
  for (let i = 0; i < teeth; i++) { const a = (i / teeth) * Math.PI * 2; g.add(at(box(0.35, h * 0.9, 0.3, mat), Math.cos(a) * r, 0, Math.sin(a) * r, 0, -a)); }
  g.add(at(box(r * 2.1, 0.8, 0.7, M.plastic(0x202020, 0.8)), 0, h / 2 - 0.3, 0));
  return g;
}

// aim a camera from direction dir so the whole object fills the frame
export function fitCamera(cam, obj, dir = new THREE.Vector3(1.1, 0.95, 1.4), margin = 1.08) {
  const box = new THREE.Box3().setFromObject(obj), c = box.getCenter(new THREE.Vector3());
  const d = dir.clone().normalize(), R = box.getSize(new THREE.Vector3()).length() / 2;
  cam.position.copy(c).addScaledVector(d, R * 3); cam.lookAt(c); cam.updateMatrixWorld();
  // the corners in camera space → the distance that fits both the width and the height
  const inv = cam.matrixWorldInverse, tanV = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)), tanH = tanV * cam.aspect;
  let need = 0;
  for (let i = 0; i < 8; i++) {
    const p = new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).applyMatrix4(inv);
    const depth = -p.z - R * 3;                                   // relative to the centre plane
    need = Math.max(need, Math.abs(p.x) / tanH - depth, Math.abs(p.y) / tanV - depth);
  }
  cam.position.copy(c).addScaledVector(d, need * margin);
  cam.near = Math.max(0.01, need / 100); cam.far = need * 20; cam.updateProjectionMatrix(); cam.lookAt(c);
  return { center: c, dist: need * margin };
}
