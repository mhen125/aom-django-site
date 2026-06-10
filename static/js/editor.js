const STORAGE_ACTIVE_ID_KEY = "aomBuildOrder.activeBuildId";
const LEGACY_STORAGE_KEY = "aomBuildOrder.active";
const STORAGE_BUILDS_KEY = "aomBuildOrder.builds";

const STATIC_URL = window.AOM_STATIC_URL || "/static/";
const GOD_DETAIL_BASE_URL = window.AOM_GOD_DETAIL_BASE_URL || "/gods/";
const BUILD_DETAIL_BASE_URL = window.AOM_BUILD_DETAIL_BASE_URL || "/builds/";
const EDITOR_BASE_URL = window.AOM_EDITOR_BASE_URL || "/editor/";
const SAVE_BUILD_URL = window.AOM_SAVE_BUILD_URL || "/api/builds/save/";
const DELETE_BUILD_URL = window.AOM_DELETE_BUILD_URL || "/api/builds/delete/";

function staticPath(path) {
  return `${STATIC_URL}${String(path).replace(/^\/+/, "")}`;
}

function normalizeStaticAssetPath(path) {
  const value = String(path || "").trim();

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

  return staticPath(
    value
      .replace(/^(\.\.\/)+/, "")
      .replace(/^\/+/, "")
  );
}

const ICONS = {
  food: staticPath("assets/images/res_Food.png"),
  wood: staticPath("assets/images/res_Wood.png"),
  gold: staticPath("assets/images/gold.png"),
  favor: staticPath("assets/images/favor.png"),
  pop: staticPath("assets/images/res_pop.png"),
  villager: staticPath("assets/images/res_population.png")
};

const GOD_TO_PANTHEON = {
  zeus: "greek",
  hades: "greek",
  poseidon: "greek",
  demeter: "greek",

  odin: "norse",
  thor: "norse",
  loki: "norse",
  freyr: "norse",

  ra: "egyptian",
  isis: "egyptian",
  set: "egyptian",

  oranos: "atlantean",
  kronos: "atlantean",
  gaia: "atlantean",
  prometheus: "atlantean",

  fuxi: "chinese",
  nuwa: "chinese",
  shennong: "chinese",

  amaterasu: "japanese",
  tsukuyomi: "japanese",
  susanoo: "japanese",

  quetzalcoatl: "aztec",
  tezcatlipoca: "aztec",
  huitzilopochtli: "aztec"
};

const DEFAULT_BUILD = {
  id: "amaterasu-opening",
  title: "Amaterasu Opening Build Order",
  subtitle: "Each row shows what changes at that moment, plus the villager distribution after the step.",
  goalLabel: "Goal",
  goalText: "Click Age Up",
  portrait: staticPath("assets/images/gods/amaterasu_portrait.png"),
  goalIcon: staticPath("assets/images/score_age_2.png"),
  meta: "Land · Standard",
  summary: "A saved Amaterasu opening build order.",
  sourceGodId: "amaterasu",
  sourcePantheonId: "japanese",
  steps: [
    {
      type: "phase",
      label: "Opening"
    },
    {
      time: "0:00",
      food: "4 - Hunt",
      wood: "",
      gold: "",
      favor: "",
      pop: "",
      action: "Queue villagers",
      note: "Send the starting villagers to food immediately.",
      split: {
        food: 4,
        wood: 0,
        gold: 0,
        favor: 0,
        pop: "4/15"
      }
    }
  ]
};

let buildCollection = [];
let editorBuild = null;
let activeComposerMode = "step";
let editingIndex = null;
let savedEditorSnapshot = "";
let suppressUnsavedNavigationWarning = false;

const UNSAVED_CHANGES_MESSAGE = "You have unsaved changes to this build order. Leave without saving?";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function getElement(id) {
  return document.getElementById(id);
}

function createId() {
  const titleSlug = slugify(getElement("titleInput")?.value || "new-build-order");

  if (titleSlug) {
    return titleSlug;
  }

  return `build-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function hasOwnField(object, key) {
  return Object.prototype.hasOwnProperty.call(object || {}, key);
}

function stringField(object, key, fallback = "") {
  if (hasOwnField(object, key)) {
    return String(object[key] ?? "");
  }

  return fallback;
}

function slugify(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/['"]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];

  for (const cookie of cookies) {
    const trimmedCookie = cookie.trim();

    if (trimmedCookie.startsWith(`${name}=`)) {
      return decodeURIComponent(trimmedCookie.slice(name.length + 1));
    }
  }

  return "";
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify(payload)
  });

  let data = null;

  try {
    data = await response.json();
  } catch (_error) {
    data = null;
  }

  if (!response.ok || !data?.ok) {
    const errorMessage = data?.error || `Request failed with status ${response.status}`;
    throw new Error(errorMessage);
  }

  return data;
}

function getUrlParam(name) {
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}

function getEditorTargetId() {
  return getUrlParam("id") || getUrlParam("build");
}

function getRequestedGodId() {
  return getUrlParam("god") || "";
}

function isCreateNewMode() {
  return getUrlParam("new") === "true";
}

function getStaticData() {
  return window.AOM_DATA || { pantheons: [], buildOrders: {} };
}

function findGodById(godId) {
  const { pantheons } = getStaticData();

  for (const pantheon of pantheons) {
    const god = pantheon.gods.find((item) => item.id === godId || item.slug === godId);

    if (god) {
      return { god, pantheon };
    }
  }

  return null;
}

function findStaticBuildById(buildId) {
  const { pantheons, buildOrders } = getStaticData();

  for (const pantheon of pantheons) {
    for (const god of pantheon.gods) {
      const godId = god.id || god.slug;
      const builds = buildOrders[godId] || [];
      const build = builds.find((item) => item.id === buildId || item.slug === buildId);

      if (build) {
        return { build, god, pantheon };
      }
    }
  }

  return null;
}

function getAllDatabaseBuilds() {
  const { pantheons, buildOrders } = getStaticData();
  const allBuilds = [];

  for (const pantheon of pantheons) {
    for (const god of pantheon.gods) {
      const godId = god.id || god.slug;
      const builds = buildOrders[godId] || [];

      builds.forEach((build) => {
        allBuilds.push(staticBuildToEditorBuild(build, god, pantheon));
      });
    }
  }

  return allBuilds;
}

function pantheonIdForGod(godId) {
  const found = findGodById(godId);

  if (found?.pantheon?.id) {
    return found.pantheon.id;
  }

  if (found?.pantheon?.slug) {
    return found.pantheon.slug;
  }

  return GOD_TO_PANTHEON[godId] || "";
}

function getCurrentGodId() {
  const requestedGodId = getRequestedGodId();

  if (requestedGodId) {
    return requestedGodId;
  }

  if (editorBuild?.sourceGodId) {
    return editorBuild.sourceGodId;
  }

  return DEFAULT_BUILD.sourceGodId;
}

function getCurrentPantheonId() {
  const godId = getCurrentGodId();

  if (editorBuild?.sourcePantheonId) {
    return editorBuild.sourcePantheonId;
  }

  return pantheonIdForGod(godId) || DEFAULT_BUILD.sourcePantheonId;
}

function godPortraitPath(godId) {
  return staticPath(`assets/images/gods/${godId}_portrait.png`);
}

function godOverviewUrl(godId) {
  if (!godId) {
    return "/";
  }

  return `${GOD_DETAIL_BASE_URL}${encodeURIComponent(godId)}/`;
}

function buildDetailUrl(buildId, godId = "") {
  const params = new URLSearchParams();

  if (godId) {
    params.set("god", godId);
  }

  const query = params.toString();

  return `${BUILD_DETAIL_BASE_URL}${encodeURIComponent(buildId)}/${query ? `?${query}` : ""}`;
}

function editorUrl(buildId, godId = "") {
  const params = new URLSearchParams();

  if (buildId) {
    params.set("id", buildId);
  }

  if (godId) {
    params.set("god", godId);
  }

  return `${EDITOR_BASE_URL}?${params.toString()}`;
}

function repairPortraitPath(portrait, build = {}) {
  if (!portrait) {
    if (build.sourceGodId) {
      return godPortraitPath(build.sourceGodId);
    }

    return DEFAULT_BUILD.portrait;
  }

  const normalizedPortrait = String(portrait).trim();

  if (normalizedPortrait.startsWith("build_orders/images/")) {
    return normalizeStaticAssetPath(
      normalizedPortrait.replace("build_orders/images/", "assets/images/")
    );
  }

  if (normalizedPortrait === "images/amaterasu_icon.png") {
    return godPortraitPath("amaterasu");
  }

  if (normalizedPortrait.startsWith("images/")) {
    return normalizeStaticAssetPath(
      normalizedPortrait.replace("images/", "assets/images/")
    );
  }

  const oldGodIconMatch = normalizedPortrait.match(/^images\/(.+)_icon\.png$/);

  if (oldGodIconMatch) {
    return godPortraitPath(oldGodIconMatch[1]);
  }

  return normalizeStaticAssetPath(normalizedPortrait);
}

function repairGoalIconPath(goalIcon) {
  if (!goalIcon) {
    return DEFAULT_BUILD.goalIcon;
  }

  const normalizedGoalIcon = String(goalIcon).trim();

  if (normalizedGoalIcon.startsWith("/images/")) {
    return normalizeStaticAssetPath(`assets${normalizedGoalIcon}`);
  }

  if (normalizedGoalIcon.startsWith("images/")) {
    return normalizeStaticAssetPath(
      normalizedGoalIcon.replace("images/", "assets/images/")
    );
  }

  if (normalizedGoalIcon.startsWith("build_orders/images/")) {
    return normalizeStaticAssetPath(
      normalizedGoalIcon.replace("build_orders/images/", "assets/images/")
    );
  }

  return normalizeStaticAssetPath(normalizedGoalIcon);
}

function normalizeBuild(build) {
  const requestedGodId = getRequestedGodId();
  const sourceGodId =
    build.sourceGodId ||
    requestedGodId ||
    DEFAULT_BUILD.sourceGodId;

  const sourcePantheonId =
    build.sourcePantheonId ||
    pantheonIdForGod(sourceGodId) ||
    DEFAULT_BUILD.sourcePantheonId;

  const normalized = {
    id: build.id || build.slug || createId(),
    title: stringField(build, "title", DEFAULT_BUILD.title),
    subtitle: stringField(
      build,
      "subtitle",
      stringField(build, "detailSubtitle", stringField(build, "summary", DEFAULT_BUILD.subtitle))
    ),
    goalLabel: stringField(build, "goalLabel", DEFAULT_BUILD.goalLabel) || "Goal",
    goalText: stringField(build, "goalText", stringField(build, "meta", DEFAULT_BUILD.goalText)),
    portrait: stringField(build, "portrait", DEFAULT_BUILD.portrait) || DEFAULT_BUILD.portrait,
    goalIcon: stringField(build, "goalIcon", DEFAULT_BUILD.goalIcon) || DEFAULT_BUILD.goalIcon,
    meta: stringField(build, "meta", stringField(build, "goalText", "")),
    summary: stringField(build, "summary", ""),
    sourceGodId,
    sourcePantheonId,
    steps: Array.isArray(build.steps) ? build.steps : clone(DEFAULT_BUILD.steps)
  };

  normalized.portrait = repairPortraitPath(normalized.portrait, normalized);
  normalized.goalIcon = repairGoalIconPath(normalized.goalIcon);

  return normalized;
}

function staticBuildToEditorBuild(staticBuild, god, pantheon) {
  return normalizeBuild({
    id: staticBuild.id || staticBuild.slug,
    title: staticBuild.title,
    subtitle: staticBuild.detailSubtitle || staticBuild.subtitle || staticBuild.summary || `${god.name} build order.`,
    goalLabel: staticBuild.goalLabel || "Goal",
    goalText: staticBuild.goalText || staticBuild.meta || "Build Order",
    portrait: staticBuild.portrait || godPortraitPath(god.id || god.slug),
    goalIcon: staticBuild.goalIcon || staticPath("assets/images/score_age_2.png"),
    meta: staticBuild.meta || "",
    summary: staticBuild.summary || "",
    sourceGodId: god.id || god.slug,
    sourcePantheonId: pantheon.id || pantheon.slug,
    steps: Array.isArray(staticBuild.steps) ? staticBuild.steps : []
  });
}

function loadBuildCollection() {
  const databaseBuilds = getAllDatabaseBuilds();

  if (databaseBuilds.length > 0) {
    return databaseBuilds.map(normalizeBuild);
  }

  return [];
}

function saveBuildCollection(_builds) {
  localStorage.removeItem(STORAGE_BUILDS_KEY);
  localStorage.removeItem(LEGACY_STORAGE_KEY);
}

function getActiveBuildId() {
  const savedId = localStorage.getItem(STORAGE_ACTIVE_ID_KEY);

  if (savedId && buildCollection.some((build) => build.id === savedId)) {
    return savedId;
  }

  const fallbackId = buildCollection[0]?.id || "";
  localStorage.setItem(STORAGE_ACTIVE_ID_KEY, fallbackId);

  return fallbackId;
}

function setActiveBuildId(buildId) {
  localStorage.setItem(STORAGE_ACTIVE_ID_KEY, buildId);
}

function getValueForSnapshot(id) {
  const element = getElement(id);
  return element ? element.value : "";
}

function getComposerSnapshot() {
  return {
    mode: activeComposerMode,
    editingIndex,
    step: {
      time: getValueForSnapshot("rowTimeInput"),
      food: getValueForSnapshot("rowFoodInput"),
      wood: getValueForSnapshot("rowWoodInput"),
      gold: getValueForSnapshot("rowGoldInput"),
      favor: getValueForSnapshot("rowFavorInput"),
      action: getValueForSnapshot("rowActionInput"),
      note: getValueForSnapshot("rowNoteInput"),
      splitFood: getValueForSnapshot("splitFoodInput"),
      splitWood: getValueForSnapshot("splitWoodInput"),
      splitGold: getValueForSnapshot("splitGoldInput"),
      splitFavor: getValueForSnapshot("splitFavorInput")
    },
    milestone: {
      time: getValueForSnapshot("milestoneTimeInput"),
      type: getValueForSnapshot("milestoneStyleInput"),
      label: getValueForSnapshot("milestoneTextInput")
    }
  };
}

function getEditorSnapshot() {
  if (!editorBuild) {
    return "";
  }

  readBuildInfoFields();

  return JSON.stringify({
    build: normalizeBuild(editorBuild),
    composer: getComposerSnapshot()
  });
}

function hasUnsavedEditorChanges() {
  if (!savedEditorSnapshot || !editorBuild) {
    return false;
  }

  return getEditorSnapshot() !== savedEditorSnapshot;
}

function updateDirtyState() {
  const isDirty = hasUnsavedEditorChanges();
  document.body.classList.toggle("editor-has-unsaved-changes", isDirty);

  const saveButton = getElement("saveBuildButton");

  if (saveButton) {
    saveButton.dataset.unsaved = isDirty ? "true" : "false";
  }

  return isDirty;
}

function markEditorClean() {
  savedEditorSnapshot = getEditorSnapshot();
  updateDirtyState();
}

function createEditorConfirmController() {
  const modal = getElement("editorConfirmModal");
  const title = getElement("editorConfirmTitle");
  const message = getElement("editorConfirmMessage");
  const cancelButton = getElement("editorConfirmCancel");
  const discardButton = getElement("editorConfirmDiscard");
  const saveButton = getElement("editorConfirmSave");

  let resolver = null;
  let lastFocusedElement = null;

  function close(result) {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("editor-confirm-open");

    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
      lastFocusedElement.focus({ preventScroll: true });
    }

    if (resolver) {
      resolver(result);
      resolver = null;
    }
  }

  function bindButton(button, result) {
    if (!button) {
      return;
    }

    button.addEventListener("click", () => close(result));
  }

  bindButton(cancelButton, "cancel");
  bindButton(discardButton, "discard");
  bindButton(saveButton, "save");

  modal.addEventListener("click", (event) => {
    if (event.target.matches("[data-editor-confirm-cancel]")) {
      close("cancel");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (modal.classList.contains("hidden")) {
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      close("cancel");
    }
  });

  return {
    open({
      titleText = "Unsaved Build Order",
      messageText = "You have unsaved changes. Save first, stay here, or continue without saving.",
      cancelText = "Stay Here",
      discardText = "Leave Without Saving",
      saveText = "Save First",
      showSave = true,
      discardIsDanger = true
    } = {}) {
      title.textContent = titleText;
      message.textContent = messageText;
      cancelButton.textContent = cancelText;
      discardButton.textContent = discardText;
      saveButton.textContent = saveText;

      saveButton.classList.toggle("hidden", !showSave);
      discardButton.classList.toggle("danger", discardIsDanger);
      discardButton.classList.toggle("secondary", !discardIsDanger);

      lastFocusedElement = document.activeElement;
      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");
      document.body.classList.add("editor-confirm-open");

      window.setTimeout(() => {
        const preferredButton = showSave ? saveButton : discardButton;
        preferredButton?.focus({ preventScroll: true });
      }, 0);

      return new Promise((resolve) => {
        resolver = resolve;
      });
    }
  };
}

const editorConfirm = createEditorConfirmController();

async function requestUnsavedEditorNavigation({
  titleText = "Unsaved Build Order",
  messageText = UNSAVED_CHANGES_MESSAGE,
  discardText = "Leave Without Saving",
  saveText = "Save First"
} = {}) {
  if (!hasUnsavedEditorChanges()) {
    return true;
  }

  const result = await editorConfirm.open({
    titleText,
    messageText,
    discardText,
    saveText,
    showSave: true,
    discardIsDanger: true
  });

  if (result === "discard") {
    return true;
  }

  if (result === "save") {
    try {
      await persistCurrentBuild("Saved");
      return true;
    } catch (error) {
      alert(`Could not save build: ${error.message}`);
      console.error(error);
      return false;
    }
  }

  return false;
}

async function requestDangerConfirmation({
  titleText,
  messageText,
  discardText = "Confirm",
  cancelText = "Cancel"
}) {
  const result = await editorConfirm.open({
    titleText,
    messageText,
    cancelText,
    discardText,
    showSave: false,
    discardIsDanger: true
  });

  return result === "discard";
}

function bindUnsavedNavigationGuard() {
  window.addEventListener("beforeunload", (event) => {
    if (suppressUnsavedNavigationWarning || !hasUnsavedEditorChanges()) {
      return;
    }

    event.preventDefault();
    event.returnValue = "";
  });

  document.addEventListener("click", async (event) => {
    const link = event.target.closest("a[href]");

    if (!link) {
      return;
    }

    const href = link.getAttribute("href") || "";

    if (
      !href ||
      href.startsWith("#") ||
      href.startsWith("javascript:") ||
      link.target === "_blank" ||
      link.hasAttribute("download") ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    const canNavigate = await requestUnsavedEditorNavigation({
      titleText: "Leave Editor?",
      messageText: "You have unsaved changes in this build order. Save first, stay here, or leave without saving.",
      discardText: "Leave Without Saving"
    });

    if (!canNavigate) {
      return;
    }

    suppressUnsavedNavigationWarning = true;
    window.location.href = link.href;
  }, true);

  document.addEventListener("input", () => {
    updateDirtyState();
  }, true);

  document.addEventListener("change", () => {
    updateDirtyState();
  }, true);
}

function getBuildById(buildId) {
  return buildCollection.find((build) => build.id === buildId) || null;
}

function getBuildInfoDetails() {
  return document.querySelector(".collapsible-editor-panel");
}

function openBuildInfoPanel({ focusTitle = false, scroll = true } = {}) {
  const details = getBuildInfoDetails();

  if (!details) {
    return;
  }

  details.open = true;

  if (scroll) {
    details.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  }

  if (focusTitle) {
    window.setTimeout(() => {
      getElement("titleInput")?.focus({ preventScroll: true });
    }, 150);
  }
}

function guideToBuildInfo() {
  openBuildInfoPanel({
    focusTitle: true,
    scroll: true
  });
}

function refreshEditorForCurrentBuild() {
  setBuildInfoFields(editorBuild);
  clearComposer();
  renderRowsList();
  renderEditorBuildPicker();
  updateNavigationLinks();
}

function createNewBuild() {
  const godId = getCurrentGodId();
  const pantheonId = pantheonIdForGod(godId) || getCurrentPantheonId();
  const idSuffix = Date.now().toString(36);

  return normalizeBuild({
    id: `new-build-order-${idSuffix}`,
    title: "",
    subtitle: "",
    goalLabel: "Goal",
    goalText: "",
    meta: "",
    summary: "",
    sourceGodId: godId,
    sourcePantheonId: pantheonId,
    portrait: godPortraitPath(godId),
    goalIcon: staticPath("assets/images/score_age_2.png"),
    steps: []
  });
}

async function duplicateCurrentBuild() {
  readBuildInfoFields();

  const duplicatedBuild = normalizeBuild({
    ...clone(editorBuild),
    id: slugify(`${editorBuild.title || "Build Order"} Copy`) || createId(),
    title: `${editorBuild.title || "Build Order"} Copy`
  });

  editorBuild = duplicatedBuild;
  setBuildInfoFields(editorBuild);

  try {
    await persistCurrentBuild("Duplicated");
    refreshEditorForCurrentBuild();
    guideToBuildInfo();
  } catch (error) {
    alert(`Could not duplicate build: ${error.message}`);
    console.error(error);
  }
}

async function deleteCurrentBuild() {
  if (!editorBuild) {
    return;
  }

  const visibleBuilds = getVisibleEditorBuilds();
  const buildTitle = editorBuild.title || "this build";

  const confirmed = await requestDangerConfirmation({
    titleText: "Delete Build?",
    messageText: `Delete "${buildTitle}"? This cannot be undone.`,
    discardText: "Delete Build",
    cancelText: "Keep Build"
  });

  if (!confirmed) {
    return;
  }

  const deleteButton = getElement("deleteBuildButton");
  const originalText = deleteButton.textContent;

  deleteButton.textContent = "Deleting...";
  deleteButton.disabled = true;

  try {
    await postJson(DELETE_BUILD_URL, {
      id: editorBuild.id,
      sourceGodId: editorBuild.sourceGodId
    });

    buildCollection = buildCollection.filter((build) => build.id !== editorBuild.id);

    let nextBuild =
      visibleBuilds.find((build) => build.id !== editorBuild.id) ||
      buildCollection.find((build) => build.sourceGodId === editorBuild.sourceGodId) ||
      buildCollection[0];

    if (!nextBuild) {
      nextBuild = createNewBuild();
    }

    editorBuild = normalizeBuild(nextBuild);
    setActiveBuildId(editorBuild.id);
    updateEditorUrl(editorBuild.id, editorBuild.sourceGodId);

    setBuildInfoFields(editorBuild);
    clearComposer();
    renderRowsList();
    renderEditorBuildPicker();
    updateNavigationLinks();
    markEditorClean();
  } catch (error) {
    alert(`Could not delete build: ${error.message}`);
    console.error(error);
  } finally {
    deleteButton.textContent = originalText;
    deleteButton.disabled = false;
  }
}

function loadInitialEditorBuild() {
  buildCollection = loadBuildCollection();

  if (isCreateNewMode()) {
    const newBuild = createNewBuild();

    editorBuild = normalizeBuild(newBuild);
    updateEditorUrl(editorBuild.id, editorBuild.sourceGodId);

    return editorBuild;
  }

  const requestedId = getEditorTargetId();

  if (requestedId) {
    const requestedBuild = getBuildById(requestedId);

    if (requestedBuild) {
      setActiveBuildId(requestedBuild.id);
      return normalizeBuild(requestedBuild);
    }

    const staticContext = findStaticBuildById(requestedId);

    if (staticContext) {
      const clonedStaticBuild = staticBuildToEditorBuild(
        staticContext.build,
        staticContext.god,
        staticContext.pantheon
      );

      setActiveBuildId(clonedStaticBuild.id);
      updateEditorUrl(clonedStaticBuild.id, clonedStaticBuild.sourceGodId);

      return normalizeBuild(clonedStaticBuild);
    }
  }

  const requestedGodId = getRequestedGodId();

  if (requestedGodId) {
    const godBuilds = buildCollection.filter((build) => build.sourceGodId === requestedGodId);

    if (godBuilds.length > 0) {
      const firstGodBuild = godBuilds[0];
      updateEditorUrl(firstGodBuild.id, firstGodBuild.sourceGodId);
      return normalizeBuild(firstGodBuild);
    }
  }

  const activeId = getActiveBuildId();
  const activeBuild = getBuildById(activeId);

  if (activeBuild) {
    updateEditorUrl(activeBuild.id, activeBuild.sourceGodId || getRequestedGodId());
    return normalizeBuild(activeBuild);
  }

  return createNewBuild();
}

function updateEditorUrl(buildId, godId = "") {
  const params = new URLSearchParams();

  if (buildId) {
    params.set("id", buildId);
  }

  const finalGodId =
    godId ||
    getRequestedGodId() ||
    editorBuild?.sourceGodId ||
    "";

  if (finalGodId) {
    params.set("god", finalGodId);
  }

  const newUrl = `${EDITOR_BASE_URL}?${params.toString()}`;
  window.history.replaceState({}, "", newUrl);
}

function getVisibleEditorBuilds() {
  const currentGodId = getCurrentGodId();

  if (!currentGodId) {
    return buildCollection;
  }

  const filtered = buildCollection.filter((build) => {
    return build.sourceGodId === currentGodId;
  });

  if (editorBuild && !filtered.some((build) => build.id === editorBuild.id)) {
    filtered.unshift(editorBuild);
  }

  return filtered.length > 0 ? filtered : buildCollection;
}

function renderEditorBuildPicker() {
  const picker = getElement("editorBuildPickerSelect");
  const visibleBuilds = getVisibleEditorBuilds();

  picker.innerHTML = visibleBuilds.map((build) => {
    const selected = editorBuild && build.id === editorBuild.id ? "selected" : "";

    return `
      <option value="${escapeHtml(build.id)}" ${selected}>
        ${escapeHtml(build.title)}
      </option>
    `;
  }).join("");
}

function updateNavigationLinks() {
  const godId = getCurrentGodId();

  const backToGodBuildsLink = getElement("backToGodBuildsLink");
  const backToDisplayLink = getElement("backToDisplayLink");

  if (backToGodBuildsLink) {
    if (godId) {
      backToGodBuildsLink.href = godOverviewUrl(godId);
    } else {
      backToGodBuildsLink.href = "/build_orders/";
    }
  }

  if (backToDisplayLink && editorBuild?.id) {
    backToDisplayLink.href = buildDetailUrl(editorBuild.id, godId);
  }
}

async function handleEditorBuildPickerChange() {
  readBuildInfoFields();

  const selectedId = getElement("editorBuildPickerSelect").value;
  const selectedBuild = getBuildById(selectedId);

  if (!selectedBuild) {
    return;
  }

  const canSwitch = await requestUnsavedEditorNavigation({
    titleText: "Switch Builds?",
    messageText: "You have unsaved changes in the current build. Save first, stay here, or switch without saving.",
    discardText: "Switch Without Saving"
  });

  if (!canSwitch) {
    renderEditorBuildPicker();
    return;
  }

  editorBuild = normalizeBuild(selectedBuild);
  setActiveBuildId(editorBuild.id);
  updateEditorUrl(editorBuild.id, editorBuild.sourceGodId);

  setBuildInfoFields(editorBuild);
  clearComposer();
  renderRowsList();
  renderEditorBuildPicker();
  updateNavigationLinks();
  markEditorClean();
}

function setBuildInfoFields(build) {
  getElement("titleInput").value = build.title;
  getElement("subtitleInput").value = build.subtitle;
  getElement("metaInput").value = build.meta || "";
  getElement("summaryInput").value = build.summary || "";
  getElement("goalLabelInput").value = build.goalLabel;
  getElement("goalTextInput").value = build.goalText;
  getElement("portraitInput").value = build.portrait;
  getElement("goalIconInput").value = build.goalIcon;
}

function readBuildInfoFields() {
  const sourceGodId = editorBuild.sourceGodId || getRequestedGodId() || DEFAULT_BUILD.sourceGodId;
  const sourcePantheonId =
    editorBuild.sourcePantheonId ||
    pantheonIdForGod(sourceGodId) ||
    DEFAULT_BUILD.sourcePantheonId;

  editorBuild.title = getElement("titleInput").value.trim() || "Untitled Build Order";
  editorBuild.id = slugify(editorBuild.id || editorBuild.title) || createId();
  editorBuild.subtitle = getElement("subtitleInput").value.trim();
  editorBuild.meta = getElement("metaInput").value.trim();
  editorBuild.summary = getElement("summaryInput").value.trim();
  editorBuild.goalLabel = getElement("goalLabelInput").value.trim() || "Goal";
  editorBuild.goalText = getElement("goalTextInput").value.trim();
  editorBuild.portrait = getElement("portraitInput").value.trim() || godPortraitPath(sourceGodId);
  editorBuild.goalIcon =
    getElement("goalIconInput").value.trim() ||
    staticPath("assets/images/score_age_2.png");
  editorBuild.sourceGodId = sourceGodId;
  editorBuild.sourcePantheonId = sourcePantheonId;

  editorBuild.portrait = repairPortraitPath(editorBuild.portrait, editorBuild);
  editorBuild.goalIcon = repairGoalIconPath(editorBuild.goalIcon);
}

function setComposerMode(mode) {
  activeComposerMode = mode;
  editingIndex = null;

  const isStep = mode === "step";

  getElement("stepModeButton").classList.toggle("active", isStep);
  getElement("milestoneModeButton").classList.toggle("active", !isStep);

  getElement("stepComposer").classList.toggle("hidden", !isStep);
  getElement("milestoneComposer").classList.toggle("hidden", isStep);

  getElement("addRowButton").textContent = isStep ? "Add Step Row" : "Add Milestone Row";

  renderRowsList();
}

function readStepComposer() {
  return {
    time: getElement("rowTimeInput").value.trim(),
    food: getElement("rowFoodInput").value.trim(),
    wood: getElement("rowWoodInput").value.trim(),
    gold: getElement("rowGoldInput").value.trim(),
    favor: getElement("rowFavorInput").value.trim(),
    action: getElement("rowActionInput").value.trim(),
    note: getElement("rowNoteInput").value.trim(),
    split: {
      food: toNonNegativeNumber(getElement("splitFoodInput").value),
      wood: toNonNegativeNumber(getElement("splitWoodInput").value),
      gold: toNonNegativeNumber(getElement("splitGoldInput").value),
      favor: toNonNegativeNumber(getElement("splitFavorInput").value)
    }
  };
}

function readMilestoneComposer() {
  return {
    type: getElement("milestoneStyleInput").value || "phase",
    time: getElement("milestoneTimeInput").value.trim(),
    label: getElement("milestoneTextInput").value.trim() || "New Milestone"
  };
}

function fillStepComposer(step) {
  getElement("rowTimeInput").value = step.time || "";
  getElement("rowFoodInput").value = step.food || "";
  getElement("rowWoodInput").value = step.wood || "";
  getElement("rowGoldInput").value = step.gold || "";
  getElement("rowFavorInput").value = step.favor || "";
  getElement("rowActionInput").value = step.action || "";
  getElement("rowNoteInput").value = step.note || "";

  const split = step.split || {};

  getElement("splitFoodInput").value = split.food ?? 0;
  getElement("splitWoodInput").value = split.wood ?? 0;
  getElement("splitGoldInput").value = split.gold ?? 0;
  getElement("splitFavorInput").value = split.favor ?? 0;
}

function fillMilestoneComposer(step) {
  getElement("milestoneTimeInput").value = step.time || "";
  getElement("milestoneStyleInput").value = step.type === "minor-phase" || step.type === "minor-milestone" ? "minor-phase" : "phase";
  getElement("milestoneTextInput").value = step.label || "";
}

function clearComposer() {
  editingIndex = null;

  getElement("rowTimeInput").value = "";
  getElement("rowFoodInput").value = "";
  getElement("rowWoodInput").value = "";
  getElement("rowGoldInput").value = "";
  getElement("rowFavorInput").value = "";
  getElement("rowActionInput").value = "";
  getElement("rowNoteInput").value = "";

  getElement("splitFoodInput").value = 0;
  getElement("splitWoodInput").value = 0;
  getElement("splitGoldInput").value = 0;
  getElement("splitFavorInput").value = 0;

  getElement("milestoneTimeInput").value = "";
  getElement("milestoneStyleInput").value = "phase";
  getElement("milestoneTextInput").value = "";

  getElement("addRowButton").textContent =
    activeComposerMode === "step" ? "Add Step Row" : "Add Milestone Row";

  renderRowsList();
}

function addOrUpdateRow() {
  readBuildInfoFields();

  const newRow = activeComposerMode === "step"
    ? readStepComposer()
    : readMilestoneComposer();

  if (editingIndex !== null && editorBuild.steps[editingIndex]) {
    editorBuild.steps[editingIndex] = newRow;
  } else {
    editorBuild.steps.push(newRow);
  }

  clearComposer();
  renderRowsList();
}

function editRow(index) {
  const step = editorBuild.steps[index];

  if (!step) {
    return;
  }

  editingIndex = index;

  if (step.type === "phase" || step.type === "milestone" || step.type === "minor-phase" || step.type === "minor-milestone") {
    activeComposerMode = "milestone";

    getElement("stepModeButton").classList.remove("active");
    getElement("milestoneModeButton").classList.add("active");
    getElement("stepComposer").classList.add("hidden");
    getElement("milestoneComposer").classList.remove("hidden");

    fillMilestoneComposer(step);
    getElement("addRowButton").textContent = "Update Milestone Row";
  } else {
    activeComposerMode = "step";

    getElement("stepModeButton").classList.add("active");
    getElement("milestoneModeButton").classList.remove("active");
    getElement("stepComposer").classList.remove("hidden");
    getElement("milestoneComposer").classList.add("hidden");

    fillStepComposer(step);
    getElement("addRowButton").textContent = "Update Step Row";
  }

  renderRowsList();

  document.querySelector(".composer-panel").scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

function duplicateRow(index) {
  const step = editorBuild.steps[index];

  if (!step) {
    return;
  }

  editorBuild.steps.splice(index + 1, 0, clone(step));
  renderRowsList();
}

function removeRow(index) {
  if (!editorBuild.steps[index]) {
    return;
  }

  editorBuild.steps.splice(index, 1);

  if (editingIndex === index) {
    clearComposer();
  } else if (editingIndex !== null && editingIndex > index) {
    editingIndex -= 1;
  }

  renderRowsList();
}

function moveRowUp(index) {
  if (index <= 0) {
    return;
  }

  const temp = editorBuild.steps[index - 1];
  editorBuild.steps[index - 1] = editorBuild.steps[index];
  editorBuild.steps[index] = temp;

  if (editingIndex === index) {
    editingIndex = index - 1;
  } else if (editingIndex === index - 1) {
    editingIndex = index;
  }

  renderRowsList();
}

function moveRowDown(index) {
  if (index >= editorBuild.steps.length - 1) {
    return;
  }

  const temp = editorBuild.steps[index + 1];
  editorBuild.steps[index + 1] = editorBuild.steps[index];
  editorBuild.steps[index] = temp;

  if (editingIndex === index) {
    editingIndex = index + 1;
  } else if (editingIndex === index + 1) {
    editingIndex = index;
  }

  renderRowsList();
}

async function clearRows() {
  const confirmed = await requestDangerConfirmation({
    titleText: "Clear Build Rows?",
    messageText: "Clear all rows from the current build? This will not affect the saved display until you click Save Build.",
    discardText: "Clear Rows",
    cancelText: "Keep Rows"
  });

  if (!confirmed) {
    return;
  }

  editorBuild.steps = [];
  clearComposer();
  renderRowsList();
}

function formatArrowText(value) {
  return String(value ?? "")
    .replace(/\s+-\s+/g, " → ")
    .replace(/^\s*-\s*$/g, "→")
    .replace(/^\s*-\s+/g, "→ ")
    .replace(/\s+-\s*$/g, " →");
}

function renderRowsList() {
  const rowsList = getElement("rowsList");

  if (!editorBuild.steps.length) {
    rowsList.innerHTML = `
      <div class="empty-state">
        No rows yet. Use the composer above to add a build step or milestone line.
      </div>
    `;
    return;
  }

  rowsList.innerHTML = editorBuild.steps.map((step, index) => {
    if (step.type === "phase" || step.type === "milestone" || step.type === "minor-phase" || step.type === "minor-milestone") {
      return renderMilestoneRow(step, index);
    }

    return renderStepRow(step, index);
  }).join("");

  bindRowButtons();
}

function renderMilestoneRow(step, index) {
  const editingClass = editingIndex === index ? "editing" : "";
  const isMinorMilestone = step.type === "minor-phase" || step.type === "minor-milestone";
  const milestoneClass = isMinorMilestone ? "minor-milestone-row" : "major-milestone-row";

  return `
    <article class="editor-row milestone-row ${milestoneClass}">
      <div class="editor-row-number">${index + 1}</div>

      <div class="editor-row-content">
        <div class="milestone-label">
          ${step.time ? `<span class="editor-time milestone-time">${escapeHtml(step.time)}</span>` : ""}
          <img src="${ICONS.pop}" alt="Milestone">
          ${escapeHtml(step.label || "Milestone")}
        </div>
      </div>

      <div class="row-actions">
        <button class="icon-button ${editingClass}" type="button" data-action="edit" data-index="${index}" title="Edit row">✎</button>
        <button class="icon-button" type="button" data-action="duplicate" data-index="${index}" title="Duplicate row">⧉</button>
        <button class="icon-button" type="button" data-action="up" data-index="${index}" title="Move up">↑</button>
        <button class="icon-button" type="button" data-action="down" data-index="${index}" title="Move down">↓</button>
        <button class="icon-button danger" type="button" data-action="delete" data-index="${index}" title="Delete row">×</button>
      </div>
    </article>
  `;
}

function renderStepRow(step, index) {
  const editingClass = editingIndex === index ? "editing" : "";
  const split = step.split || {
    food: 0,
    wood: 0,
    gold: 0,
    favor: 0,
    pop: "0/0"
  };

  return `
    <article class="editor-row">
      <div class="editor-row-number">${index + 1}</div>

      <div class="editor-row-content">
        <div class="editor-row-main">
          ${step.time ? `<span class="editor-time">${escapeHtml(step.time)}</span>` : ""}

          ${makeEditorPill(step.food, "food", "food")}
          ${makeEditorPill(step.wood, "wood", "wood")}
          ${makeEditorPill(step.gold, "gold", "gold")}
          ${makeEditorPill(step.favor, "favor", "favor")}

          ${step.action ? `
            <span class="editor-action">
              <img src="${ICONS.villager}" alt="Action">
              ${escapeHtml(step.action)}
            </span>
          ` : ""}
        </div>

        ${step.note ? `<span class="editor-note">${escapeHtml(step.note)}</span>` : ""}

        <div class="editor-split">
          <span><img src="${ICONS.food}" alt="Food">${escapeHtml(split.food ?? 0)}</span>
          <span><img src="${ICONS.wood}" alt="Wood">${escapeHtml(split.wood ?? 0)}</span>
          <span><img src="${ICONS.gold}" alt="Gold">${escapeHtml(split.gold ?? 0)}</span>
          <span><img src="${ICONS.favor}" alt="Favor">${escapeHtml(split.favor ?? 0)}</span>
        </div>
      </div>

      <div class="row-actions">
        <button class="icon-button ${editingClass}" type="button" data-action="edit" data-index="${index}" title="Edit row">✎</button>
        <button class="icon-button" type="button" data-action="duplicate" data-index="${index}" title="Duplicate row">⧉</button>
        <button class="icon-button" type="button" data-action="up" data-index="${index}" title="Move up">↑</button>
        <button class="icon-button" type="button" data-action="down" data-index="${index}" title="Move down">↓</button>
        <button class="icon-button danger" type="button" data-action="delete" data-index="${index}" title="Delete row">×</button>
      </div>
    </article>
  `;
}

function makeEditorPill(value, resourceClass, iconName) {
  if (!value || String(value).trim() === "") {
    return "";
  }

  return `
    <span class="editor-pill ${resourceClass}">
      <img src="${ICONS[iconName]}" alt="${resourceClass}">
      ${escapeHtml(formatArrowText(value))}
    </span>
  `;
}

function bindRowButtons() {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.action;
      const index = Number(button.dataset.index);

      if (!Number.isInteger(index)) {
        return;
      }

      if (action === "edit") {
        editRow(index);
      }

      if (action === "duplicate") {
        duplicateRow(index);
      }

      if (action === "up") {
        moveRowUp(index);
      }

      if (action === "down") {
        moveRowDown(index);
      }

      if (action === "delete") {
        removeRow(index);
      }
    });
  });
}

async function persistCurrentBuild(successText = "Saved") {
  readBuildInfoFields();

  if (!editorBuild.id) {
    editorBuild.id = slugify(editorBuild.title) || createId();
  }

  const normalizedBuild = normalizeBuild(editorBuild);
  const result = await postJson(SAVE_BUILD_URL, normalizedBuild);
  const savedBuild = normalizeBuild(result.build || normalizedBuild);
  const existingIndex = buildCollection.findIndex((build) => build.id === savedBuild.id);

  if (existingIndex >= 0) {
    buildCollection[existingIndex] = savedBuild;
  } else {
    buildCollection.push(savedBuild);
  }

  editorBuild = normalizeBuild(savedBuild);
  setBuildInfoFields(editorBuild);

  saveBuildCollection(buildCollection);
  setActiveBuildId(editorBuild.id);
  updateEditorUrl(editorBuild.id, editorBuild.sourceGodId);
  renderEditorBuildPicker();
  updateNavigationLinks();
  markEditorClean();

  const button = getElement("saveBuildButton");
  const originalText = button.textContent;

  button.textContent = successText;
  button.disabled = true;

  setTimeout(() => {
    button.textContent = originalText;
    button.disabled = false;
  }, 900);
}

async function saveBuild() {
  try {
    await persistCurrentBuild("Saved");
  } catch (error) {
    alert(`Could not save build: ${error.message}`);
    console.error(error);

    const button = getElement("saveBuildButton");
    button.textContent = "Save Build";
    button.disabled = false;
  }
}

async function createAndSwitchToNewBuild() {
  readBuildInfoFields();

  const shouldCreate = await requestUnsavedEditorNavigation({
    titleText: "Create New Build?",
    messageText: "You have unsaved changes in the current build. Save first, stay here, or create a new build without saving.",
    discardText: "Create Without Saving"
  });

  if (!shouldCreate) {
    return;
  }

  editorBuild = normalizeBuild(createNewBuild());

  setActiveBuildId(editorBuild.id);
  updateEditorUrl(editorBuild.id, editorBuild.sourceGodId);

  refreshEditorForCurrentBuild();
  markEditorClean();
  guideToBuildInfo();
}

function exportJson() {
  readBuildInfoFields();
  getElement("jsonBox").value = JSON.stringify(normalizeBuild(editorBuild), null, 2);
}

async function importJson() {
  const rawJson = getElement("jsonBox").value.trim();

  if (!rawJson) {
    alert("Paste build JSON into the box first.");
    return;
  }

  try {
    const importedBuild = normalizeBuild(JSON.parse(rawJson));
    editorBuild = importedBuild;

    // Important: persistCurrentBuild() reads from the form before saving.
    // Write imported Build Info into the form first so title/subtitle/summary/etc.
    // do not get overwritten by stale fields from the previously viewed build.
    setBuildInfoFields(editorBuild);

    await persistCurrentBuild("Imported");

    refreshEditorForCurrentBuild();
    guideToBuildInfo();

    alert("Build JSON imported and saved.");
  } catch (error) {
    alert(`Invalid JSON or save failed: ${error.message}`);
    console.error(error);
  }
}

async function resetBuild() {
  const confirmed = await requestDangerConfirmation({
    titleText: "Reset Build?",
    messageText: "Reset this build to the default Amaterasu build? This will replace the currently selected build after you save.",
    discardText: "Reset Build",
    cancelText: "Keep Current Build"
  });

  if (!confirmed) {
    return;
  }

  const currentId = editorBuild.id;
  const sourceGodId = editorBuild.sourceGodId || getRequestedGodId() || DEFAULT_BUILD.sourceGodId;
  const sourcePantheonId = editorBuild.sourcePantheonId || pantheonIdForGod(sourceGodId) || DEFAULT_BUILD.sourcePantheonId;

  editorBuild = normalizeBuild({
    ...clone(DEFAULT_BUILD),
    id: currentId,
    sourceGodId,
    sourcePantheonId,
    portrait: godPortraitPath(sourceGodId)
  });

  setBuildInfoFields(editorBuild);
  clearComposer();
  renderRowsList();
  updateNavigationLinks();
}

function toNonNegativeNumber(value) {
  const number = Number(value);

  if (!Number.isFinite(number) || number < 0) {
    return 0;
  }

  return number;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function clearOldBuildLocalStorage() {
  localStorage.removeItem(STORAGE_BUILDS_KEY);
  localStorage.removeItem(LEGACY_STORAGE_KEY);
}

function bindPageEvents() {
  getElement("editorBuildPickerSelect").addEventListener("change", handleEditorBuildPickerChange);

  getElement("stepModeButton").addEventListener("click", () => setComposerMode("step"));
  getElement("milestoneModeButton").addEventListener("click", () => setComposerMode("milestone"));

  getElement("addRowButton").addEventListener("click", addOrUpdateRow);
  getElement("clearComposerButton").addEventListener("click", clearComposer);

  getElement("clearRowsButton").addEventListener("click", clearRows);

  getElement("newBuildButton").addEventListener("click", createAndSwitchToNewBuild);
  getElement("duplicateBuildButton").addEventListener("click", duplicateCurrentBuild);
  getElement("deleteBuildButton").addEventListener("click", deleteCurrentBuild);
  getElement("saveBuildButton").addEventListener("click", saveBuild);
  getElement("exportJsonButton").addEventListener("click", exportJson);
  getElement("importJsonButton").addEventListener("click", importJson);
  getElement("resetButton").addEventListener("click", resetBuild);
}

function initEditorPage() {
  clearOldBuildLocalStorage();

  const shouldGuideToBuildInfo = isCreateNewMode();

  editorBuild = loadInitialEditorBuild();

  setBuildInfoFields(editorBuild);
  renderEditorBuildPicker();
  setComposerMode("step");
  bindPageEvents();
  bindUnsavedNavigationGuard();
  renderRowsList();
  updateNavigationLinks();
  markEditorClean();

  if (shouldGuideToBuildInfo) {
    guideToBuildInfo();
  }
}

initEditorPage();