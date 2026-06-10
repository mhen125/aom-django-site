const STATIC_URL = window.AOM_STATIC_URL || "/static/";

const ICONS = {
  food: staticPath("assets/images/res_Food.png"),
  wood: staticPath("assets/images/res_Wood.png"),
  gold: staticPath("assets/images/gold.png"),
  hunt: optimizedImagePath("hunt.webp"),
  favor: staticPath("assets/images/favor.png"),
  pop: staticPath("assets/images/res_pop.png"),
  population: staticPath("assets/images/res_pop.png"),

  villager: staticPath("assets/images/unit_type_villager.png"),
  villagers: staticPath("assets/images/unit_type_villager.png"),

  gatherer: optimizedImagePath("villager_norse_icon.webp"),
  gatherers: optimizedImagePath("villager_norse_icon.webp"),

  dwarf: optimizedImagePath("villager_dwarf_icon.webp"),
  dwarves: optimizedImagePath("villager_dwarf_icon.webp"),

  ox: optimizedImagePath("ox_cart_icon.webp"),
  cart: optimizedImagePath("ox_cart_icon.webp"),
  ox_cart: optimizedImagePath("eco_builds/ox_cart_icon.webp"),
  oxcart: optimizedImagePath("eco_builds/ox_cart_icon.webp"),

  miko: optimizedImagePath("miko_icon.webp"),
  temple: optimizedImagePath("temple_icon.webp"),
  shrine: optimizedImagePath("shrine_icon.webp"),
  storehouse: optimizedImagePath("eco_builds/storehouse_icon.webp"),
  silo: optimizedImagePath("eco_builds/silo_icon.webp"),
  granary: optimizedImagePath("eco_builds/granary_icon.webp"),
  lumber_camp: optimizedImagePath("eco_builds/lumber_camp_icon.webp"),
  watermill: optimizedImagePath("eco_builds/watermill_icon.webp"),
  economic_guild: optimizedImagePath("eco_builds/economic_guild_icon.webp"),
  calpulli: optimizedImagePath("eco_builds/calpulli_icon.webp"),
  calpulli_craft_workshop: optimizedImagePath("eco_builds/calpulli_craft_workshop_icon.webp"),
  calpulli_livestock_pen: optimizedImagePath("eco_builds/calpulli_livestock_pen_icon.webp"),
  calpulli_lumber_outpost: optimizedImagePath("eco_builds/calpulli_lumber_outpost_icon.webp"),

  kuafu: optimizedImagePath("kuafu_icon.webp"),
  kuafu_hero: optimizedImagePath("kuafu_hero_icon.webp"),

  pickaxe: optimizedImagePath("pickaxe_icon.webp"),
  pick_axe: optimizedImagePath("pickaxe_icon.webp"),
  handaxe: optimizedImagePath("hand_axe_icon.webp"),
  hand_axe: optimizedImagePath("hand_axe_icon.webp"),

  priest: optimizedImagePath("priest_icon.webp"),
  pharaoh: optimizedImagePath("pharaoh_icon.webp"),

  house: optimizedImagePath("house_icon.webp"),
  houses: optimizedImagePath("house_icon.webp"),
  tree: optimizedImagePath("tree_icon.webp"),

  berserk: optimizedImagePath("berserk_icon.webp"),
  hersir: optimizedImagePath("hersir_icon.webp"),

  // Scout units
  kataskopos: optimizedImagePath("kataskopos_icon.webp"),
  kitsune: optimizedImagePath("kitsune_icon.webp"),
  quimchin_spy: optimizedImagePath("quimchin_spy_icon.webp"),
  oracle: optimizedImagePath("oracle_icon.webp"),
  oracle_hero: optimizedImagePath("oracle_hero_icon.webp"),
  pioneer: optimizedImagePath("pioneer_icon.webp"),

  ajax: optimizedImagePath("heroes/ajax_icon.webp"),
  jason: optimizedImagePath("heroes/jason_icon.webp"),
  orpheus: optimizedImagePath("heroes/orpheus_icon.webp"),
  theseus: optimizedImagePath("heroes/theseus_icon.webp"),
};

const SHORTCODE_ALIASES = {
  f: "food",
  w: "wood",
  g: "gold",
  fa: "favor",

  food: "food",
  wood: "wood",
  gold: "gold",
  favor: "favor",
  hunt: "hunt",

  pop: "pop",
  population: "population",

  house: "house",
  houses: "house",
  tree: "tree",
  trees: "tree",

  villager: "villager",
  villagers: "villager",

  gatherer: "gatherer",
  gatherers: "gatherer",

  dwarf: "dwarf",
  dwarves: "dwarf",

  ox: "ox",
  cart: "cart",
  ox_cart: "ox_cart",
  oxcart: "ox_cart",

  miko: "miko",
  temple: "temple",
  shrine: "shrine",
  storehouse: "storehouse",
  silo: "silo",
  granary: "granary",
  lumber_camp: "lumber_camp",
  lumbercamp: "lumber_camp",
  watermill: "watermill",
  water_mill: "watermill",
  economic_guild: "economic_guild",
  guild: "economic_guild",
  calpulli: "calpulli",
  calpulli_craft_workshop: "calpulli_craft_workshop",
  craft_workshop: "calpulli_craft_workshop",
  workshop: "calpulli_craft_workshop",
  calpulli_livestock_pen: "calpulli_livestock_pen",
  livestock_pen: "calpulli_livestock_pen",
  calpulli_lumber_outpost: "calpulli_lumber_outpost",
  lumber_outpost: "calpulli_lumber_outpost",


  kuafu: "kuafu",
  kuafu_hero: "kuafu_hero",
  chieftain: "kuafu_hero",

  pickaxe: "pickaxe",
  pick_axe: "pickaxe",
  handaxe: "hand_axe",
  hand_axe: "hand_axe",

  priest: "priest",
  pharaoh: "pharaoh",

  berserk: "berserk",
  hersir: "hersir",

  // Scout units
  kataskopos: "kataskopos",
  kitsune: "kitsune",
  quimchin_spy: "quimchin_spy",
  oracle: "oracle",
  oracle_hero: "oracle_hero",
  pioneer: "pioneer",

  ajax: "ajax",
  jason: "jason",
  orpheus: "orpheus",
  theseus: "theseus",

};

function staticPath(path) {
  return `${STATIC_URL}${String(path).replace(/^\/+/, "")}`;
}

function optimizedImagePath(path) {
  return staticPath(`assets/optimized/images/${String(path).replace(/^\/+/, "")}`);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatArrowText(value) {
  return String(value ?? "")
    .replace(/\s+-\s+/g, " → ")
    .replace(/^\s*-\s*$/g, "→")
    .replace(/^\s*-\s+/g, "→ ")
    .replace(/\s+-\s*$/g, " →");
}

function getShortcodeIconName(rawName) {
  const key = String(rawName || "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");

  return SHORTCODE_ALIASES[key] || key;
}

function makeShortcodeIcon(rawName) {
  const iconName = getShortcodeIconName(rawName);
  const iconPath = ICONS[iconName];

  if (!iconPath) {
    return `[${escapeHtml(rawName)}]`;
  }

  return `
    <img
      class="shortcode-icon"
      src="${iconPath}"
      alt="${escapeHtml(iconName)}"
      title="${escapeHtml(iconName)}"
      loading="lazy"
    >
  `;
}

function renderShortcodes(value) {
  const text = String(value ?? "");

  if (!text) {
    return "";
  }

  const parts = text.split(/(\[[a-zA-Z0-9_\-\s]+\])/g);

  return parts.map((part) => {
    const match = part.match(/^\[([a-zA-Z0-9_\-\s]+)\]$/);

    if (match) {
      return makeShortcodeIcon(match[1]);
    }

    return escapeHtml(part);
  }).join("");
}

function renderFormattedShortcodes(value) {
  return renderShortcodes(formatArrowText(value));
}

function enhanceShortcodeElements() {
  document.querySelectorAll("[data-shortcodes]").forEach((element) => {
    const rawText = element.textContent || "";
    element.innerHTML = renderFormattedShortcodes(rawText);
  });
}

function bindBuildPicker() {
  const buildPicker = document.getElementById("buildPickerSelect");

  if (!buildPicker) {
    return;
  }

  buildPicker.addEventListener("change", () => {
    const nextUrl = buildPicker.value;

    if (nextUrl) {
      window.location.href = nextUrl;
    }
  });
}

function initBuildDetailPage() {
  enhanceShortcodeElements();
  bindBuildPicker();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initBuildDetailPage);
} else {
  initBuildDetailPage();
}
