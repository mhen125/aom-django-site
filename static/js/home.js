const AOM_DATA = window.AOM_DATA || {};
const pantheons = Array.isArray(AOM_DATA.pantheons) ? AOM_DATA.pantheons : [];

const selectionSection = document.getElementById("selectionSection");
const selectionEyebrow = document.getElementById("selectionEyebrow");
const selectionHeading = document.getElementById("selection-heading");
const selectionDescription = document.getElementById("selectionDescription");
const pantheonGrid = document.getElementById("pantheonGrid");
const godGrid = document.getElementById("godGrid");
const resetSelectionButton = document.getElementById("resetSelectionButton");

let selectedPantheonId = null;
let isTransitioning = false;
let carouselIndex = 0;
let carouselWheelLocked = false;

function getUrlParam(name) {
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getPantheonId(pantheon) {
  return pantheon.id || "";
}

function getPantheonName(pantheon) {
  return pantheon.name || pantheon.title || "Pantheon";
}

function getPantheonDescription(pantheon) {
  return pantheon.description || pantheon.subtitle || "Select this pantheon to view its major gods.";
}

function getPantheonIcon(pantheon) {
  return (
    pantheon.icon ||
    pantheon.image ||
    pantheon.iconPath ||
    pantheon.badge ||
    pantheon.logo ||
    pantheon.pantheonIcon ||
    ""
  );
}

function getPantheonBackground(pantheon) {
  return (
    pantheon.background ||
    pantheon.backgroundImage ||
    pantheon.bg ||
    ""
  );
}

function getPantheonGods(pantheon) {
  if (Array.isArray(pantheon.gods)) {
    return pantheon.gods;
  }

  if (Array.isArray(pantheon.majorGods)) {
    return pantheon.majorGods;
  }

  if (Array.isArray(pantheon.major_gods)) {
    return pantheon.major_gods;
  }

  return [];
}

function getGodId(god) {
  return god.id || god.slug || "";
}

function getGodName(god) {
  return god.name || god.title || "Major God";
}

const STATIC_URL = window.AOM_STATIC_URL || "/static/";

function staticPath(path) {
  return `${STATIC_URL}${String(path).replace(/^\/+/, "")}`;
}

function normalizeStaticAssetPath(path) {
  const value = String(path || "").trim();

  if (!value) {
    return "";
  }

  if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("data:")) {
    return value;
  }

  if (value.startsWith(STATIC_URL)) {
    return value;
  }

  if (value.startsWith("/static/")) {
    return value;
  }

  return staticPath(value);
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

function pictureMarkup({ imagePath, optimizedPath, className, altText }) {
  const fallback = normalizeStaticAssetPath(imagePath);

  if (!fallback) {
    return "";
  }

  if (!optimizedPath) {
    return `<img class="${className}" src="${escapeHtml(fallback)}" alt="${escapeHtml(altText)}">`;
  }

  return `
    <picture>
      <source srcset="${escapeHtml(optimizedPath)}" type="image/webp">
      <img class="${className}" src="${escapeHtml(fallback)}" alt="${escapeHtml(altText)}">
    </picture>
  `;
}

function godCardPortraitPath(godId) {
  return staticPath(`assets/images/gods/${godId}_portrait.png`);
}

function godHeroPortraitPath(godId) {
  return staticPath(`assets/images/gods/${godId}_breakoutportrait.png`);
}

function godCardBackgroundValue(godId) {
  const sourcePath = godCardPortraitPath(godId);
  return imageSetValue(sourcePath, optimizedAssetPath(sourcePath, ".card"));
}

function godHeroBackgroundValue(godId) {
  const sourcePath = godHeroPortraitPath(godId);
  return imageSetValue(sourcePath, optimizedAssetPath(sourcePath, ".hero"));
}

function themedBackgroundValue(path) {
  const sourcePath = normalizeStaticAssetPath(path);
  return imageSetValue(sourcePath, optimizedAssetPath(sourcePath));
}

function buildUrl(godId) {
  return `/gods/${encodeURIComponent(godId)}/`;
}

function findPantheonById(pantheonId) {
  return pantheons.find((pantheon) => getPantheonId(pantheon) === pantheonId) || null;
}

function circularDistance(indexA, indexB, length) {
  const direct = Math.abs(indexA - indexB);
  return Math.min(direct, length - direct);
}

function shortestCarouselOffset(index, activeIndex, length) {
  let offset = index - activeIndex;

  if (offset > length / 2) {
    offset -= length;
  }

  if (offset < -length / 2) {
    offset += length;
  }

  return offset;
}

function createPantheonCard(pantheon, index) {
  const card = document.createElement("button");

  const pantheonId = getPantheonId(pantheon);
  const pantheonName = getPantheonName(pantheon);
  const pantheonDescription = getPantheonDescription(pantheon);
  const iconPath = getPantheonIcon(pantheon);

  card.className = "pantheon-card carousel-slide";
  card.type = "button";
  card.dataset.pantheonId = pantheonId;
  card.dataset.carouselIndex = String(index);
  card.setAttribute("aria-label", `Select ${pantheonName} pantheon`);
  card.title = pantheonDescription;

  card.innerHTML = `
    <div class="carousel-pantheon-visual">
      ${
        iconPath
          ? pictureMarkup({
              imagePath: iconPath,
              optimizedPath: optimizedAssetPath(iconPath, ".emblem"),
              className: "carousel-pantheon-img",
              altText: `${pantheonName} icon`,
            })
          : `<div class="carousel-pantheon-img carousel-pantheon-img-fallback" aria-hidden="true"></div>`
      }
    </div>

    <div class="nameplate carousel-pantheon-nameplate">
      <span>${escapeHtml(pantheonName)}</span>
    </div>
  `;

  card.addEventListener("click", () => {
    if (isTransitioning) {
      return;
    }

    if (index !== carouselIndex) {
      setCarouselIndex(index);
      return;
    }

    selectPantheon(pantheonId);
  });

  return card;
}

function createGodCard(god, index) {
  const card = document.createElement("button");

  const godId = getGodId(god);
  const godName = getGodName(god);

  card.className = "god-card";
  card.type = "button";
  card.style.animationDelay = `${index * 75}ms`;
  card.dataset.godId = godId;
  card.dataset.heroImage = godHeroPortraitPath(godId);
  card.setAttribute("aria-label", `View build orders for ${godName}`);

  card.innerHTML = `
    <div class="god-icon-shell">
      <div class="god-art" style="background-image: ${escapeHtml(godCardBackgroundValue(godId))};"></div>
      <div class="god-frame" aria-hidden="true"></div>
    </div>

    <div class="nameplate god-nameplate">
      <span>${escapeHtml(godName)}</span>
    </div>
  `;

  card.addEventListener("click", () => {
    window.location.href = buildUrl(godId);
  });

  return card;
}

function updateCarouselState() {
  const slides = Array.from(document.querySelectorAll(".carousel-slide"));

  if (slides.length === 0) {
    return;
  }

  slides.forEach((slide, index) => {
    const offset = shortestCarouselOffset(index, carouselIndex, slides.length);
    const distance = circularDistance(index, carouselIndex, slides.length);

    slide.dataset.offset = String(offset);
    slide.style.setProperty("--offset", offset);
    slide.style.setProperty("--distance", distance);
    slide.style.setProperty("--roll-delay", `${Math.min(distance, 3) * 95}ms`);

    slide.classList.toggle("active", index === carouselIndex);
    slide.classList.toggle("near", distance === 1);
    slide.classList.toggle("far", distance > 1);

    slide.setAttribute("aria-hidden", index === carouselIndex ? "false" : "true");
    slide.tabIndex = index === carouselIndex ? 0 : -1;
  });

  const activePantheon = pantheons[carouselIndex];

  if (activePantheon && !selectedPantheonId) {
    const backgroundPath = getPantheonBackground(activePantheon);

    if (backgroundPath) {
      selectionSection.style.setProperty("--pantheon-bg", themedBackgroundValue(backgroundPath));
      selectionSection.classList.add("has-pantheon-bg");
    } else {
      selectionSection.style.removeProperty("--pantheon-bg");
      selectionSection.classList.remove("has-pantheon-bg");
    }
  }
}

function setCarouselIndex(index) {
  if (pantheons.length === 0) {
    carouselIndex = 0;
    return;
  }

  carouselIndex = (index + pantheons.length) % pantheons.length;
  updateCarouselState();
}

function moveCarousel(direction) {
  setCarouselIndex(carouselIndex + direction);
}

function renderPantheonCarouselControls() {
  const controls = document.createElement("div");
  controls.className = "pantheon-carousel-controls";

  controls.innerHTML = `
    <button class="pantheon-carousel-button pantheon-carousel-button-back" type="button" data-carousel-action="prev" aria-label="Previous pantheon"></button>
    <button class="pantheon-carousel-button pantheon-carousel-button-forward" type="button" data-carousel-action="next" aria-label="Next pantheon"></button>
  `;

  controls.querySelector("[data-carousel-action='prev']").addEventListener("click", () => {
    moveCarousel(-1);
  });

  controls.querySelector("[data-carousel-action='next']").addEventListener("click", () => {
    moveCarousel(1);
  });

  return controls;
}

function bindCarouselWheelControls() {
  const viewport = document.querySelector(".pantheon-carousel-viewport");

  if (!viewport) {
    return;
  }

  viewport.addEventListener(
    "wheel",
    (event) => {
      if (selectedPantheonId || isTransitioning) {
        return;
      }

      event.preventDefault();

      if (carouselWheelLocked) {
        return;
      }

      const primaryDelta =
        Math.abs(event.deltaX) > Math.abs(event.deltaY)
          ? event.deltaX
          : event.deltaY;

      if (Math.abs(primaryDelta) < 8) {
        return;
      }

      carouselWheelLocked = true;
      moveCarousel(primaryDelta > 0 ? 1 : -1);

      window.setTimeout(() => {
        carouselWheelLocked = false;
      }, 240);
    },
    { passive: false }
  );
}

function mountCarouselWithRollout() {
  if (!pantheonGrid) {
    return;
  }

  pantheonGrid.classList.remove("carousel-mounted");
  pantheonGrid.classList.add("carousel-rollout");

  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      pantheonGrid.classList.add("carousel-mounted");

      window.setTimeout(() => {
        pantheonGrid.classList.remove("carousel-rollout");
      }, 1100);
    });
  });
}

function mountGodGridWithRollout() {
  if (!godGrid) {
    return;
  }

  const cards = Array.from(godGrid.querySelectorAll(".god-card"));

  if (cards.length === 0) {
    return;
  }

  godGrid.classList.remove("god-grid-mounted");
  godGrid.classList.add("god-grid-rollout");

  window.requestAnimationFrame(() => {
    const gridRect = godGrid.getBoundingClientRect();
    const centerX = gridRect.left + gridRect.width / 2;
    const centerY = gridRect.top + gridRect.height / 2;

    let sourceCard = null;
    let sourceDistance = Number.POSITIVE_INFINITY;

    cards.forEach((card) => {
      card.classList.remove("god-source");

      const cardRect = card.getBoundingClientRect();
      const cardCenterX = cardRect.left + cardRect.width / 2;
      const cardCenterY = cardRect.top + cardRect.height / 2;

      const rollX = centerX - cardCenterX;
      const rollY = centerY - cardCenterY;
      const distance = Math.hypot(rollX, rollY);

      card.style.setProperty("--god-roll-x", `${rollX}px`);
      card.style.setProperty("--god-roll-y", `${rollY}px`);
      card.style.setProperty("--god-roll-delay", `${Math.min(distance / 3.5, 240)}ms`);

      if (distance < sourceDistance) {
        sourceDistance = distance;
        sourceCard = card;
      }
    });

    if (sourceCard) {
      sourceCard.classList.add("god-source");
      sourceCard.style.setProperty("--god-roll-delay", "0ms");
    }

    window.requestAnimationFrame(() => {
      godGrid.classList.add("god-grid-mounted");

      window.setTimeout(() => {
        godGrid.classList.remove("god-grid-rollout");
      }, 1250);
    });
  });
}

function renderPantheons() {
  if (!pantheonGrid) {
    return;
  }

  pantheonGrid.innerHTML = "";
  pantheonGrid.classList.add("pantheon-carousel");
  pantheonGrid.classList.remove("carousel-mounted");

  const viewport = document.createElement("div");
  viewport.className = "pantheon-carousel-viewport";

  const track = document.createElement("div");
  track.className = "pantheon-carousel-track";

  pantheons.forEach((pantheon, index) => {
    track.appendChild(createPantheonCard(pantheon, index));
  });

  viewport.appendChild(track);
  pantheonGrid.appendChild(viewport);
  pantheonGrid.appendChild(renderPantheonCarouselControls());

  updateCarouselState();
  bindCarouselWheelControls();
  mountCarouselWithRollout();
}

function renderGods(pantheon) {
  if (!godGrid) {
    return;
  }

  const gods = getPantheonGods(pantheon);

  godGrid.innerHTML = "";
  godGrid.classList.remove("god-grid-mounted", "god-grid-rollout");

  gods.forEach((god, index) => {
    godGrid.appendChild(createGodCard(god, index));
  });
}

function selectPantheon(pantheonId) {
  const pantheon = findPantheonById(pantheonId);

  if (!pantheon || !selectionSection || !pantheonGrid || !godGrid) {
    return;
  }

  selectedPantheonId = pantheonId;
  isTransitioning = true;

  const pantheonName = getPantheonName(pantheon);
  const backgroundPath = getPantheonBackground(pantheon);

  if (backgroundPath) {
    selectionSection.style.setProperty("--pantheon-bg", themedBackgroundValue(backgroundPath));
    selectionSection.classList.add("has-pantheon-bg");
  } else {
    selectionSection.style.removeProperty("--pantheon-bg");
    selectionSection.classList.remove("has-pantheon-bg");
  }

  selectionSection.classList.add("god-selection-active");

  if (selectionEyebrow) {
    selectionEyebrow.textContent = `${pantheonName} Pantheon`;
  }

  if (selectionHeading) {
    selectionHeading.textContent = "Choose a Major God";
  }

  if (selectionDescription) {
    selectionDescription.textContent = "Select a major god to view build orders, openings, and strategy notes.";
  }

  if (resetSelectionButton) {
    resetSelectionButton.classList.remove("hidden");
  }

  pantheonGrid.classList.add("leaving");

  window.setTimeout(() => {
    pantheonGrid.classList.add("hidden");
    pantheonGrid.classList.remove("leaving");

    renderGods(pantheon);

    godGrid.classList.remove("hidden");
    godGrid.classList.add("entering");

    mountGodGridWithRollout();

    window.setTimeout(() => {
      godGrid.classList.remove("entering");
      isTransitioning = false;
    }, 620);
  }, 260);
}

function clearSelection() {
  if (isTransitioning || !selectionSection || !pantheonGrid || !godGrid) {
    return;
  }

  selectedPantheonId = null;
  isTransitioning = true;

  if (selectionEyebrow) {
    selectionEyebrow.textContent = "Pantheon Selection";
  }

  if (selectionHeading) {
    selectionHeading.textContent = "Choose a Pantheon";
  }

  if (selectionDescription) {
    selectionDescription.textContent = "Select a pantheon to reveal its major gods.";
  }

  if (resetSelectionButton) {
    resetSelectionButton.classList.add("hidden");
  }

  selectionSection.classList.remove("god-selection-active");
  godGrid.classList.add("leaving");

  window.setTimeout(() => {
    godGrid.classList.add("hidden");
    godGrid.classList.remove("leaving", "god-grid-mounted", "god-grid-rollout");
    godGrid.innerHTML = "";

    pantheonGrid.classList.remove("hidden");
    pantheonGrid.classList.add("entering");
    pantheonGrid.classList.remove("carousel-mounted");

    selectedPantheonId = null;
    updateCarouselState();
    mountCarouselWithRollout();

    window.setTimeout(() => {
      pantheonGrid.classList.remove("entering");
      isTransitioning = false;
    }, 540);
  }, 260);
}

function initFromUrl() {
  const requestedPantheonId = getUrlParam("pantheon");

  if (!requestedPantheonId) {
    return;
  }

  const pantheonIndex = pantheons.findIndex((pantheon) => getPantheonId(pantheon) === requestedPantheonId);

  if (pantheonIndex < 0) {
    return;
  }

  carouselIndex = pantheonIndex;
  updateCarouselState();

  window.setTimeout(() => {
    selectPantheon(requestedPantheonId);
  }, 80);
}

function bindCarouselKeyboardControls() {
  document.addEventListener("keydown", (event) => {
    if (selectedPantheonId || isTransitioning) {
      return;
    }

    if (event.key === "ArrowLeft") {
      event.preventDefault();
      moveCarousel(-1);
    }

    if (event.key === "ArrowRight") {
      event.preventDefault();
      moveCarousel(1);
    }

    if (event.key === "Enter") {
      const activePantheon = pantheons[carouselIndex];

      if (activePantheon) {
        event.preventDefault();
        selectPantheon(getPantheonId(activePantheon));
      }
    }
  });
}

function renderHomeDataMissingState() {
  if (!pantheonGrid) {
    return;
  }

  pantheonGrid.innerHTML = `
    <div class="empty-builds">
      Build-order data did not load. Check /build_orders/data.json or static/js/data.js.
    </div>
  `;
}

function initHomePage() {
  document.body.classList.add("using-carousel");

  if (!window.AOM_DATA || !Array.isArray(window.AOM_DATA.pantheons)) {
    console.error("AOM_DATA.pantheons was not found. Make sure data.js loads before home.js.");
    renderHomeDataMissingState();
    return;
  }

  if (!selectionSection || !pantheonGrid || !godGrid) {
    console.error("Home page elements were not found. Make sure home.js is only loaded on the build-order home page.");
    return;
  }

  if (pantheons.length === 0) {
    console.error("AOM_DATA.pantheons was empty. No pantheon cards can be rendered.");
    renderHomeDataMissingState();
    return;
  }

  if (resetSelectionButton) {
    resetSelectionButton.addEventListener("click", clearSelection);
  }

  renderPantheons();
  bindCarouselKeyboardControls();
  initFromUrl();
}

initHomePage();
