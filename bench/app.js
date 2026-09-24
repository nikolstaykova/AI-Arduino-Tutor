// CircuitQuest Wiring Bench — a real 3D workbench (three.js) of detailed,
// true-to-size parts, wired to the real engine in bench_server.py.
//
// Everything electrical is decided by the engine: this page only places
// parts where their real legs fall (0.1" pitch), draws wires between exact
// holes / header sockets, and sends the whole board to the engine on every check.
import { Bench3D, Inspector3D } from "./three/scene.js";
import { PITCH, pinsFor, makePart, makeBoard, makeBreadboard, thumbnail, thumbnailById, iconThumb, UNO_COMPONENTS } from "./three/models.js";
import { buildModel, hasModel } from "./three/catalog3d.js";
import * as THREE from "three";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const BB_SIZE = { "wokwi-breadboard-half": "half", "wokwi-breadboard-mini": "mini", "wokwi-breadboard": "full" };

// ---------------------------------------------------------------------------
// Engine API
// ---------------------------------------------------------------------------
async function api(path, body) {
  const headers = { "Content-Type": "application/json" };
  if (window.__cqToken) headers.Authorization = "Bearer " + window.__cqToken;     // signed in (accounts on)
  else if (window.__cqGuest) headers["X-CQ-Guest"] = window.__cqGuest;            // a guest (typed a name)
  const res = await fetch(path, { method: "POST", headers, body: JSON.stringify(body || {}) });
  const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
// Lesson text is shared between people (and written by Claude), so it's never
// trusted as HTML: everything is escaped, then only bold / italic / code /
// line breaks (which the engine uses round pin numbers) are let back in.
function safeHtml(text) {
  return esc(text).replace(/&lt;(\/?)(b|i|em|strong|code)&gt;/gi, "<$1$2>").replace(/&lt;br\s*\/?&gt;/gi, "<br>");
}
function guarded(fn) {
  return async (...args) => { try { await fn(...args); } catch (e) { console.error(e); toast("⚠️ " + e.message); } };
}
function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), 2600);
}

const S = {
  lessons: [], progress: null, lessonId: null, difficulty: "beginner", session: null, view: null,
  layout: null, trayParts: [], clip: "", hints: [], lastPhysics: null, pressed: {}, pot: {},
  placed: {},           // id -> {def, legs: {pin: hole|null}, rot, anchor}
  wires: [],            // {a, b, state}
  selected: null, selectedWire: null,
};

// ---------------------------------------------------------------------------
// The 3D workbench
// ---------------------------------------------------------------------------
let B = null;                               // Bench3D
const G = { bbId: "bb1", boardId: "uno", bbType: "wokwi-breadboard-half", boardType: "wokwi-arduino-uno" };

// turn a (columns, rows) offset clockwise by deg (seen from above)
function rot(dx, dz, deg) {
  const r = (deg * Math.PI) / 180, c = Math.round(Math.cos(r)), s = Math.round(Math.sin(r));
  return [dx * c - dz * s, dx * s + dz * c];
}
function splitEnd(end) { const i = end.indexOf(":"); return [end.slice(0, i), end.slice(i + 1)]; }
function endWorld(end) {
  const [kind, rest] = splitEnd(end);
  if (kind === "bb") return B.holeWorld(rest);
  if (kind === G.boardId) return B.boardPinWorld(rest);
  return S.placed[kind] ? B.partPinWorld(kind, rest) : null;
}
function endOf(p) {
  if (!p) return null;
  if (p.kind === "leg") return `${p.id}:${p.pin}`;
  if (p.kind === "hole") return `bb:${p.hole}`;
  if (p.kind === "boardPin") return `${G.boardId}:${p.pin}`;
  return null;
}

async function buildBoard() {
  G.bbType = S.layout.breadboard ? S.layout.breadboard.type : null;       // null: building without a breadboard
  G.bbId = S.layout.breadboard ? S.layout.breadboard.id : "bb1";
  G.boardType = S.layout.board ? S.layout.board.type : "wokwi-arduino-uno";
  G.boardId = S.layout.board ? S.layout.board.id : "uno";
  await B.load({ breadboardType: G.bbType, boardType: G.boardType });
}

// ---------------------------------------------------------------------------
// Parts: tray (3D-rendered tiles), placing by real leg geometry
// ---------------------------------------------------------------------------
function defaultRotation(def) { return 0; }

function renderTray() {
  const tray = $("tray"); tray.innerHTML = "";
  S.trayParts.forEach((def) => {
    const item = document.createElement("div");
    item.className = "tray-item" + (S.placed[def.id] ? " used" : "");
    item.dataset.part = def.id;
    item.title = `${def.label} — drag it onto the ${B && B.noBreadboard ? "table" : "breadboard"}, double-click to inspect`;
    item.innerHTML = `<div class="tray-art"></div><div class="tray-label">${esc(def.label.replace(/ \(.*\)$/, ""))}</div><div class="tray-sub">${esc(def.id)}</div>`;
    thumbnailById(def.card_id, def.wokwi_type, def.attrs || {}).then((url) => {
      if (url) item.querySelector(".tray-art").innerHTML = `<img src="${url}" alt="">`;
    });
    item.addEventListener("pointerdown", (e) => { if (!S.placed[def.id]) startPartDrag(e, def, null); });
    item.addEventListener("dblclick", () => openInspector({ kind: "part", wokwiType: def.wokwi_type, attrs: def.attrs, cardId: def.card_id, label: def.label }));
    tray.appendChild(item);
  });
}

// where every leg of `def` lands if its FIRST leg goes into `hole`, turned `rotation`
function legsFor(def, hole, rotation) {
  const pins = pinsFor(def.wokwi_type), L = B.bbLayout;
  const h = L.holes.find((q) => q.name === hole);
  const legs = {};
  pins.forEach(([name, dx, dz]) => {
    const [rx, rz] = rot(dx, dz, rotation);
    legs[name] = B.holeNear(h.x + rx * PITCH, h.z + rz * PITCH);
  });
  return legs;
}

function placePart(def, hole, rotation) {
  const legs = legsFor(def, hole, rotation);
  const occupied = new Map();
  Object.values(S.placed).filter((p) => p.def.id !== def.id).forEach((p) => Object.values(p.legs).forEach((h) => h && occupied.set(h, p.def.label)));
  S.wires.forEach((w) => [w.a, w.b].forEach((e) => e.startsWith("bb:") && occupied.set(e.slice(3), "a wire")));
  const clash = Object.values(legs).find((h) => h && occupied.has(h));
  if (clash) { toast(`Hole ${clash} already has ${occupied.get(clash)} in it.`); return false; }
  B.addPart(def.id, def.wokwi_type, def.attrs || {}, hole, rotation);
  S.placed[def.id] = { def, legs, rot: rotation, anchor: hole };
  if (def.wokwi_type === "wokwi-potentiometer") B.parts[def.id].userData.setValue(S.pot[def.id] ?? 512);
  const dangling = Object.entries(legs).filter(([, v]) => !v).map(([k]) => k);
  toast(dangling.length ? `${def.label} placed — leg ${dangling.join(", ")} isn't in a hole.`
                        : `${def.label} placed · ${Object.entries(legs).map(([k, v]) => `${k}→${v}`).join("  ")}`);
  renderTray(); renderWires(); select(def.id);
  return true;
}

// no breadboard: the part stands on the table; its legs are free ends to clip leads onto
function placePartAt(def, at, rotation) {
  B.addPartAt(def.id, def.wokwi_type, def.attrs || {}, at, rotation);
  const legs = Object.fromEntries(pinsFor(def.wokwi_type).map(([n]) => [n, null]));
  S.placed[def.id] = { def, legs, rot: rotation, at: { x: at.x, z: at.z, isVector3: true } };
  if (def.wokwi_type === "wokwi-potentiometer") B.parts[def.id].userData.setValue(S.pot[def.id] ?? 512);
  toast(`${def.label} is on the table — drag from a leg tip to connect it.`);
  renderTray(); renderWires(); select(def.id);
  return true;
}

function removePart(id, quiet) {
  if (!S.placed[id]) return;
  B.removePart(id);
  delete S.placed[id];
  if (!quiet) {
    S.wires = S.wires.filter((w) => !w.a.startsWith(id + ":") && !w.b.startsWith(id + ":"));
    renderTray(); renderWires(); select(null);
  }
}

function select(id) {
  S.selected = id; S.selectedWire = null;
  B.setSelected(id);
  const bar = $("selectedBar");
  if (!id) { bar.classList.remove("show"); return; }
  const part = S.placed[id];
  bar.innerHTML = `<b>${esc(part.def.label)}</b>
    <button class="quiet" data-a="rotate" title="Rotate (R)"><svg class="ic" viewBox="0 0 24 24"><path d="M20 12a8 8 0 11-2.3-5.6M20 4v5h-5"/></svg></button>
    <button class="quiet" data-a="inspect" title="Inspect"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/></svg></button>
    <button class="quiet" data-a="remove" title="Remove (Delete)"><svg class="ic" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`;
  bar.classList.add("show");
  bar.querySelector('[data-a="rotate"]').onclick = () => rotateSelected();
  bar.querySelector('[data-a="remove"]').onclick = () => removePart(id);
  bar.querySelector('[data-a="inspect"]').onclick = () => openInspector(partTarget(id));
}
function selectWire(i) {
  select(null); S.selectedWire = i;
  const w = S.wires[i], bar = $("selectedBar");
  bar.innerHTML = `<b>Wire</b> <span class="chip">${esc(w.a.replace(/^bb:/, ""))} ↔ ${esc(w.b.replace(/^bb:/, ""))}</span>
    <button class="quiet" data-a="remove" title="Pull it out (Delete)"><svg class="ic" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`;
  bar.classList.add("show");
  bar.querySelector('[data-a="remove"]').onclick = () => { S.wires.splice(i, 1); renderWires(); select(null); };
}
function partTarget(id) {
  const d = S.placed[id].def;
  return { kind: "part", wokwiType: d.wokwi_type, attrs: d.attrs, cardId: d.card_id, label: d.label, instance: id };
}

function rotateSelected() {
  const part = S.placed[S.selected];
  if (!part) return;
  if (part.at) placePartAt(part.def, part.at, (part.rot + 90) % 360);
  else placePart(part.def, part.anchor, (part.rot + 90) % 360);
}

// dragging a part from the tray (or picking a placed one up): a see-through
// 3D copy snaps to the hole under the pointer
let drag = null;
const lastPointer = { x: 0, y: 0 };
window.addEventListener("pointermove", (e) => { lastPointer.x = e.clientX; lastPointer.y = e.clientY; }, true);
function startPartDrag(e, def, existing) {
  e.preventDefault && e.preventDefault();
  const ghost = document.createElement("img");
  ghost.className = "drag-ghost";
  thumbnail(def.wokwi_type, def.attrs || {}).then((u) => { if (u) ghost.src = u; });
  document.body.appendChild(ghost);
  drag = { def, ghost, rot: existing ? existing.rot : defaultRotation(def), existing, hole: null };
  dragMove(e.clientX, e.clientY);
}
function dragMove(cx, cy) {
  const onCanvas = document.elementFromPoint(cx, cy) === B.canvas;
  const p = onCanvas ? B.pick(cx, cy) : null;
  if (B.noBreadboard) {
    const free = p && p.point && (p.kind === null || p.kind === "wire");
    drag.at = free ? p.point : null;
    B.showGhost(drag.def.wokwi_type, drag.def.attrs || {}, drag.at, drag.rot);
    if (drag.at) showTip(cx, cy, `${esc(drag.def.label)} — drop it on the table<br><span class="dim">R turns it</span>`); else hideTip();
    drag.ghost.style.opacity = drag.at ? "0" : "0.9";
    drag.ghost.style.left = `${cx - 40}px`; drag.ghost.style.top = `${cy - 40}px`;
    return;
  }
  drag.hole = p && p.kind === "hole" ? p.hole : null;
  B.showGhost(drag.def.wokwi_type, drag.def.attrs || {}, drag.hole, drag.rot);
  if (drag.hole) {
    const legs = legsFor(drag.def, drag.hole, drag.rot), marks = {};
    Object.values(legs).forEach((h) => h && (marks[h] = "on"));
    B.paintHoles(marks);
    showTip(cx, cy, `${esc(drag.def.label)}: ${Object.entries(legs).map(([k, v]) => `<b>${esc(k)}</b>→${esc(v || "air")}`).join(" · ")}<br><span class="dim">R turns it</span>`);
  } else { B.paintHoles({}); hideTip(); }
  drag.ghost.style.opacity = drag.hole ? "0" : "0.9";
  drag.ghost.style.left = `${cx - 40}px`; drag.ghost.style.top = `${cy - 40}px`;
}
function endDrag() {
  const d = drag; drag = null;
  d.ghost.remove(); B.hideGhost(); B.paintHoles({}); hideTip();
  if (d.hole) placePart(d.def, d.hole, d.rot);
  else if (d.at) placePartAt(d.def, d.at, d.rot);
  else renderTray();
}

// ---------------------------------------------------------------------------
// Wires
// ---------------------------------------------------------------------------
function wireColour(w, i) {
  const pins = [w.a, w.b].map((e) => splitEnd(e)[1]);
  if (pins.some((p) => /^GND/.test(p) || /^[tb]n\./.test(p))) return 0x1d1d1f;
  if (pins.some((p) => /^(5V|3\.3V|VIN)$/.test(p) || /^[tb]p\./.test(p))) return 0xd0312d;
  return undefined;
}
const isLeg = (end) => { const [k] = splitEnd(end); return k !== "bb" && k !== G.boardId; };
// Without a breadboard, what physically makes a connection depends on the legs
// and the chosen join style — the same rules as core/build_methods.py:
//   bare lead -> socket: twist style pushes the lead in (loose); clips style uses
//   a jumper in the socket + an alligator clip on the lead; solder style solders
//   a jumper wire to the lead. A knob's flat tabs ("lug") are clipped or
//   soldered; only real header pins ("pin", on modules) take a female jumper.
//   Soldering is shown as its result — no iron is simulated.
//   leg <-> leg: twisted (wire leads only), soldered, or clipped.
const leadsOf = (end) => (S.trayParts.find((d) => d.id === splitEnd(end)[0]) || {}).leads || "pin";
// "Connect with" (no-breadboard toolbar): "planned" follows the lesson's
// join style; otherwise the learner picks what they're holding.
S.connectWith = "planned";
function chosenKind(a, b) {
  const w = S.connectWith, legs = isLeg(a) && isLeg(b), wireLeads = [a, b].filter(isLeg).every((e) => leadsOf(e) === "wire-lead");
  if (w === "clip") return legs ? "clip" : "clip-stub";
  if (w === "solder") return legs ? "solder" : "solder-wire";
  if (w === "push") {        // only thin wire leads can be pushed into a socket / twisted
    if (wireLeads) return legs ? "twist" : "insert";
    toast("That leg is too short or too stiff to push in or twist — using the planned way instead.");
  }
  return null;
}
function linkKind(a, b) {
  const picked = S.connectWith !== "planned" && chosenKind(a, b);
  if (picked) return picked;
  const join = (S.build && S.build.join) || "clips";
  if (isLeg(a) && isLeg(b)) {
    if (join === "twist" && leadsOf(a) === "wire-lead" && leadsOf(b) === "wire-lead") return "twist";
    return join === "solder" ? "solder" : "clip";
  }
  const lead = leadsOf(isLeg(a) ? a : b);
  if (lead === "pin") return "mf-jumper";
  if (lead === "wire-lead" && join === "twist") return "insert";
  return join === "solder" ? "solder-wire" : "clip-stub";
}
const LINK_WORDS = { "ff-jumper": "female-to-female jumper between the legs", insert: "lead pushed into the socket (loose fit)", "clip-stub": "jumper in the socket + clip on the leg",
  "solder-wire": "jumper wire soldered to the leg", "mf-jumper": "male-to-female jumper on the pin", clip: "alligator clip lead",
  twist: "legs twisted together", solder: "legs soldered together", jumper: "jumper wire" };
function addLink(from, to) {
  if (!B.noBreadboard || (!isLeg(from) && !isLeg(to))) {
    S.wires.push({ a: from, b: to, state: "pending" }); renderWires(); return;
  }
  const [a, b] = isLeg(from) ? [from, to] : [to, from];     // the leg end first
  const kind = linkKind(a, b);
  if (kind === "insert" && S.wires.some((w) => w.kind === "insert" && w.b === b)) {
    toast(`The ${splitEnd(b)[1].split(".")[0]} socket already has a leg in it — one leg per socket. Twist this leg onto that one instead.`);
    return;
  }
  S.wires.push({ a, b, state: "pending", kind });
  renderWires();
  toast(`${LINK_WORDS[kind][0].toUpperCase()}${LINK_WORDS[kind].slice(1)}.`);
}
function renderWires() {
  B.setWires(S.wires.map((w, i) => ({ ...w, pa: endWorld(w.a), pb: endWorld(w.b), colour: wireColour(w, i), clipA: isLeg(w.a), clipB: isLeg(w.b) })));
}
function engineEnd(end) {
  const [kind, rest] = splitEnd(end);
  return kind === "bb" ? `${G.bbId}:${rest}` : end;
}
function detectedPairs() {
  const pairs = [];
  Object.values(S.placed).forEach((p) => Object.entries(p.legs).forEach(([pin, hole]) => {
    if (hole) pairs.push([`${p.def.id}:${pin}`, `${G.bbId}:${hole}`]);
  }));
  S.wires.forEach((w) => pairs.push([engineEnd(w.a), engineEnd(w.b)]));
  return pairs;
}

// ---------------------------------------------------------------------------
// Pointer handling: orbit (empty space), wire (hole/socket), move/press/turn parts
// ---------------------------------------------------------------------------
let wiring = null, press = null, knob = null, partDown = null;
function finishWire(end) {
  const taken = end.startsWith("bb:") && Object.values(S.placed).some((q) => Object.values(q.legs).includes(end.slice(3)));
  if (taken) toast(`Hole ${end.slice(3)} already has a leg in it.`);
  else addLink(wiring.from, end);
  cancelWire();
}
function cancelWire() { wiring = null; if (B) { B.showPreview(null); B.edge = null; } }
function wireStage() {
  B.on("down", (p, e) => {
    if (e.button !== 0) return false;
    if (p.kind === "hole" || p.kind === "boardPin" || p.kind === "leg") {
      const end = endOf(p);
      if (wiring && wiring.sticky) {                 // second click: finish the wire here (or cancel on the start)
        if (end !== wiring.from) finishWire(end); else cancelWire();
        return true;
      }
      wiring = { from: end, pos: p.point, x: e.clientX, y: e.clientY, dragged: false, sticky: false };
      return true;
    }
    if (wiring && wiring.sticky) return false;        // empty table: orbit the view, the wire stays in hand
    if (p.kind === "buttonCap") {
      press = p.id; S.pressed[p.id] = true; B.parts[p.id].userData.setPressed(true); applyPhysics(); return true;
    }
    if (p.kind === "knob") { knob = { id: p.id, x: e.clientX, v: S.pot[p.id] ?? 512 }; return true; }
    if (p.kind === "slider") {                       // slide switch: a click flips it, and it stays
      S.pressed[p.id] = !S.pressed[p.id]; B.parts[p.id].userData.setPosition(S.pressed[p.id]); applyPhysics();
      toast(`Switch slid toward pin ${S.pressed[p.id] ? 3 : 1}.`); return true;
    }
    if (p.kind === "part") { partDown = { id: p.id, x: e.clientX, y: e.clientY }; return true; }
    if (p.kind === "wire") { selectWire(p.index); return true; }
    select(null);
    return false;
  });
  B.on("move", (p, e) => {
    if (wiring) {
      B.showPreview(wiring.pos, p.point && (p.kind === "hole" || p.kind === "boardPin" || p.kind === "leg" ? p.point : p.point.clone().setY(p.point.y + 2)));
      if (Math.hypot(e.clientX - wiring.x, e.clientY - wiring.y) > 6) wiring.dragged = true;
      // near an edge of the bench view the camera turns that way, so you can reach round
      const r = B.canvas.getBoundingClientRect(), m = 56;
      B.edge = { x: e.clientX < r.left + m ? -1 : e.clientX > r.right - m ? 1 : 0, y: e.clientY < r.top + m ? -1 : e.clientY > r.bottom - m ? 1 : 0 };
    }
    if (knob) {
      const v = Math.max(0, Math.min(1023, Math.round(knob.v + (e.clientX - knob.x) * 4)));
      S.pot[knob.id] = v; B.parts[knob.id].userData.setValue(v);
      showTip(e.clientX, e.clientY, `knob → <b>${v}</b> / 1023`); renderPhysics(S.lastPhysics, currentScenario());
    }
    if (partDown && !drag && Math.hypot(e.clientX - partDown.x, e.clientY - partDown.y) > 6) {
      const part = S.placed[partDown.id]; partDown = null;
      removePart(part.def.id, true); renderTray(); select(null);
      startPartDrag(e, part.def, { rot: part.rot });
    }
  });
  B.on("up", (p) => {
    if (wiring && !wiring.sticky) {
      const end = endOf(p);
      if (!wiring.dragged && (!end || end === wiring.from)) {
        // a click, not a drag: keep the wire in hand — look around, then click where it goes
        wiring.sticky = true; B.edge = null;
        toast("Now click where the other end goes. Drag the table to look around — Esc cancels.");
      } else if (end && end !== wiring.from) finishWire(end);
      else cancelWire();
    }
    if (press) { S.pressed[press] = false; B.parts[press] && B.parts[press].userData.setPressed(false); press = null; applyPhysics(); }
    if (knob) { knob = null; hideTip(); }
    if (partDown) { select(partDown.id); partDown = null; }
  });
  B.on("hover", (p, e) => { if (!drag && !knob) hover(p, e); });
  B.on("dbl", (p) => {
    if (["part", "knob", "buttonCap", "slider", "leg"].includes(p.kind)) openInspector(partTarget(p.id));
    else if (p.kind === "board" || p.kind === "boardPin") openInspector({ kind: "board", wokwiType: G.boardType, label: G.boardType.replace("wokwi-", "").replace(/-/g, " "), instance: G.boardId, focus: p.component, pin: p.pin });
    else if (p.kind === "hole" || p.kind === "breadboard") openInspector({ kind: "breadboard", wokwiType: G.bbType, label: "Breadboard", cardId: "breadboard" });
  });

}
// The 3D bench (a WebGL renderer) is only created when the first lesson
// starts, so the start page and the map load without it.
function ensureStage() {
  if (B) return;
  B = new Bench3D($("stage"));
  wireStage();
}
function setupStage() {
  window.__bench3d = { get B() { return B; }, S, G, endWorld, THREE, placePart: (id, hole, r) => placePart(S.trayParts.find((d) => d.id === id), hole, r || 0), addWire: (a, b) => { S.wires.push({ a, b, state: "pending" }); renderWires(); } };      // for the browser tests
  window.addEventListener("pointermove", (e) => { if (drag) dragMove(e.clientX, e.clientY); });
  window.addEventListener("pointerup", () => { if (drag) endDrag(); });
  window.addEventListener("keydown", (e) => {
    if (e.target.matches && e.target.matches("input, textarea")) return;
    if ((e.key === "r" || e.key === "R") && drag) { drag.rot = (drag.rot + 90) % 360; dragMove(lastPointer.x, lastPointer.y); }
    else if (e.key === "r" || e.key === "R") rotateSelected();
    else if ((e.key === "Delete" || e.key === "Backspace") && S.selected) removePart(S.selected);
    else if ((e.key === "Delete" || e.key === "Backspace") && S.selectedWire !== null) { S.wires.splice(S.selectedWire, 1); renderWires(); select(null); }
    else if (e.key === "Escape") { cancelWire(); select(null); closeInspector(); }
  });
}

// hover: every hole, socket and part says exactly what it is
let cardCache = {};
async function cardFor(wokwiType, attrs, cardId) {
  const key = wokwiType + JSON.stringify(attrs || {}) + (cardId || "");
  if (!cardCache[key]) cardCache[key] = api("/api/part", { wokwi_type: wokwiType, attrs, card_id: cardId }).catch(() => null);
  return cardCache[key];
}
function showTip(x, y, html) {
  const tip = $("tip"); tip.innerHTML = html; tip.classList.add("show");
  tip.style.left = `${x + 16}px`; tip.style.top = `${y + 16}px`;
}
function hideTip() { $("tip").classList.remove("show"); }
function holeStory(hole) {
  const [strip, row] = hole.split(".");
  if (/^[tb][pn]$/.test(strip)) {
    const side = strip[0] === "t" ? "top" : "bottom", plus = strip[1] === "p";
    return `${side} power rail <span class="${plus ? "plus" : "minus"}">${plus ? "＋" : "−"}</span>, hole ${row}. The whole rail is one connection.`;
  }
  const col = parseInt(strip, 10), half = strip.endsWith("t") ? "a–e" : "f–j";
  return `column ${col}, row ${row}. Joined inside the board to the other holes ${half} of column ${col}.`;
}
function whatIsIn(hole) {
  const legs = Object.values(S.placed).flatMap((p) => Object.entries(p.legs).filter(([, h]) => h === hole).map(([pin]) => `${p.def.label} leg ${pin}`));
  const wires = S.wires.filter((w) => w.a === `bb:${hole}` || w.b === `bb:${hole}`).map((w) => `wire to ${(w.a === `bb:${hole}` ? w.b : w.a).replace(/^bb:/, "")}`);
  return [...legs, ...wires];
}
async function hover(p, e) {
  if (!p) { hideTip(); B.paintHoles({}); B.paintSockets({}); B.markRing(null); return; }
  let html = "";
  B.paintHoles(p.kind === "hole" ? { [p.hole]: "hover" } : {});
  B.paintSockets(p.kind === "boardPin" ? { [p.pin]: true } : {});
  B.markRing(p.kind === "hole" || p.kind === "boardPin" || p.kind === "leg" ? p.point : null);
  if (p.kind === "hole") {
    const inside = whatIsIn(p.hole);
    html = `<b>${esc(p.hole)}</b> — ${holeStory(p.hole)}${inside.length ? `<br>in it: ${esc(inside.join(", "))}` : ""}`;
  } else if (p.kind === "boardPin") {
    const info = (document.createElement(G.boardType).pinInfo || []).find((q) => q.name === p.pin);
    const sig = (info && info.signals || []).map((s) => s.type === "pwm" ? "PWM" : s.signal || s.type).filter(Boolean).join(", ");
    html = `<b>${esc(p.pin)}</b> — Arduino header socket${sig ? ` (${esc(sig)})` : ""}. Drag from here to run a wire.`;
  } else if (p.kind === "leg") {
    const part = S.placed[p.id];
    const leads = S.wires.filter((w) => w.a === `${p.id}:${p.pin}` || w.b === `${p.id}:${p.pin}`).map((w) => (w.a === `${p.id}:${p.pin}` ? w.b : w.a).replace(/^bb:/, ""));
    const data = await cardFor(part.def.wokwi_type, part.def.attrs, part.def.card_id);
    const meaning = data && data.card.pins && data.card.pins[p.pin];
    html = `<b>${esc(part.def.label)} · ${esc(p.pin)}</b>${meaning ? " — " + esc(meaning) : ""}<br>${leads.length ? "connected to " + esc(leads.join(", ")) : "bare leg — drag from here to connect it"}`;
  } else if (p.kind === "part" || p.kind === "knob" || p.kind === "buttonCap" || p.kind === "slider") {
    const part = S.placed[p.id];
    const extra = p.kind === "knob" ? "drag the knob sideways to turn it" : p.kind === "buttonCap" ? "hold to press" : p.kind === "slider" ? `click to slide it (now toward pin ${S.pressed[p.id] ? 3 : 1})` : "drag to move · double-click to inspect";
    html = `<b>${esc(part.def.label)}</b> — ${extra}${part.at ? "" : `<br>${Object.entries(part.legs).map(([k, v]) => `${esc(k)}→${esc(v || "air")}`).join(" · ")}`}`;
  } else if (p.kind === "board" && UNO_COMPONENTS[p.component] && G.boardType === "wokwi-arduino-uno") {
    const c = UNO_COMPONENTS[p.component];
    html = `<b>${esc(c.name)}</b> — ${esc(c.what.split(". ")[0])}.<br><span class="dim">double-click for the full story</span>`;
  } else if (p.kind === "wire") {
    const w = S.wires[p.index];
    html = `<b>${esc(w.kind ? LINK_WORDS[w.kind] : "wire")}</b> ${esc(w.a.replace(/^bb:/, ""))} ↔ ${esc(w.b.replace(/^bb:/, ""))} — click to select, Delete to pull out`;
  }
  if (html) showTip(e.clientX, e.clientY, html); else hideTip();
  B.canvas.style.cursor = p.kind === "hole" || p.kind === "boardPin" || p.kind === "leg" ? "crosshair" : p.kind === "part" ? "move" : p.kind === "knob" || p.kind === "buttonCap" || p.kind === "wire" ? "pointer" : "grab";
}

// ---------------------------------------------------------------------------
// Part inspector: the same 3D model, big, turntable, every pin labelled
// ---------------------------------------------------------------------------
const card_pins_for = (type) => (type ? pinsFor(type) : []);
let I = null;
async function openInspector(target) {
  $("inspector").hidden = false;
  const info = $("inspInfo");
  info.innerHTML = `<p class="empty-note">Loading…</p>`;
  if (!I) { I = new Inspector3D($("inspStage")); I.onPick((key) => activateComponent(key)); }
  let obj, pins3d = [], pins = [];
  if (target.kind === "breadboard") {
    obj = makeBreadboard(BB_SIZE[target.wokwiType] || "half");
  } else if (target.kind === "board") {
    obj = await makeBoard(target.wokwiType);
    const sm = obj.getObjectByName("boardPins");
    pins = document.createElement(target.wokwiType).pinInfo || [];
    pins3d = sm ? sm.userData.pins.map((n, i) => ({ name: n, pos: new THREE.Vector3(...sm.userData.positions[i]) })) : [];
  } else if (target.cardId && hasModel(target.cardId) && !["led", "resistor-220", "resistor-1k", "resistor-10k", "pushbutton", "potentiometer-10k"].includes(target.cardId)) {
    obj = buildModel(target.cardId);            // the catalogue's model of the real part
    pins = (card_pins_for(target.wokwiType)).map(([n]) => ({ name: n, signals: [] }));
  } else {
    obj = makePart(target.wokwiType, target.attrs || {});
    const top = 8.5;
    pins3d = obj.userData.pins.map(([n, dx, dz]) => ({ name: n, pos: new THREE.Vector3(dx * PITCH, top - 1.2, dz * PITCH) }));
    pins = pins3d.map((p) => ({ name: p.name, signals: [] }));
  }
  I.show(obj, pins3d, activatePin);

  const data = await cardFor(target.wokwiType, target.attrs, target.cardId);
  const card = data ? data.card : { display_name: target.label, description: "" };
  const part = target.instance && S.placed[target.instance];
  const facts = [];
  if (card.polarized) facts.push("Polarized — only works one way round");
  (data && data.interchangeable || []).forEach(([a, b]) => facts.push(`${a} ⇄ ${b} interchangeable`));
  (data && data.groups || []).forEach((g) => facts.push(`${g.join(" + ")} are one connection`));
  if (card.legs_placed_together) facts.push("Goes in as one object — all legs at once");
  if (card.straddles_center_gap) facts.push("Must straddle the centre gap");
  if (card.led_builtin) facts.push(`On-board LED on pin ${card.led_builtin}`);
  const pinRows = pins.map((p) => {
    let meaning = card.pins && card.pins[p.name];
    if (!meaning && target.kind === "board") {
      const sig = (p.signals || []).map((s) => s.type === "pwm" ? "PWM" : s.type === "analog" ? `analog in ${s.channel ?? ""}` : s.signal ? `${s.type.toUpperCase()} ${s.signal}` : s.type).join(", ");
      const d = card.pin_domains || {};
      const kind = (d.digital || []).includes(p.name) ? "digital I/O" : (d.analog || []).includes(p.name) ? "analog in (also digital)" : /^GND/.test(p.name) ? "ground" : /V/.test(p.name) ? "power" : "";
      meaning = [kind, sig].filter(Boolean).join(" · ");
    }
    const where = part && part.legs[p.name] ? ` <span class="chip">in ${esc(part.legs[p.name])}</span>` : "";
    return `<tr data-pin="${esc(p.name)}"><td>${esc(p.name)}</td><td>${esc(meaning || "")}${where}</td></tr>`;
  }).join("");
  const comps = target.kind === "board" && target.wokwiType === "wokwi-arduino-uno"
    ? Object.entries(UNO_COMPONENTS).map(([k, c]) => `<div class="comp" data-comp="${k}"><b>${esc(c.name)}</b><span>${esc(c.what)}</span></div>`).join("") : "";
  const bbText = target.kind === "breadboard" ? `<p>Under the holes are metal clip strips. Columns are numbered along the board (1, 2, 3 …) and rows are lettered (a–j). The five holes of one column in the top half — e.g. 12a, 12b, 12c, 12d, 12e — sit on one strip, so they're one connection; the bottom half (12f–12j) is a separate strip, and the centre gap keeps the halves apart. A lettered row (all the "c" holes) is <b>not</b> connected along the board. The red (+) and blue (−) rails along the edges are each one long connection. Hover any single hole on the workbench to see exactly where it is and what's in it.</p>` : "";
  info.innerHTML = `<h2>${esc(card.display_name || target.label)}</h2>
    ${part ? `<div class="chip">${esc(part.def.id)} in your circuit</div>` : ""}
    <p>${esc(card.description || "")}</p>${card.how_to_use ? `<p><b>How to use:</b> ${esc(card.how_to_use)}</p>` : ""}${bbText}
    ${facts.length ? `<div class="insp-facts">${facts.map((f) => `<span class="fact">${esc(f)}</span>`).join("")}</div>` : ""}
    ${comps ? `<div class="panel-title" style="margin-top:12px;">Everything on the board — click one (or click the model)</div><div class="comp-list">${comps}</div>` : ""}
    ${pinRows ? `<div class="panel-title" style="margin-top:12px;">Every pin</div><table class="pin-table">${pinRows}</table>` : ""}`;
  info.querySelectorAll("tr[data-pin]").forEach((tr) => tr.onclick = () => activatePin(tr.dataset.pin));
  info.querySelectorAll(".comp[data-comp]").forEach((el) => el.onclick = () => activateComponent(el.dataset.comp));
  if (target.focus) activateComponent(target.focus); else if (target.pin) activatePin(target.pin);
}
function activatePin(pin) {
  I && I.setActive(pin);
  document.querySelectorAll(".pin-table tr").forEach((r) => r.classList.toggle("active", r.dataset.pin === pin));
  const row = document.querySelector(`.pin-table tr[data-pin="${CSS.escape(pin)}"]`);
  row && row.scrollIntoView({ block: "nearest" });
}
function activateComponent(key) {
  I && I.focus(key);
  document.querySelectorAll(".comp[data-comp]").forEach((el) => el.classList.toggle("active", el.dataset.comp === key));
  document.querySelectorAll(".pin-table tr").forEach((r) => r.classList.remove("active"));
  const el = document.querySelector(`.comp[data-comp="${CSS.escape(key)}"]`);
  el && el.scrollIntoView({ block: "nearest", behavior: "smooth" });
}
function closeInspector() { $("inspector").hidden = true; I && I.stop(); }
function setupInspector() {
  $("inspClose").onclick = closeInspector;
  $("inspector").addEventListener("pointerdown", (e) => { if (e.target.id === "inspector") closeInspector(); });
}

// ---------------------------------------------------------------------------
// Lesson flow (engine)
// ---------------------------------------------------------------------------
async function refreshLessons() {
  const data = await api("/api/lessons");
  S.lessons = data.lessons; S.progress = data.progress;
  // an older bench_server (started before the world map) sends no worlds:
  // fall back to one world of every lesson so the map still draws
  S.worlds = data.worlds && data.worlds.length ? data.worlds : [{
    id: "all", name: "All levels", emoji: "🗺️", theme: "workshop", number: 1, coming_soon: false,
    blurb: "Restart bench_server.py to see the themed worlds.",
    levels: data.lessons.map((l, i) => ({ ...l, level: `1-${i + 1}`, prereqs_done: l.prereqs_done ?? l.unlocked, stars: l.stars ?? (l.completed ? 1 : 0) })),
  }];
}
function processActions(actions) {
  actions.forEach((a) => {
    if (a.type === "play_clip") { S.clip = a.text; S.hints = []; }
    else if (a.type === "hint") S.hints.push(a.text);
    else if (a.type === "error") toast(a.message);
  });
}
async function startLesson(lessonId, difficulty, build) {
  ensureStage();
  B.clearReveal(); S.revealedAt = undefined;
  // a fresh level: nothing selected, no old feedback, no wire in hand
  select(null); cancelWire(); $("feedback").className = "feedback"; $("feedback").innerHTML = "";
  $("circuitSheet").classList.remove("open");
  const r = await api("/api/start", { lesson_id: lessonId, difficulty, build });
  S.build = r.build || { method: "breadboard" };
  S.reference = r.reference || [];
  $("trayTitle").textContent = S.build.method === "breadboard"
    ? "Drag a part onto the breadboard · R turns it"
    : "Drag a part onto the table, then from a leg tip to connect it";
  $("connectWith").hidden = S.build.method === "breadboard";
  S.connectWith = "planned";
  $("connectWith").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.with === "planned"));
  $("stageHint").textContent = S.build.method === "breadboard"
    ? "drag the table to orbit · right-drag to pan · scroll to zoom · drag from any hole or header socket to wire · double-click to inspect"
    : `no breadboard (${{ clips: "clip leads", twist: "twisted legs", solder: "solder" }[S.build.join]}): drag from a bare leg tip to a header socket or another leg to join them · drag the table to orbit · double-click to inspect`;
  Object.assign(S, { lessonId, difficulty, session: r.session, view: r.view, trayParts: r.parts, layout: r.layout,
                     progress: r.progress, placed: {}, wires: [], selected: null, lastPhysics: null, pressed: {} });
  processActions(r.actions);
  S.pot = {};
  await buildBoard(); renderTray(); renderWires(); renderStep(); renderPhysics(null); renderTracking(); renderTop();
}
async function engineEvent(ev) {
  const r = await api("/api/event", { session: S.session, event: ev });
  S.view = r.view; processActions(r.actions);
  return r;
}
function lessonMeta() { return S.lessons.find((l) => l.id === S.lessonId) || { title: S.lessonId }; }

// ---------------------------------------------------------------------------
// Reveal step: mark in red exactly what the current step connects, on the
// learner's OWN board (their parts where they actually put them, their
// swapped pins) — a free hole in the right column, the right socket, and a
// dashed line where a wire goes. Counts as a hint.
// ---------------------------------------------------------------------------
const ROWS = { t: ["a", "b", "c", "d", "e"], b: ["f", "g", "h", "i", "j"] };
function occupiedHoles() {
  const used = new Set();
  Object.values(S.placed).forEach((p) => Object.values(p.legs).forEach((h) => h && used.add(h)));
  S.wires.forEach((w) => [w.a, w.b].forEach((e) => e.startsWith("bb:") && used.add(e.slice(3))));
  return used;
}
function freeHoleIn(hole, taken) {
  const strip = hole.split(".")[0];
  const names = /^[tb][pn]$/.test(strip)
    ? B.bbLayout.holes.filter((h) => h.strip === strip).map((h) => h.name)
    : ROWS[strip.slice(-1)].map((r) => `${strip}.${r}`);
  return names.find((n) => !taken.has(n)) || hole;
}
function referenceHoles() {
  const ref = new Map();
  (S.reference || []).forEach(([a, b]) => {
    const [ka, ra] = splitEnd(a), [kb, rb] = splitEnd(b);
    if (ka === G.bbId && kb !== G.bbId) ref.set(b, ra);
    if (kb === G.bbId && ka !== G.bbId) ref.set(a, rb);
  });
  return ref;
}
const partLabel = (id) => (S.trayParts.find((d) => d.id === id) || { label: id }).label;
function legWords(end) {
  const [id, pin] = splitEnd(end), d = S.trayParts.find((x) => x.id === id) || {};
  if (d.wokwi_type === "wokwi-led") return pin === "A" ? "LED long leg (+)" : "LED short leg (−)";
  if (d.wokwi_type === "wokwi-potentiometer") return pin === "SIG" ? "knob middle leg" : "knob outer leg";
  if ((d.wokwi_type || "").startsWith("wokwi-pushbutton")) return "button leg";
  if (d.wokwi_type === "wokwi-resistor") return "resistor leg";
  return `${partLabel(id)} ${pin}`;
}
function revealTargets(act) {
  const markers = [], lines = [], taken = occupiedHoles(), ref = referenceHoles();
  const mark = (hole, label) => { taken.add(hole); const pos = B.holeWorld(hole); if (pos) markers.push({ pos, label, hole }); return pos; };
  const isBoard = (end) => splitEnd(end)[0] === G.boardId;
  const socket = (end) => { const pin = splitEnd(end)[1], pos = B.boardPinWorld(pin); markers.push({ pos, label: `pin ${pin.split(".")[0]}`, socket: pin }); return pos; };
  // a placing step: where each leg of the part goes (the lesson's own layout)
  const comps = [...new Set(act.landing.map((e) => splitEnd(e)[0]))];
  comps.forEach((id) => {
    const d = S.trayParts.find((x) => x.id === id);
    pinsFor(d ? d.wokwi_type : "").forEach(([pin]) => { const h = ref.get(`${id}:${pin}`); if (h) mark(h, legWords(`${id}:${pin}`)); });
  });
  if (B.noBreadboard) {
    act.pairs.forEach(([a, b]) => {
      const at = (e) => (isBoard(e) ? socket(e) : S.placed[splitEnd(e)[0]] ? (markers.push({ pos: B.partPinWorld(...splitEnd(e)), label: legWords(e) }), B.partPinWorld(...splitEnd(e))) : null);
      const pa = at(a), pb = at(b);
      if (pa && pb) lines.push([pa, pb]);
    });
    return { markers, lines };
  }
  act.pairs.forEach(([a, b]) => {
    const placedHole = (e) => { const [id, pin] = splitEnd(e); return S.placed[id] ? S.placed[id].legs[pin] : null; };
    const [ha, hb] = [placedHole(a), placedHole(b)];
    // a leg that isn't placed yet joining one that is: it just goes in the same column
    for (const [loose, fixed, hFixed] of [[a, b, hb], [b, a, ha]]) {
      if (!isBoard(loose) && !placedHole(loose) && !isBoard(fixed) && hFixed) {
        mark(freeHoleIn(hFixed, taken), `${legWords(loose)} here`); return;
      }
    }
    // otherwise a wire: from a free hole in each leg's column (or the reference spot) to the other end
    const endPos = (e, h) => {
      if (isBoard(e)) return socket(e);
      if (h) return mark(freeHoleIn(h, taken), "wire end here");
      const r = ref.get(e);                        // part not placed yet: show where it goes
      if (!r) return null;
      mark(r, `${legWords(e)} here`);
      return mark(freeHoleIn(r, taken), "wire end here");
    };
    const pa = endPos(a, ha), pb = endPos(b, hb);
    if (pa && pb) lines.push([pa, pb]);
  });
  return { markers, lines };
}
async function revealStep() {
  const r = await engineEvent({ command: "reveal" });
  const act = r.actions.find((a) => a.type === "reveal");
  if (!act) return;
  const { markers, lines } = revealTargets(act);
  B.showReveal(markers);
  S.revealedAt = S.view.step_index;
  toast(lines.length ? "Connect the two red spots with a wire." : "Put the legs in the red holes.");
  renderTracking();
}

function renderTop() {
  const p = S.progress;
  const how = !S.build || S.build.method === "breadboard" ? "" : ` · no breadboard (${{ clips: "clip leads", twist: "twisted legs", solder: "solder" }[S.build.join]})`;
  $("brandSub").textContent = `${lessonMeta().title} · ${S.difficulty}${how}${p ? ` · level ${p.level} · ${p.xp} XP` : ""}`;
  document.querySelectorAll("#levelPills .pill").forEach((b) => b.setAttribute("aria-pressed", b.dataset.level === S.difficulty));
}
function renderStep() {
  const v = S.view, s = v && v.step;
  if (B && S.revealedAt !== undefined && v && v.step_index !== S.revealedAt) { B.clearReveal(); S.revealedAt = undefined; }
  const total = (v && v.step_count) || 1;
  $("progressRow").innerHTML = Array.from({ length: total }, (_, i) =>
    `<div class="progress-dot ${i < v.step_index ? "done" : i === v.step_index ? "current" : ""}"></div>`).join("");
  const phase = s ? s.phase : (v && v.phase) || "";
  $("stepPhase").textContent = phase === "build" ? `Step ${v.step_index} of ${total - 2}` : phase === "upload" ? "Upload the code" : phase === "final_check" ? "Final check" : phase;
  $("stepClip").innerHTML = safeHtml(S.clip || (s && s.clip) || "");
  $("hintList").innerHTML = S.hints.map((h, i) => `<div class="hint-item"><b>Hint ${i + 1}.</b> ${safeHtml(h)}</div>`).join("");
  $("prevBtn").disabled = !v || v.step_index <= 1;
  const upload = s && s.phase === "upload";
  $("codeView").classList.toggle("show", !!upload);
  $("checkBtn").style.display = upload ? "none" : "";
  if (upload) $("codeBlock").textContent = v.code || "";
}
function renderTracking() {
  const v = S.view || {};
  const chips = (arr, f) => arr && arr.length ? arr.map(f).map((x) => `<span class="chip">${esc(x)}</span>`).join("") : '<span class="empty-note">none</span>';
  $("trackingBody").innerHTML = `
    <div class="panel-title">confirmed connections</div>${chips(v.confirmed_pairs, ([a, b]) => `${a} ↔ ${b}`)}
    <div class="panel-title" style="margin-top:8px;">pin swaps</div>${chips(v.pin_substitutions, (s) => `${s.original} → ${s.actual}`)}
    <div class="panel-title" style="margin-top:8px;">remaps</div>${chips(v.pin_remaps, (r) => `${r.component}: ${r.original} → ${r.actual}`)}`;
}

function verdictAndMessage(actions) {
  const fb = actions.find((a) => a.type === "feedback");
  const verdict = fb ? fb.verdict : "pass";
  const pick = (t) => actions.filter((a) => a.type === t).map((a) => esc(a.message));
  const lost = pick("connection_lost"), strays = pick("stray_connection"), hazards = pick("physics_hazard");
  if (lost.length) return { verdict: "wrong", msg: "🔌 " + lost.join("<br>🔌 ") };
  if (strays.length) return { verdict: "wrong", msg: "🧷 " + strays.join("<br>🧷 ") };
  if (hazards.length) return { verdict: "wrong", msg: "⚡ " + hazards.join("<br>⚡ ") };
  const parts = [];
  if (verdict === "wrong") parts.push(...(pick("substitution_refused").length ? pick("substitution_refused") : ["Not quite — check the connection."]));
  else {
    parts.push(...pick("part_turned").map((m) => "↻ " + m), ...pick("board_changes").map((m) => "📋 " + m),
               ...pick("pin_substituted"), ...pick("breadboard_bypassed"));
    if (!parts.length) parts.push(verdict === "harmless" ? "Connected — a different but electrically equivalent way." : "Wired correctly.");
  }
  return { verdict, msg: parts.join("<br>") };
}
function showFeedback(verdict, title, msg) {
  const fb = $("feedback"); fb.className = "feedback show " + verdict;
  fb.innerHTML = `<div class="feedback-title">${title}</div>${msg}`;
  // a plain pass fades away; "not yet" and the finish stay until they matter no more
  clearTimeout(showFeedback._t);
  if (verdict === "pass" && title === "Pass") showFeedback._t = setTimeout(() => fb.classList.remove("show"), 3500);
}

// physics → the 3D LEDs glow, the button's pressed state is shown
function currentScenario() {
  const r = S.lastPhysics;
  return r && (r.scenarios.find((s) => Object.entries(s.pressed || {}).every(([id, p]) => !!S.pressed[id] === p)) || r.scenarios[0]);
}
function applyPhysics() {
  const r = S.lastPhysics;
  if (!r) return;
  const scenario = currentScenario();
  Object.values(S.placed).forEach((p) => {
    const o = B.parts[p.def.id];
    if (p.def.wokwi_type !== "wokwi-led" || !o) return;
    const led = scenario && scenario.leds[p.def.id];
    o.userData.setLit(!!led && led.state !== "off", led && led.state === "dim");
  });
  renderPhysics(r, scenario);
}
function renderPhysics(result, scenario) {
  const el = $("physicsBody");
  // a dot on the Circuit button when the physics has something to say
  $("circuitBtn").classList.toggle("alert", !!(result && result.findings.some((f) => f.severity !== "info")));
  if (!result) { el.innerHTML = '<span class="empty-note">Check your wiring to see currents, LED brightness and pin readings. Press the real button on the board to see its pressed state.</span>'; return; }
  const out = result.findings.map((f) => `<div class="phys-item phys-${f.severity}">${f.severity === "hazard" ? "⚡" : f.severity === "warning" ? "⚠️" : "ℹ️"} ${esc(f.message)}</div>`);
  const sc = scenario || result.scenarios[0];
  if (sc) {
    out.push(`<div class="panel-title" style="margin-top:6px;">${esc(sc.label)}</div>`);
    Object.entries(sc.leds).forEach(([id, l]) => out.push(`<div class="phys-item">${esc(id)}: <b>${esc(l.state)}</b>${l.current_ma ? ` · ${l.current_ma} mA` : ""}</div>`));
    Object.entries(sc.buzzers || {}).forEach(([id, bz]) => out.push(`<div class="phys-item">${esc(id)}: <b>${bz.state === "sounding" ? "sounding" : bz.state === "reversed" ? "wired backwards (+ and − swapped)" : "silent"}</b></div>`));
    Object.entries(sc.pins).forEach(([pin, info]) => {
      if (info.reading !== undefined) {
        let reading = info.reading;
        const pot = Object.values(S.placed).find((p) => p.def.wokwi_type === "wokwi-potentiometer");
        if (info.mode === "ANALOG_IN" && pot && reading !== null) reading = `${S.pot[pot.def.id] ?? 512} (turn the knob)`;
        out.push(`<div class="phys-item">${esc(pin)} reads <b>${esc(reading ?? "—")}</b></div>`);
      } else out.push(`<div class="phys-item">${esc(pin)} (${esc(info.mode)}) · ${info.current_ma} mA</div>`);
    });
  }
  el.innerHTML = out.join("") || '<span class="empty-note">Nothing powered yet.</span>';
}

function awardHtml(a) {
  if (!a) return "";
  const lines = [`<br><b>+${a.xp_gained} XP</b>${a.xp_gained === 0 ? " (no improvement on your best run)" : ""}`];
  if (a.level_up) lines.push(`⬆️ Level up — you're now level ${a.progress.level}!`);
  a.new_badges.forEach((b) => lines.push(`🏅 ${esc(a.progress.badge_names[b] || b)}`));
  return lines.join("<br>");
}

async function check(final) {
  if (final && S.view.phase === "upload") await engineEvent({ command: "done" });
  const r = await engineEvent({ command: "done", detected_pairs: detectedPairs(), snapshot: true });
  S.lastPhysics = r.physics || S.lastPhysics;
  applyPhysics(); renderTracking();
  if (r.actions.some((a) => a.type === "complete")) {      // only THIS check passing celebrates
    showFeedback("pass", "Complete 🎉", "Every connection is correct and the circuit is physically sound." + awardHtml(r.award));
    if (r.award) { S.progress = r.award.progress; await refreshLessons(); renderTop(); }
    if (bench.onComplete) bench.onComplete(r.award);
    S.wires.forEach((w) => (w.state = "ok")); renderWires();
    return;
  }
  const { verdict, msg } = verdictAndMessage(r.actions);
  showFeedback(verdict, verdict === "pass" ? "Pass" : verdict === "harmless" ? "Harmless" : "Not yet", msg);
  S.wires.forEach((w) => (w.state = verdict === "wrong" ? w.state : "ok")); renderWires();
  if (verdict !== "wrong") setTimeout(renderStep, 500);
}

// ---------------------------------------------------------------------------
// The workbench's own controls, and the API the app flow (flow.js) uses
// ---------------------------------------------------------------------------
function setupBenchControls() {
  $("levelPills").onclick = guarded(async (e) => { const b = e.target.closest(".pill"); if (b) await startLesson(S.lessonId, b.dataset.level, S.build); });
  $("hintBtn").onclick = guarded(async () => { await engineEvent({ command: "hint" }); renderStep(); });
  $("revealBtn").onclick = guarded(revealStep);
  // the solder / clip / push buttons show a render of the real item
  $("connectWith").querySelectorAll("button[data-with]").forEach((b) => {
    if (b.dataset.with === "planned") return;
    iconThumb(b.dataset.with).then((url) => { if (url) b.querySelector(".ic").outerHTML = `<img class="ic-3d" src="${url}" alt="">`; }).catch(() => {});
  });
  $("connectWith").onclick = (e) => {
    const b = e.target.closest("button[data-with]"); if (!b) return;
    S.connectWith = b.dataset.with;
    $("connectWith").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
  };
  $("circuitBtn").onclick = () => $("circuitSheet").classList.toggle("open");
  $("circuitClose").onclick = () => $("circuitSheet").classList.remove("open");
  $("helpBtn").onclick = () => $("stageHint").classList.toggle("show");
  // the hand tool: a toggle, or hold Space for a quick move
  const setHand = (on) => { if (!B) return; B.setHand(on); $("handBtn").setAttribute("aria-pressed", on); };
  $("handBtn").onclick = () => setHand(!(B && B.handMode));
  let spaceHand = false;
  window.addEventListener("keydown", (e) => {
    if (e.code !== "Space" || e.repeat || (e.target.matches && e.target.matches("input, textarea, select, button"))) return;
    if ($("lessonScreen").hidden || (B && B.handMode)) return;
    e.preventDefault(); spaceHand = true; setHand(true);
  });
  window.addEventListener("keyup", (e) => { if (e.code === "Space" && spaceHand) { spaceHand = false; setHand(false); } });
  $("prevBtn").onclick = guarded(async () => { await engineEvent({ command: "previous" }); renderStep(); });
  $("checkBtn").onclick = guarded(() => check(false));
  $("finishBtn").onclick = guarded(() => check(true));
  $("undoWireBtn").onclick = () => { S.wires.pop(); renderWires(); };
  $("resetBoardBtn").onclick = () => {
    if ((Object.keys(S.placed).length || S.wires.length) && !confirm("Clear everything off the board?")) return;
    Object.keys(S.placed).forEach((id) => removePart(id, true)); S.wires = []; renderTray(); renderWires(); select(null);
  };
  $("view3dBtn").onclick = () => B.view("3d");
  $("viewTopBtn").onclick = () => B.view("top");
}

export const bench = {
  S, api, esc, toast, guarded, refreshLessons,
  onComplete: null,                         // set by flow.js: (award) => celebrate
  async start(lessonId, difficulty, build) { await startLesson(lessonId, difficulty, build); },
  init() { setupStage(); setupInspector(); setupBenchControls(); },
};
