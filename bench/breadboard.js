// <cq-breadboard size="half|mini|full"> — the one part Wokwi doesn't publish
// in @wokwi/elements, drawn in its style so real Wokwi parts sit on it.
//
// Geometry is Wokwi's: 0.1" pitch = 9.6 px (the same unit every Wokwi
// element's pinInfo uses), so a part's legs land exactly on holes.
// Hole names match Wokwi diagrams: "<column><t|b>.<row>" (e.g. "12t.c"),
// rails "tp.N" / "tn.N" / "bp.N" / "bn.N". Like a Wokwi element it exposes
// `pinInfo` ([{name, x, y}]) and emits "hole-enter"/"hole-leave" events;
// hovering a hole highlights every hole it's connected to.

export const PITCH = 9.6;
const SIZES = { mini: { cols: 17, rails: false }, half: { cols: 30, rails: true }, full: { cols: 63, rails: true } };
const ROWS_TOP = ["a", "b", "c", "d", "e"];
const ROWS_BOTTOM = ["f", "g", "h", "i", "j"];

export class CqBreadboard extends HTMLElement {
  static get observedAttributes() { return ["size"]; }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  connectedCallback() { this.render(); }
  attributeChangedCallback() { if (this.isConnected) this.render(); }

  get size() { return SIZES[this.getAttribute("size")] ? this.getAttribute("size") : "half"; }

  // --- geometry -------------------------------------------------------
  layout() {
    const { cols, rails } = SIZES[this.size];
    const margin = PITCH * 1.5;
    const railBlock = rails ? PITCH * 3 : 0;         // two rail rows + spacing
    const top = margin + railBlock;
    const rowY = {};
    ROWS_TOP.forEach((r, i) => { rowY[r] = top + i * PITCH; });
    ROWS_BOTTOM.forEach((r, i) => { rowY[r] = top + (i + 7) * PITCH; });   // centre gap: e→f is 3 pitches
    const colX = (c) => margin + PITCH + (c - 1) * PITCH;
    const width = colX(cols) + margin + PITCH;
    const height = rowY.j + margin + railBlock;
    const railY = rails ? { tp: margin, tn: margin + PITCH, bn: rowY.j + PITCH * 2, bp: rowY.j + PITCH * 3 } : {};
    const railCount = rails ? Math.floor((cols - 1) * 5 / 6) : 0;
    const railX = (n) => colX(1 + (n - 1) + Math.floor((n - 1) / 5));   // groups of five, a gap every sixth
    return { cols, rails, width, height, rowY, colX, railY, railCount, railX };
  }

  get pinInfo() {
    const g = this.layout();
    const pins = [];
    for (let c = 1; c <= g.cols; c++) {
      ROWS_TOP.forEach((r) => pins.push({ name: `${c}t.${r}`, x: g.colX(c), y: g.rowY[r], strip: `${c}t` }));
      ROWS_BOTTOM.forEach((r) => pins.push({ name: `${c}b.${r}`, x: g.colX(c), y: g.rowY[r], strip: `${c}b` }));
    }
    for (const rail of Object.keys(g.railY)) {
      for (let n = 1; n <= g.railCount; n++) pins.push({ name: `${rail}.${n}`, x: g.railX(n), y: g.railY[rail], strip: rail });
    }
    return pins;
  }

  // the strip ("12t", "tp", ...) a hole belongs to — all its holes are one connection
  static stripOf(hole) { return hole.split(".")[0]; }

  highlight(strip) {
    this.shadowRoot.querySelectorAll(".hole").forEach((h) => h.classList.toggle("lit", strip && h.dataset.strip === strip));
  }

  render() {
    const g = this.layout();
    const holes = this.pinInfo.map((p) =>
      `<rect class="hole" data-hole="${p.name}" data-strip="${p.strip}" x="${p.x - 2.6}" y="${p.y - 2.6}" width="5.2" height="5.2" rx="1"/>`
    ).join("");
    const labels = [];
    for (let c = 1; c <= g.cols; c++) {
      if (c === 1 || c % 5 === 0) {
        labels.push(`<text x="${g.colX(c)}" y="${g.rowY.a - PITCH * 0.9}">${c}</text>`);
        labels.push(`<text x="${g.colX(c)}" y="${g.rowY.j + PITCH * 1.3}">${c}</text>`);
      }
    }
    [...ROWS_TOP, ...ROWS_BOTTOM].forEach((r) => {
      labels.push(`<text x="${g.colX(1) - PITCH}" y="${g.rowY[r] + 2.2}">${r}</text>`);
    });
    const railLines = Object.entries(g.railY).map(([rail, y]) => {
      const colour = rail.endsWith("p") ? "#d6453d" : "#3b6fd1";
      const off = rail === "tp" || rail === "bn" ? -PITCH * 0.55 : PITCH * 0.55;
      return `<line x1="${g.colX(1)}" x2="${g.railX(g.railCount)}" y1="${y + off}" y2="${y + off}" stroke="${colour}" stroke-width="0.8"/>`;
    }).join("");
    this.style.display = "inline-block";
    this.style.width = `${g.width}px`;
    this.style.height = `${g.height}px`;
    this.shadowRoot.innerHTML = `
      <style>
        svg { display: block; overflow: visible; }
        .body { fill: #f3f1ea; stroke: #d9d4c4; stroke-width: 1; }
        .gap { fill: #e4e0d3; }
        .hole { fill: #3d3a34; cursor: crosshair; transition: fill .1s; }
        .hole:hover, .hole.lit { fill: #e0a458; }
        text { font: 5px ui-monospace, monospace; fill: #8d8672; text-anchor: middle; pointer-events: none; }
      </style>
      <svg width="${g.width}" height="${g.height}" viewBox="0 0 ${g.width} ${g.height}">
        <rect class="body" x="0.5" y="0.5" width="${g.width - 1}" height="${g.height - 1}" rx="5"/>
        <rect class="gap" x="${PITCH}" y="${g.rowY.e + PITCH}" width="${g.width - 2 * PITCH}" height="${PITCH}" rx="1.5"/>
        ${railLines}${labels.join("")}${holes}
      </svg>`;
    this.shadowRoot.querySelectorAll(".hole").forEach((h) => {
      h.addEventListener("mouseenter", () => {
        this.highlight(h.dataset.strip);
        this.dispatchEvent(new CustomEvent("hole-enter", { detail: { hole: h.dataset.hole, strip: h.dataset.strip }, bubbles: true, composed: true }));
      });
      h.addEventListener("mouseleave", () => {
        this.highlight(null);
        this.dispatchEvent(new CustomEvent("hole-leave", { detail: { hole: h.dataset.hole }, bubbles: true, composed: true }));
      });
    });
  }
}

if (!customElements.get("cq-breadboard")) customElements.define("cq-breadboard", CqBreadboard);
