const STATIC_URL = window.AOM_STATIC_URL || "/static/";

const ICONS = {
  food: staticPath("assets/images/res_Food.png"),
  wood: staticPath("assets/images/res_Wood.png"),
  gold: staticPath("assets/images/gold.png"),
  favor: staticPath("assets/images/favor.png"),
  pop: staticPath("assets/images/res_pop.png"),
  population: staticPath("assets/images/res_pop.png"),

  villager: staticPath("assets/images/unit_type_villager.png"),
  villagers: staticPath("assets/images/unit_type_villager.png"),

  gatherer: staticPath("assets/images/villager_norse_icon.png"),
  gatherers: staticPath("assets/images/villager_norse_icon.png"),

  dwarf: staticPath("assets/images/villager_dwarf_icon.png"),
  dwarves: staticPath("assets/images/villager_dwarf_icon.png"),

  ox: staticPath("assets/images/ox_cart_icon.png"),
  cart: staticPath("assets/images/ox_cart_icon.png"),
  ox_cart: staticPath("assets/images/ox_cart_icon.png"),
  oxcart: staticPath("assets/images/ox_cart_icon.png"),

  miko: staticPath("assets/images/miko_icon.png"),
  temple: staticPath("assets/images/temple_icon.png"),
  shrine: staticPath("assets/images/shrine_icon.png"),
  storehouse: staticPath("assets/images/storehouse_icon.png"),

  kuafu: staticPath("assets/images/kuafu_icon.png"),
  kuafu_hero: staticPath("assets/images/kuafu_hero_icon.png"),

  pickaxe: staticPath("assets/images/pickaxe_icon.png"),
  pick_axe: staticPath("assets/images/pickaxe_icon.png"),
  handaxe: staticPath("assets/images/hand_axe_icon.png"),
  hand_axe: staticPath("assets/images/hand_axe_icon.png"),

  priest: staticPath("assets/images/priest_icon.png"),
  pharaoh: staticPath("assets/images/pharaoh_icon.png"),

  house: staticPath("assets/images/house_icon.png"),
  houses: staticPath("assets/images/house_icon.png")
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

  pop: "pop",
  population: "population",

  house: "house",
  houses: "house",

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

  kuafu: "kuafu",
  kuafu_hero: "kuafu_hero",

  pickaxe: "pickaxe",
  pick_axe: "pickaxe",
  handaxe: "hand_axe",
  hand_axe: "hand_axe",

  priest: "priest",
  pharaoh: "pharaoh"
};

function staticPath(path) {
  return `${STATIC_URL}${String(path).replace(/^\/+/, "")}`;
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
