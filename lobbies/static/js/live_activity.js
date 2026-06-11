(() => {
const API_BASE_URL = window.AOM_API_BASE_URL || "";

let liveActivityMap = null;
let liveRegionLayer = null;
let liveActivityLoaded = false;
let liveActivityRefreshTimer = null;
let liveActivityMapPayload = null;
let liveActivityMapRenderedAt = 0;
let liveActivityMapSeedBucket = null;
let liveActivityMapBeaconSignature = "";
const LIVE_ACTIVITY_REFRESH_MS = 15000;
const LIVE_ACTIVITY_MAP_REFRESH_MS = 120000;
const LIVE_MAP_DEV_STORAGE_KEY = "prostagmaLiveMapDevOpen";
const LIVE_MAP_BEACON_STYLE_STORAGE_KEY = "prostagmaLiveMapBeaconStyleV7";

let liveMapBeaconRerollSeed = 0;
let liveMapLastBeaconMetrics = null;
let liveMapBeaconStyle = {
  intensity: 0.40,
  size: 1.50,
  spread: 1.10,
  landBias: 1.00,
  populationBias: 0.55,
  color: "#98efff",
  regionGlowIntensity: 1.00,
  regionGlowSize: 0.80,
  regionGlowColor: "#5bdcff",
};

const LIVE_MAP_LAND_MASK = {
  canvas: null,
  context: null,
  width: 0,
  height: 0,
  ready: false,
  isLoading: false,
};

const LIVE_SERVER_AREAS = [
  { id: "us-east", label: "US East", lat: 39.0, lon: -77.0 },
  { id: "us-west", label: "US West", lat: 37.8, lon: -122.4 },
  { id: "brazil-south", label: "Brazil South", lat: -23.5, lon: -46.6 },
  { id: "europe-west", label: "West Europe", lat: 50.1, lon: 8.6 },
  { id: "europe-north", label: "North Europe", lat: 53.3, lon: -6.2 },
  { id: "asia-east", label: "East Asia", lat: 35.7, lon: 139.7 },
  { id: "australia-southeast", label: "Australia Southeast", lat: -33.9, lon: 151.2 },
];

const liveBusynessLabel = document.getElementById("liveBusynessLabel");
const liveBusynessDetail = document.getElementById("liveBusynessDetail");
const livePublicLobbies = document.getElementById("livePublicLobbies");
const livePlayersInLobbies = document.getElementById("livePlayersInLobbies");
const liveTopRegion = document.getElementById("liveTopRegion");
const liveSteamOnline = document.getElementById("liveSteamOnline");
const liveCustomLobbies = document.getElementById("liveCustomLobbies");
const liveRankedLobbies = document.getElementById("liveRankedLobbies");
const liveJoinableLobbies = document.getElementById("liveJoinableLobbies");
const liveRegionsList = document.getElementById("liveRegionsList");
const liveModesList = document.getElementById("liveModesList");
const liveActivityMapElement = document.getElementById("liveActivityMap");
const liveEarthNightImage = document.getElementById("liveEarthNightImage");
const liveMapDevPanel = document.getElementById("liveMapDevPanel");
const liveMapDevToggle = document.getElementById("liveMapDevToggle");
const liveMapDevSource = document.getElementById("liveMapDevSource");
const liveMapDevExpected = document.getElementById("liveMapDevExpected");
const liveMapDevDrawn = document.getElementById("liveMapDevDrawn");
const liveMapDevTracked = document.getElementById("liveMapDevTracked");
const liveMapDevSteam = document.getElementById("liveMapDevSteam");
const liveMapDevLand = document.getElementById("liveMapDevLand");
const liveMapDevWater = document.getElementById("liveMapDevWater");
const liveMapDevRegions = document.getElementById("liveMapDevRegions");
const liveMapBeaconIntensity = document.getElementById("liveMapBeaconIntensity");
const liveMapBeaconSize = document.getElementById("liveMapBeaconSize");
const liveMapBeaconSpread = document.getElementById("liveMapBeaconSpread");
const liveMapBeaconLandBias = document.getElementById("liveMapBeaconLandBias");
const liveMapBeaconPopulationBias = document.getElementById("liveMapBeaconPopulationBias");
const liveMapBeaconColor = document.getElementById("liveMapBeaconColor");
const liveMapRegionGlowIntensity = document.getElementById("liveMapRegionGlowIntensity");
const liveMapRegionGlowSize = document.getElementById("liveMapRegionGlowSize");
const liveMapRegionGlowColor = document.getElementById("liveMapRegionGlowColor");
const liveMapDevControlValues = {
  intensity: document.getElementById("liveMapBeaconIntensityValue"),
  size: document.getElementById("liveMapBeaconSizeValue"),
  spread: document.getElementById("liveMapBeaconSpreadValue"),
  landBias: document.getElementById("liveMapBeaconLandBiasValue"),
  populationBias: document.getElementById("liveMapBeaconPopulationBiasValue"),
  color: document.getElementById("liveMapBeaconColorValue"),
  regionGlowIntensity: document.getElementById("liveMapRegionGlowIntensityValue"),
  regionGlowSize: document.getElementById("liveMapRegionGlowSizeValue"),
  regionGlowColor: document.getElementById("liveMapRegionGlowColorValue"),
};
const liveMapBeaconReset = document.getElementById("liveMapBeaconReset");
const liveMapBeaconReroll = document.getElementById("liveMapBeaconReroll");

async function loadLiveActivity(forceRefresh = false) {
  if (!liveBusynessLabel) {
    return;
  }

  const params = new URLSearchParams();

  if (forceRefresh) {
    params.set("refresh", "1");
  }

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/activity/live${query ? `?${query}` : ""}`);

  if (!response.ok) {
    throw new Error(`Live activity request failed: ${response.status}`);
  }

  const payload = await response.json();
  liveActivityLoaded = true;
  renderLiveActivity(payload);
}

function formatLiveNumber(value) {
  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return value ?? "-";
  }

  return numberValue.toLocaleString();
}

function getLiveNumber(value) {
  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return 0;
  }

  return numberValue;
}

function getLiveSummaryValue(summary, keys, fallback = 0) {
  for (const key of keys) {
    const value = summary?.[key];
    const numberValue = Number(value);

    if (Number.isFinite(numberValue)) {
      return numberValue;
    }
  }

  return fallback;
}

function getClientMapRegion() {
  return { id: "world", label: "Worldwide", lat: 18.0, lon: 8.0 };
}

function getLiveMapRegions(payload) {
  const regions = Array.isArray(payload?.regions) ? payload.regions : [];

  if (regions.length > 1) {
    return regions;
  }

  return LIVE_SERVER_AREAS.map((region) => ({
    ...region,
    isServerArea: true,
  }));
}

function getQueueNumber(queue, key) {
  return getLiveNumber(queue?.[key]);
}

function renderLiveActivity(payload) {
  if (!payload) {
    return;
  }

  const liveSummary = payload.summary || {};
  const queue = payload.queue || {};
  const lobbyNumbers = payload.lobbyNumbers || {};

  const steamOnline = getLiveSummaryValue(liveSummary, [
    "steamPlayersOnline",
    "steam_players_online",
    "playersOnline",
    "players_online",
  ]);

  const customGames = getLiveSummaryValue(
    liveSummary,
    ["customMatches", "customGames", "customLobbies"],
    getLiveNumber(lobbyNumbers.custom),
  );

  const rankedGames = getLiveSummaryValue(
    liveSummary,
    ["rankedMatches", "rankedGames", "rankedLobbies"],
    getLiveNumber(lobbyNumbers.ranked),
  );

  const inLobbies = getLiveSummaryValue(
    liveSummary,
    ["joinableLobbies", "openLobbies", "inLobbies"],
    getLiveNumber(lobbyNumbers.joinable),
  );

  const totalGames = getLiveSummaryValue(
    liveSummary,
    ["totalGames", "totalMatches", "trackedGames"],
    customGames + rankedGames + inLobbies,
  );

  const playersInQueue = getLiveSummaryValue(
    liveSummary,
    ["playersInQueue", "queuePlayers"],
    getQueueNumber(queue, "num_in_queue"),
  );

  const rankedPlayers = getLiveSummaryValue(
    liveSummary,
    ["rankedPlayers", "playersInRanked", "rankedVisiblePlayers"],
    rankedGames * 2,
  );

  const customPlayers = getLiveSummaryValue(
    liveSummary,
    ["customPlayers", "playersInCustom", "customVisiblePlayers"],
    Math.round(customGames * 1.35),
  );

  const lobbyPlayers = getLiveSummaryValue(
    liveSummary,
    ["lobbyPlayers", "playersWaitingInLobbies", "joinablePlayers"],
    inLobbies,
  );

  const playersInMatches = getLiveSummaryValue(
    liveSummary,
    ["playersInMatches", "playersInGames", "playersInLobbies"],
    rankedPlayers + customPlayers + lobbyPlayers,
  );

  const trackedPlayers = getLiveSummaryValue(
    liveSummary,
    ["totalVisiblePlayers", "estimatedVisiblePlayers", "trackedPlayers"],
    playersInMatches + playersInQueue,
  );

  const onlinePlayers = steamOnline > 0 ? steamOnline : trackedPlayers;

  if (liveBusynessLabel) {
    liveBusynessLabel.innerHTML = `<strong>${escapeHtml(formatLiveNumber(onlinePlayers))}</strong><span>players online</span>`;
  }

  if (liveBusynessDetail) {
    liveBusynessDetail.innerHTML = `
      <span><strong>${escapeHtml(formatLiveNumber(trackedPlayers))}</strong><em>players</em></span>
      <span class="live-caption-joiner">in</span>
      <span><strong>${escapeHtml(formatLiveNumber(totalGames))}</strong><em>${totalGames === 1 ? "match" : "matches"}</em></span>
    `;
  }

  if (livePublicLobbies) {
    livePublicLobbies.textContent = formatLiveNumber(totalGames);
  }

  if (livePlayersInLobbies) {
    livePlayersInLobbies.textContent = formatLiveNumber(trackedPlayers);
  }

  if (liveCustomLobbies) {
    liveCustomLobbies.textContent = formatLiveNumber(customPlayers);
  }

  if (liveRankedLobbies) {
    liveRankedLobbies.textContent = formatLiveNumber(rankedPlayers);
  }

  if (liveJoinableLobbies) {
    liveJoinableLobbies.textContent = formatLiveNumber(lobbyPlayers);
  }

  if (liveTopRegion) {
    liveTopRegion.textContent = "Worldwide";
  }

  if (liveSteamOnline) {
    liveSteamOnline.textContent = formatLiveNumber(onlinePlayers);
  }

  if (lastUpdated) {
    lastUpdated.textContent = `Last updated: ${formatTimestamp(payload.generatedAt)}`;
  }

  if (liveRegionsList) {
    liveRegionsList.innerHTML = renderActiveServerRegions({
      ...payload,
      summary: {
        ...liveSummary,
        customPlayers,
        rankedPlayers,
        lobbyPlayers,
        totalVisiblePlayers: trackedPlayers,
        totalGames,
      },
    });
  }

  if (liveModesList) {
    const quickMatch = getQueueNumber(queue, "num_quickmatch");
    const ranked = getQueueNumber(queue, "num_ranked");
    const rankedTeams = getQueueNumber(queue, "num_teamqueue");

    liveModesList.innerHTML = `
      <div class="live-list-row">
        <span>Quick Match</span>
        <strong>${escapeHtml(formatLiveNumber(quickMatch))}</strong>
      </div>
      <div class="live-list-row">
        <span>Ranked</span>
        <strong>${escapeHtml(formatLiveNumber(ranked))}</strong>
      </div>
      <div class="live-list-row">
        <span>Ranked Teams</span>
        <strong>${escapeHtml(formatLiveNumber(rankedTeams))}</strong>
      </div>
      <div class="live-list-row live-list-row-total">
        <span>Total</span>
        <strong>${escapeHtml(formatLiveNumber(playersInQueue))}</strong>
      </div>
    `;
  }

  updateLiveActivityMap({
    ...payload,
    summary: {
      ...liveSummary,
      steamPlayersOnline: onlinePlayers,
      totalVisiblePlayers: trackedPlayers,
      totalGames,
      customGames,
      rankedGames,
      inLobbies,
      customPlayers,
      rankedPlayers,
      lobbyPlayers,
    },
  });
}

function getCanvasPixelRatio() {
  return Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
}

function resizeCanvasToElement(canvas, element) {
  const pixelRatio = getCanvasPixelRatio();
  const rect = element.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));

  if (canvas.width !== Math.round(width * pixelRatio) || canvas.height !== Math.round(height * pixelRatio)) {
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
  }

  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const context = canvas.getContext("2d");
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

  return { context, width, height };
}

const LIVE_MAP_LAT_MAX = 84;
const LIVE_MAP_LAT_MIN = -58;

function projectWorldPoint(lat, lon, width, height) {
  const latitude = Number(lat);
  const longitude = Number(lon);

  const x = ((longitude + 180) / 360) * width;
  const y = ((LIVE_MAP_LAT_MAX - latitude) / (LIVE_MAP_LAT_MAX - LIVE_MAP_LAT_MIN)) * height;

  return { x, y };
}

function drawProjectedPolygon(context, width, height, points) {
  if (!points.length) {
    return;
  }

  const first = projectWorldPoint(points[0][0], points[0][1], width, height);
  context.beginPath();
  context.moveTo(first.x, first.y);

  for (const [lat, lon] of points.slice(1)) {
    const point = projectWorldPoint(lat, lon, width, height);
    context.lineTo(point.x, point.y);
  }

  context.closePath();
  context.fill();
}

function hashLiveSeed(value) {
  const text = String(value || "prostagma");
  let hash = 2166136261;

  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return hash >>> 0;
}

function createSeededRandom(seedValue) {
  let seed = hashLiveSeed(seedValue);

  return function seededRandom() {
    seed += 0x6D2B79F5;
    let next = seed;
    next = Math.imul(next ^ (next >>> 15), next | 1);
    next ^= next + Math.imul(next ^ (next >>> 7), next | 61);
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296;
  };
}

function randomNormal(random) {
  const u = Math.max(random(), 0.000001);
  const v = Math.max(random(), 0.000001);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function drawLiveWorldBase(context, width, height) {
  const oceanGradient = context.createLinearGradient(0, 0, 0, height);
  oceanGradient.addColorStop(0, "#071324");
  oceanGradient.addColorStop(0.46, "#102c41");
  oceanGradient.addColorStop(0.78, "#1b5a72");
  oceanGradient.addColorStop(1, "#07111d");

  context.fillStyle = oceanGradient;
  context.fillRect(0, 0, width, height);

  context.save();
  context.globalCompositeOperation = "screen";
  const lowerHaze = context.createRadialGradient(
    width * 0.5,
    height * 0.84,
    width * 0.04,
    width * 0.5,
    height * 0.86,
    width * 0.76,
  );
  lowerHaze.addColorStop(0, "rgba(108, 215, 239, 0.24)");
  lowerHaze.addColorStop(0.42, "rgba(70, 156, 190, 0.13)");
  lowerHaze.addColorStop(1, "rgba(70, 156, 190, 0)");
  context.fillStyle = lowerHaze;
  context.fillRect(0, 0, width, height);
  context.restore();

  context.save();
  context.globalAlpha = 0.62;
  context.fillStyle = "#122533";

  const continents = [
    [[72, -168], [67, -151], [59, -140], [54, -124], [49, -124], [42, -122], [33, -117], [25, -108], [19, -100], [16, -91], [20, -82], [28, -81], [34, -88], [40, -75], [46, -67], [55, -61], [63, -82], [71, -110]],
    [[14, -82], [9, -76], [3, -71], [-7, -67], [-17, -63], [-30, -58], [-44, -68], [-54, -72], [-44, -76], [-27, -75], [-11, -80]],
    [[72, -12], [68, 20], [59, 40], [52, 68], [56, 98], [61, 132], [50, 158], [34, 146], [22, 112], [8, 88], [17, 72], [27, 60], [31, 38], [37, 20], [44, 8], [52, -6]],
    [[37, -17], [31, 5], [16, 18], [3, 29], [-13, 31], [-29, 24], [-35, 8], [-23, -3], [-4, -9], [18, -16]],
    [[25, 42], [20, 60], [7, 77], [22, 90], [31, 80], [31, 58]],
    [[-11, 112], [-25, 115], [-39, 139], [-31, 154], [-18, 146]],
    [[61, -51], [72, -42], [77, -23], [68, -18], [59, -36]],
  ];

  for (const continent of continents) {
    drawProjectedPolygon(context, width, height, continent);
  }
  context.restore();

  context.save();
  context.globalCompositeOperation = "screen";
  context.strokeStyle = "rgba(142, 226, 246, 0.08)";
  context.lineWidth = Math.max(1, width * 0.0011);

  for (const continent of continents) {
    const first = projectWorldPoint(continent[0][0], continent[0][1], width, height);
    context.beginPath();
    context.moveTo(first.x, first.y);

    for (const [lat, lon] of continent.slice(1)) {
      const point = projectWorldPoint(lat, lon, width, height);
      context.lineTo(point.x, point.y);
    }

    context.closePath();
    context.stroke();
  }
  context.restore();

  context.save();
  context.globalAlpha = 0.13;
  context.strokeStyle = "rgba(177, 226, 239, 0.18)";
  context.lineWidth = 1;

  for (let lon = -120; lon <= 120; lon += 60) {
    const start = projectWorldPoint(-70, lon, width, height);
    const end = projectWorldPoint(76, lon, width, height);
    context.beginPath();
    context.moveTo(start.x, start.y);
    context.lineTo(end.x, end.y);
    context.stroke();
  }

  for (let lat = -45; lat <= 60; lat += 35) {
    const start = projectWorldPoint(lat, -180, width, height);
    const end = projectWorldPoint(lat, 180, width, height);
    context.beginPath();
    context.moveTo(start.x, start.y);
    context.lineTo(end.x, end.y);
    context.stroke();
  }
  context.restore();

  context.save();
  context.globalAlpha = 0.08;
  context.fillStyle = "#ffffff";
  const scanlineGap = Math.max(5, Math.round(height / 78));
  for (let y = 0; y < height; y += scanlineGap) {
    context.fillRect(0, y, width, 1);
  }
  context.restore();
}

function drawNightLight(context, x, y, radius, alpha, color = "168, 230, 255") {
  context.save();
  context.globalCompositeOperation = "screen";

  const glow = context.createRadialGradient(x, y, 0, x, y, radius * 8);
  glow.addColorStop(0, `rgba(234, 251, 255, ${alpha})`);
  glow.addColorStop(0.28, `rgba(${color}, ${alpha * 0.52})`);
  glow.addColorStop(1, `rgba(${color}, 0)`);
  context.fillStyle = glow;
  context.beginPath();
  context.arc(x, y, radius * 8, 0, Math.PI * 2);
  context.fill();

  context.fillStyle = `rgba(228, 250, 255, ${Math.min(0.92, alpha + 0.22)})`;
  context.beginPath();
  context.arc(x, y, Math.max(0.75, radius), 0, Math.PI * 2);
  context.fill();

  context.restore();
}

function getRegionActivityWeights(mapRegions) {
  const defaultWeights = {
    "us-east": 0.26,
    "us-west": 0.16,
    "brazil": 0.07,
    "brazil-south": 0.07,
    "europe": 0.25,
    "europe-west": 0.17,
    "europe-north": 0.08,
    "asia": 0.15,
    "asia-east": 0.15,
    "australia": 0.05,
    "australia-southeast": 0.05,
  };

  const regions = mapRegions.map((region) => {
    const players = getLiveNumber(region.players);
    const lobbies = getLiveNumber(region.lobbies);
    const idWeight = defaultWeights[region.id] ?? 0.08;
    const activityWeight = players > 0 || lobbies > 0 ? players + lobbies * 2 : idWeight * 100;

    return {
      ...region,
      players,
      lobbies,
      activityWeight,
    };
  });

  const totalWeight = regions.reduce((total, region) => total + region.activityWeight, 0) || 1;

  return regions.map((region) => ({
    ...region,
    activityShare: region.activityWeight / totalWeight,
  }));
}

function renderActiveServerRegions(payload) {
  const weightedRegions = getRegionActivityWeights(getLiveMapRegions(payload))
    .filter((region) => region.id !== "unknown")
    .sort((a, b) => b.activityWeight - a.activityWeight)
    .slice(0, 5);

  if (!weightedRegions.length) {
    return `<div class="muted">No region activity available yet.</div>`;
  }

  return weightedRegions
    .map((region, index) => {
      const percent = Math.max(3, Math.round((region.activityShare || 0) * 100));
      const label = region.label || region.id || "Server region";
      const rank = String(index + 1).padStart(2, "0");

      return `
        <div class="live-region-row">
          <span class="live-region-rank">${escapeHtml(rank)}</span>
          <span class="live-region-name">${escapeHtml(label)}</span>
          <div class="live-region-meter" aria-hidden="true">
            <i style="width: ${percent}%"></i>
          </div>
          <strong class="live-region-percent">${escapeHtml(String(percent))}%</strong>
        </div>
      `;
    })
    .join("");
}

const LIVE_REGION_ACTIVITY_AREAS = {
  "us-east": [
    { lat: 40.7, lon: -74.0, weight: 1.25, spreadLat: 1.55, spreadLon: 2.45, looseSpreadLat: 2.8, looseSpreadLon: 4.8 },
    { lat: 38.9, lon: -77.0, weight: 0.72, spreadLat: 1.15, spreadLon: 1.95, looseSpreadLat: 2.2, looseSpreadLon: 3.7 },
    { lat: 42.4, lon: -71.0, weight: 0.58, spreadLat: 1.0, spreadLon: 1.8, looseSpreadLat: 1.9, looseSpreadLon: 3.2 },
    { lat: 33.7, lon: -84.4, weight: 0.82, spreadLat: 1.45, spreadLon: 2.25, looseSpreadLat: 2.5, looseSpreadLon: 4.1 },
    { lat: 41.9, lon: -87.6, weight: 0.82, spreadLat: 1.3, spreadLon: 2.2, looseSpreadLat: 2.3, looseSpreadLon: 4.0 },
    { lat: 29.8, lon: -95.4, weight: 0.5, spreadLat: 1.25, spreadLon: 2.0, looseSpreadLat: 2.3, looseSpreadLon: 3.8 },
    { lat: 25.8, lon: -80.2, weight: 0.35, spreadLat: 0.85, spreadLon: 1.35, looseSpreadLat: 1.5, looseSpreadLon: 2.3 },
  ],
  "us-west": [
    { lat: 34.0, lon: -118.2, weight: 1.0, spreadLat: 1.25, spreadLon: 2.0, looseSpreadLat: 2.1, looseSpreadLon: 3.7 },
    { lat: 37.8, lon: -122.4, weight: 0.9, spreadLat: 1.0, spreadLon: 1.75, looseSpreadLat: 1.9, looseSpreadLon: 3.2 },
    { lat: 47.6, lon: -122.3, weight: 0.5, spreadLat: 0.95, spreadLon: 1.55, looseSpreadLat: 1.7, looseSpreadLon: 2.7 },
    { lat: 45.5, lon: -122.7, weight: 0.28, spreadLat: 0.75, spreadLon: 1.2, looseSpreadLat: 1.4, looseSpreadLon: 2.2 },
    { lat: 36.2, lon: -115.1, weight: 0.25, spreadLat: 0.8, spreadLon: 1.4, looseSpreadLat: 1.5, looseSpreadLon: 2.4 },
  ],
  brazil: [
    { lat: -23.5, lon: -46.6, weight: 1.0, spreadLat: 1.6, spreadLon: 2.45, looseSpreadLat: 2.9, looseSpreadLon: 4.4 },
    { lat: -22.9, lon: -43.2, weight: 0.48, spreadLat: 1.05, spreadLon: 1.65, looseSpreadLat: 2.0, looseSpreadLon: 3.0 },
    { lat: -19.9, lon: -43.9, weight: 0.28, spreadLat: 0.95, spreadLon: 1.55, looseSpreadLat: 1.8, looseSpreadLon: 2.7 },
    { lat: -30.0, lon: -51.2, weight: 0.22, spreadLat: 0.9, spreadLon: 1.4, looseSpreadLat: 1.6, looseSpreadLon: 2.5 },
  ],
  "brazil-south": [
    { lat: -23.5, lon: -46.6, weight: 1.0, spreadLat: 1.6, spreadLon: 2.45, looseSpreadLat: 2.9, looseSpreadLon: 4.4 },
    { lat: -22.9, lon: -43.2, weight: 0.48, spreadLat: 1.05, spreadLon: 1.65, looseSpreadLat: 2.0, looseSpreadLon: 3.0 },
    { lat: -19.9, lon: -43.9, weight: 0.28, spreadLat: 0.95, spreadLon: 1.55, looseSpreadLat: 1.8, looseSpreadLon: 2.7 },
    { lat: -30.0, lon: -51.2, weight: 0.22, spreadLat: 0.9, spreadLon: 1.4, looseSpreadLat: 1.6, looseSpreadLon: 2.5 },
  ],
  europe: [
    { lat: 51.5, lon: -0.1, weight: 0.9, spreadLat: 1.05, spreadLon: 1.75, looseSpreadLat: 1.8, looseSpreadLon: 3.0 },
    { lat: 50.1, lon: 8.6, weight: 1.15, spreadLat: 1.35, spreadLon: 2.25, looseSpreadLat: 2.25, looseSpreadLon: 3.9 },
    { lat: 48.9, lon: 2.4, weight: 0.9, spreadLat: 1.05, spreadLon: 1.75, looseSpreadLat: 1.8, looseSpreadLon: 3.0 },
    { lat: 52.4, lon: 4.9, weight: 0.62, spreadLat: 0.9, spreadLon: 1.55, looseSpreadLat: 1.6, looseSpreadLon: 2.7 },
    { lat: 45.5, lon: 9.2, weight: 0.48, spreadLat: 0.9, spreadLon: 1.45, looseSpreadLat: 1.5, looseSpreadLon: 2.5 },
    { lat: 40.4, lon: -3.7, weight: 0.32, spreadLat: 0.95, spreadLon: 1.55, looseSpreadLat: 1.7, looseSpreadLon: 2.8 },
    { lat: 52.2, lon: 21.0, weight: 0.35, spreadLat: 0.95, spreadLon: 1.65, looseSpreadLat: 1.7, looseSpreadLon: 2.9 },
  ],
  "europe-west": [
    { lat: 51.5, lon: -0.1, weight: 0.9, spreadLat: 1.05, spreadLon: 1.75, looseSpreadLat: 1.8, looseSpreadLon: 3.0 },
    { lat: 50.1, lon: 8.6, weight: 1.15, spreadLat: 1.35, spreadLon: 2.25, looseSpreadLat: 2.25, looseSpreadLon: 3.9 },
    { lat: 48.9, lon: 2.4, weight: 0.9, spreadLat: 1.05, spreadLon: 1.75, looseSpreadLat: 1.8, looseSpreadLon: 3.0 },
    { lat: 52.4, lon: 4.9, weight: 0.62, spreadLat: 0.9, spreadLon: 1.55, looseSpreadLat: 1.6, looseSpreadLon: 2.7 },
    { lat: 45.5, lon: 9.2, weight: 0.48, spreadLat: 0.9, spreadLon: 1.45, looseSpreadLat: 1.5, looseSpreadLon: 2.5 },
  ],
  "europe-north": [
    { lat: 53.3, lon: -6.2, weight: 0.48, spreadLat: 0.75, spreadLon: 1.15, looseSpreadLat: 1.25, looseSpreadLon: 2.0 },
    { lat: 59.3, lon: 18.1, weight: 0.42, spreadLat: 0.9, spreadLon: 1.45, looseSpreadLat: 1.55, looseSpreadLon: 2.5 },
    { lat: 55.7, lon: 12.6, weight: 0.38, spreadLat: 0.75, spreadLon: 1.2, looseSpreadLat: 1.35, looseSpreadLon: 2.1 },
    { lat: 59.9, lon: 10.8, weight: 0.24, spreadLat: 0.7, spreadLon: 1.15, looseSpreadLat: 1.3, looseSpreadLon: 2.0 },
  ],
  asia: [
    { lat: 35.7, lon: 139.7, weight: 1.0, spreadLat: 1.05, spreadLon: 1.65, looseSpreadLat: 1.8, looseSpreadLon: 2.9 },
    { lat: 37.5, lon: 127.0, weight: 0.62, spreadLat: 0.75, spreadLon: 1.2, looseSpreadLat: 1.35, looseSpreadLon: 2.1 },
    { lat: 31.2, lon: 121.5, weight: 0.78, spreadLat: 1.0, spreadLon: 1.65, looseSpreadLat: 1.8, looseSpreadLon: 2.8 },
    { lat: 22.3, lon: 114.2, weight: 0.36, spreadLat: 0.75, spreadLon: 1.1, looseSpreadLat: 1.25, looseSpreadLon: 2.0 },
    { lat: 1.35, lon: 103.8, weight: 0.38, spreadLat: 0.58, spreadLon: 0.9, looseSpreadLat: 1.1, looseSpreadLon: 1.7 },
  ],
  "asia-east": [
    { lat: 35.7, lon: 139.7, weight: 1.0, spreadLat: 1.05, spreadLon: 1.65, looseSpreadLat: 1.8, looseSpreadLon: 2.9 },
    { lat: 37.5, lon: 127.0, weight: 0.62, spreadLat: 0.75, spreadLon: 1.2, looseSpreadLat: 1.35, looseSpreadLon: 2.1 },
    { lat: 31.2, lon: 121.5, weight: 0.78, spreadLat: 1.0, spreadLon: 1.65, looseSpreadLat: 1.8, looseSpreadLon: 2.8 },
    { lat: 22.3, lon: 114.2, weight: 0.36, spreadLat: 0.75, spreadLon: 1.1, looseSpreadLat: 1.25, looseSpreadLon: 2.0 },
  ],
  australia: [
    { lat: -33.9, lon: 151.2, weight: 0.9, spreadLat: 0.95, spreadLon: 1.45, looseSpreadLat: 1.7, looseSpreadLon: 2.7 },
    { lat: -37.8, lon: 144.9, weight: 0.52, spreadLat: 0.82, spreadLon: 1.25, looseSpreadLat: 1.5, looseSpreadLon: 2.4 },
    { lat: -27.5, lon: 153.0, weight: 0.26, spreadLat: 0.75, spreadLon: 1.2, looseSpreadLat: 1.4, looseSpreadLon: 2.2 },
  ],
  "australia-southeast": [
    { lat: -33.9, lon: 151.2, weight: 0.9, spreadLat: 0.95, spreadLon: 1.45, looseSpreadLat: 1.7, looseSpreadLon: 2.7 },
    { lat: -37.8, lon: 144.9, weight: 0.52, spreadLat: 0.82, spreadLon: 1.25, looseSpreadLat: 1.5, looseSpreadLon: 2.4 },
    { lat: -27.5, lon: 153.0, weight: 0.26, spreadLat: 0.75, spreadLon: 1.2, looseSpreadLat: 1.4, looseSpreadLon: 2.2 },
  ],
};

function getRegionActivityAreas(region) {
  return LIVE_REGION_ACTIVITY_AREAS[region.id] || [
    {
      lat: Number(region.lat ?? region.latitude),
      lon: Number(region.lon ?? region.lng ?? region.longitude),
      weight: 1,
      spreadLat: 2.1,
      spreadLon: 3.4,
    },
  ];
}

function chooseWeightedArea(areas, random) {
  const total = areas.reduce((sum, area) => sum + Number(area.weight || 1), 0) || 1;
  let cursor = random() * total;

  for (const area of areas) {
    cursor -= Number(area.weight || 1);

    if (cursor <= 0) {
      return area;
    }
  }

  return areas[areas.length - 1];
}

function livePointIsInBox(latitude, longitude, zone) {
  return latitude >= zone.minLat &&
    latitude <= zone.maxLat &&
    longitude >= zone.minLon &&
    longitude <= zone.maxLon;
}

function livePointIsInEllipse(latitude, longitude, zone) {
  const latRadius = Number(zone.latRadius || 1);
  const lonRadius = Number(zone.lonRadius || 1);
  const latDelta = (latitude - Number(zone.lat)) / latRadius;
  const lonDelta = (longitude - Number(zone.lon)) / lonRadius;

  return (latDelta * latDelta) + (lonDelta * lonDelta) <= 1;
}

function livePointLooksLikeLandHeuristic(lat, lon) {
  const latitude = Number(lat);
  const longitude = Number(lon);

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return false;
  }

  const landBoxes = [
    // United States / Canada / Mexico population corridors.
    { minLat: 25.0, maxLat: 49.5, minLon: -124.8, maxLon: -66.6 },
    { minLat: 29.0, maxLat: 44.5, minLon: -105.5, maxLon: -74.0 },
    { minLat: 32.0, maxLat: 48.7, minLon: -124.8, maxLon: -113.5 },
    { minLat: 18.0, maxLat: 32.8, minLon: -117.0, maxLon: -86.0 },

    // Brazil and nearby South America population corridors.
    { minLat: -34.5, maxLat: 3.5, minLon: -73.5, maxLon: -34.5 },
    { minLat: -34.0, maxLat: -14.0, minLon: -59.5, maxLon: -38.0 },

    // Europe and surrounding islands.
    { minLat: 36.0, maxLat: 61.5, minLon: -10.8, maxLon: 31.5 },
    { minLat: 49.5, maxLat: 59.5, minLon: -8.8, maxLon: 2.4 },
    { minLat: 55.0, maxLat: 63.5, minLon: 10.0, maxLon: 25.5 },

    // East Asia, Southeast Asia, and Australia.
    { minLat: 18.0, maxLat: 46.5, minLon: 103.0, maxLon: 145.8 },
    { minLat: 30.0, maxLat: 45.9, minLon: 129.0, maxLon: 146.0 },
    { minLat: 31.0, maxLat: 39.7, minLon: 124.0, maxLon: 131.5 },
    { minLat: 0.4, maxLat: 7.0, minLon: 98.5, maxLon: 105.5 },
    { minLat: -39.5, maxLat: -25.0, minLon: 141.0, maxLon: 154.0 },
  ];

  const islandAndCoastEllipses = [
    { lat: 40.7, lon: -74.0, latRadius: 4.7, lonRadius: 5.9 },
    { lat: 34.0, lon: -118.2, latRadius: 3.4, lonRadius: 5.0 },
    { lat: 47.6, lon: -122.3, latRadius: 2.9, lonRadius: 4.0 },
    { lat: 25.8, lon: -80.2, latRadius: 2.1, lonRadius: 2.4 },
    { lat: -23.5, lon: -46.6, latRadius: 5.5, lonRadius: 6.2 },
    { lat: 51.5, lon: -0.1, latRadius: 5.8, lonRadius: 4.4 },
    { lat: 50.1, lon: 8.6, latRadius: 6.6, lonRadius: 8.0 },
    { lat: 59.3, lon: 18.1, latRadius: 4.4, lonRadius: 5.5 },
    { lat: 35.7, lon: 139.7, latRadius: 4.8, lonRadius: 4.0 },
    { lat: 37.5, lon: 127.0, latRadius: 3.4, lonRadius: 3.2 },
    { lat: 31.2, lon: 121.5, latRadius: 5.4, lonRadius: 6.4 },
    { lat: 1.35, lon: 103.8, latRadius: 2.0, lonRadius: 2.1 },
    { lat: -33.9, lon: 151.2, latRadius: 4.4, lonRadius: 3.8 },
    { lat: -37.8, lon: 144.9, latRadius: 3.4, lonRadius: 3.2 },
  ];

  return landBoxes.some((zone) => livePointIsInBox(latitude, longitude, zone)) ||
    islandAndCoastEllipses.some((zone) => livePointIsInEllipse(latitude, longitude, zone));
}


function projectLiveMapPointToMaskPixel(lat, lon) {
  if (!LIVE_MAP_LAND_MASK.ready || !LIVE_MAP_LAND_MASK.width || !LIVE_MAP_LAND_MASK.height) {
    return null;
  }

  const point = projectWorldPoint(lat, lon, LIVE_MAP_LAND_MASK.width, LIVE_MAP_LAND_MASK.height);

  return {
    x: Math.max(0, Math.min(LIVE_MAP_LAND_MASK.width - 1, Math.round(point.x))),
    y: Math.max(0, Math.min(LIVE_MAP_LAND_MASK.height - 1, Math.round(point.y))),
  };
}

function liveMapPixelLooksLikeBlueWater(red, green, blue, alpha = 255) {
  if (alpha < 8) {
    return true;
  }

  /*
    The beacon base map uses dark blue for water and dark green/teal for land.
    This intentionally treats clearly blue pixels as forbidden. Land, borders,
    and coastlines are allowed; blue ocean/lake pixels are not.
  */
  const blueDominance = blue - Math.max(red, green);
  const isClearlyBlue = blueDominance >= 7 && blue >= 26;
  const isDeepOcean = blue >= 38 && green >= 18 && blue > green + 5;

  return isClearlyBlue || isDeepOcean;
}

function liveMapPixelLooksLikeLand(red, green, blue, alpha = 255) {
  return !liveMapPixelLooksLikeBlueWater(red, green, blue, alpha);
}

function liveMapMaskPointLooksLikeLand(lat, lon, sampleRadius = 1) {
  if (!LIVE_MAP_LAND_MASK.ready || !LIVE_MAP_LAND_MASK.context) {
    return null;
  }

  const pixel = projectLiveMapPointToMaskPixel(lat, lon);

  if (!pixel) {
    return null;
  }

  /*
    Hard rule: the beacon center cannot be on a blue pixel.
    A tiny neighborhood check helps avoid anti-aliased coast artifacts, but the
    center pixel must still pass so we never knowingly draw a beacon over blue.
  */
  const center = LIVE_MAP_LAND_MASK.context.getImageData(pixel.x, pixel.y, 1, 1).data;

  if (!liveMapPixelLooksLikeLand(center[0], center[1], center[2], center[3])) {
    return false;
  }

  let landSamples = 0;
  let checkedSamples = 0;

  for (let yOffset = -sampleRadius; yOffset <= sampleRadius; yOffset += 1) {
    for (let xOffset = -sampleRadius; xOffset <= sampleRadius; xOffset += 1) {
      const x = Math.max(0, Math.min(LIVE_MAP_LAND_MASK.width - 1, pixel.x + xOffset));
      const y = Math.max(0, Math.min(LIVE_MAP_LAND_MASK.height - 1, pixel.y + yOffset));
      const data = LIVE_MAP_LAND_MASK.context.getImageData(x, y, 1, 1).data;
      checkedSamples += 1;

      if (liveMapPixelLooksLikeLand(data[0], data[1], data[2], data[3])) {
        landSamples += 1;
      }
    }
  }

  return checkedSamples > 0 && landSamples / checkedSamples >= 0.42;
}

function livePointLooksLikeLand(lat, lon) {
  const maskResult = liveMapMaskPointLooksLikeLand(lat, lon, 1);

  if (maskResult !== null) {
    return maskResult;
  }

  return livePointLooksLikeLandHeuristic(lat, lon);
}

function rebuildLiveMapLandMask() {
  const image = document.getElementById("liveEarthNightImage");

  if (!image || !image.complete || !image.naturalWidth || !image.naturalHeight) {
    return false;
  }

  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;

  const context = canvas.getContext("2d", { willReadFrequently: true });

  if (!context) {
    return false;
  }

  context.drawImage(image, 0, 0, canvas.width, canvas.height);

  LIVE_MAP_LAND_MASK.canvas = canvas;
  LIVE_MAP_LAND_MASK.context = context;
  LIVE_MAP_LAND_MASK.width = canvas.width;
  LIVE_MAP_LAND_MASK.height = canvas.height;
  LIVE_MAP_LAND_MASK.ready = true;
  LIVE_MAP_LAND_MASK.isLoading = false;

  return true;
}

function initializeLiveMapLandMask() {
  const image = document.getElementById("liveEarthNightImage");

  if (!image || LIVE_MAP_LAND_MASK.ready || LIVE_MAP_LAND_MASK.isLoading) {
    return;
  }

  if (rebuildLiveMapLandMask()) {
    return;
  }

  LIVE_MAP_LAND_MASK.isLoading = true;

  image.addEventListener("load", () => {
    rebuildLiveMapLandMask();
    forceLiveActivityMapRender();
  }, { once: true });

  image.addEventListener("error", () => {
    LIVE_MAP_LAND_MASK.isLoading = false;
  }, { once: true });
}

function getLiveBeaconDistanceScore(candidateLat, candidateLon, area) {
  const latSpread = Math.max(0.35, Number(area.spreadLat || 1));
  const lonSpread = Math.max(0.35, Number(area.spreadLon || 1));
  const latDistance = (candidateLat - Number(area.lat)) / latSpread;
  const lonDistance = (candidateLon - Number(area.lon)) / lonSpread;

  return Math.sqrt((latDistance * latDistance) + (lonDistance * lonDistance));
}

function scoreLiveBeaconCandidate(candidate, area, landBias, populationBias) {
  const distanceScore = getLiveBeaconDistanceScore(candidate.lat, candidate.lon, area);
  const landScore = candidate.isLand ? 100 * landBias : -160 * landBias;
  const populationScore = -distanceScore * (10 + populationBias * 30);
  const coastForgiveness = candidate.isLand ? 0 : -24;

  return landScore + populationScore + coastForgiveness;
}

function drawServerRegionGlow(context, x, y, radius, alpha) {
  context.save();
  context.globalCompositeOperation = "screen";

  const glow = context.createRadialGradient(x, y, 0, x, y, radius);
  glow.addColorStop(0, `rgba(172, 232, 255, ${alpha})`);
  glow.addColorStop(0.36, `rgba(74, 176, 218, ${alpha * 0.42})`);
  glow.addColorStop(1, "rgba(74, 176, 218, 0)");
  context.fillStyle = glow;
  context.beginPath();
  context.arc(x, y, radius, 0, Math.PI * 2);
  context.fill();

  context.restore();
}

function drawSubtleServerRegionGlows(context, width, height, payload) {
  const glowIntensity = clampLiveMapNumber(liveMapBeaconStyle.regionGlowIntensity, 0.32, 0, 1.5);
  const glowSize = clampLiveMapNumber(liveMapBeaconStyle.regionGlowSize, 1.00, 0.35, 2.5);

  if (glowIntensity <= 0) {
    return;
  }

  const glowRgb = hexToRgbParts(liveMapBeaconStyle.regionGlowColor || "#5bdcff");
  const beaconRegions = getRegionBeaconCounts(getLiveMapRegions(payload), payload)
    .filter((region) => getLiveNumber(region.beaconCount) > 0);

  if (!beaconRegions.length) {
    return;
  }

  const totalBeacons = beaconRegions.reduce((total, region) => total + getLiveNumber(region.beaconCount), 0) || 1;

  for (const region of beaconRegions) {
    const beaconCount = getLiveNumber(region.beaconCount);
    const areas = getRegionActivityAreas(region)
      .filter((area) => Number.isFinite(Number(area.lat)) && Number.isFinite(Number(area.lon)));

    if (!areas.length) {
      continue;
    }

    const totalWeight = areas.reduce((sum, area) => sum + Number(area.weight || 1), 0) || 1;

    for (const area of areas) {
      const areaShare = Number(area.weight || 1) / totalWeight;
      const areaBeacons = beaconCount * areaShare;

      if (areaBeacons < 1.5) {
        continue;
      }

      const point = projectWorldPoint(Number(area.lat), Number(area.lon), width, height);
      const share = beaconCount / totalBeacons;
      const radius = Math.max(15, Math.min(58, 14 + Math.sqrt(areaBeacons) * 4.2)) * glowSize;
      const alpha = Math.max(0.004, Math.min(0.060, (0.010 + Math.sqrt(areaBeacons) * 0.0021 + share * 0.010) * glowIntensity));

      context.save();
      context.globalCompositeOperation = "screen";

      const glow = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
      glow.addColorStop(0, `rgba(238, 254, 255, ${alpha * 0.38})`);
      glow.addColorStop(0.38, `rgba(${glowRgb.r}, ${glowRgb.g}, ${glowRgb.b}, ${alpha})`);
      glow.addColorStop(1, `rgba(${glowRgb.r}, ${glowRgb.g}, ${glowRgb.b}, 0)`);

      context.fillStyle = glow;
      context.beginPath();
      context.arc(point.x, point.y, radius, 0, Math.PI * 2);
      context.fill();
      context.restore();
    }
  }
}

function drawAmbientCityLights(context, width, height, random) {
  const cityClusters = [
    { lat: 40.7, lon: -74.0, count: 110, spreadLon: 12, spreadLat: 5 },
    { lat: 39.7, lon: -95.0, count: 70, spreadLon: 20, spreadLat: 8 },
    { lat: 34.0, lon: -118.2, count: 54, spreadLon: 10, spreadLat: 5 },
    { lat: 32.8, lon: -96.8, count: 42, spreadLon: 12, spreadLat: 5 },
    { lat: 51.5, lon: -0.1, count: 70, spreadLon: 9, spreadLat: 5 },
    { lat: 50.1, lon: 8.6, count: 130, spreadLon: 15, spreadLat: 6 },
    { lat: 41.9, lon: 12.5, count: 44, spreadLon: 9, spreadLat: 5 },
    { lat: 35.7, lon: 139.7, count: 86, spreadLon: 8, spreadLat: 4 },
    { lat: 37.5, lon: 127.0, count: 42, spreadLon: 6, spreadLat: 3 },
    { lat: 31.2, lon: 121.5, count: 70, spreadLon: 11, spreadLat: 5 },
    { lat: 19.1, lon: 72.9, count: 58, spreadLon: 10, spreadLat: 5 },
    { lat: -23.5, lon: -46.6, count: 38, spreadLon: 10, spreadLat: 5 },
    { lat: -33.9, lon: 151.2, count: 30, spreadLon: 9, spreadLat: 4 },
  ];

  for (const cluster of cityClusters) {
    for (let index = 0; index < cluster.count; index += 1) {
      const lat = cluster.lat + randomNormal(random) * cluster.spreadLat;
      const lon = cluster.lon + randomNormal(random) * cluster.spreadLon;
      const point = projectWorldPoint(lat, lon, width, height);
      drawNightLight(context, point.x, point.y, 0.35 + random() * 0.9, 0.045 + random() * 0.09, "235, 200, 105");
    }
  }
}

function clampLiveMapNumber(value, fallback = 0, min = -Infinity, max = Infinity) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return fallback;
  }

  return Math.min(max, Math.max(min, number));
}

function loadLiveMapBeaconStyle() {
  try {
    const saved = JSON.parse(localStorage.getItem(LIVE_MAP_BEACON_STYLE_STORAGE_KEY) || "{}");

    liveMapBeaconStyle = {
      intensity: clampLiveMapNumber(saved.intensity, 0.40, 0.25, 2.5),
      size: clampLiveMapNumber(saved.size, 1.50, 0.35, 2.2),
      spread: clampLiveMapNumber(saved.spread, 1.10, 0.35, 2.2),
      landBias: clampLiveMapNumber(saved.landBias, 1.00, 0, 1),
      populationBias: clampLiveMapNumber(saved.populationBias, 0.55, 0, 1),
      color: /^#[0-9a-f]{6}$/i.test(String(saved.color || "")) ? saved.color : "#98efff",
      regionGlowIntensity: clampLiveMapNumber(saved.regionGlowIntensity, 1.00, 0, 1.5),
      regionGlowSize: clampLiveMapNumber(saved.regionGlowSize, 0.80, 0.35, 2.5),
      regionGlowColor: /^#[0-9a-f]{6}$/i.test(String(saved.regionGlowColor || "")) ? saved.regionGlowColor : "#5bdcff",
    };
  } catch (error) {
    liveMapBeaconStyle = {
      intensity: 0.40,
      size: 1.50,
      spread: 1.10,
      landBias: 1.00,
      populationBias: 0.55,
      color: "#98efff",
      regionGlowIntensity: 1.00,
      regionGlowSize: 0.80,
      regionGlowColor: "#5bdcff",
    };
  }

  if (liveMapBeaconIntensity) liveMapBeaconIntensity.value = String(liveMapBeaconStyle.intensity);
  if (liveMapBeaconSize) liveMapBeaconSize.value = String(liveMapBeaconStyle.size);
  if (liveMapBeaconSpread) liveMapBeaconSpread.value = String(liveMapBeaconStyle.spread);
  if (liveMapBeaconLandBias) liveMapBeaconLandBias.value = String(liveMapBeaconStyle.landBias);
  if (liveMapBeaconPopulationBias) liveMapBeaconPopulationBias.value = String(liveMapBeaconStyle.populationBias);
  if (liveMapBeaconColor) liveMapBeaconColor.value = liveMapBeaconStyle.color;
  if (liveMapRegionGlowIntensity) liveMapRegionGlowIntensity.value = String(liveMapBeaconStyle.regionGlowIntensity);
  if (liveMapRegionGlowSize) liveMapRegionGlowSize.value = String(liveMapBeaconStyle.regionGlowSize);
  if (liveMapRegionGlowColor) liveMapRegionGlowColor.value = liveMapBeaconStyle.regionGlowColor;
  updateLiveMapDevControlValues();
}


function formatLiveMapControlValue(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "-";
}

function updateLiveMapDevControlValues() {
  if (liveMapDevControlValues.intensity) liveMapDevControlValues.intensity.textContent = formatLiveMapControlValue(liveMapBeaconStyle.intensity);
  if (liveMapDevControlValues.size) liveMapDevControlValues.size.textContent = formatLiveMapControlValue(liveMapBeaconStyle.size);
  if (liveMapDevControlValues.spread) liveMapDevControlValues.spread.textContent = formatLiveMapControlValue(liveMapBeaconStyle.spread);
  if (liveMapDevControlValues.landBias) liveMapDevControlValues.landBias.textContent = formatLiveMapControlValue(liveMapBeaconStyle.landBias);
  if (liveMapDevControlValues.populationBias) liveMapDevControlValues.populationBias.textContent = formatLiveMapControlValue(liveMapBeaconStyle.populationBias);
  if (liveMapDevControlValues.color) liveMapDevControlValues.color.textContent = String(liveMapBeaconStyle.color || "#98efff").toUpperCase();
  if (liveMapDevControlValues.regionGlowIntensity) liveMapDevControlValues.regionGlowIntensity.textContent = formatLiveMapControlValue(liveMapBeaconStyle.regionGlowIntensity);
  if (liveMapDevControlValues.regionGlowSize) liveMapDevControlValues.regionGlowSize.textContent = formatLiveMapControlValue(liveMapBeaconStyle.regionGlowSize);
  if (liveMapDevControlValues.regionGlowColor) liveMapDevControlValues.regionGlowColor.textContent = String(liveMapBeaconStyle.regionGlowColor || "#5bdcff").toUpperCase();
}

function saveLiveMapBeaconStyle() {
  try {
    localStorage.setItem(LIVE_MAP_BEACON_STYLE_STORAGE_KEY, JSON.stringify(liveMapBeaconStyle));
  } catch (error) {
    // Ignore storage errors; controls still work for the current page session.
  }
}

function hexToRgbParts(hex) {
  const value = String(hex || "#98efff").replace("#", "");
  const safeValue = /^[0-9a-f]{6}$/i.test(value) ? value : "98efff";

  return {
    r: parseInt(safeValue.slice(0, 2), 16),
    g: parseInt(safeValue.slice(2, 4), 16),
    b: parseInt(safeValue.slice(4, 6), 16),
  };
}

function getTrackedBeaconSource(payload, regions, regionPlayerTotal) {
  if (regionPlayerTotal > 0) {
    return "region.players";
  }

  const summary = payload?.summary || {};
  const sourceKeys = [
    "totalVisiblePlayers",
    "estimatedVisiblePlayers",
    "trackedPlayers",
    "activePlayers",
    "playersInMatches",
    "playersInGames",
    "playersInLobbies",
  ];

  const sourceKey = sourceKeys.find((key) => getLiveNumber(summary[key]) > 0) || "none";
  return sourceKey === "none" || !regions.length ? "none" : `summary.${sourceKey}`;
}

function getTrackedBeaconPlayerCount(payload, regions, regionPlayerTotal) {
  if (regionPlayerTotal > 0) {
    return regionPlayerTotal;
  }

  const summary = payload?.summary || {};
  return getLiveSummaryValue(
    summary,
    [
      "totalVisiblePlayers",
      "estimatedVisiblePlayers",
      "trackedPlayers",
      "activePlayers",
      "playersInMatches",
      "playersInGames",
      "playersInLobbies",
    ],
    0,
  );
}

function createLiveMapBeaconMetrics(payload, beaconRegions, drawnBeacons = 0, landBeacons = 0, waterBeacons = 0) {
  const summary = payload?.summary || {};
  const expectedBeacons = beaconRegions.reduce((total, region) => total + getLiveNumber(region.beaconCount), 0);
  const regionPlayerTotal = beaconRegions.reduce((total, region) => total + getLiveNumber(region.players), 0);
  const trackedPlayers = getTrackedBeaconPlayerCount(payload, beaconRegions, regionPlayerTotal);
  const source = getTrackedBeaconSource(payload, beaconRegions, regionPlayerTotal);

  return {
    source,
    expectedBeacons,
    drawnBeacons,
    landBeacons,
    waterBeacons,
    landPercent: drawnBeacons > 0 ? Math.round((landBeacons / drawnBeacons) * 100) : 0,
    trackedPlayers,
    steamPlayersOnline: getLiveNumber(summary.steamPlayersOnline),
    regions: beaconRegions.map((region) => ({
      id: region.id,
      label: region.label || region.id || "Server region",
      players: getLiveNumber(region.players),
      lobbies: getLiveNumber(region.lobbies),
      share: Number(region.activityShare || 0),
      beaconCount: getLiveNumber(region.beaconCount),
    })),
  };
}

function renderLiveMapDevPanel(metrics = liveMapLastBeaconMetrics) {
  if (!liveMapDevPanel || !metrics) {
    return;
  }

  if (liveMapDevSource) liveMapDevSource.textContent = metrics.source || "unknown";
  if (liveMapDevExpected) liveMapDevExpected.textContent = formatLiveNumber(metrics.expectedBeacons || 0);
  if (liveMapDevDrawn) liveMapDevDrawn.textContent = formatLiveNumber(metrics.drawnBeacons || 0);
  if (liveMapDevTracked) liveMapDevTracked.textContent = formatLiveNumber(metrics.trackedPlayers || 0);
  if (liveMapDevSteam) liveMapDevSteam.textContent = formatLiveNumber(metrics.steamPlayersOnline || 0);
  if (liveMapDevLand) liveMapDevLand.textContent = `${formatLiveNumber(metrics.landBeacons || 0)} (${metrics.landPercent || 0}%)`;
  if (liveMapDevWater) liveMapDevWater.textContent = formatLiveNumber(metrics.waterBeacons || 0);

  if (liveMapDevRegions) {
    const total = metrics.expectedBeacons || 0;
    const regions = [...(metrics.regions || [])]
      .filter((region) => getLiveNumber(region.beaconCount) > 0)
      .sort((a, b) => getLiveNumber(b.beaconCount) - getLiveNumber(a.beaconCount));

    liveMapDevRegions.innerHTML = regions.length
      ? regions.map((region) => {
          const beacons = getLiveNumber(region.beaconCount);
          const percent = total > 0 ? Math.round((beacons / total) * 100) : Math.round((region.share || 0) * 100);

          return `
            <div class="live-map-dev-region">
              <span>${escapeHtml(region.label)}</span>
              <strong>${escapeHtml(formatLiveNumber(beacons))}</strong>
              <small>${escapeHtml(String(percent))}%</small>
            </div>
          `;
        }).join("")
      : `<div class="muted">No beacons drawn yet.</div>`;
  }
}

function isLiveMapDevEnabled() {
  const params = new URLSearchParams(window.location.search);
  return params.get("mapDev") === "1";
}

function applyLiveMapDevPanelState() {
  if (!liveMapDevPanel || !liveMapDevToggle) {
    return;
  }

  const devEnabled = isLiveMapDevEnabled();

  liveMapDevPanel.hidden = !devEnabled;
  liveMapDevPanel.classList.toggle("is-enabled", devEnabled);

  if (!devEnabled) {
    liveMapDevPanel.classList.remove("is-open");
    liveMapDevToggle.setAttribute("aria-expanded", "false");
    return;
  }

  const shouldOpen = localStorage.getItem(LIVE_MAP_DEV_STORAGE_KEY) !== "0";

  liveMapDevPanel.classList.toggle("is-open", shouldOpen);
  liveMapDevToggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
}

function setLiveMapDevPanelOpen(isOpen) {
  if (!liveMapDevPanel || !liveMapDevToggle || !isLiveMapDevEnabled()) {
    return;
  }

  liveMapDevPanel.hidden = false;
  liveMapDevPanel.classList.add("is-enabled");
  liveMapDevPanel.classList.toggle("is-open", isOpen);
  liveMapDevToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");

  try {
    localStorage.setItem(LIVE_MAP_DEV_STORAGE_KEY, isOpen ? "1" : "0");
  } catch (error) {
    // Ignore storage errors.
  }
}

function forceLiveActivityMapRender() {
  if (!liveActivityMapPayload) {
    return;
  }

  liveActivityMapRenderedAt = 0;
  updateLiveActivityMap(liveActivityMapPayload, true);
}

function bindLiveMapDevControls() {
  if (!liveMapDevPanel) {
    return;
  }

  if (!isLiveMapDevEnabled()) {
    liveMapDevPanel.hidden = true;
    liveMapDevPanel.classList.remove("is-enabled", "is-open");
    liveMapDevToggle?.setAttribute("aria-expanded", "false");
    return;
  }

  loadLiveMapBeaconStyle();
  applyLiveMapDevPanelState();

  liveMapDevToggle?.addEventListener("click", () => {
    setLiveMapDevPanelOpen(!liveMapDevPanel.classList.contains("is-open"));
  });

  const updateStyleFromControls = () => {
    liveMapBeaconStyle = {
      intensity: clampLiveMapNumber(liveMapBeaconIntensity?.value, 0.40, 0.25, 2.5),
      size: clampLiveMapNumber(liveMapBeaconSize?.value, 1.50, 0.35, 2.2),
      spread: clampLiveMapNumber(liveMapBeaconSpread?.value, 1.10, 0.35, 2.2),
      landBias: clampLiveMapNumber(liveMapBeaconLandBias?.value, 1.00, 0, 1),
      populationBias: clampLiveMapNumber(liveMapBeaconPopulationBias?.value, 0.55, 0, 1),
      color: /^#[0-9a-f]{6}$/i.test(String(liveMapBeaconColor?.value || "")) ? liveMapBeaconColor.value : "#98efff",
      regionGlowIntensity: clampLiveMapNumber(liveMapRegionGlowIntensity?.value, 1.00, 0, 1.5),
      regionGlowSize: clampLiveMapNumber(liveMapRegionGlowSize?.value, 0.80, 0.35, 2.5),
      regionGlowColor: /^#[0-9a-f]{6}$/i.test(String(liveMapRegionGlowColor?.value || "")) ? liveMapRegionGlowColor.value : "#5bdcff",
    };

    updateLiveMapDevControlValues();
    saveLiveMapBeaconStyle();
    forceLiveActivityMapRender();
  };

  [liveMapBeaconIntensity, liveMapBeaconSize, liveMapBeaconSpread, liveMapBeaconLandBias, liveMapBeaconPopulationBias, liveMapBeaconColor, liveMapRegionGlowIntensity, liveMapRegionGlowSize, liveMapRegionGlowColor]
    .filter(Boolean)
    .forEach((input) => input.addEventListener("input", updateStyleFromControls));

  liveMapBeaconReset?.addEventListener("click", () => {
    liveMapBeaconStyle = {
      intensity: 0.40,
      size: 1.50,
      spread: 1.10,
      landBias: 1.00,
      populationBias: 0.55,
      color: "#98efff",
      regionGlowIntensity: 1.00,
      regionGlowSize: 0.80,
      regionGlowColor: "#5bdcff",
    };

    if (liveMapBeaconIntensity) liveMapBeaconIntensity.value = "0.40";
    if (liveMapBeaconSize) liveMapBeaconSize.value = "1.50";
    if (liveMapBeaconSpread) liveMapBeaconSpread.value = "1.10";
    if (liveMapBeaconLandBias) liveMapBeaconLandBias.value = "1.00";
    if (liveMapBeaconPopulationBias) liveMapBeaconPopulationBias.value = "0.55";
    if (liveMapBeaconColor) liveMapBeaconColor.value = "#98efff";
    if (liveMapRegionGlowIntensity) liveMapRegionGlowIntensity.value = "1.00";
    if (liveMapRegionGlowSize) liveMapRegionGlowSize.value = "0.80";
    if (liveMapRegionGlowColor) liveMapRegionGlowColor.value = "#5bdcff";

    updateLiveMapDevControlValues();
    saveLiveMapBeaconStyle();
    forceLiveActivityMapRender();
  });

  liveMapBeaconReroll?.addEventListener("click", () => {
    liveMapBeaconRerollSeed += 1;
    liveActivityMapBeaconSignature = "";
    forceLiveActivityMapRender();
  });
}


function getRegionBeaconCounts(mapRegions, payload) {
  const regions = mapRegions.filter((region) => region.id !== "unknown");
  const regionPlayerTotal = regions.reduce((total, region) => total + getLiveNumber(region.players), 0);

  if (regionPlayerTotal > 0) {
    return getRegionActivityWeights(regions).map((region) => ({
      ...region,
      beaconCount: getLiveNumber(region.players),
    }));
  }

  const trackedPlayers = getTrackedBeaconPlayerCount(payload, regions, regionPlayerTotal);

  if (trackedPlayers <= 0 || !regions.length) {
    return getRegionActivityWeights(regions).map((region) => ({
      ...region,
      beaconCount: 0,
    }));
  }

  const weightedRegions = getRegionActivityWeights(regions);
  let remainingBeacons = Math.round(trackedPlayers);

  return weightedRegions
    .map((region, index) => {
      const isLastRegion = index === weightedRegions.length - 1;
      const beaconCount = isLastRegion
        ? remainingBeacons
        : Math.max(0, Math.round(trackedPlayers * (region.activityShare || 0)));

      remainingBeacons -= beaconCount;

      return {
        ...region,
        beaconCount,
      };
    })
    .map((region) => ({
      ...region,
      beaconCount: Math.max(0, region.beaconCount),
    }));
}


function getBeaconAreaForSlot(region, slotIndex) {
  const areas = getRegionActivityAreas(region).filter((area) =>
    Number.isFinite(Number(area.lat)) && Number.isFinite(Number(area.lon)),
  );

  if (!areas.length) {
    return null;
  }

  const random = createSeededRandom(`beacon-area:${region.id || region.label}:${slotIndex}:${liveMapBeaconRerollSeed}`);
  return chooseWeightedArea(areas, random);
}

function pullBeaconCandidateTowardLand(candidateLat, candidateLon, baseLat, baseLon) {
  /*
    Spread is allowed to try a wider position first, but land lock should win.
    When a candidate falls into water, walk it back along the same vector toward
    its population anchor. This preserves the "direction" of the spread while
    preventing high spread values from turning into ocean beacons.
  */
  const pullSteps = [0.9, 0.8, 0.68, 0.56, 0.44, 0.34, 0.25, 0.17, 0.1, 0.04, 0];

  for (const factor of pullSteps) {
    const lat = baseLat + (candidateLat - baseLat) * factor;
    const lon = baseLon + (candidateLon - baseLon) * factor;

    if (livePointLooksLikeLand(lat, lon)) {
      return { lat, lon, isLand: true, wasPulledToLand: factor < 0.999 };
    }
  }

  return null;
}


function createHardLandFallbackPoint(region, slotIndex, area) {
  const fallbackRandom = createSeededRandom(`beacon-hard-land:${region.id || region.label}:${slotIndex}:${liveMapBeaconRerollSeed}`);
  const areas = getRegionActivityAreas(region).filter((candidateArea) =>
    Number.isFinite(Number(candidateArea.lat)) &&
    Number.isFinite(Number(candidateArea.lon)) &&
    livePointLooksLikeLand(Number(candidateArea.lat), Number(candidateArea.lon)),
  );
  const safeAreas = areas.length ? areas : [area].filter(Boolean);

  for (const safeArea of safeAreas) {
    const baseLat = Number(safeArea.lat);
    const baseLon = Number(safeArea.lon);

    if (livePointLooksLikeLand(baseLat, baseLon)) {
      return { lat: baseLat, lon: baseLon, isLand: true, wasHardLockedToLand: true };
    }
  }

  /*
    Last resort: deterministic land scan near the region anchor. This keeps the
    beacon count honest without allowing blue pixels. It is intentionally slow
    only in the rare case where all normal attempts fail.
  */
  const baseLat = Number(area?.lat);
  const baseLon = Number(area?.lon);

  if (!Number.isFinite(baseLat) || !Number.isFinite(baseLon)) {
    return null;
  }

  for (let radius = 0.15; radius <= 8.0; radius += 0.18) {
    const spokes = 18 + Math.round(radius * 8);
    const offset = fallbackRandom() * Math.PI * 2;

    for (let spoke = 0; spoke < spokes; spoke += 1) {
      const angle = offset + (Math.PI * 2 * spoke) / spokes;
      const lat = baseLat + Math.sin(angle) * radius * 0.62;
      const lon = baseLon + Math.cos(angle) * radius;

      if (livePointLooksLikeLand(lat, lon)) {
        return { lat, lon, isLand: true, wasHardLockedToLand: true };
      }
    }
  }

  return null;
}

function createStableBeaconPoint(region, slotIndex, spreadScale = 1) {
  const area = getBeaconAreaForSlot(region, slotIndex);

  if (!area) {
    return null;
  }

  const baseLat = Number(area.lat);
  const baseLon = Number(area.lon);
  const landBias = clampLiveMapNumber(liveMapBeaconStyle.landBias, 1, 0, 1);
  const populationBias = clampLiveMapNumber(liveMapBeaconStyle.populationBias, 0.35, 0, 1);
  const looseSpreadLat = Number(area.looseSpreadLat || area.spreadLat || 2.1);
  const looseSpreadLon = Number(area.looseSpreadLon || area.spreadLon || 3.4);
  const tightSpreadLat = Number(area.spreadLat || looseSpreadLat);
  const tightSpreadLon = Number(area.spreadLon || looseSpreadLon);

  /*
    Spread no longer simply overrides land placement. The slider controls how far
    a beacon tries to move from its anchor, while the land guard pulls water hits
    back onto land. Pop bias narrows the base cloud before spread is applied.
  */
  const spreadLat = (looseSpreadLat + (tightSpreadLat - looseSpreadLat) * populationBias) * spreadScale;
  const spreadLon = (looseSpreadLon + (tightSpreadLon - looseSpreadLon) * populationBias) * spreadScale;
  const random = createSeededRandom(`beacon-point:${region.id || region.label}:${slotIndex}:${liveMapBeaconRerollSeed}`);
  const attempts = Math.round(54 + landBias * 126);
  const requireLand = landBias >= 0.5;
  let bestLandCandidate = null;
  let bestLandScore = -Infinity;
  let bestAnyCandidate = {
    lat: baseLat,
    lon: baseLon,
    isLand: livePointLooksLikeLand(baseLat, baseLon),
  };
  let bestAnyScore = scoreLiveBeaconCandidate(bestAnyCandidate, area, landBias, populationBias);

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const candidateLat = baseLat + randomNormal(random) * spreadLat;
    const candidateLon = baseLon + randomNormal(random) * spreadLon;
    const candidate = {
      lat: candidateLat,
      lon: candidateLon,
      isLand: livePointLooksLikeLand(candidateLat, candidateLon),
    };
    const landCandidate = candidate.isLand
      ? candidate
      : pullBeaconCandidateTowardLand(candidateLat, candidateLon, baseLat, baseLon);

    const candidateScore = scoreLiveBeaconCandidate(candidate, area, landBias, populationBias);
    if (candidateScore > bestAnyScore) {
      bestAnyCandidate = candidate;
      bestAnyScore = candidateScore;
    }

    if (landCandidate) {
      const distanceScore = getLiveBeaconDistanceScore(landCandidate.lat, landCandidate.lon, area);
      const readabilityBonus = Math.min(2.2, distanceScore) * (1.25 - populationBias);
      const landScore = scoreLiveBeaconCandidate(landCandidate, area, landBias, populationBias) + readabilityBonus;

      if (landScore > bestLandScore) {
        bestLandCandidate = landCandidate;
        bestLandScore = landScore;
      }

      if (attempt > 16 && random() < 0.18 + landBias * 0.24) {
        return landCandidate;
      }
    }
  }

  if (bestLandCandidate && (requireLand || !bestAnyCandidate.isLand)) {
    return bestLandCandidate;
  }

  if (requireLand) {
    return createHardLandFallbackPoint(region, slotIndex, area);
  }

  return bestAnyCandidate && livePointLooksLikeLand(bestAnyCandidate.lat, bestAnyCandidate.lon)
    ? { ...bestAnyCandidate, isLand: true }
    : createHardLandFallbackPoint(region, slotIndex, area);
}

function getLiveMapBeaconSignature(payload) {
  const beaconRegions = getRegionBeaconCounts(getLiveMapRegions(payload), payload);

  return beaconRegions
    .filter((region) => getLiveNumber(region.beaconCount) > 0)
    .map((region) => `${region.id || region.label}:${getLiveNumber(region.beaconCount)}`)
    .join("|");
}

function drawActivityBeacon(context, x, y, radius, alpha, style = liveMapBeaconStyle) {
  const rgb = hexToRgbParts(style.color);
  const intensity = clampLiveMapNumber(style.intensity, 1, 0.25, 2.5);
  const size = clampLiveMapNumber(style.size, 1, 0.45, 2.2);
  const adjustedRadius = radius * size;
  const adjustedAlpha = Math.min(1, alpha * intensity);

  context.save();
  context.globalCompositeOperation = "screen";

  const glowRadius = adjustedRadius * (4.2 + intensity * 1.35);
  const glow = context.createRadialGradient(x, y, 0, x, y, glowRadius);
  glow.addColorStop(0, `rgba(245, 254, 255, ${adjustedAlpha})`);
  glow.addColorStop(0.28, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${adjustedAlpha * 0.52})`);
  glow.addColorStop(1, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0)`);

  context.fillStyle = glow;
  context.beginPath();
  context.arc(x, y, glowRadius, 0, Math.PI * 2);
  context.fill();

  context.fillStyle = `rgba(238, 254, 255, ${Math.min(0.98, adjustedAlpha + 0.1)})`;
  context.beginPath();
  context.arc(x, y, Math.max(0.42, adjustedRadius * 0.78), 0, Math.PI * 2);
  context.fill();

  context.restore();
}

function drawActivityBeacons(context, width, height, payload) {
  const beaconRegions = getRegionBeaconCounts(getLiveMapRegions(payload), payload);
  const totalBeacons = beaconRegions.reduce((total, region) => total + getLiveNumber(region.beaconCount), 0);
  const intensityBoost = Math.max(0.86, Math.min(1.08, Math.log10(totalBeacons + 10) / 3.35));
  const spreadScale = clampLiveMapNumber(liveMapBeaconStyle.spread, 1.10, 0.35, 2.2);
  let drawnBeacons = 0;
  let landBeacons = 0;
  let waterBeacons = 0;

  for (const region of beaconRegions) {
    const beaconCount = getLiveNumber(region.beaconCount);

    if (beaconCount <= 0) {
      continue;
    }

    for (let index = 0; index < beaconCount; index += 1) {
      const stablePoint = createStableBeaconPoint(region, index, spreadScale);

      if (!stablePoint) {
        continue;
      }

      const random = createSeededRandom(`beacon-style:${region.id || region.label}:${index}:${liveMapBeaconRerollSeed}`);
      const point = projectWorldPoint(stablePoint.lat, stablePoint.lon, width, height);
      const radius = 0.42 + random() * 0.28;
      const alpha = Math.min(0.82, (0.52 + random() * 0.20) * intensityBoost);

      drawActivityBeacon(context, point.x, point.y, radius, alpha, liveMapBeaconStyle);
      drawnBeacons += 1;

      if (stablePoint.isLand) {
        landBeacons += 1;
      } else {
        waterBeacons += 1;
      }
    }
  }

  return createLiveMapBeaconMetrics(payload, beaconRegions, drawnBeacons, landBeacons, waterBeacons);
}

function updateLiveActivityMap(payload, force = false) {
  if (!liveActivityMapElement) {
    return;
  }

  const now = Date.now();
  const seedBucket = Math.floor(now / LIVE_ACTIVITY_MAP_REFRESH_MS);
  const mapIsStale = now - liveActivityMapRenderedAt >= LIVE_ACTIVITY_MAP_REFRESH_MS;
  const nextBeaconSignature = getLiveMapBeaconSignature(payload);
  const beaconCountsChanged = nextBeaconSignature !== liveActivityMapBeaconSignature;

  liveActivityMapPayload = payload;

  if (!force && liveActivityMapRenderedAt && !mapIsStale && !beaconCountsChanged) {
    return;
  }

  liveActivityMapRenderedAt = now;
  liveActivityMapSeedBucket = seedBucket;
  liveActivityMapBeaconSignature = nextBeaconSignature;
  renderLiveActivityMap(payload, seedBucket);
}

function renderLiveActivityMap(payload, seedBucket = liveActivityMapSeedBucket) {
  if (!liveActivityMapElement) {
    return;
  }

  const canvas = document.getElementById("liveActivityCanvas");

  if (!canvas) {
    return;
  }

  const { context, width, height } = resizeCanvasToElement(canvas, liveActivityMapElement);

  context.clearRect(0, 0, width, height);
  drawSubtleServerRegionGlows(context, width, height, payload);
  liveMapLastBeaconMetrics = drawActivityBeacons(context, width, height, payload);
  renderLiveMapDevPanel(liveMapLastBeaconMetrics);

  const edgeGradient = context.createRadialGradient(
    width * 0.5,
    height * 0.5,
    width * 0.10,
    width * 0.5,
    height * 0.5,
    width * 0.72,
  );
  edgeGradient.addColorStop(0, "rgba(0, 0, 0, 0)");
  edgeGradient.addColorStop(0.72, "rgba(0, 0, 0, 0.035)");
  edgeGradient.addColorStop(1, "rgba(0, 0, 0, 0.22)");
  context.fillStyle = edgeGradient;
  context.fillRect(0, 0, width, height);
}



function startLiveActivityAutoRefresh() {
  if (!liveActivityMapElement || liveActivityRefreshTimer) {
    return;
  }

  liveActivityRefreshTimer = window.setInterval(() => {
    loadLiveActivity(false).catch((error) => {
      console.error(error);
      renderLiveActivityError(error);
    });
  }, LIVE_ACTIVITY_REFRESH_MS);
}

function redrawLiveActivityMap() {
  if (!liveActivityLoaded || !liveActivityMapPayload) {
    return;
  }

  updateLiveActivityMap(liveActivityMapPayload, true);
}

function renderLiveActivityError(error) {
  if (liveBusynessLabel) {
    liveBusynessLabel.textContent = "Unavailable";
  }

  if (liveBusynessDetail) {
    liveBusynessDetail.textContent = error?.message || "Unable to load live activity.";
  }
}


function initializeLiveActivityRuntime() {
  if (!liveActivityMapElement) {
    return;
  }

  initializeLiveMapLandMask();
  bindLiveMapDevControls();

  window.addEventListener("resize", () => {
    window.clearTimeout(window.liveActivityResizeTimer);
    window.liveActivityResizeTimer = window.setTimeout(redrawLiveActivityMap, 180);
  });
}

function loadAndStartLiveActivity(forceRefresh = false) {
  return loadLiveActivity(forceRefresh)
    .then(() => startLiveActivityAutoRefresh())
    .catch((error) => {
      console.error(error);
      renderLiveActivityError(error);
      startLiveActivityAutoRefresh();
      throw error;
    });
}

window.ProstagmaLiveActivity = {
  load: loadLiveActivity,
  loadAndStart: loadAndStartLiveActivity,
  startAutoRefresh: startLiveActivityAutoRefresh,
  redraw: redrawLiveActivityMap,
  renderError: renderLiveActivityError,
  isLoaded: () => liveActivityLoaded,
};

initializeLiveActivityRuntime();

if (document.body?.dataset.page === "live-activity") {
  loadAndStartLiveActivity(false).catch(() => {});
}
})();
