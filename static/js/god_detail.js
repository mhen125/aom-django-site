const { pantheons, buildOrders } = window.AOM_DATA;

const STORAGE_BUILDS_KEY = "aomBuildOrder.builds";

const buildPage = document.getElementById("buildPage");
const pantheonLabel = document.getElementById("pantheonLabel");
const godName = document.getElementById("godName");
const godSummary = document.getElementById("godSummary");
const godHeroArt = document.getElementById("godHeroArt");
let godDetailsPanel = document.getElementById("godDetailsPanel");
const buildGrid = document.getElementById("buildGrid");
const buildSectionHeading = document.getElementById("buildSectionHeading");
const createBuildOrderLink = document.getElementById("createBuildOrderLink");

const STATIC_URL = window.AOM_STATIC_URL || "/static/";
const GOD_DETAIL_BASE_URL = window.AOM_GOD_DETAIL_BASE_URL || "/gods/";
const BUILD_DETAIL_BASE_URL = window.AOM_BUILD_DETAIL_BASE_URL || "/builds/";
const HOME_URL = normalizeInternalPath(window.AOM_HOME_URL || "/build_orders/");
const EDITOR_BASE_URL = normalizeInternalPath(window.AOM_EDITOR_BASE_URL || "/editor/");


function normalizeInternalPath(value) {
  const path = String(value || "").trim();

  if (!path || path === "/") {
    return "/build_orders/";
  }

  return path.endsWith("/") ? path : `${path}/`;
}

function editorCreateUrl(godId) {
  const params = new URLSearchParams();
  params.set("new", "true");

  if (godId) {
    params.set("god", godId);
  }

  return `${EDITOR_BASE_URL}?${params.toString()}`;
}

const GOD_DETAILS = {
  zeus: {
    focus: "Infantry and Heroes.",
    bonuses: [
      "Starts with 10 Favor.",
      "Gains Favor 20% faster.",
      "Myth units cost 1 less population.",
      "Infantry do +60% damage to buildings.",
      "Hoplites move 15% faster."
    ]
  },
  hades: {
    focus: "Ranged Soldiers and Buildings.",
    bonuses: []
  },
  poseidon: {
    focus: "Cavalry and Economy.",
    bonuses: []
  },
  demeter: {
    focus: "Expansion and Resource Gathering.",
    bonuses: []
  },
  ra: {
    focus: "Migdol Stronghold units and Empowerment.",
    bonuses: []
  },
  isis: {
    focus: "Technology.",
    bonuses: [
      "Town Centers and Citadel Centers support +5 population.",
      "Monuments shield against enemy God Powers.",
      "Empowered Monuments heal nearby units and generate Favor faster.",
      "Technologies cost -10%.",
      "Obelisks cost -5 Gold and are built faster."
    ]
  },
  set: {
    focus: "Barracks units.",
    bonuses: [
      "Pharaohs can summon Animals of Set.",
      "Priests can convert wild animals.",
      "Spearmen, Axemen, and Slingers move faster.",
      "Barracks, Siege Works, and Migdol Strongholds cost more Gold.",
      "Monuments reduce the cost of units near Barracks and Migdol Strongholds."
    ]
  },
  thor: {
    focus: "Dwarves and Armory.",
    bonuses: [
      "Starts with Dwarves instead of Gatherers.",
      "Dwarves cost less Gold and gather Food and Wood efficiently.",
      "Dwarven Armory can be built and upgraded in any age.",
      "Armory upgrades cost less.",
      "Receives a free Dwarf for each Dwarven Armory upgrade.",
      "Can research extra Dwarven Armory upgrades."
    ]
  },
  odin: {
    focus: "Great Hall units.",
    bonuses: []
  },
  loki: {
    focus: "Myth units.",
    bonuses: []
  },
  freyr: {
    focus: "Technology and Defense.",
    bonuses: [
      "Has a defensive God Power that grows stronger each age.",
      "Technologies cost less Food, Wood, and Gold, but take longer to research.",
      "Hill Forts and Hill Fort units deal more damage.",
      "Repairing buildings is free.",
      "Gatherers and Dwarves can repair."
    ]
  },
  oranos: {
    focus: "Vision and Mobility.",
    bonuses: [
      "Citizens can build a new Sky Passage each age.",
      "Units can teleport between Sky Passages.",
      "All units have increased Line of Sight.",
      "Oracles generate more Favor at full Line of Sight.",
      "Damaged enemy units remain visible for a short duration."
    ]
  },
  gaia: {
    focus: "Economy and Buildings.",
    bonuses: []
  },
  kronos: {
    focus: "Siege and Myth units.",
    bonuses: []
  },
  fuxi: {
    focus: "Human Soldiers and Heroes.",
    bonuses: [
      "God Blessing: Yin and Yang.",
      "On Favored Land, buildings research faster.",
      "On Favored Land, Military Camp and Machine Workshop additions cost less.",
      "Gains access to Nezha in the Classical Age."
    ]
  },
  nuwa: {
    focus: "Economy and Support.",
    bonuses: []
  },
  nüwa: {
    focus: "Economy and Support.",
    bonuses: []
  },
  shennong: {
    focus: "Economy and Farming.",
    bonuses: [
      "God Blessing: Gift of Beasts.",
      "On Favored Land, Myth units regenerate hit points.",
      "Farms are available in the Archaic Age.",
      "Farms build instantly on Favored Land.",
      "Farm upgrades are researched instantly for free in their respective ages."
    ]
  },
  amaterasu: {
    focus: "Economy and Samurai.",
    bonuses: [
      "Earns an increasing Gold trickle with each Bushido tier.",
      "Samurai and Onna-mushas earn 300% more XP outside of combat.",
      "Shrines increase the content of nearby resources, up to 140%.",
      "Samurai and Onna-mushas regenerate hit points, twice as fast in combat."
    ]
  },
  tsukuyomi: {
    focus: "Technology, Shinobi, and Cavalry.",
    bonuses: [
      "Increases Shinobi and Cavalry attack with each Bushido tier.",
      "Each technology researched grants Bushido XP.",
      "Advancing to the next Age is faster.",
      "A free Kitsune appears at the Temple each Age."
    ]
  },
  susanoo: {
    focus: "Myth Units and God Powers.",
    bonuses: []
  },
  huitzilopochtli: {
    focus: "Military and Economy.",
    bonuses: []
  },
  huitlipochtli: {
    focus: "Military and Economy.",
    bonuses: []
  },
  quetzalcoatl: {
    focus: "Military and Economy.",
    bonuses: []
  },
  tezcatlipoca: {
    focus: "Military and Economy.",
    bonuses: []
  }
};

let gameStringTableGodDetails = null;

const GAME_STRING_TOKEN_REPLACEMENTS = {
  AMATERASU_PASSIVE_XP_BONUS: "300",
  AMATERASU_RESOURCE_INVENTORY_CAP: "140",
  AMATERASU_COMBAT_REGEN_MULTIPLIER: "2"
};

function normalizeGodDetailsKey(value) {
  const raw = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/%20/g, "-")
    .replace(/_/g, "-")
    .replace(/[^a-z0-9\-]+/g, "")
    .replace(/^-+|-+$/g, "");

  const aliases = {
    "fu-xi": "fuxi",
    "nu-wa": "nuwa",
    "nwa": "nuwa",
    "huitlipochtli": "huitzilopochtli"
  };

  return aliases[raw] || raw;
}

function cleanGameStringText(value) {
  return String(value || "")
    .replace(/\\n/g, "\n")
    .replace(/\$\{([^}]+)\}/g, (match, tokenName) => {
      return GAME_STRING_TOKEN_REPLACEMENTS[tokenName] ?? match;
    })
    .replace(/hitpoints/g, "hit points")
    .replace(/Bushidō/g, "Bushido")
    .trim();
}

function parseGodLongRolloverText(value) {
  const text = cleanGameStringText(value);

  if (!text) {
    return null;
  }

  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  let focus = "";
  const bonuses = [];

  for (const line of lines) {
    if (/^focus\s*:/i.test(line)) {
      focus = line.replace(/^focus\s*:\s*/i, "").trim();
      continue;
    }

    if (line.startsWith("•") || line.startsWith("-") || line.startsWith("*")) {
      const bonus = line.replace(/^[•\-*]\s*/, "").trim();

      if (bonus) {
        bonuses.push(bonus);
      }
    }
  }

  if (!focus && !bonuses.length) {
    return null;
  }

  return { focus, bonuses };
}

function parseGodDetailsFromStringTable(rawText) {
  const detailsByGod = {};
  const pattern = /ID\s*=\s*"STR_CIV_([^";]+?)_LR"\s*;\s*Str\s*=\s*"([\s\S]*?)"\s*(?=\r?\n(?:ID\s*=|\/\/|\s*$))/g;
  let match;

  while ((match = pattern.exec(rawText)) !== null) {
    const godKey = normalizeGodDetailsKey(match[1]);
    const parsedDetails = parseGodLongRolloverText(match[2]);

    if (godKey && parsedDetails) {
      detailsByGod[godKey] = parsedDetails;
    }
  }

  return detailsByGod;
}

async function loadGameStringTableGodDetails() {
  if (gameStringTableGodDetails !== null) {
    return gameStringTableGodDetails;
  }

  gameStringTableGodDetails = {};

  try {
    const response = await fetch(staticPath("assets/game-data/string_table.txt"), {
      cache: "force-cache"
    });

    if (!response.ok) {
      return gameStringTableGodDetails;
    }

    const rawText = await response.text();
    gameStringTableGodDetails = parseGodDetailsFromStringTable(rawText);
  } catch (error) {
    console.warn("Could not load game string table god details.", error);
  }

  return gameStringTableGodDetails;
}

function normalizeGodDetails(details) {
  if (!details || typeof details !== "object") {
    return null;
  }

  const focus = String(details.focus || "").trim();
  const bonuses = Array.isArray(details.bonuses)
    ? details.bonuses.map((bonus) => String(bonus || "").trim()).filter(Boolean)
    : [];

  if (!focus && !bonuses.length) {
    return null;
  }

  return { focus, bonuses };
}

function getGodDetails(god) {
  const godId = normalizeGodDetailsKey(god?.id || god?.slug || god?.name);

  return (
    normalizeGodDetails(god?.details) ||
    normalizeGodDetails(gameStringTableGodDetails?.[godId]) ||
    normalizeGodDetails(GOD_DETAILS[godId]) ||
    null
  );
}

function ensureGodDetailsPanel() {
  if (godDetailsPanel) {
    return godDetailsPanel;
  }

  if (!godSummary) {
    return null;
  }

  godDetailsPanel = document.createElement("section");
  godDetailsPanel.id = "godDetailsPanel";
  godDetailsPanel.className = "god-details-panel hidden";
  godDetailsPanel.setAttribute("aria-label", "God focus and bonuses");
  godSummary.insertAdjacentElement("afterend", godDetailsPanel);

  return godDetailsPanel;
}

function renderGodDetails(god) {
  const panel = ensureGodDetailsPanel();

  if (!panel) {
    return;
  }

  const details = getGodDetails(god);

  if (!details) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }

  const bonuses = Array.isArray(details.bonuses)
    ? details.bonuses
    : [];

  const bonusesHtml = bonuses
    .map((bonus) => `<li>${escapeHtml(bonus)}</li>`)
    .join("");

  panel.innerHTML = `
    <div class="god-details-focus">
      <span>Focus:</span>
      <strong>${escapeHtml(details.focus || "General strategy.")}</strong>
    </div>

    ${bonusesHtml ? `
      <ul class="god-details-list">
        ${bonusesHtml}
      </ul>
    ` : ""}
  `;

  panel.classList.remove("hidden");
}

function staticPath(path) {
  return `${STATIC_URL}${String(path).replace(/^\/+/, "")}`;
}

function normalizeStaticAssetPath(path) {
  const value = String(path || "");

  if (!value) {
    return "";
  }

  if (
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("/static/")
  ) {
    return value;
  }

  return staticPath(value.replace(/^(\.\.\/)+/, "").replace(/^\/+/, ""));
}

function optimizedAssetPath(path, variant = "") {
  const normalized = normalizeStaticAssetPath(path);

  if (!normalized || !normalized.endsWith(".png")) {
    return "";
  }

  const staticPrefix = normalized.startsWith(STATIC_URL) ? STATIC_URL : "/static/";
  const relativePath = normalized.slice(staticPrefix.length);

  if (!relativePath.startsWith("assets/images/")) {
    return "";
  }

  const extensionless = relativePath.replace(/\.png$/i, "");
  const optimizedPath = extensionless.replace("assets/images/", "assets/optimized/images/");

  return `${staticPrefix}${optimizedPath}${variant}.webp`;
}

function imageSetValue(fallbackPath, optimizedPath) {
  const fallback = normalizeStaticAssetPath(fallbackPath);

  if (!fallback) {
    return "";
  }

  if (!optimizedPath) {
    return `url("${fallback}")`;
  }

  return `image-set(url("${optimizedPath}") type("image/webp"), url("${fallback}") type("image/png"))`;
}

function themedBackgroundValue(path) {
  const sourcePath = normalizeStaticAssetPath(path);
  return imageSetValue(sourcePath, optimizedAssetPath(sourcePath));
}

function normalizeGodLookupValue(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/%20/g, "-")
    .replace(/_/g, "-")
    .replace(/[^a-z0-9-]+/g, "")
    .replace(/^-+|-+$/g, "");
}

function getGodIdFromUrl() {
  const pathParts = window.location.pathname.split("/").filter(Boolean);

  if (pathParts[0] === "gods" && pathParts[1]) {
    return normalizeGodLookupValue(decodeURIComponent(pathParts[1]));
  }

  if (pathParts[0] === "build_orders" && pathParts[1] === "gods" && pathParts[2]) {
    return normalizeGodLookupValue(decodeURIComponent(pathParts[2]));
  }

  const params = new URLSearchParams(window.location.search);
  return normalizeGodLookupValue(params.get("god"));
}

function findGod(godId) {
  const normalizedGodId = normalizeGodLookupValue(godId);

  for (const pantheon of pantheons) {
    const god = pantheon.gods.find((item) => {
      const possibleValues = [
        item.id,
        item.slug,
        item.name,
        String(item.name || "").replace(/\s+/g, "-"),
      ];

      return possibleValues.some((value) => normalizeGodLookupValue(value) === normalizedGodId);
    });

    if (god) {
      return {
        god,
        pantheon
      };
    }
  }

  return null;
}

function godHeroPortraitPath(godId) {
  return staticPath(`assets/images/gods/${godId}_breakoutportrait.png`);
}

function godHeroBackgroundValue(godId) {
  const sourcePath = godHeroPortraitPath(godId);
  return imageSetValue(sourcePath, optimizedAssetPath(sourcePath, ".hero"));
}

function pantheonReturnUrl(pantheon) {
  const pantheonId = pantheon?.id || pantheon?.slug || "";

  if (!pantheonId) {
    return HOME_URL;
  }

  return `${HOME_URL}?pantheon=${encodeURIComponent(pantheonId)}`;
}

function buildDetailUrl(buildId, godId) {
  const params = new URLSearchParams();

  if (godId) {
    params.set("god", godId);
  }

  const query = params.toString();

  return `${BUILD_DETAIL_BASE_URL}${encodeURIComponent(buildId)}/${query ? `?${query}` : ""}`;
}

function newBuildEditorUrl(godId) {
  const params = new URLSearchParams();

  params.set("new", "true");

  if (godId) {
    params.set("god", godId);
  }

  return `${EDITOR_BASE_URL}?${params.toString()}`;
}

function updateAddBuildOrderLink(god) {
  const addLink = document.getElementById("addBuildOrderBottomLink");

  if (!addLink || !god) {
    return;
  }

  const godId = god.id || god.slug || getGodIdFromUrl();

  addLink.href = newBuildEditorUrl(godId);
  addLink.title = `Add your own ${god.name || "major god"} build order`;
}


function updateReturnLinks(pantheon) {
  const returnUrl = pantheonReturnUrl(pantheon);
  const backButton = document.querySelector(".build-back-button");
  const chooseAnotherGodLink = document.querySelector(".primary-link-button");

  if (backButton) {
    backButton.href = returnUrl;
    backButton.setAttribute("aria-label", `Back to ${pantheon.name} pantheon`);
  }

  if (chooseAnotherGodLink) {
    chooseAnotherGodLink.href = HOME_URL;
    chooseAnotherGodLink.textContent = "Choose Another God";
  }

  if (createBuildOrderLink) {
    createBuildOrderLink.href = HOME_URL;
    createBuildOrderLink.classList.add("hidden");
  }
}

function readSavedBuilds() {
  try {
    const raw = localStorage.getItem(STORAGE_BUILDS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed;
  } catch (error) {
    console.error("Could not read saved builds.", error);
    return [];
  }
}

function getStaticBuildsForGod(godId) {
  return buildOrders[godId] || [];
}

function getSavedBuildsForGod(godId) {
  return readSavedBuilds().filter((build) => {
    return build.sourceGodId === godId;
  });
}

function mergeBuilds(staticBuilds, savedBuilds) {
  const merged = new Map();

  staticBuilds.forEach((build) => {
    merged.set(build.id, {
      ...build,
      isSavedBuild: false
    });
  });

  savedBuilds.forEach((build) => {
    merged.set(build.id, {
      ...build,
      isSavedBuild: true
    });
  });

  return Array.from(merged.values());
}



function createFallbackBuild(_god, _pantheon) {
  return [];
}



function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getGodDetails(god) {
  return god.details || GOD_DETAILS[god.id] || null;
}

function renderGodDetails(god) {
  if (!godDetailsPanel) {
    return;
  }

  const details = getGodDetails(god);

  if (!details) {
    godDetailsPanel.classList.add("hidden");
    godDetailsPanel.innerHTML = "";
    return;
  }

  const bonuses = Array.isArray(details.bonuses)
    ? details.bonuses
    : [];

  const bonusesHtml = bonuses
    .map((bonus) => `<li>${escapeHtml(bonus)}</li>`)
    .join("");

  godDetailsPanel.innerHTML = `
    <div class="god-details-focus">
      <span>Focus:</span>
      <strong>${escapeHtml(details.focus || "General strategy.")}</strong>
    </div>

    ${bonusesHtml ? `
      <ul class="god-details-list">
        ${bonusesHtml}
      </ul>
    ` : ""}
  `;

  godDetailsPanel.classList.remove("hidden");
}

function renderHero(god, pantheon) {
  document.title = `${god.name} Build Orders | AoM Build Orders`;

  const pantheonBackground = normalizeStaticAssetPath(pantheon.background);

  if (pantheonBackground) {
    buildPage.style.setProperty("--pantheon-bg", themedBackgroundValue(pantheonBackground));
  }

  pantheonLabel.textContent = `${pantheon.name} Pantheon`;
  godName.textContent = god.name;
  godSummary.textContent = god.subtitle;
  godHeroArt.style.backgroundImage = godHeroBackgroundValue(god.id);
  buildSectionHeading.textContent = `${god.name} Build Orders`;

  updateReturnLinks(pantheon);
  renderGodDetails(god);

  if (createBuildOrderLink) {
    createBuildOrderLink.href = editorCreateUrl(god.id);
    createBuildOrderLink.classList.remove("hidden");
  }
}

function renderBuildCard(build, god) {
  const card = document.createElement("article");
  card.className = "build-card";

  const meta = build.meta || build.goalText || "";
  const summary =
    build.summary ||
    build.subtitle ||
    "A saved build order created in the editor.";

  card.innerHTML = `
    <div class="build-card-header">
      <h3>${escapeHtml(build.title)}</h3>
      <div class="build-card-meta">${escapeHtml(meta)}</div>
    </div>

    <p class="build-card-summary">${escapeHtml(summary)}</p>

    <a class="build-card-link" href="${buildDetailUrl(build.id, god.id)}">
      View Build
    </a>
  `;

  return card;
}



function renderBuilds(god, pantheon) {
  const godId = god.id || god.slug || "";
  const staticBuilds = getStaticBuildsForGod(godId);
  const savedBuilds = getSavedBuildsForGod(godId);
  const builds = mergeBuilds(staticBuilds, savedBuilds);

  buildGrid.innerHTML = "";

  if (builds.length === 0) {
    buildGrid.innerHTML = `
      <div class="empty-builds">
        No build orders have been added for ${escapeHtml(god.name)} yet.
      </div>
    `;
  } else {
    builds.forEach((build) => {
      buildGrid.appendChild(renderBuildCard(build, god));
    });
  }

  updateAddBuildOrderLink(god);
}




function renderNotFound() {
  document.title = "God Not Found | AoM Build Orders";

  pantheonLabel.textContent = "Unknown God";
  godName.textContent = "Build Orders Not Found";
  godSummary.textContent =
    "The requested god could not be found. Return to the build order archive and choose a pantheon again.";

  const backButton = document.querySelector(".build-back-button");
  const chooseAnotherGodLink = document.querySelector(".primary-link-button");

  if (backButton) {
    backButton.href = HOME_URL;
    backButton.setAttribute("aria-label", "Back to Pantheon Selection");
  }

  if (chooseAnotherGodLink) {
    chooseAnotherGodLink.href = HOME_URL;
    chooseAnotherGodLink.textContent = "Choose Another God";
  }

  updateAddBuildOrderLink({ id: "" });

  if (godDetailsPanel) {
    godDetailsPanel.classList.add("hidden");
    godDetailsPanel.innerHTML = "";
  }

  buildGrid.innerHTML = `
    <div class="empty-builds">
      No matching god was found for this URL. Use the back button or choose another god from the build order archive.
    </div>
  `;
}

async function initBuildPage() {
  const godId = getGodIdFromUrl();
  const result = findGod(godId);

  if (!result) {
    renderNotFound();
    return;
  }

  renderHero(result.god, result.pantheon);
  updateAddBuildOrderLink(result.god);
  renderBuilds(result.god, result.pantheon);
}

initBuildPage();
