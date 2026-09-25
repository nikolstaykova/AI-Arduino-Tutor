// Bench3D — the real three.js workbench: a lit wooden table, the breadboard
// (every hole its own pickable instance), the Arduino, parts and wires.
// It knows geometry only; app.js decides what is placed where and asks the
// engine whether it's right.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { PITCH, makeBreadboard, makeBoard, makePart, makeWire, makeLink, pinsFor } from "./models.js";

const HOLE_COLOUR = new THREE.Color(0x141210), HOLE_HOVER = new THREE.Color(0xffa62b), HOLE_ON = new THREE.Color(0x5fd08a);
const SOCK_COLOUR = new THREE.Color(0x0e0e10), REVEAL = new THREE.Color(0xe0392f);
const WIRE_COLOURS = [0x2f9a45, 0xf08a24, 0x2b8fd6, 0xf3d23c, 0x8c4bc8, 0xf5f5f5];

function woodTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 1024;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#8a6440"; ctx.fillRect(0, 0, 1024, 1024);
  for (let plank = 0; plank < 4; plank++) {
    const y0 = plank * 256, tone = [0, 12, -8, 6][plank];
    ctx.fillStyle = `rgb(${138 + tone},${100 + tone},${64 + tone})`; ctx.fillRect(0, y0, 1024, 254);
    for (let i = 0; i < 70; i++) {
      const y = y0 + Math.random() * 254, a = 0.04 + Math.random() * 0.08;
      ctx.strokeStyle = `rgba(60,36,18,${a})`; ctx.lineWidth = 0.6 + Math.random() * 2.2;
      ctx.beginPath(); ctx.moveTo(0, y);
      for (let x = 0; x <= 1024; x += 64) ctx.lineTo(x, y + Math.sin((x + i * 37) / 140) * 3);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(40,24,10,.55)"; ctx.fillRect(0, y0 + 254, 1024, 2);
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 2); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}

export class Bench3D {
  constructor(container) {
    this.container = container;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping; this.renderer.toneMappingExposure = 1.05;
    this.renderer.shadowMap.enabled = true; this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.canvas = this.renderer.domElement; this.canvas.className = "bench-canvas";
    container.appendChild(this.canvas);

    this.scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.add(new THREE.HemisphereLight(0xfff4e6, 0x3a2c1c, 0.5));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(-60, 160, 90); sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02;
    Object.assign(sun.shadow.camera, { left: -130, right: 130, top: 130, bottom: -130, near: 10, far: 400 });
    this.scene.add(sun);

    const table = new THREE.Mesh(new THREE.PlaneGeometry(900, 900), new THREE.MeshStandardMaterial({ map: woodTexture(), roughness: 0.7 }));
    table.rotation.x = -Math.PI / 2; table.receiveShadow = true; table.name = "table";
    this.scene.add(table); this.table = table;

    this.camera = new THREE.PerspectiveCamera(32, 1, 1, 3000);
    this.home = { pos: new THREE.Vector3(10, 190, 175), target: new THREE.Vector3(0, 0, -2) };
    this.camera.position.copy(this.home.pos);

    // our pointer handler is registered BEFORE OrbitControls', so it can turn orbit off
    // when the pointer goes down on something interactive
    this.handlers = {};
    this.canvas.addEventListener("pointerdown", (e) => this._down(e));
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.target.copy(this.home.target);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.12;
    this.controls.minDistance = 40; this.controls.maxDistance = 600;
    this.controls.maxPolarAngle = Math.PI * 0.47;
    this.controls.screenSpacePanning = false;     // panning slides across the tabletop, never into it
    this.canvas.addEventListener("pointermove", (e) => this._move(e));
    window.addEventListener("pointerup", (e) => this._up(e));
    this.canvas.addEventListener("dblclick", (e) => this._dbl(e));
    this.canvas.addEventListener("pointerleave", () => this._hover(null));

    this.ray = new THREE.Raycaster(); this.ndc = new THREE.Vector2();
    this.parts = {};            // id -> Object3D
    this.wires = new THREE.Group(); this.scene.add(this.wires);
    this.ghost = null;
    this.hoverRing = new THREE.Mesh(new THREE.TorusGeometry(1.05, 0.18, 10, 32), new THREE.MeshBasicMaterial({ color: 0xffa62b }));
    this.hoverRing.rotation.x = -Math.PI / 2; this.hoverRing.visible = false; this.scene.add(this.hoverRing);
    this.preview = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineDashedMaterial({ color: 0xffa62b, dashSize: 2, gapSize: 1.2 }));
    this.preview.visible = false; this.scene.add(this.preview);

    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    this.revealLayer = document.createElement("div"); this.revealLayer.className = "reveal-layer"; container.appendChild(this.revealLayer);
    this.revealLabels = [];
    const loop = () => {
      requestAnimationFrame(loop);
      if (!this.canvas.offsetParent) return;
      this.controls.update();
      // don't let panning slide the view off the table
      const t = this.controls.target, lim = 140, cx = Math.max(-lim, Math.min(lim, t.x)), cz = Math.max(-lim - 60, Math.min(lim, t.z));
      if (cx !== t.x || cz !== t.z) { const dx = cx - t.x, dz = cz - t.z; t.x = cx; t.z = cz; this.camera.position.x += dx; this.camera.position.z += dz; }
      if (Math.abs(t.y) > 1e-3) { this.camera.position.y -= t.y; t.y = 0; }   // the view stays on the table
      this._tickReveal(); this.renderer.render(this.scene, this.camera);
    };
    loop();
  }

  // hand tool: left-drag slides the table around instead of turning it
  setHand(on) {
    this.handMode = !!on;
    this.controls.mouseButtons.LEFT = on ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
    this.canvas.classList.toggle("hand", !!on);
  }
  on(name, fn) { this.handlers[name] = fn; }
  emit(name, ...a) { return this.handlers[name] && this.handlers[name](...a); }

  resize() {
    const w = this.container.clientWidth || 800, h = this.container.clientHeight || 500;
    this.renderer.setSize(w, h, false); this.canvas.style.width = "100%"; this.canvas.style.height = "100%";
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }

  view(kind) {
    const t = this.home.target.clone();
    const pos = kind === "top" ? new THREE.Vector3(t.x, 280, t.z + 1) : this.home.pos.clone();
    this.controls.target.copy(t); this.camera.position.copy(pos);
  }

  // --- the fixed board + breadboard ----------------------------------------
  async load(layout) {
    for (const o of [this.bb, this.board]) o && this.scene.remove(o);
    Object.keys(this.parts).forEach((id) => this.removePart(id));
    this.setWires([]);
    this.noBreadboard = !layout.breadboardType;
    if (this.noBreadboard) {
      // no breadboard: parts sit straight on the table behind the Arduino
      this.bb = null; this.holeMesh = null; this.holeIndex = new Map();
      this.bbLayout = { holes: [], top: 8.5, width: 90, depth: 50 };
    } else {
      const size = { "wokwi-breadboard-half": "half", "wokwi-breadboard-mini": "mini", "wokwi-breadboard": "full" }[layout.breadboardType] || "half";
      this.bb = makeBreadboard(size);
      this.bbLayout = this.bb.userData.layout;
      this.bb.position.set(-this.bbLayout.width / 2, 0, -this.bbLayout.depth - 3);
      this.scene.add(this.bb);
      this.holeMesh = this.bb.getObjectByName("holes");
      this.holeIndex = new Map(this.bbLayout.holes.map((h, i) => [h.name, i]));
    }

    this.board = await makeBoard(layout.boardType || "wokwi-arduino-uno");
    const bw = this.board.userData.width;
    this.board.position.set(-bw / 2, 0, 5);
    this.scene.add(this.board);
    this.sockMesh = this.board.getObjectByName("boardPins");
    this.sockPins = this.sockMesh ? this.sockMesh.userData.pins : [];

    const zMid = ((this.bb ? this.bb.position.z : -50) + this.board.position.z + this.board.userData.depth) / 2;
    this.home.target.set(0, 0, zMid);
    this.home.pos.set(10, 150, zMid + 140);
    this.view("3d");
  }

  // world position (top of the contact) of an end: "bb:12t.c", "<board>:13", "<part>:A"
  holeWorld(name) {
    if (!this.bb) return null;
    const h = this.bbLayout.holes[this.holeIndex.get(name)];
    return h && new THREE.Vector3(h.x, this.bbLayout.top, h.z).add(this.bb.position);
  }
  boardPinWorld(name) {
    const i = this.sockPins.indexOf(name);
    if (i < 0) return null;
    return new THREE.Vector3(...this.sockMesh.userData.positions[i]).add(this.board.position);
  }
  partPinWorld(id, pin) {
    const o = this.parts[id]; if (!o) return null;
    const p = o.userData.pins.find((q) => q[0] === pin); if (!p) return null;
    // on the table the wire clips onto the bare leg a little above its tip
    const y = o.userData.onTable ? this.bbLayout.top - 1.2 + 2.2 : this.bbLayout.top;
    return o.localToWorld(new THREE.Vector3(p[1] * PITCH, y, p[2] * PITCH));
  }
  // the hole nearest a board-local (x, z) within half a pitch
  holeNear(x, z) {
    if (!this.bb) return null;
    let best = null, bd = PITCH / 2;
    for (const h of this.bbLayout.holes) { const d = Math.hypot(h.x - x, h.z - z); if (d < bd) { bd = d; best = h.name; } }
    return best;
  }

  // --- parts -----------------------------------------------------------------
  // place a part's first pin over the hole `anchor`, turned `rot` degrees clockwise
  addPart(id, wokwiType, attrs, anchor, rot) {
    this.removePart(id);
    const o = makePart(wokwiType, attrs);
    const a = this.holeWorld(anchor);
    o.position.set(a.x, 0, a.z); o.rotation.y = -rot * Math.PI / 180;
    o.userData.id = id;
    o.traverse((m) => { m.userData.partId = id; });
    this.scene.add(o); this.parts[id] = o;
    o.scale.setScalar(0.6);   // pop in
    const t0 = performance.now();
    const pop = () => { const k = Math.min(1, (performance.now() - t0) / 260); o.scale.setScalar(0.6 + 0.4 * (1 + 0.25 * Math.sin(k * Math.PI)) * k + (1 - k) * 0); if (k < 1) requestAnimationFrame(pop); else o.scale.setScalar(1); };
    pop();
    return o;
  }
  // no breadboard: stand the part on the table at `point` (legs touching it),
  // with an invisible grab-sphere at each leg to clip a lead onto
  addPartAt(id, wokwiType, attrs, point, rot) {
    this.removePart(id);
    const o = makePart(wokwiType, attrs);
    o.position.set(point.x, -(this.bbLayout.top - 1.2), point.z); o.rotation.y = -rot * Math.PI / 180;
    o.userData.id = id; o.userData.onTable = true;
    const bead = new THREE.MeshStandardMaterial({ color: 0xc27b53, emissive: 0xc27b53, emissiveIntensity: 0.35, roughness: 0.4 });
    o.userData.pins.forEach(([name, dx, dz]) => {
      // an invisible grab-sphere (just under half the 2.54 mm pitch, so neighbours don't overlap)…
      const s = new THREE.Mesh(new THREE.SphereGeometry(1.2, 12, 8), new THREE.MeshBasicMaterial({ visible: false }));
      s.position.set(dx * PITCH, this.bbLayout.top - 1.2 + 2.2, dz * PITCH); s.userData.leg = name; o.add(s);
      // …and a visible bead on the bare leg, so you can see where to grab
      const b = new THREE.Mesh(new THREE.SphereGeometry(0.55, 12, 8), bead);
      b.position.copy(s.position); b.userData.leg = name; o.add(b);
    });
    o.traverse((m) => { m.userData.partId = id; });
    this.scene.add(o); this.parts[id] = o;
    return o;
  }
  removePart(id) { const o = this.parts[id]; if (o) { this.scene.remove(o); delete this.parts[id]; } }
  setSelected(id) {
    if (this.selBox) { this.scene.remove(this.selBox); this.selBox = null; }
    const o = id && this.parts[id];
    if (!o) return;
    const box = new THREE.Box3().setFromObject(o).expandByScalar(0.8);
    this.selBox = new THREE.Box3Helper(box, 0xffa62b);
    this.scene.add(this.selBox);
  }

  // a see-through copy of a part that follows the pointer while dragging
  showGhost(wokwiType, attrs, anchor, rot) {
    if (this.ghost && this.ghost.userData.key !== wokwiType + JSON.stringify(attrs)) { this.scene.remove(this.ghost); this.ghost = null; }
    if (!this.ghost) {
      this.ghost = makePart(wokwiType, attrs);
      this.ghost.userData.key = wokwiType + JSON.stringify(attrs);
      this.ghost.traverse((m) => { if (m.isMesh) { m.material = m.material.clone(); m.material.transparent = true; m.material.opacity = 0.55; m.castShadow = false; m.raycast = () => {}; } });
      this.scene.add(this.ghost);
    }
    const a = anchor && (anchor.isVector3 ? anchor : this.holeWorld(anchor));
    this.ghost.visible = !!a;
    if (a) {
      this.ghost.position.set(a.x, anchor.isVector3 ? -(this.bbLayout.top - 1.2) + 4 : 6, a.z);
      this.ghost.rotation.y = -rot * Math.PI / 180;
    }
  }
  hideGhost() { if (this.ghost) { this.scene.remove(this.ghost); this.ghost = null; } }

  // --- holes -----------------------------------------------------------------
  // colour individual holes: {name: "hover" | "on" | "bad"}
  paintHoles(marks) {
    if (!this.holeMesh) return;
    this._lastMarks = marks;
    this.bbLayout.holes.forEach((h, i) => this.holeMesh.setColorAt(i, this.revealHoles && this.revealHoles.has(h.name) ? REVEAL : HOLE_COLOUR));
    Object.entries(marks || {}).forEach(([name, kind]) => {
      const i = this.holeIndex.get(name);
      if (i !== undefined) this.holeMesh.setColorAt(i, kind === "hover" ? HOLE_HOVER : HOLE_ON);
    });
    this.holeMesh.instanceColor.needsUpdate = true;
  }
  paintSockets(marks) {
    if (!this.sockMesh) return;
    this._lastSock = marks;
    this.sockPins.forEach((p, i) => this.sockMesh.setColorAt(i, marks && marks[p] ? HOLE_HOVER : this.revealSockets && this.revealSockets.has(p) ? REVEAL : SOCK_COLOUR));
    this.sockMesh.instanceColor.needsUpdate = true;
  }
  markRing(pos) {
    this.hoverRing.visible = !!pos;
    if (pos) this.hoverRing.position.set(pos.x, pos.y + 0.25, pos.z);
  }

  // --- wires -----------------------------------------------------------------
  // wires: [{a, b, state}], ends resolved by app.js to world positions
  setWires(list) {
    this.wires.clear();
    const seen = new Set();
    list.forEach((w, i) => {
      if (!w.pa || !w.pb) return;
      const colour = w.colour ?? WIRE_COLOURS[i % WIRE_COLOURS.length];
      // without a breadboard each link is drawn as what it physically is (clip, solder, twisted legs, ...)
      const g = w.kind ? makeLink(w.kind, w.pa.toArray(), w.pb.toArray(), colour) : makeWire(w.pa.toArray(), w.pb.toArray(), colour, { clipA: w.clipA, clipB: w.clipB });
      g.userData.wireIndex = i;
      g.traverse((m) => { m.userData.wireIndex = i; });
      if (w.state === "bad") g.traverse((m) => { if (m.isMesh && m.material.color && m.geometry.type === "TubeGeometry") { m.material = m.material.clone(); m.material.emissive = new THREE.Color(0x801010); } });
      this.wires.add(g);
      // a joint that's just been made: watch the solder flow in
      const key = `${w.a}~${w.b}~${w.kind}`; seen.add(key);
      if (this.knownLinks && !this.knownLinks.has(key)) {
        const sleeves = []; g.traverse((m) => { if (m.userData.sleeve) sleeves.push(m); });
        g.traverse((m) => { if (m.userData.solderBlob) this.solderFx(m, sleeves); });
      }
    });
    this.knownLinks = seen;
  }
  // a molten bead forms on the joint (glowing, a flash of light, a puff of
  // smoke), then cools to shiny silver. The iron itself isn't shown.
  solderFx(blob, sleeves = []) {
    const target = blob.scale.clone(), pos = blob.getWorldPosition(new THREE.Vector3());
    // heat-shrink goes on after the joint has cooled: hide it, slide it in at the end
    const sleeveHome = sleeves.map((sl) => sl.position.clone());
    sleeves.forEach((sl) => { sl.visible = false; });
    blob.scale.setScalar(0.001);
    blob.material = blob.material.clone(); blob.material.emissive = new THREE.Color(0xffa040);
    const flash = new THREE.PointLight(0xffa040, 0, 18, 2); flash.position.copy(pos).add(new THREE.Vector3(0, 1.5, 0)); this.scene.add(flash);
    const puffs = [0, 1, 2, 3].map((i) => {
      const s = new THREE.Mesh(new THREE.SphereGeometry(0.5, 10, 8), new THREE.MeshBasicMaterial({ color: 0xe8e6e0, transparent: true, opacity: 0, depthWrite: false }));
      s.position.copy(pos); s.userData.dx = (Math.random() - 0.5) * 1.2; s.userData.delay = 0.15 + i * 0.12; this.scene.add(s); return s;
    });
    const t0 = performance.now();
    const step = (now) => {
      const t = (now - t0) / 1000;
      const grow = Math.min(1, t / 0.55), e = 1 - Math.pow(1 - grow, 3);
      blob.scale.set(target.x * e, target.y * e, target.z * e);
      const heat = t < 0.6 ? 1 : Math.max(0, 1 - (t - 0.6) / 0.9);                 // glowing, then cooling
      blob.material.emissiveIntensity = 2.2 * heat;
      blob.material.emissive.setHSL(0.08, 1, 0.45 + 0.25 * heat);
      flash.intensity = 22 * heat * (0.8 + 0.2 * Math.sin(t * 40));
      puffs.forEach((p) => {
        const k = Math.max(0, t - p.userData.delay) / 1.3;
        p.position.set(pos.x + p.userData.dx * k * 3, pos.y + 1 + k * 7, pos.z);
        p.scale.setScalar(0.6 + k * 2.2); p.material.opacity = k > 0 && k < 1 ? 0.45 * (1 - k) : 0;
      });
      if (t > 1.6) sleeves.forEach((sl, i) => {                      // slide the sleeve down over the joint
        const k = Math.min(1, (t - 1.6) / 0.5);
        sl.visible = true; sl.position.copy(sleeveHome[i]).add(new THREE.Vector3(0, (1 - k) * 5, 0));
      });
      if (t < 2.2) requestAnimationFrame(step);
      else { blob.material.emissiveIntensity = 0; this.scene.remove(flash); puffs.forEach((p) => this.scene.remove(p)); sleeves.forEach((sl, i) => { sl.visible = true; sl.position.copy(sleeveHome[i]); }); }
    };
    requestAnimationFrame(step);
  }

  showPreview(a, b) {
    this.preview.visible = !!(a && b);
    if (!a || !b) return;
    const mid = a.clone().lerp(b, 0.5); mid.y = Math.max(a.y, b.y) + 10;
    const pts = new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(30);
    this.preview.geometry.setFromPoints(pts); this.preview.computeLineDistances();
  }

  // --- "reveal step": red dots on exactly where things go ------------------------
  // markers: [{pos: Vector3, label}], lines: [[Vector3, Vector3]] (a wire to run)
  showReveal(markers) {
    this.clearReveal();
    this.revealHoles = new Set(markers.filter((m) => m.hole).map((m) => m.hole));
    this.revealSockets = new Set(markers.filter((m) => m.socket).map((m) => m.socket));
    this.paintHoles(this._lastMarks || {}); this.paintSockets(this._lastSock || {});
    const g = new THREE.Group(); g.name = "reveal"; this.reveal = g; this.scene.add(g);
    const red = new THREE.MeshBasicMaterial({ color: 0xd9443a }), ringMat = new THREE.MeshBasicMaterial({ color: 0xd9443a, transparent: true, opacity: 0.8 });
    markers.forEach((mk) => {
      const dot = new THREE.Mesh(new THREE.SphereGeometry(0.8, 16, 12), red); dot.position.copy(mk.pos).add(new THREE.Vector3(0, 0.7, 0)); g.add(dot);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(1.7, 0.22, 8, 32), ringMat.clone()); ring.rotation.x = -Math.PI / 2;
      ring.position.copy(mk.pos).add(new THREE.Vector3(0, 0.35, 0)); ring.userData.pulse = true; g.add(ring);
      if (mk.label) {
        const el = document.createElement("div"); el.className = "reveal-label"; el.textContent = mk.label;
        this.revealLayer.appendChild(el); this.revealLabels.push({ el, pos: mk.pos.clone().add(new THREE.Vector3(0, 3, 0)) });
      }
    });
  }
  clearReveal() {
    if (this.reveal) { this.scene.remove(this.reveal); this.reveal = null; }
    this.revealLabels.forEach((l) => l.el.remove()); this.revealLabels = [];
    const had = (this.revealHoles && this.revealHoles.size) || (this.revealSockets && this.revealSockets.size);
    this.revealHoles = new Set(); this.revealSockets = new Set();
    if (had) { this.paintHoles(this._lastMarks || {}); this.paintSockets(this._lastSock || {}); }
  }
  // turn the view a little (used while a wire is being run and the pointer sits at an edge)
  nudgeView(dTheta, dPhi) {
    const off = this.camera.position.clone().sub(this.controls.target);
    const sph = new THREE.Spherical().setFromVector3(off);
    sph.theta += dTheta;
    sph.phi = Math.max(0.15, Math.min(this.controls.maxPolarAngle, sph.phi + dPhi));
    this.camera.position.copy(this.controls.target).add(new THREE.Vector3().setFromSpherical(sph));
    this.camera.lookAt(this.controls.target);
  }
  _tickReveal() {
    if (this.edge && (this.edge.x || this.edge.y)) this.nudgeView(-this.edge.x * 0.018, this.edge.y * 0.012);
    if (!this.reveal) return;
    const t = performance.now() / 1000;
    this.reveal.children.forEach((o) => { if (o.userData.pulse) { const k = 1 + (Math.sin(t * 4) + 1) * 0.18; o.scale.setScalar(k); o.material.opacity = 0.9 - (k - 1) * 1.6; } });
    const r = this.canvas.getBoundingClientRect(), cr = this.container.getBoundingClientRect();
    this.revealLabels.forEach(({ el, pos }) => {
      const p = pos.clone().project(this.camera);
      el.style.left = `${(p.x + 1) / 2 * r.width + r.left - cr.left}px`; el.style.top = `${(1 - p.y) / 2 * r.height + r.top - cr.top}px`;
      el.style.display = p.z < 1 ? "" : "none";
    });
  }

  // --- picking -----------------------------------------------------------------
  // what's under the pointer: {kind: "hole"|"boardPin"|"part"|"knob"|"buttonCap"|"wire"|"board"|"breadboard"|null, ...}
  pick(clientX, clientY) {
    const r = this.canvas.getBoundingClientRect();
    this.ndc.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(this.ndc, this.camera);
    const targets = [this.bb, this.board, ...Object.values(this.parts), this.wires].filter(Boolean);
    // invisible leg grab-spheres count as hits; other invisible helpers don't
    const hits = this.ray.intersectObjects(targets, true).filter((h) => (h.object.visible || h.object.userData.leg) && !h.object.userData.passThrough);
    // a leg tip's grab-sphere wins over the part's own body/lead around it
    const hit = hits.find((h) => h.object.userData.leg) || hits[0];
    const point = hit ? hit.point : this._tablePoint();
    if (!hit) return { kind: null, point };
    const o = hit.object;
    if (o.userData.wireIndex !== undefined) return { kind: "wire", index: o.userData.wireIndex, point };
    if (o.userData.leg) return { kind: "leg", id: o.userData.partId, pin: o.userData.leg, point: this.partPinWorld(o.userData.partId, o.userData.leg) };
    if (o.userData.partId) {
      const id = o.userData.partId;
      let k = o; while (k && !k.userData.kind && k.userData.partId) k = k.parent;
      const kind = o.userData.kind === "knob" || (k && k.userData.kind === "knob") ? "knob"
        : o.userData.kind === "buttonCap" ? "buttonCap" : o.userData.kind === "slider" ? "slider" : o.userData.kind === "pir" ? "pir" : o.userData.kind === "ldr" ? "ldr" : "part";
      return { kind, id, point };
    }
    if (this.bb && this._within(o, this.bb)) {
      const local = this.bb.worldToLocal(hit.point.clone());
      const hole = this.holeNear(local.x, local.z);
      return hole ? { kind: "hole", hole, point: this.holeWorld(hole) } : { kind: "breadboard", point };
    }
    if (this._within(o, this.board)) {
      let best = null, bd = PITCH * 0.6;
      if (hit.point.y > 6) this.sockPins.forEach((p) => {
        const w = this.boardPinWorld(p); const d = Math.hypot(w.x - hit.point.x, w.z - hit.point.z);
        if (d < bd) { bd = d; best = p; }
      });
      return best ? { kind: "boardPin", pin: best, point: this.boardPinWorld(best) } : { kind: "board", component: o.userData.component, point };
    }
    return { kind: null, point };
  }
  _within(o, root) { while (o) { if (o === root) return true; o = o.parent; } return false; }
  _tablePoint() {
    const p = new THREE.Vector3();
    return this.ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), p) ? p : null;
  }
  // screen position of a world point (for tests and floating labels)
  toScreen(v) {
    const r = this.canvas.getBoundingClientRect(), p = v.clone().project(this.camera);
    return { x: r.left + (p.x + 1) / 2 * r.width, y: r.top + (1 - p.y) / 2 * r.height };
  }

  _down(e) {
    if (this.handMode) return;                    // the hand only moves the view
    const p = this.pick(e.clientX, e.clientY);
    const takes = this.emit("down", p, e);
    if (takes) { this.controls.enabled = false; this._grab = true; }
  }
  _move(e) {
    const p = this.pick(e.clientX, e.clientY);
    this.emit("move", p, e);
    this._hover(p, e);
  }
  _up(e) {
    if (this._grab) { this._grab = false; this.controls.enabled = true; }
    const inside = e.target === this.canvas;
    this.emit("up", inside ? this.pick(e.clientX, e.clientY) : { kind: null }, e);
  }
  _dbl(e) { this.emit("dbl", this.pick(e.clientX, e.clientY), e); }
  _hover(p, e) { this.emit("hover", p, e); }
}

// ---------------------------------------------------------------------------
// Inspector: one part, big, turntable, every pin labelled
// ---------------------------------------------------------------------------
export class Inspector3D {
  constructor(container) {
    this.container = container;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace; this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.canvas = this.renderer.domElement; this.canvas.className = "insp-canvas";
    container.prepend(this.canvas);
    this.scene = new THREE.Scene();
    this.scene.environment = new THREE.PMREMGenerator(this.renderer).fromScene(new RoomEnvironment(), 0.04).texture;
    const key = new THREE.DirectionalLight(0xffffff, 1.8); key.position.set(40, 80, 60); this.scene.add(key);
    this.camera = new THREE.PerspectiveCamera(30, 1, 0.1, 3000);
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.enableDamping = true; this.controls.autoRotate = true; this.controls.autoRotateSpeed = 1.6;
    this.canvas.addEventListener("pointerdown", () => { this.controls.autoRotate = false; });
    this.labels = document.createElement("div"); this.labels.className = "insp-labels"; container.appendChild(this.labels);
    this.markers = []; this.active = null; this.running = false;
    new ResizeObserver(() => this.resize()).observe(container);
  }
  resize() {
    const w = this.container.clientWidth || 400, h = this.container.clientHeight || 300;
    this.renderer.setSize(w, h, false); this.canvas.style.width = "100%"; this.canvas.style.height = "100%";
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }
  // obj: an Object3D; pins: [{name, pos: Vector3 (object-local)}]
  show(obj, pins, onPin) {
    if (this.obj) this.scene.remove(this.obj);
    if (this.focusBox) { this.scene.remove(this.focusBox); this.focusBox = null; }
    this.obj = obj; this.scene.add(obj);
    const box = new THREE.Box3().setFromObject(obj), c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3());
    const r = Math.max(s.x, s.y * 1.5, s.z);
    this.controls.target.copy(c);
    this.camera.position.copy(c).add(new THREE.Vector3(r * 0.9, r * 1.0, r * 1.25));
    this.camera.near = r / 50; this.camera.far = r * 20; this.camera.updateProjectionMatrix();
    this.controls.autoRotate = true;
    this.labels.innerHTML = "";
    this.markers = pins.map((p) => {
      const el = document.createElement("button"); el.className = "insp-pin"; el.dataset.pin = p.name;
      el.innerHTML = `<span>${p.name.replace(/[&<>"]/g, "")}</span>`;
      el.onclick = () => onPin && onPin(p.name);
      this.labels.appendChild(el);
      return { el, pos: p.pos };
    });
    this.labels.classList.toggle("many", pins.length > 12);
    this.resize();
    if (!this.running) { this.running = true; this._loop(); }
  }
  setActive(name) { this.markers.forEach((m) => m.el.classList.toggle("active", m.el.dataset.pin === name)); this.controls.autoRotate = false; }

  // highlight one tagged component (userData.component) and swing the camera to it
  focus(key) {
    if (this.focusBox) { this.scene.remove(this.focusBox); this.focusBox = null; }
    this.markers.forEach((m) => m.el.classList.remove("active"));
    if (!this.obj) return;
    const box = new THREE.Box3();
    this.obj.traverse((m) => { if (m.isMesh && m.userData.component === key) box.expandByObject(m); });
    if (box.isEmpty()) return;
    box.expandByScalar(0.6);
    this.focusBox = new THREE.Box3Helper(box, 0xffa62b); this.scene.add(this.focusBox);
    this.controls.autoRotate = false;
    const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()).length();
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    const dist = Math.max(size * 2.2, 45);
    const fromT = this.controls.target.clone(), fromP = this.camera.position.clone();
    const toP = c.clone().add(dir.multiplyScalar(dist)), t0 = performance.now();
    const step = (now) => {
      const k = Math.min(1, (now - t0) / 650), e = 1 - Math.pow(1 - k, 3);
      this.controls.target.lerpVectors(fromT, c, e); this.camera.position.lerpVectors(fromP, toP, e);
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  // click (not drag) on the model -> the component under the pointer
  onPick(fn) {
    let down = null;
    this.canvas.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; });
    this.canvas.addEventListener("pointerup", (e) => {
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5 || !this.obj) return;
      const r = this.canvas.getBoundingClientRect(), ray = new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), this.camera);
      const hit = ray.intersectObject(this.obj, true).find((h) => h.object.userData.component);
      if (hit) fn(hit.object.userData.component);
    });
  }
  stop() { this.running = false; }
  _loop() {
    if (!this.running) return;
    requestAnimationFrame(() => this._loop());
    this.controls.update(); this.renderer.render(this.scene, this.camera);
    const r = this.canvas.getBoundingClientRect(), cr = this.container.getBoundingClientRect();
    this.markers.forEach((m) => {
      const p = this.obj.localToWorld(m.pos.clone()).project(this.camera);
      m.el.style.left = `${(p.x + 1) / 2 * r.width + r.left - cr.left}px`;
      m.el.style.top = `${(1 - p.y) / 2 * r.height + r.top - cr.top}px`;
    });
  }
}
