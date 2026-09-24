// Detailed 3D models for the Parts & Tools section — one builder per library
// id. buildDetailed(id) -> THREE.Group | null (null: use the regular model).
import { BASIC } from "./basic.js";
import { BOARDS } from "./boards.js";
import { MODULES } from "./modules.js";
import { DISPLAYS } from "./displays.js";
import { WIRING } from "./wiring.js";
import { TOOLS } from "./tools.js";

const ALL = { ...BASIC, ...BOARDS, ...MODULES, ...DISPLAYS, ...WIRING, ...TOOLS };

export function hasDetailed(id) { return !!ALL[id]; }
export function buildDetailed(id) {
  const make = ALL[id];
  if (!make) return null;
  const g = make();
  g.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return g;
}
export const DETAILED_IDS = Object.keys(ALL);
