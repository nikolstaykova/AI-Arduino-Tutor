// CircuitQuest app flow: Sparky says hi → a real chat → Learn (parts picker,
// camera soon, lesson path) or Create (chat with the lesson generator) →
// the workbench (app.js). Celebrations when a lesson is completed.
import { bench } from "./app.js";
import { thumbnailById } from "./three/models.js";
import { createWorldMap } from "./overworld.js";
import { renderLibrary } from "./library.js";
import { setupAuth } from "./auth.js";

const { api, esc, toast, guarded } = bench;
const $ = (id) => document.getElementById(id);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const store = {
  get(k, d) { try { const v = localStorage.getItem("cq." + k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("cq." + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};

const F = { name: null, progress: null, catalog: [], selected: new Set(store.get("parts", [])), showAll: false, matches: {} };
// A lesson's icon is a render of its key real part (the button in a button
// lesson, the knob in a knob lesson, ...) — the same 3D models as the bench,
// so hand-written and AI-made lessons look alike.
const ICON_SKIP = new Set(["board", "breadboard", "wire", "cable", "tool", "consumable", "resistor"]);
const ICON_RANK = ["display", "motor", "sensor", "buzzer", "pushbutton", "potentiometer", "input", "switch", "led"];
function keyPart(lesson) {
  const parts = (lesson.parts_used || []).map((id) => F.catalog.find((p) => p.id === id)).filter(Boolean);
  const pool = parts.filter((p) => !ICON_SKIP.has(p.subtype) && p.wokwi_type);
  const rank = (p) => { const i = ICON_RANK.indexOf(p.subtype); return i < 0 ? ICON_RANK.length : i; };
  return pool.sort((a, b) => rank(a) - rank(b))[0] || parts.find((p) => p.subtype === "resistor") || null;
}
async function ensureIcons() {
  F.icons = F.icons || {};
  await Promise.all(bench.S.lessons.filter((l) => !(l.id in F.icons)).map(async (l) => {
    const p = keyPart(l);
    F.icons[l.id] = p ? await thumbnailById(p.id, p.wokwi_type, p.attrs || {}, 128) : null;
  }));
}
const icon = (id, cls = "ico") => (F.icons && F.icons[id] ? `<img class="${cls}" src="${F.icons[id]}" alt="">` : "");

// ---------------------------------------------------------------------------
// Sparky — a friendly LED
// ---------------------------------------------------------------------------
$("mascot").innerHTML = `
<svg viewBox="0 0 120 150" width="120" height="150" aria-label="Sparky the LED">
  <defs><radialGradient id="sg" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#f6d2b0"/><stop offset=".55" stop-color="#df9563"/><stop offset="1" stop-color="#b86b44"/></radialGradient></defs>
  <circle class="glow" cx="60" cy="58" r="52" fill="#df9563" opacity=".18"/>
  <path d="M26 62 a34 34 0 0 1 68 0 v28 h-68z" fill="url(#sg)"/>
  <rect x="22" y="88" width="76" height="9" rx="4" fill="#b86b44"/>
  <rect x="44" y="97" width="5" height="44" rx="2" fill="#b9b3a5"/><rect x="71" y="97" width="5" height="36" rx="2" fill="#b9b3a5"/>
  <ellipse class="eye" cx="48" cy="60" rx="5.5" ry="7" fill="#2b1a0c"/><ellipse class="eye" cx="72" cy="60" rx="5.5" ry="7" fill="#2b1a0c"/>
  <circle cx="50" cy="57" r="1.8" fill="#fff"/><circle cx="74" cy="57" r="1.8" fill="#fff"/>
  <path d="M50 75 q10 9 20 0" stroke="#2b1a0c" stroke-width="3" fill="none" stroke-linecap="round"/>
  <ellipse cx="40" cy="44" rx="7" ry="10" fill="#fff" opacity=".35" transform="rotate(-25 40 44)"/>
</svg>`;
function sparkyHop() { const m = $("mascot"); m.classList.remove("happy"); void m.offsetWidth; m.classList.add("happy"); }
$("mascot").onclick = sparkyHop;

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------
async function say(chat, html, pause = 650) {
  const t = document.createElement("div"); t.className = "typing"; t.innerHTML = "<i></i><i></i><i></i>";
  chat.appendChild(t); t.scrollIntoView({ block: "end", behavior: "smooth" });
  await wait(pause);
  t.remove();
  const b = document.createElement("div"); b.className = "bubble bot"; b.innerHTML = html;
  chat.appendChild(b); b.scrollIntoView({ block: "end", behavior: "smooth" });
  return b;
}
function me(chat, text) {
  const b = document.createElement("div"); b.className = "bubble me"; b.textContent = text;
  chat.appendChild(b); b.scrollIntoView({ block: "end", behavior: "smooth" });
}
function choices(chat, items) {
  const row = document.createElement("div"); row.className = "choices";
  items.forEach((it, i) => {
    const c = document.createElement("button"); c.className = "choice"; c.style.animationDelay = `${i * 90}ms`;
    c.innerHTML = `<span class="ce">${it.emoji}</span><span>${esc(it.label)}${it.sub ? `<small>${esc(it.sub)}</small>` : ""}</span>`;
    c.onclick = () => { row.remove(); me(chat, `${it.emoji} ${it.label}`); it.go(); };
    row.appendChild(c);
  });
  chat.appendChild(row); row.scrollIntoView({ block: "end", behavior: "smooth" });
}

// ---------------------------------------------------------------------------
// Screens + header
// ---------------------------------------------------------------------------
let current = "home";
function go(screen) {
  const from = current; current = screen;
  $("tip").classList.remove("show");
  ["home", "learn", "create", "lesson", "library"].forEach((s) => ($(`${s}Screen`).hidden = s !== screen));
  window.scrollTo({ top: 0 });
  if (screen === "learn") renderLearn();
  if (screen === "library") renderLibrary((id) => openLessonPop(id));
  if (screen === "home" && from !== "home") homeChat();   // a fresh hello each time you come back
}
document.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => go(b.dataset.go)));
$("homeBtn").onclick = () => go("home");
$("backHomeBtn").onclick = () => go("learn");

function renderHeader(p, animateFrom) {
  if (!p) return;
  $("avatar").textContent = (F.name || "?").slice(0, 1).toUpperCase();
  $("lvlNum").textContent = p.level;
  $("lvlRing").style.strokeDashoffset = 97.4 * (1 - p.level_xp / p.level_span);
  $("streakChip").querySelector("span").textContent = (p.streak && p.streak.days) || 0;
  const target = p.xp, start = animateFrom ?? target, t0 = performance.now();
  const step = (t) => {
    const k = Math.min(1, (t - t0) / 900);
    $("xpNum").textContent = Math.round(start + (target - start) * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ---------------------------------------------------------------------------
// Home: hi → what do you wanna do today?
// ---------------------------------------------------------------------------
function nextLesson() {
  return bench.S.lessons.find((l) => l.prereqs_done && !l.completed) || bench.S.lessons.find((l) => !l.completed);
}
// ---- the start page: rendered at once (no typing delays), centred ----
const ICON = {
  play: '<path d="M8 5v14l11-7z"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/>',
  pen: '<path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4"/>',
  box: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7zM3 7l9 4 9-4M12 11v10"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
  skip: '<path d="M5 12h14M13 6l6 6-6 6"/>',
};
const svg = (name) => `<svg class="ic" viewBox="0 0 24 24">${ICON[name]}</svg>`;
function homeCards(items) {
  const row = $("homeActions"); row.innerHTML = "";
  items.forEach((it, i) => {
    const c = document.createElement("button");
    c.className = "choice home-card" + (it.primary ? " primary" : ""); c.style.animationDelay = `${i * 60}ms`;
    c.innerHTML = `${svg(it.icon)}<b>${esc(it.label)}</b>${it.sub ? `<small>${esc(it.sub)}</small>` : ""}`;
    c.onclick = it.go;
    row.appendChild(c);
  });
}
function homeMain() {
  $("homeQ").hidden = true; $("homeBack").hidden = true; $("homeInputRow").hidden = true;
  const p = F.progress, next = nextLesson();
  $("homeTitle").textContent = `Hi ${F.name}`;
  $("homeSub").innerHTML = p && p.xp
    ? `Level <b>${p.level}</b> · <b>${p.xp}</b> XP${p.streak && p.streak.days ? ` · <b>${p.streak.days}</b>-day streak` : ""}. What do you want to do today?`
    : "Ready to build your first real circuit? I'll check every wire with you. What do you want to do today?";
  const items = [
    { icon: "map", label: "Learn", sub: "Drive the world map of lessons", go: () => partsChat() },
    { icon: "pen", label: "Create my own lesson", sub: F.guest ? "🔒 Sign in with Google to create" : F.claude && F.claude.mode === "locked" ? "🔒 Connect your own Claude to unlock" : "Describe an idea, I'll design it", go: () => { go("create"); createIntro(); } },
    { icon: "box", label: "Parts & Tools", sub: "What everything is, in 3D, with videos", go: () => go("library") },
  ];
  if (next) items.unshift({ icon: "play", label: `Continue: ${next.title}`, sub: "Pick up where you left off", primary: true, go: () => openLessonPop(next.id) });
  homeCards(items);
}
async function homeChat() {
  sparkyHop();
  if (!F.name) {
    $("homeTitle").textContent = "Hi! I'm Sparky";
    $("homeSub").textContent = "Your circuit buddy — I'll check every wire with you. What's your name?";
    $("homeActions").innerHTML = ""; $("homeQ").hidden = true; $("homeBack").hidden = true;
    $("homeInputRow").hidden = false; $("homeInput").focus();
    return;
  }
  homeMain();
}
async function sendName() {
  const name = $("homeInput").value.trim();
  if (!name) return;
  if (F.becomingGuest) {                      // accounts on: a guest id this browser keeps
    const gid = crypto.randomUUID(); store.set("guestId", gid); window.__cqGuest = gid; F.becomingGuest = false;
    await api("/api/profile", { name });
    $("homeInputRow").hidden = true;
    return startApp();
  }
  const r = await api("/api/profile", { name });
  F.name = r.name; F.progress = r.progress; renderHeader(F.progress);
  homeMain();
}
$("homeSend").onclick = guarded(sendName);
$("homeInput").addEventListener("keydown", (e) => { if (e.key === "Enter") guarded(sendName)(); });

// ---------------------------------------------------------------------------
// Before the map: a quick chat about what's on your desk
// ---------------------------------------------------------------------------
const STARTER_KIT = ["arduino-uno", "usb-cable", "breadboard", "jumper-wire", "led", "resistor-220", "resistor-1k",
                     "resistor-10k", "pushbutton", "potentiometer-10k"];
function setParts(ids) { F.selected = new Set(ids); store.set("parts", ids); }
function toMap(openParts, note) {
  go("learn");
  if (openParts) setTimeout(() => openDrawer(note), 350);
}
function partsChat() {
  $("homeQ").hidden = false; $("homeBack").hidden = false;
  $("homeBack").onclick = homeMain;
  if (F.selected.size) {
    $("homeQ").textContent = `Still got the same ${F.selected.size} parts on your desk?`;
    homeCards([
      { icon: "map", label: "Yes, same parts", sub: "Straight to the map", primary: true, go: () => toMap() },
      { icon: "list", label: "Change my parts", sub: "Open the parts list", go: () => toMap(true) },
      { icon: "skip", label: "Just show the map", sub: "Forget my parts for now", go: () => { setParts([]); toMap(); } },
    ]);
    return;
  }
  $("homeQ").textContent = "Before the map — what's on your desk? I'll mark every level you can build right now.";
  homeCards([
    { icon: "box", label: "A starter kit", sub: "Uno, breadboard, wires, LEDs, resistors, a button and a knob", primary: true, go: () => { setParts(STARTER_KIT); toMap(); } },
    { icon: "list", label: "Let me pick my parts", sub: "Tap them on a list", go: () => toMap(true) },
    { icon: "skip", label: "Skip — show me the map", sub: "I'll pick parts later", go: () => toMap() },
  ]);
}
function openDrawer(note) {
  if (note) $("drawerNote").textContent = note;
  renderPicker();
  $("partsVeil").hidden = false; $("partsDrawer").classList.add("open"); $("partsDrawer").setAttribute("aria-hidden", "false");
}
function closeDrawer() {
  $("partsVeil").hidden = true; $("partsDrawer").classList.remove("open"); $("partsDrawer").setAttribute("aria-hidden", "true");
}
$("partsBtn").onclick = () => openDrawer();
$("closeParts").onclick = closeDrawer;
$("partsVeil").onclick = closeDrawer;

// ---------------------------------------------------------------------------
// Learn: parts picker (camera soon) + the lesson path
// ---------------------------------------------------------------------------
function partArt(p) {
  const holder = document.createElement("div"); holder.className = "art";
  const type = p.subtype === "breadboard" ? "wokwi-breadboard-mini" : p.wokwi_type;
  thumbnailById(p.id, type, p.attrs || {}).then((url) => { if (url) holder.innerHTML = `<img src="${url}" alt="">`; });
  return holder;
}
function renderPicker() {
  const grid = $("partGrid"); grid.innerHTML = "";
  const list = F.showAll ? F.catalog : F.catalog.filter((p) => p.popular || F.selected.has(p.id));
  list.forEach((p, i) => {
    const t = document.createElement("div");
    t.className = "ptile" + (F.selected.has(p.id) ? " on" : ""); t.style.animationDelay = `${Math.min(i, 20) * 25}ms`;
    t.title = p.description;
    t.appendChild(partArt(p));
    const nm = document.createElement("div"); nm.className = "nm"; nm.textContent = p.name.replace(/ \(.*\)/, "");
    t.appendChild(nm);
    t.onclick = () => {
      F.selected.has(p.id) ? F.selected.delete(p.id) : F.selected.add(p.id);
      t.classList.toggle("on"); store.set("parts", [...F.selected]); refreshMatches();
    };
    grid.appendChild(t);
  });
  $("morePartsBtn").textContent = F.showAll ? "Show fewer parts" : `Show all ${F.catalog.length} parts`;
}
let matchTimer = null;
function refreshMatches() {
  clearTimeout(matchTimer);
  matchTimer = setTimeout(guarded(async () => {
    const strip = $("matchStrip");
    $("partsCount").textContent = F.selected.size;
    if (!F.selected.size) { strip.innerHTML = ""; F.matches = {}; MAP.updateMatches({}); return; }
    const r = await api("/api/find", { parts: [...F.selected] });
    F.matches = Object.fromEntries(r.lessons.map((l) => [l.id, l]));
    const nobb = (l) => (l.build && l.build.method === "no-breadboard" ? " · no breadboard" : "");
    const label = { ready: "✅ You have everything", substitute: "🔁 Works with a stand-in", missing: "" };
    strip.innerHTML = r.lessons.filter((l) => l.status !== "missing").map((l, i) =>
      `<div class="match" data-id="${esc(l.id)}" style="animation-delay:${i * 60}ms">${icon(l.id)}<b>${esc(l.title)}</b><span class="st">${label[l.status]}${nobb(l)}</span></div>`).join("")
      || `<div class="muted">No lesson fits just these parts yet — tap a few more.</div>`;
    strip.querySelectorAll(".match").forEach((m) => (m.onclick = () => openLessonPop(m.dataset.id)));
    MAP.updateMatches(F.matches);
  }), 250);
}
// the world map: themed worlds, one road, Sparky hops between levels
let MAP_ = null;
const MAP = new Proxy({}, { get: (_, k) => (MAP_ || (MAP_ = makeMap(), window.__worldMap = MAP_))[k] });   // __worldMap: for the browser tests
const makeMap = () => createWorldMap($("worldMap"), {
  lessonIcon: (id) => (F.icons || {})[id],
  onSoon: (t) => toast(`Level ${t.level} · ${t.title} — coming soon. It's one of Arduino's built-in examples; the lesson is on its way.`),
  onOpen: (id) => openLessonPop(id),
  onCreate: () => { go("create"); createIntro(); },
});
function levelOf(id) {
  for (const w of bench.S.worlds || []) { const l = w.levels.find((x) => x.id === id); if (l) return { ...l, world: w }; }
  return null;
}
function renderPath() {
  ensureIcons().catch(() => {}).then(() => { MAP.render(bench.S.worlds || [], F.matches); afterRender(); });
}
function afterRender() {
  if (F.justCompleted) { const id = F.justCompleted; F.justCompleted = null; setTimeout(() => MAP.celebrate(id), 450); }
}
function renderLearn() { renderPicker(); renderPath(); refreshMatches(); }
$("morePartsBtn").onclick = () => { F.showAll = !F.showAll; renderPicker(); };
$("clearParts").onclick = () => { F.selected.clear(); store.set("parts", []); renderPicker(); refreshMatches(); };
$("cameraBtn").onclick = () => ($("cameraPop").hidden = false);
document.querySelectorAll("[data-close]").forEach((b) => (b.onclick = () => (b.closest(".modal").hidden = true)));
document.querySelectorAll(".modal").forEach((m) => m.addEventListener("pointerdown", (e) => { if (e.target === m) m.hidden = true; }));

// How the parts get connected — plain words, no icons
const JOIN_NAME = { clips: "Clip leads", twist: "Twisting", solder: "Solder" };
const WAY_EXPLAIN = {
  breadboard: "Push the parts into the breadboard's holes — every hole in a column is connected — and link them to the Arduino with jumper wires.",
  clips: "No breadboard: the parts sit on the table. Legs that can go straight into the Arduino's sockets do; the rest are joined with alligator-clip wires that grip the bare legs. Nothing permanent.",
  twist: "No breadboard: the parts sit on the table and their legs are wrapped tightly around each other by hand. Needs nothing extra, but twisted legs can work loose.",
  solder: "No breadboard: the legs are joined for good with melted solder. Needs a soldering iron and a few tools — permanent.",
};
const wayKey = (w) => (w.method === "breadboard" ? "breadboard" : w.join);
async function openLessonPop(id) {
  const l = bench.S.lessons.find((x) => x.id === id);
  if (!l) return;
  let level = F.level || "beginner";
  const lv = levelOf(id);
  const before = (l.requires || []).filter((r) => !(bench.S.lessons.find((x) => x.id === r) || {}).completed)
    .map((r) => { const q = levelOf(r); return q ? `${q.level} ${q.title}` : r; });
  const stars = [1, 2, 3].map((k) => (k <= (l.stars || 0) ? "★" : "☆")).join("");
  const m = F.matches[id];
  $("lessonPopCard").innerHTML = `
    ${lv ? `<div class="pop-level">WORLD ${lv.world.number} · LEVEL ${esc(lv.level)} · ${esc(lv.world.name)}</div>` : ""}
    <div class="pop-icon">${icon(l.id, "pop-ico")}</div><h2>${esc(l.title)} ${l.completed ? `<span style="color:#ffc53d">${stars}</span>` : ""}</h2>
    <p class="muted">${esc(l.description)}</p>
    ${l.creator ? `<div class="pop-by">Made by <b>${esc(l.creator)}</b></div>` : ""}
    ${l.source ? `<div class="pop-source">From the guide <a href="${esc(l.source.url)}" target="_blank" rel="noopener">${esc(l.source.title)} ↗</a>${
      (l.substitutions || []).length ? `<br><span class="muted">Changed from the guide: ${l.substitutions.map((x) => `${esc(x.guide)} → ${esc(x.used)}`).join("; ")}</span>` : " — followed exactly."}</div>` : ""}
    ${before.length ? `<div class="pop-tip">Tip: this level builds on <b>${esc(before.join(", "))}</b>. You can still jump in now — it counts as completed either way.</div>` : ""}
    <div class="seg-label" style="margin-top:12px;">Build it</div>
    <div id="popWays"><span class="muted">Working out every way…</span></div>
    <div class="plan-box" id="popPlan"></div>
    <div class="pill-row" id="popLevel" style="display:inline-flex;margin-bottom:14px;">
      <button class="pill" data-level="beginner">Beginner</button><button class="pill" data-level="advanced">Advanced</button></div>
    <p class="muted" style="font-size:11.5px;margin:0;">Three stars: finish it · use no hints · get every step right first time</p>
    <div class="btn-row"><button class="btn btn-primary" id="popStart">${l.completed ? "Play again" : before.length ? "Play anyway" : "Start level"} →</button><button class="btn ghost" data-close>Not now</button></div>`;
  $("lessonPop").hidden = false;
  const pills = () => document.querySelectorAll("#popLevel .pill").forEach((b) => b.setAttribute("aria-pressed", b.dataset.level === level));
  document.querySelectorAll("#popLevel .pill").forEach((b) => (b.onclick = () => { level = b.dataset.level; F.level = level; pills(); }));
  pills();
  $("lessonPopCard").querySelectorAll("[data-close]").forEach((b) => (b.onclick = () => ($("lessonPop").hidden = true)));

  // every way to build it: breadboard / clip leads / twisted legs / solder
  let ways = [], chosen = null;
  const owned = (pid) => F.selected.has(pid);
  const matchWay = (w) => m && m.ways && m.ways.find((x) => x.method === w.method && x.join === w.join);
  const ownsAll = (w) => { const mw = matchWay(w); return !!(mw && !mw.missing.length); };
  function showPlan() {
    const w = ways.find((x) => wayKey(x) === chosen);
    const nobb = ways.filter((x) => x.method !== "breadboard").sort((x, y) => (y.join === "solder") - (x.join === "solder"));   // solder first
    const bb = ways.find((x) => x.method === "breadboard");
    const dot = (x) => `<i class="dot${ownsAll(x) ? " own" : ""}"></i>`;
    $("popWays").innerHTML = `
      <div class="seg" id="segMethod">
        <button data-way="breadboard" aria-pressed="${chosen === "breadboard"}">${dot(bb)}Breadboard</button>
        ${nobb.length ? `<button data-way="${chosen !== "breadboard" ? chosen : (nobb.find((x) => x.join === "solder") ? "solder" : wayKey(nobb[0]))}" aria-pressed="${chosen !== "breadboard"}">${nobb.some(ownsAll) ? '<i class="dot own"></i>' : '<i class="dot"></i>'}No breadboard</button>` : ""}
      </div>
      ${chosen !== "breadboard" && nobb.length > 1 ? `<div class="seg-label">Join the legs with</div><div class="seg" id="segJoin">
        ${nobb.map((x) => `<button data-way="${wayKey(x)}" aria-pressed="${wayKey(x) === chosen}">${dot(x)}${JOIN_NAME[x.join]}</button>`).join("")}</div>` : ""}
      <p class="way-explain">${esc(WAY_EXPLAIN[chosen])}${m ? (ownsAll(w) ? " <b>You have everything for this.</b>" : "") : ""}</p>`;
    document.querySelectorAll("#popWays .seg button").forEach((b) => (b.onclick = () => { chosen = b.dataset.way; showPlan(); }));
    const mw = matchWay(w), subs = mw ? Object.fromEntries(mw.substitutes.map((x) => [x.need, x.use])) : {};
    const nameOf = (pid) => (F.catalog.find((p) => p.id === pid) || { name: pid }).name.replace(/ \(.*\)/, "");
    const item = (p) => {
      const have = owned(p.id) || subs[p.id];
      return `<span class="${have ? "have" : ""}">${have ? "✓ " : ""}${p.count > 1 ? p.count + "× " : ""}${esc(p.name.replace(/ \(.*\)/, ""))}${subs[p.id] ? ` (use your ${esc(nameOf(subs[p.id]))})` : ""}</span>`;
    };
    const ch = w.changes, added = [...ch.added, ...ch.tools_added].map((x) => x.name.replace(/ \(.*\)/, ""));
    const steps = w.steps.flatMap((st) => st.connections.map((c) => `<li>${esc(c.how)}</li>`)).join("");
    $("popPlan").innerHTML = `
      <div class="panel-title">You'll need</div><div class="need">${w.parts.map(item).join("")}</div>
      ${w.tools.length ? `<div class="panel-title" style="margin-top:6px;">Tools</div><div class="need">${w.tools.map((t) => item({ ...t, count: 1 })).join("")}</div>` : ""}
      ${w.method !== "breadboard" ? `<div class="chg">Compared with a breadboard: ${added.length ? "you also need " + esc(added.join(", ")) : "nothing extra to get"}.</div>` : ""}
      ${steps ? `<details><summary>How each connection is made</summary><ol>${steps}</ol></details>` : ""}
      ${w.notes.length ? `<div class="plan-note">${w.notes.map(esc).join("<br>")}</div>` : ""}`;
  }
  const start = $("popStart");
  start.onclick = guarded(async () => {
    start.disabled = true; start.textContent = "Setting up your bench…";
    const build = !chosen || chosen === "breadboard" ? { method: "breadboard" } : { method: "no-breadboard", join: chosen };
    await bench.start(id, level, build);
    $("lessonPop").hidden = true; go("lesson");
  });
  const r = await api("/api/plan", { lesson_id: id }).catch(() => null);
  if (!r) { $("popWays").innerHTML = ""; return; }
  ways = r.ways;
  const best = m && m.build ? (m.build.method === "breadboard" ? "breadboard" : m.build.join) : "breadboard";
  chosen = ways.some((w) => wayKey(w) === best) ? best : "breadboard";
  showPlan();
}

// ---------------------------------------------------------------------------
// Create: chat with the lesson generator
// ---------------------------------------------------------------------------
let createStarted = false;
async function createIntro() {
  if (createStarted) return;
  createStarted = true;
  const chat = $("createChat");
  await say(chat, "Tell me what you want to build ✨ — or paste a link to a tutorial and I'll follow it exactly.", 400);
  await say(chat, "I'll design the circuit, the code and the steps — then check every wire, the physics and every way a learner could build it before you get it.");
  const ai = await api("/api/ai_status").catch(() => ({ backend: null, claude: { mode: "local" } }));
  F.aiBackend = ai.backend; F.flowCheck = ai.flow_check; F.claude = ai.claude;
  const mode = (ai.claude || {}).mode;
  if (mode === "signin") { F.claude.mode = "locked"; lockCreate(true); await signInToCreateCard(chat); }
  else if (mode === "locked") { lockCreate(true); await connectClaudeCard(chat); }
  else if (mode === "own") await ownClaudeNote(chat, ai.claude.hint);
  else if (mode === "owner") await say(chat, "🔑 You're the owner here, so I'm using <b>your Claude login</b>. A new lesson takes a minute or two.", 300);
  else await say(chat, ai.backend === "claude-code" ? "🔑 I'm using <b>your Claude Code login</b> on this computer — no API key needed. A new lesson takes a minute or two."
    : ai.backend === "api" ? "🔑 I'm using the Anthropic API key on this computer. A new lesson takes a minute or two."
    : "⚠️ I can't reach Claude from this computer yet: log in to Claude Code (run <code>claude</code> once in a terminal) or set an Anthropic API key, then restart the bench.", 300);
  const row = $("suggestRow"); row.innerHTML = "";
  [["💡 Ideas from my parts", "ideas"], ["🚦 A traffic light", "A traffic light with a red, a yellow and a green LED"],
   ["🌙 A night light", "An LED that turns on when a potentiometer is turned past halfway"],
   ["⚡ A reaction game", "A reaction game: an LED lights up and you press a button as fast as you can"]].forEach(([label, text], i) => {
    const b = document.createElement("button"); b.className = "suggest"; b.style.animationDelay = `${i * 80}ms`; b.textContent = label;
    b.onclick = guarded(async () => (text === "ideas" ? ideas() : build(text)));
    row.appendChild(b);
  });
  if (F.claude && F.claude.mode === "locked") lockCreate(true);
}
// ---- your own Claude (hosted, accounts on): Create stays locked until you connect it ----
function lockCreate(locked) {
  $("createInput").disabled = locked; $("createSend").disabled = locked;
  $("createInput").placeholder = locked ? "🔒 Connect your Claude first (above)" : "e.g. a traffic light with three LEDs";
  $("suggestRow").querySelectorAll("button").forEach((b) => (b.disabled = locked));
}
async function connectClaudeCard(chat) {
  const card = await say(chat, `<div class="claude-lock"><b>🔒 Creating lessons uses your own Claude</b>
    <p class="muted">Each new lesson is written by Claude, so it runs on <b>your</b> Anthropic account — you pay Anthropic directly for what you use, and you can set a monthly limit there. Playing levels is always free.</p>
    <ol class="muted"><li>Open <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener">console.anthropic.com → API keys ↗</a> (sign up, add a little credit).</li>
    <li>Create a key and paste it here. It's checked with Anthropic, then stored encrypted — only its last 4 characters are ever shown.</li></ol>
    <div class="chat-input claude-key-row"><input class="text-input" type="password" autocomplete="off" placeholder="sk-ant-…" data-key>
    <button class="btn btn-primary" data-connect>Connect</button></div><div class="claude-msg" data-msg></div></div>`, 200);
  const input = card.querySelector("[data-key]"), msg = card.querySelector("[data-msg]"), btn = card.querySelector("[data-connect]");
  const connect = async () => {
    const key = input.value.trim(); if (!key) return;
    btn.disabled = true; msg.textContent = "Checking with Anthropic…";
    try {
      const r = await api("/api/claude_key", { key });
      input.value = ""; card.querySelector(".claude-lock").innerHTML = `<b>✅ Your Claude is connected</b> <span class="muted">(key …${esc(r.hint)})</span>`;
      F.claude = { ready: true, mode: "own", hint: r.hint }; lockCreate(false);
      await say(chat, "Unlocked! Tell me what you want to build ✨", 200);
    } catch (e) { msg.textContent = "⚠️ " + e.message; btn.disabled = false; }
  };
  btn.onclick = connect;
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") connect(); });
}
async function signInToCreateCard(chat) {
  const card = await say(chat, `<div class="claude-lock"><b>🔒 Creating lessons needs a Google sign-in</b>
    <p class="muted">You're playing as a guest. Sign in to create lessons (with your own Claude) — your stars and XP from this browser come with you.</p>
    <button class="btn btn-primary" data-signin>Sign in with Google</button></div>`, 200);
  card.querySelector("[data-signin]").onclick = () => F.auth.signIn();
}
async function ownClaudeNote(chat, hint) {
  const b = await say(chat, `🔑 Using <b>your own Claude</b> (key …${esc(hint)}). A new lesson takes a minute or two. <button class="linkish" data-disconnect>Disconnect</button>`, 300);
  b.querySelector("[data-disconnect]").onclick = guarded(async () => {
    if (!confirm("Disconnect your Claude? Its key is deleted from CircuitQuest (it stays valid on Anthropic until you delete it there).")) return;
    await api("/api/claude_key", { remove: true });
    F.claude = { ready: false, mode: "locked" }; lockCreate(true);
    await connectClaudeCard(chat);
  });
}

async function ideas() {
  const chat = $("createChat");
  if (!F.selected.size) { await say(chat, "Pick the parts you have in <b>Learn</b> first, then I'll suggest projects that fit them.", 300); return; }
  me(chat, "💡 Ideas from my parts");
  try {
    const r = await api("/api/ideas", { parts: [...F.selected] });
    if (!r.ideas.length) return say(chat, "Nothing fits exactly those parts yet — try adding a couple more.");
    await say(chat, "Here are some projects your parts can do:");
    choices(chat, r.ideas.map((i) => ({ emoji: "🔧", label: i.title, sub: i.concept, go: () => build(`${i.title}: ${i.description}`, true) })));
  } catch (e) { await say(chat, aiUnavailable(e)); }
}
function aiUnavailable(e) {
  return /AI unavailable|anthropic|API key|ModuleNotFound/i.test(e.message)
    ? `I can't reach Claude right now — ${esc(e.message.replace(/^AI unavailable:\s*/, ""))} Everything else works without it!`
    : `Something went wrong: ${esc(e.message)}`;
}
// A link to a tutorial: read it, show exactly what was found and what (if
// anything) has to change, and build only once the learner says so.
// Before spending Claude: a lesson that might be the same (same tutorial link,
// or the same words). The learner decides — open it, or create anyway.
async function existingFirst(chat, request, url) {
  const sim = await api("/api/similar", { request, url }).catch(() => ({ matches: [] }));
  if (!sim.matches.length) return true;
  const where = (id) => { const lv = levelOf(id); return lv ? `Level ${lv.level} · ${lv.world.name}` : "AI Lab"; };
  const card = await say(chat, `This might be the same as ${sim.matches.length > 1 ? "one of these" : "a level we already have"} — want to check it out?
    <div class="similar-list">${sim.matches.map((m) => `<div class="similar">${icon(m.id, "sim-ico") ? `<div class="similar-icon">${icon(m.id, "sim-ico")}</div>` : ""}<div class="similar-text"><b>${esc(m.title)}</b>
      <span class="muted">${esc(where(m.id))}${m.creator ? ` · made by ${esc(m.creator)}` : ""} · ${esc(m.why)}</span></div>
      <button class="btn btn-primary" data-open="${esc(m.id)}">Open level</button></div>`).join("")}</div>
    <div class="btn-row" style="margin-top:8px;"><button class="btn ghost" data-anyway>No, it's different — create it anyway</button></div>`, 200);
  return new Promise((resolve) => {
    card.querySelectorAll("[data-open]").forEach((b) => (b.onclick = () => { card.querySelectorAll("button").forEach((x) => (x.disabled = true)); resolve(false); openLevel(b.dataset.open); }));
    card.querySelector("[data-anyway]").onclick = () => { card.querySelectorAll("button").forEach((x) => (x.disabled = true)); resolve(true); };
  });
}
// go to the map, let Sparky drive to the level, then open its card
async function openLevel(id) {
  go("learn");
  await wait(700);
  try { await MAP.walkTo(id); } catch (e) { /* not on the road (yet): just open it */ }
  openLessonPop(id);
}

async function guideFlow(url, text) {
  const chat = $("createChat");
  me(chat, text); $("createInput").value = "";
  if (!(await existingFirst(chat, text, url))) return;
  const b = await say(chat, `<b>Reading the guide…</b><div class="gen-steps"><div class="gen-step now"><span class="ic"><span class="spin">◌</span></span>Opening the page</div><div class="gen-step"><span class="ic">○</span>Finding every part, value and connection</div></div>`, 200);
  const els = [...b.querySelectorAll(".gen-step")];
  const tick = setTimeout(() => { els[0].className = "gen-step done"; els[0].querySelector(".ic").textContent = "✓"; els[1].className = "gen-step now"; els[1].querySelector(".ic").innerHTML = '<span class="spin">◌</span>'; }, 2500);
  let plan;
  try { plan = await api("/api/guide", { url }); }
  catch (e) { clearTimeout(tick); await say(chat, aiUnavailable(e)); return; }
  clearTimeout(tick); els.forEach((x) => { x.className = "gen-step done"; x.querySelector(".ic").textContent = "✓"; });
  const mark = { exact: "✓", substitute: "↔", skipped: "–", unsupported: "✗" };
  // parts, then (tidily) the tools; row classes are gp-* so they never clash with other styles
  const partRows = plan.parts.filter((r) => r.status !== "tool").map((r) => `<li class="gp gp-${r.status}"><span class="gp-mark">${mark[r.status]}</span><span class="gp-text"><b>${esc(r.guide)}</b>${
    r.status === "substitute" ? ` → <b>${esc(r.card_name || r.card)}</b>` : ""}${r.note ? `<small>${esc(r.note)}</small>` : ""}</span></li>`).join("");
  const tools = plan.parts.filter((r) => r.status === "tool").map((r) => esc(r.guide.replace(/^1× /, "")));
  const rows = partRows + (tools.length ? `<li class="gp gp-tools"><span class="gp-mark">·</span><span class="gp-text"><b>Tools:</b> ${tools.join(", ")}<small>Listed for the real build — not simulated.</small></span></li>` : "");
  const card = await say(chat, `<div class="result-card guide-plan"><b>${esc(plan.title)}</b><br><span class="muted">${esc(plan.behaviour)}</span>
    <ul class="gp-list">${rows}</ul>
    ${plan.ok ? `<span class="muted">✓ = exactly as in the guide · ↔ = we don't have it, so this stands in</span>
      <div class="btn-row" style="margin-top:10px;"><button class="btn btn-primary" data-go-build>Build this lesson →</button><button class="btn ghost" data-no>Not now</button></div>`
      : `<span class="muted">This guide needs parts CircuitQuest can't simulate yet, so I can't build it faithfully.</span>`}</div>`, 300);
  const go = card.querySelector("[data-go-build]");
  if (!go) return;
  card.querySelector("[data-no]").onclick = () => card.querySelector(".btn-row").remove();
  go.onclick = guarded(async () => { card.querySelector(".btn-row").remove(); await build(`the guide "${plan.title}"`, true, { ...plan, url }); });
}

async function build(request, alreadySaid, guide) {
  const chat = $("createChat");
  const link = !guide && (request.match(/https?:\/\/\S+/) || [])[0];
  if (link) return guideFlow(link, request);
  if (!alreadySaid) me(chat, request);
  $("createInput").value = "";
  if (!guide && !(await existingFirst(chat, request))) return;
  const steps = ["Writing the circuit, code and steps", "Checking every wire and pin", "Solving the physics",
    F.flowCheck === "smart" ? "Trying the main ways a learner could build it" : "Trying every way a learner could build it"];
  const b = await say(chat, `<b>On it!</b><div class="gen-steps">${steps.map((s) => `<div class="gen-step"><span class="ic">○</span>${s}</div>`).join("")}</div>`, 300);
  const els = [...b.querySelectorAll(".gen-step")];
  let i = 0;
  const tick = setInterval(() => {
    if (i > 0) { els[i - 1].className = "gen-step done"; els[i - 1].querySelector(".ic").textContent = "✓"; }
    if (i < els.length) { els[i].className = "gen-step now"; els[i].querySelector(".ic").innerHTML = '<span class="spin">◌</span>'; }
    i = Math.min(i + 1, els.length - 1);
  }, 1800);
  try {
    const r = await api("/api/generate", { request, guide, parts: $("onlyMine").checked ? [...F.selected] : [] });
    clearInterval(tick);
    els.forEach((e) => { e.className = r.ok ? "gen-step done" : "gen-step"; e.querySelector(".ic").textContent = r.ok ? "✓" : "○"; });
    if (r.ok) {
      await bench.refreshLessons();
      const l = bench.S.lessons.find((x) => x.id === r.lesson_id);
      sparkyHop();
      const card = await say(chat, `<div class="result-card"><b>✨ ${esc(l ? l.title : r.lesson_id)}</b><br>${esc(l ? l.description : "")}
        <br><span class="muted">Passed every check after ${r.attempts.length} draft(s).</span><div class="btn-row" style="margin-top:8px;"><button class="btn btn-primary">Open it →</button></div></div>`);
      card.querySelector("button").onclick = () => openLessonPop(r.lesson_id);
    } else {
      await say(chat, `I couldn't make that one pass every check in ${r.attempts.length} tries. The last problems were:<br>${r.errors.slice(0, 3).map((e) => "• " + esc(e)).join("<br>")}<br>Want to try describing it differently?`);
    }
  } catch (e) {
    clearInterval(tick);
    await say(chat, aiUnavailable(e));
  }
}
$("createSend").onclick = guarded(async () => { const t = $("createInput").value.trim(); if (t) await build(t); });
$("createInput").addEventListener("keydown", (e) => { if (e.key === "Enter") $("createSend").click(); });

// ---------------------------------------------------------------------------
// Celebrations
// ---------------------------------------------------------------------------
function confetti() {
  const c = $("confetti"), ctx = c.getContext("2d");
  c.width = innerWidth; c.height = innerHeight;
  const colours = ["#e0a458", "#5cb86a", "#3b6fd1", "#e15c52", "#f2d45c"];
  const bits = Array.from({ length: 160 }, () => ({
    x: innerWidth / 2 + (Math.random() - 0.5) * 200, y: innerHeight * 0.35, vx: (Math.random() - 0.5) * 16, vy: -Math.random() * 16 - 4,
    r: Math.random() * 6 + 3, c: colours[(Math.random() * colours.length) | 0], a: Math.random() * 6, va: (Math.random() - 0.5) * 0.3,
  }));
  const t0 = performance.now();
  const frame = (t) => {
    ctx.clearRect(0, 0, c.width, c.height);
    bits.forEach((b) => { b.vy += 0.45; b.x += b.vx; b.y += b.vy; b.a += b.va;
      ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.a); ctx.fillStyle = b.c; ctx.fillRect(-b.r / 2, -b.r / 2, b.r, b.r * 0.6); ctx.restore(); });
    if (t - t0 < 2600) requestAnimationFrame(frame); else ctx.clearRect(0, 0, c.width, c.height);
  };
  requestAnimationFrame(frame);
}
function xpFloat(n) {
  const chip = $("xpChip").getBoundingClientRect(), f = $("xpFloat");
  f.textContent = `+${n} XP`; f.style.left = `${chip.left}px`; f.style.top = `${chip.bottom + 6}px`;
  f.classList.remove("go"); void f.offsetWidth; f.classList.add("go");
  $("xpChip").classList.remove("bump"); void $("xpChip").offsetWidth; $("xpChip").classList.add("bump");
}
bench.onComplete = async (award) => {
  confetti();
  F.justCompleted = bench.S.lessonId;      // the map plays the win when you're back
  if (!award) return;
  const before = F.progress ? F.progress.xp : 0;
  F.progress = award.progress;
  if (award.xp_gained) xpFloat(award.xp_gained);
  renderHeader(F.progress, before);
  for (const b of award.new_badges) { await wait(700); toast(`🏅 ${award.progress.badge_names[b] || b}`); }
  if (award.level_up) {
    await wait(900);
    $("levelPopCard").innerHTML = `<div class="big">⭐</div><h2>Level ${award.progress.level}!</h2>
      <p class="muted">You've got ${award.progress.xp} XP. Head back to the map — Sparky's ready for the next level.</p>
      <button class="btn btn-primary" data-close>Keep going →</button>`;
    $("levelPop").hidden = false;
    $("levelPopCard").querySelector("[data-close]").onclick = () => ($("levelPop").hidden = true);
  }
};

// ---------------------------------------------------------------------------
// Accounts (only when the server has them on): sign in with Google first
const GOOGLE_G = `<svg class="ic" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>`;
// Accounts on and nobody signed in: sign in with Google, or just type a name (a guest)
function signInScreen() {
  sparkyHop();
  $("homeTitle").textContent = "Hi! I'm Sparky";
  $("homeSub").textContent = "Your circuit buddy — I'll check every wire with you. How do you want to play?";
  $("homeQ").hidden = true; $("homeBack").hidden = true; $("homeInputRow").hidden = true;
  const row = $("homeActions"); row.innerHTML = "";
  const google = document.createElement("button");
  google.className = "choice home-card primary";
  google.innerHTML = `${GOOGLE_G}<b>Sign in with Google</b><small>Your stars and XP are kept in your account, on any device — and you can create your own lessons.</small>`;
  google.onclick = () => F.auth.signIn();
  const guest = document.createElement("button");
  guest.className = "choice home-card";
  guest.innerHTML = `<svg class="ic" viewBox="0 0 24 24"><path d="M12 12a4 4 0 100-8 4 4 0 000 8zM4 20c0-3.3 3.6-6 8-6s8 2.7 8 6"/></svg><b>Just type my name</b><small>Play straight away. Progress is saved in this browser only, and creating lessons needs a sign-in.</small>`;
  guest.onclick = () => {
    $("homeSub").textContent = "Great — what's your name? (You can sign in with Google any time to keep your progress everywhere.)";
    row.innerHTML = ""; $("homeInputRow").hidden = false; $("homeInput").focus();
    $("homeBack").hidden = false; $("homeBack").onclick = signInScreen;
    F.becomingGuest = true;
  };
  row.append(google, guest);
}
function guestChip() {
  const a = $("avatar");
  a.title = "Playing as a guest — click to sign in with Google"; a.style.cursor = "pointer";
  a.onclick = () => { if (confirm("Sign in with Google? Your stars and XP from this browser come with you, and you'll be able to create lessons.")) F.auth.signIn(); };
}
function accountChip(auth) {
  const a = $("avatar");
  if (auth.user.avatar) a.innerHTML = `<img src="${esc(auth.user.avatar)}" alt="" referrerpolicy="no-referrer">`;
  a.title = `Signed in as ${auth.user.name} — click to sign out`;
  a.style.cursor = "pointer";
  a.onclick = () => { if (confirm(`Signed in as ${auth.user.name} (${auth.user.email}).\n\nSign out?`)) auth.signOut(); };
}

// ---------------------------------------------------------------------------
async function init() {
  bench.init();
  F.auth = await setupAuth().catch(() => ({ enabled: false, user: null }));
  const gid = store.get("guestId", null);
  if (F.auth.enabled && !F.auth.user) {
    if (!gid) return signInScreen();
    window.__cqGuest = gid; F.guest = true; guestChip();         // a returning guest
  }
  if (F.auth.user) {
    accountChip(F.auth);
    if (gid) {                                                   // a guest who just signed in: bring their progress along
      await api("/api/profile", { adopt_guest: gid }).catch(() => {});
      store.set("guestId", null);
    }
  }
  return startApp();
}
async function startApp() {
  if (window.__cqGuest) { F.guest = true; guestChip(); }
  try {
    const [profile, catalog] = await Promise.all([api("/api/profile"), api("/api/parts_catalog"), bench.refreshLessons()]);
    F.name = profile.name; F.progress = profile.progress; F.level = profile.difficulty; F.catalog = catalog.parts;
    if (F.auth && F.auth.enabled) F.claude = (await api("/api/ai_status").catch(() => ({}))).claude;
    renderHeader(F.progress);
    await homeChat();
  } catch (e) {
    $("homeTitle").textContent = "Can't reach the engine";
    $("homeSub").innerHTML = "Start it with <code>python3 bench_server.py</code>, then reload this page.";
  }
}
init();
