const API_BASE_URL = window.AOM_API_BASE_URL || "";
const STATIC_URL = window.AOM_STATIC_URL || "/static/";
const ACTIVE_MATCHES_SCRIPT_URL = window.AOM_ACTIVE_MATCHES_SCRIPT_URL || "";

const MAP_ICON_BASE_PATHS = [`${STATIC_URL}map-icons`];

const OPTIMIZED_MAP_ICON_BASE_PATHS = [`${STATIC_URL}assets/optimized/map-icons`];

const MAP_IMAGE_BASE_PATHS = [
  ...OPTIMIZED_MAP_ICON_BASE_PATHS,
  ...MAP_ICON_BASE_PATHS,
];

const AVAILABLE_MAP_ICON_FILENAMES = new Set([
  "acropolis",
  "air",
  "alfheim",
  "all_maps",
  "anatolia",
  "archipelago",
  "arena",
  "aso_grasslands",
  "bamboo_grove",
  "black_sea",
  "blood_river_crossing",
  "blue_lagoon",
  "cloud_forest",
  "elysium",
  "erebus",
  "ghost_lake",
  "giza",
  "gold_rush",
  "great_wall",
  "highland",
  "ironwood",
  "islands",
  "jotunheim",
  "kerlaugar",
  "kii",
  "land_nomad",
  "land_unknown",
  "MapThumb_Land",
  "MapThumb_Navy",
  "MapThumb_Standard",
  "marsh",
  "mediterranean",
  "megalopolis",
  "midgard",
  "mirage",
  "mirkwood",
  "mount_olympus",
  "muspellheim",
  "nile_shallows",
  "nomad",
  "oasis",
  "obsidian_ridge",
  "okuchichibu",
  "peach_blossom_land",
  "qinghai_lake",
  "river_styx",
  "savannah",
  "sea_of_worms",
  "senjogahara",
  "setonaikai",
  "silk_road",
  "snake_dance",
  "steppe",
  "team_migration",
  "temple_of_the_jaguar",
  "the_unknown",
  "tiny",
  "tundra",
  "valley_of_kings",
  "valley_of_the_sun_serpent",
  "vinlandsaga",
  "watering_hole",
  "yellow_river",
]);

const GOD_ICON_BASE_PATHS = [
  `${STATIC_URL}god-icons`,
  "/static/god-icons",
  "/god-icons",
  "god-icons",
];

const PLAYER_MATCH_TYPES = [
  { id: 1, label: "1v1 Supremacy" },
  { id: 2, label: "Team Supremacy" },
  { id: 3, label: "Deathmatch" },
  { id: 4, label: "Team Deathmatch" },
];

let lobbies = [];
let filteredLobbies = [];
let selectedLobbyId = null;
let sortKey = "max_players";
let sortDirection = "desc";
let activeTab = "custom";
let hoveredLobby = null;
let activeMatchesScriptPromise = null;

let leaderboardCache = new Map();
let leaderboardPending = new Map();
let playerDetailsCache = new Map();
let playerDetailsPending = new Map();
let activePlayerDetails = null;

/*
  Displayed ELO is intentionally internal now.
  The old user-facing dropdown has been removed from the Open Lobbies controls.
*/
const displayedEloMode = "auto";

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

const tabButtons = document.querySelectorAll(".tab-button");

const searchInput = document.getElementById("searchInput");
const regionFilter = document.getElementById("regionFilter");
const modeFilter = document.getElementById("modeFilter");
const mapFilter = document.getElementById("mapFilter");

const hideAiGames = document.getElementById("hideAiGames");
const hideFullLobbies = document.getElementById("hideFullLobbies");
const hidePassworded = document.getElementById("hidePassworded");
const hideCheats = document.getElementById("hideCheats");

const summary = document.getElementById("summary");
const filterNote = document.getElementById("filterNote");
const lastUpdated = document.getElementById("lastUpdated");
const refreshButton = document.getElementById("refreshButton");
const lobbyTableBody = document.getElementById("lobbyTableBody");
const detailsSidebar = document.getElementById("detailsSidebar");
const hoverTooltip = document.getElementById("hoverTooltip");

const liveBusynessLabel = document.getElementById("liveBusynessLabel");
const liveBusynessDetail = document.getElementById("liveBusynessDetail");
const livePublicLobbies = document.getElementById("livePublicLobbies");
const livePlayersInLobbies = document.getElementById("livePlayersInLobbies");
const liveTopRegion = document.getElementById("liveTopRegion");
const liveSteamOnline = document.getElementById("liveSteamOnline");
const liveCustomLobbies = document.getElementById("liveCustomLobbies");
const liveRankedLobbies = document.getElementById("liveRankedLobbies");
const liveJoinableLobbies = document.getElementById("liveJoinableLobbies");
const liveRefreshButton = document.getElementById("liveRefreshButton");
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function makeAssetFilename(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/['’]/g, "")
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function getWidgetFrameOrnamentsMarkup() {
  return `
    <div class="widget-frame-ornaments" aria-hidden="true">
      <span class="widget-corner widget-corner-tl"></span>
      <span class="widget-corner widget-corner-tr"></span>
      <span class="widget-corner widget-corner-bl"></span>
      <span class="widget-corner widget-corner-br"></span>
      <span class="widget-edge widget-edge-top"></span>
      <span class="widget-edge widget-edge-bottom"></span>
      <span class="widget-edge-side widget-edge-left"></span>
      <span class="widget-edge-side widget-edge-right"></span>
    </div>
  `;
}

function buildPlaceholderSvg(label) {
  const safeLabel = escapeHtml(String(label || "?").slice(0, 16));
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
      <rect width="96" height="96" rx="14" fill="#161922"/>
      <rect x="5" y="5" width="86" height="86" rx="11" fill="none" stroke="#b99148" stroke-width="2"/>
      <text x="48" y="52" text-anchor="middle" font-family="serif" font-size="12" fill="#f4dfaa">${safeLabel}</text>
    </svg>
  `;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function ensureLobbyPanelSections() {
  const lobbyPanel = document.querySelector("#customTab .lobby-panel");

  if (!lobbyPanel || lobbyPanel.querySelector(":scope > .lobby-controls-frame")) {
    return;
  }

  const controlsFrame = document.createElement("section");
  controlsFrame.className = "lobby-subpanel lobby-controls-frame";
  controlsFrame.insertAdjacentHTML("afterbegin", getWidgetFrameOrnamentsMarkup());

  const listFrame = document.createElement("section");
  listFrame.className = "lobby-subpanel lobby-list-frame";
  listFrame.insertAdjacentHTML("afterbegin", getWidgetFrameOrnamentsMarkup());

  const controlsContent = document.createElement("div");
  controlsContent.className = "lobby-subpanel-content lobby-controls-content";

  const listContent = document.createElement("div");
  listContent.className = "lobby-subpanel-content lobby-list-content";

  const filterBar = lobbyPanel.querySelector(":scope > .filter-bar");
  const quickFilters = lobbyPanel.querySelector(":scope > .quick-filters");
  const summaryRow = lobbyPanel.querySelector(":scope > .summary-row");
  const tableCard = lobbyPanel.querySelector(":scope > .table-card");

  if (filterBar) {
    controlsContent.appendChild(filterBar);
  }

  if (quickFilters) {
    controlsContent.appendChild(quickFilters);
  }

  if (summaryRow) {
    controlsContent.appendChild(summaryRow);
  }

  if (tableCard) {
    listContent.appendChild(tableCard);
  }

  controlsFrame.appendChild(controlsContent);
  listFrame.appendChild(listContent);

  lobbyPanel.appendChild(controlsFrame);
  lobbyPanel.appendChild(listFrame);
}

function ensurePlayerDetailsModal() {
  if (document.getElementById("playerDetailsOverlay")) {
    return;
  }

  const overlay = document.createElement("div");
  overlay.id = "playerDetailsOverlay";
  overlay.className = "player-details-overlay";
  overlay.innerHTML = `
    <div class="player-details-modal" role="dialog" aria-modal="true" aria-labelledby="playerDetailsTitle">
      ${getWidgetFrameOrnamentsMarkup()}
      <div class="player-details-frame">
        <button id="playerDetailsClose" class="player-details-close" type="button" aria-label="Close player details">×</button>
        <div id="playerDetailsContent" class="player-details-content">
          <div class="muted">Select a player to view details.</div>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      closePlayerDetails();
    }
  });

  overlay.querySelector("#playerDetailsClose")?.addEventListener("click", closePlayerDetails);
}

function closePlayerDetails() {
  const overlay = document.getElementById("playerDetailsOverlay");

  if (!overlay) {
    return;
  }

  overlay.classList.remove("is-visible");
  activePlayerDetails = null;
}

function normalizeLeaderboardId(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const numericValue = Number(value);

  if (Number.isFinite(numericValue) && numericValue >= 0) {
    return String(Math.trunc(numericValue));
  }

  const stringValue = String(value).trim();

  if (!stringValue || stringValue === "-1") {
    return null;
  }

  return stringValue;
}

function normalizeLeaderboardKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

function isHostParticipant(participant, lobby) {
  const participantName = String(participant?.name || "").trim().toLowerCase();
  const hostName = String(lobby?.host || "").trim().toLowerCase();

  return Boolean(participantName && hostName && participantName === hostName);
}

function getParticipantLeaderboardId(participant, lobby = null) {
  if (!participant || typeof participant !== "object") {
    return null;
  }

  const possibleValues = [
    participant.profile_id,
    participant.rl_user_id,
    participant.rlUserId,
    participant.profileId,
    participant.profileID,
    participant.player_profile_id,
    participant.playerProfileId,
    participant.user_id,
    participant.userId,
    participant.userID,
    participant.leaderboard_id,
    participant.id,
    participant.profileInfo?.id,
    participant.profile_info?.id,
  ];

  if (lobby && isHostParticipant(participant, lobby)) {
    possibleValues.push(
      lobby.host_profile_id,
      lobby.hostProfileId,
      lobby.host_profileID,
    );
  }

  for (const value of possibleValues) {
    const normalizedId = normalizeLeaderboardId(value);

    if (normalizedId !== null) {
      return normalizedId;
    }
  }

  return null;
}

function getSelectedDisplayedEloMode() {
  return "auto";
}

function lobbyLooksLikeTeamGame(lobby) {
  const humans = getVisibleParticipants(lobby).filter(
    (participant) => participant.type === "Human",
  );

  const teamIds = humans
    .map((participant) => participant.team_id ?? participant.team)
    .filter((teamId) => teamId !== null && teamId !== undefined && teamId !== "");

  if (teamIds.length < 2) {
    return false;
  }

  const uniqueTeams = new Set(teamIds.map(String));

  if (uniqueTeams.size <= 1) {
    return false;
  }

  return humans.length > 2 || uniqueTeams.size === 2;
}

function lobbyLooksLikeDeathmatch(lobby) {
  const values = [
    lobby?.game_mode,
    lobby?.game_type,
    lobby?.mode,
    lobby?.victory_condition,
  ];

  return values.some((value) => makeAssetFilename(value).includes("deathmatch"));
}

function getDisplayedRatingMatchType(lobby = null) {
  const mode = getSelectedDisplayedEloMode();

  if (["1", "2", "3", "4"].includes(String(mode))) {
    return Number(mode);
  }

  if (!lobby) {
    return 1;
  }

  const isTeamGame = lobbyLooksLikeTeamGame(lobby);
  const isDeathmatch = lobbyLooksLikeDeathmatch(lobby);

  if (isDeathmatch && isTeamGame) {
    return 4;
  }

  if (isDeathmatch) {
    return 3;
  }

  if (isTeamGame) {
    return 2;
  }

  return 1;
}

function getDisplayedRatingLabel(matchType) {
  const labels = {
    1: "1v1 Supremacy",
    2: "Team Supremacy",
    3: "Deathmatch",
    4: "Team Deathmatch",
  };

  return labels[Number(matchType)] || "1v1 Supremacy";
}

function getLeaderboardCacheKey(playerName, participant = null, lobby = null) {
  const profileId = getParticipantLeaderboardId(participant, lobby);
  const matchType = getDisplayedRatingMatchType(lobby);

  if (profileId) {
    return `id:${profileId}:mt:${matchType}`;
  }

  const nameKey = normalizeLeaderboardKey(playerName);
  return nameKey ? `name:${nameKey}:mt:${matchType}` : "";
}

function getLeaderboardEntryForParticipant(participant, lobby = null) {
  if (!participant || participant.type === "Open" || participant.type === "AI") {
    return null;
  }

  const key = getLeaderboardCacheKey(participant.name, participant, lobby);

  if (!key) {
    return null;
  }

  return leaderboardCache.get(key) || null;
}

function isLeaderboardLookupPending(participant, lobby = null) {
  const key = getLeaderboardCacheKey(participant?.name, participant, lobby);
  return Boolean(key && leaderboardPending.has(key));
}

function shouldLookupLeaderboardForParticipant(participant, lobby = null) {
  if (!participant || participant.type === "Open" || participant.type === "AI") {
    return false;
  }

  const key = getLeaderboardCacheKey(participant.name, participant, lobby);
  return Boolean(key && !leaderboardCache.has(key) && !leaderboardPending.has(key));
}

function getPrimaryRating(entry) {
  return entry?.rating || entry?.best_match || null;
}

async function lookupLeaderboardForPlayer(playerName, participant = null, lobby = null) {
  const key = getLeaderboardCacheKey(playerName, participant, lobby);

  if (!key) {
    return null;
  }

  if (leaderboardCache.has(key)) {
    return leaderboardCache.get(key);
  }

  if (leaderboardPending.has(key)) {
    return leaderboardPending.get(key);
  }

  const profileId = getParticipantLeaderboardId(participant, lobby);
  const params = new URLSearchParams();

  if (profileId) {
    params.set("profile_id", profileId);
  }

  if (playerName) {
    params.set("player", playerName);
  }

  params.set("match_type", String(getDisplayedRatingMatchType(lobby)));
  params.set("transport", "curl");

  const request = fetch(`${API_BASE_URL}/api/player/rating?${params.toString()}`)
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Player rating lookup failed for ${playerName || profileId}: ${response.status}`);
      }

      return response.json();
    })
    .then((payload) => {
      const entry = {
        player: playerName,
        participant_id: profileId,
        ok: Boolean(payload.ok),
        source: payload.source || null,
        rating: payload.rating || null,
        best_match: payload.rating || null,
        ratings: Array.isArray(payload.ratings) ? payload.ratings : [],
        requested_match_type: payload.requested_match_type || getDisplayedRatingMatchType(lobby),
        requested_match_type_label:
          payload.requested_match_type_label ||
          getDisplayedRatingLabel(getDisplayedRatingMatchType(lobby)),
        reason: payload.reason || null,
        error: null,
      };

      leaderboardCache.set(key, entry);
      return entry;
    })
    .catch((error) => {
      console.warn(error);

      const entry = {
        player: playerName,
        participant_id: profileId,
        ok: false,
        source: null,
        rating: null,
        best_match: null,
        ratings: [],
        requested_match_type: getDisplayedRatingMatchType(lobby),
        requested_match_type_label: getDisplayedRatingLabel(getDisplayedRatingMatchType(lobby)),
        reason: error.message || String(error),
        error: error.message || String(error),
      };

      leaderboardCache.set(key, entry);
      return entry;
    })
    .finally(() => {
      leaderboardPending.delete(key);
    });

  leaderboardPending.set(key, request);
  return request;
}

async function loadLeaderboardForLobby(lobby) {
  if (!lobby || String(lobby.id) !== String(selectedLobbyId)) {
    return;
  }

  const participants = getVisibleParticipants(lobby).filter((participant) =>
    shouldLookupLeaderboardForParticipant(participant, lobby),
  );

  const uniqueParticipants = new Map();

  for (const participant of participants) {
    const key = getLeaderboardCacheKey(participant.name, participant, lobby);

    if (key && !uniqueParticipants.has(key)) {
      uniqueParticipants.set(key, participant);
    }
  }

  if (!uniqueParticipants.size) {
    return;
  }

  await Promise.all(
    [...uniqueParticipants.values()].map((participant) =>
      lookupLeaderboardForPlayer(participant.name, participant, lobby),
    ),
  );

  if (String(lobby.id) === String(selectedLobbyId)) {
    renderDetailsSidebar(lobby, { skipLeaderboardLoad: true });
  }
}

function renderLeaderboardBadge(participant, lobby = null) {
  if (!participant || participant.type === "Open" || participant.type === "AI") {
    return "";
  }

  const entry = getLeaderboardEntryForParticipant(participant, lobby);
  const rating = getPrimaryRating(entry);

  if (rating && rating.rating !== null && rating.rating !== undefined) {
    const label = `ELO: ${rating.rating}`;
    const sourceLabel = rating.source === "full_stats" ? "FullStats" : "Leaderboard";
    const titleParts = [
      sourceLabel,
      rating.match_type_label || entry.requested_match_type_label || "1v1 Supremacy",
    ];

    if (rating.highest_rating !== null && rating.highest_rating !== undefined) {
      titleParts.push(`Peak ${rating.highest_rating}`);
    }

    if (rating.games !== null && rating.games !== undefined) {
      titleParts.push(`${rating.games} games`);
    }

    return `<span class="player-rating-inline" title="${escapeHtml(titleParts.join(" · "))}">${escapeHtml(label)}</span>`;
  }

  if (isLeaderboardLookupPending(participant, lobby)) {
    return `<span class="player-rating-inline player-rating-loading" title="Loading rating">...</span>`;
  }

  if (entry && !rating) {
    const title = entry.reason || "No listed rating was returned.";
    return `<span class="player-rating-inline player-rating-empty" title="${escapeHtml(title)}">-</span>`;
  }

  return "";
}

function formatRating(participant) {
  if (!participant) {
    return "Unrated";
  }

  if (participant.type === "AI") {
    return "AI";
  }

  if (participant.type === "Open") {
    return "Open";
  }

  const possibleValues = [
    participant.rating,
    participant.elo,
    participant.ranking,
    participant.leaderboard_rating,
  ];

  for (const value of possibleValues) {
    const numericValue = Number(value);

    if (Number.isFinite(numericValue) && numericValue > 0) {
      return String(Math.trunc(numericValue));
    }
  }

  return "Unrated";
}

function getPlayerDetailsCacheKey(participant, lobby = null, matchType = 1) {
  const profileId = getParticipantLeaderboardId(participant, lobby);
  return profileId ? `profile:${profileId}:recent:${matchType}` : "";
}

function getParticipantCountry(participant) {
  return participant?.country ? String(participant.country).toUpperCase() : "";
}

function getPlatformLabel(participant) {
  const platformName = String(participant?.platform_name || participant?.platform || "");

  if (platformName.startsWith("/steam/")) {
    return "Steam";
  }

  if (platformName.startsWith("/xboxlive/")) {
    return "Xbox";
  }

  if (platformName.startsWith("/playstation/")) {
    return "PlayStation";
  }

  return platformName || "";
}

async function fetchPlayerDetails(participant, lobby, recentMatchType = 1) {
  const profileId = getParticipantLeaderboardId(participant, lobby);

  if (!profileId) {
    throw new Error("This player does not have a lobby profile_id.");
  }

  const cacheKey = getPlayerDetailsCacheKey(participant, lobby, recentMatchType);

  if (playerDetailsCache.has(cacheKey)) {
    return playerDetailsCache.get(cacheKey);
  }

  if (playerDetailsPending.has(cacheKey)) {
    return playerDetailsPending.get(cacheKey);
  }

  const params = new URLSearchParams({
    profile_id: profileId,
    player: participant.name || "unknown user",
    recent_match_type: String(recentMatchType),
    recent_count: "10",
    transport: "curl",
  });

  const request = fetch(`${API_BASE_URL}/api/player/summary?${params.toString()}`)
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Player summary failed: ${response.status}`);
      }

      return response.json();
    })
    .then((payload) => {
      playerDetailsCache.set(cacheKey, payload);
      return payload;
    })
    .finally(() => {
      playerDetailsPending.delete(cacheKey);
    });

  playerDetailsPending.set(cacheKey, request);
  return request;
}

function renderRatingsTable(ratings) {
  const rows = Array.isArray(ratings)
    ? ratings.map((record) => {
        const rating = record?.rating || {};
        const label = record?.match_type_label || rating.match_type_label || "Unknown";

        if (rating.rating === null || rating.rating === undefined) {
          return `
            <tr>
              <th scope="row">${escapeHtml(label)}</th>
              <td>-</td>
              <td>-</td>
              <td>-</td>
              <td>-</td>
              <td>-</td>
            </tr>
          `;
        }

        return `
          <tr>
            <th scope="row">${escapeHtml(label)}</th>
            <td>${escapeHtml(rating.rating)}</td>
            <td>${escapeHtml(rating.wins ?? "-")}</td>
            <td>${escapeHtml(rating.losses ?? "-")}</td>
            <td>${escapeHtml(rating.games ?? "-")}</td>
            <td>${escapeHtml(rating.win_rate !== null && rating.win_rate !== undefined ? `${rating.win_rate}%` : "-")}</td>
          </tr>
        `;
      }).join("")
    : "";

  return `
    <div class="player-ratings-table-wrap">
      <table class="player-ratings-table">
        <thead>
          <tr>
            <th>Game Type</th>
            <th>Rating</th>
            <th>Wins</th>
            <th>Losses</th>
            <th>Games</th>
            <th>Win Rate</th>
          </tr>
        </thead>
        <tbody>
          ${rows || `<tr><td colspan="6" class="muted">No ratings returned.</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function formatMatchDate(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatMatchTime(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTimestamp(value) {
  if (!value) {
    return "never";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatMatchLength(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  const minutes = Math.floor(numericValue);
  const seconds = Math.round((numericValue - minutes) * 60);

  if (seconds <= 0) {
    return `${minutes}m`;
  }

  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function renderRecentMatchesTable(matches) {
  const sortedMatches = Array.isArray(matches)
    ? [...matches].sort((a, b) => {
        const aDate = new Date(a.date_time || 0).getTime() || Number(a.sort_timestamp || 0) * 1000;
        const bDate = new Date(b.date_time || 0).getTime() || Number(b.sort_timestamp || 0) * 1000;
        return bDate - aDate;
      })
    : [];

  const rows = sortedMatches.length
    ? sortedMatches.slice(0, 10).map((match) => {
        const result = match.result || "-";
        const dateText = formatMatchDate(match.date_time) || "-";
        const timeText = formatMatchTime(match.date_time);
        const mapName = formatMapName(match.map || "Unknown");
        const lengthText = formatMatchLength(match.match_length);

        return `
          <tr class="recent-match-table-row">
            <td class="recent-info-table-cell">
              <div class="recent-info-cell">
                <strong>${escapeHtml(dateText)}</strong>
                ${timeText ? `<span>${escapeHtml(timeText)}</span>` : ""}
                <span class="mono">${match.match_id ? `#${escapeHtml(match.match_id)}` : "-"}</span>
              </div>
            </td>
            <td>
              <div class="recent-map-cell">
                ${renderMapImage(match.map || "Unknown", "recent-map-icon")}
                <span>${escapeHtml(mapName)}</span>
              </div>
            </td>
            <td>${escapeHtml(match.match_type_label || match.match_type || "-")}</td>
            <td><span class="recent-result">${escapeHtml(result)}</span></td>
            <td class="recent-length-cell">${escapeHtml(lengthText)}</td>
          </tr>
        `;
      }).join("")
    : `<tr><td colspan="5" class="muted">No recent matches returned for this category.</td></tr>`;

  return `
    <div class="recent-match-table-wrap">
      <table class="recent-match-table">
        <thead>
          <tr>
            <th>Info</th>
            <th>Map</th>
            <th>Type</th>
            <th>Result</th>
            <th>Length</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>
  `;
}

function renderRecentMatchTabs(activeMatchType) {
  return `
    <div class="recent-match-tabs" role="tablist" aria-label="Recent match category">
      ${PLAYER_MATCH_TYPES.map((matchType) => {
        const isActive = Number(activeMatchType) === matchType.id;

        return `
          <button
            id="recentMatchTab-${matchType.id}"
            type="button"
            class="recent-match-tab ${isActive ? "is-active" : ""}"
            data-match-type="${matchType.id}"
            role="tab"
            aria-selected="${isActive ? "true" : "false"}"
            aria-controls="recentMatchPanel"
            tabindex="${isActive ? "0" : "-1"}"
          >
            ${escapeHtml(matchType.label)}
          </button>
        `;
      }).join("")}
    </div>
  `;
}

function renderPlayerDetailsShell(participant, lobby, bodyMarkup, payload = null) {
  const profileId = getParticipantLeaderboardId(participant, lobby);
  const country = getParticipantCountry(participant);
  const platform = getPlatformLabel(participant);
  const displayName = payload?.display_name || participant?.name || "Unknown Player";
  const avatarUrl = payload?.avatar_url || "";
  const avatarMarkup = avatarUrl
    ? `<img src="${escapeHtml(avatarUrl)}" alt="" loading="lazy">`
    : escapeHtml(String(displayName || "?").trim().slice(0, 1).toUpperCase() || "?");

  const metaItems = [
    profileId ? `ID ${profileId}` : "",
    country,
    platform,
    participant?.god ? `God: ${participant.god}` : "",
  ].filter(Boolean);

  return `
    <div class="player-details-header">
      <div class="player-avatar ${avatarUrl ? "player-avatar-image" : "player-avatar-placeholder"}">${avatarMarkup}</div>
      <div>
        <h2 id="playerDetailsTitle">${escapeHtml(displayName)}</h2>
        <div class="player-details-meta">${metaItems.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
      </div>
    </div>
    ${bodyMarkup}
  `;
}

function renderPlayerDetailsLoading(participant, lobby) {
  const content = document.getElementById("playerDetailsContent");

  if (!content) {
    return;
  }

  content.innerHTML = renderPlayerDetailsShell(
    participant,
    lobby,
    `
      <div class="player-details-loading">
        <div class="loading-spinner"></div>
        <span>Loading player details...</span>
      </div>
    `,
  );
}

function renderPlayerDetailsError(participant, lobby, message) {
  const content = document.getElementById("playerDetailsContent");

  if (!content) {
    return;
  }

  content.innerHTML = renderPlayerDetailsShell(
    participant,
    lobby,
    `<div class="player-details-error">${escapeHtml(message || "Unable to load player details.")}</div>`,
  );
}

function attachRecentMatchTabHandlers(participant, lobby) {
  const content = document.getElementById("playerDetailsContent");

  if (!content) {
    return;
  }

  content.querySelectorAll(".recent-match-tab").forEach((button) => {
    button.addEventListener("click", async () => {
      const matchType = Number(button.dataset.matchType || 1);

      content.querySelectorAll(".recent-match-tab").forEach((item) => {
        const itemIsActive = Number(item.dataset.matchType) === matchType;
        item.classList.toggle("is-active", itemIsActive);
        item.setAttribute("aria-selected", itemIsActive ? "true" : "false");
        item.setAttribute("tabindex", itemIsActive ? "0" : "-1");
      });

      const sectionBody = content.querySelector(".recent-match-dynamic-body");

      if (sectionBody) {
        sectionBody.innerHTML = `<div class="player-details-loading player-details-loading-inline"><div class="loading-spinner"></div><span>Loading recent matches...</span></div>`;
      }

      try {
        const payload = await fetchPlayerDetails(participant, lobby, matchType);

        if (
          activePlayerDetails &&
          activePlayerDetails.participant === participant &&
          String(activePlayerDetails.lobby?.id) === String(lobby?.id)
        ) {
          renderPlayerDetailsData(participant, lobby, payload);
        }
      } catch (error) {
        console.error(error);

        if (sectionBody) {
          sectionBody.innerHTML = `<div class="player-details-error">${escapeHtml(error.message || String(error))}</div>`;
        }
      }
    });
  });
}

function renderPlayerDetailsData(participant, lobby, payload) {
  const content = document.getElementById("playerDetailsContent");

  if (!content) {
    return;
  }

  const ratings = Array.isArray(payload?.ratings) ? payload.ratings : [];
  const recentMatches = payload?.recent_matches?.matches || [];
  const activeMatchType = Number(payload?.recent_match_type || 1);
  const activeMatchTypeLabel = payload?.recent_match_type_label || "1v1 Supremacy";

  content.innerHTML = renderPlayerDetailsShell(
    participant,
    lobby,
    `
      <div class="player-details-section">
        <div class="player-details-section-title">Ratings</div>
        ${renderRatingsTable(ratings)}
      </div>

      <div class="player-details-section">
        <div class="player-details-section-title">Recent Matches</div>
        ${renderRecentMatchTabs(activeMatchType)}
        <div id="recentMatchPanel" class="recent-match-dynamic-body" role="tabpanel" aria-live="polite">
          <div class="recent-match-active-label">${escapeHtml(activeMatchTypeLabel)}</div>
          ${renderRecentMatchesTable(recentMatches)}
        </div>
      </div>
    `,
    payload,
  );

  attachRecentMatchTabHandlers(participant, lobby);
}

async function openPlayerDetails(participant, lobby) {
  if (!participant || participant.type === "Open" || participant.type === "AI") {
    return;
  }

  ensurePlayerDetailsModal();

  const overlay = document.getElementById("playerDetailsOverlay");

  if (!overlay) {
    return;
  }

  overlay.classList.add("is-visible");
  activePlayerDetails = { participant, lobby };

  renderPlayerDetailsLoading(participant, lobby);

  try {
    const payload = await fetchPlayerDetails(participant, lobby);

    if (
      activePlayerDetails &&
      activePlayerDetails.participant === participant &&
      String(activePlayerDetails.lobby?.id) === String(lobby?.id)
    ) {
      renderPlayerDetailsData(participant, lobby, payload);
    }
  } catch (error) {
    console.error(error);
    renderPlayerDetailsError(participant, lobby, error.message || String(error));
  }
}

window.openPlayerDetails = openPlayerDetails;

async function loadLobbies(forceRefresh = false) {
  if (summary) {
    summary.textContent = "Loading lobbies...";
  }

  if (filterNote) {
    filterNote.textContent = "";
  }

  const params = new URLSearchParams();

  if (forceRefresh) {
    params.set("refresh", "1");
  }

  params.set("pages", "4");

  const response = await fetch(`${API_BASE_URL}/api/lobbies/?${params.toString()}`);

  if (!response.ok) {
    throw new Error(`Lobby request failed: ${response.status}`);
  }

  const payload = await response.json();

  if (!payload.ok) {
    throw new Error(payload.error || "Unable to load lobbies.");
  }

  lobbies = Array.isArray(payload.lobbies) ? payload.lobbies : [];
  filteredLobbies = [...lobbies];

  if (lastUpdated) {
    lastUpdated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }

  populateFilters();
  applyFiltersAndRender();
}

function populateFilters() {
  populateSelect(regionFilter, getUniqueRawValues("region"), {
    formatter: formatRegion,
  });

  populateSelect(modeFilter, getUniqueValues("game_mode", formatGameType));
  populateSelect(mapFilter, getUniqueValues("map", formatMapName));
}

function getUniqueRawValues(key) {
  return [
    ...new Set(
      lobbies
        .map((lobby) => lobby[key])
        .filter(Boolean),
    ),
  ].sort((a, b) => String(formatRegion(a)).localeCompare(String(formatRegion(b))));
}

function getUniqueValues(key, formatter = (value) => value) {
  return [
    ...new Set(
      lobbies
        .map((lobby) => formatter(lobby[key]))
        .filter(Boolean),
    ),
  ].sort((a, b) => String(a).localeCompare(String(b)));
}

function populateSelect(selectElement, values, options = {}) {
  if (!selectElement) {
    return;
  }

  const formatter = options.formatter || ((value) => value);
  const currentValue = selectElement.value;
  const firstOptionText = selectElement.options[0]?.textContent || "All";

  selectElement.innerHTML = "";

  const firstOption = document.createElement("option");
  firstOption.value = "";
  firstOption.textContent = firstOptionText;
  selectElement.appendChild(firstOption);

  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = formatter(value);
    selectElement.appendChild(option);
  }

  if (values.includes(currentValue)) {
    selectElement.value = currentValue;
  }
}

function applyFiltersAndRender() {
  const searchText = searchInput?.value.trim().toLowerCase() || "";
  const selectedRegion = regionFilter?.value || "";
  const selectedMode = modeFilter?.value || "";
  const selectedMap = mapFilter?.value || "";

  filteredLobbies = lobbies.filter((lobby) => {
    const participantNames = getVisibleParticipants(lobby)
      .map((participant) =>
        `${participant.name} ${participant.god} ${participant.country || ""}`,
      )
      .join(" ");

    const searchableText = [
      lobby.name,
      lobby.host,
      lobby.map,
      formatMapName(lobby.map),
      lobby.region,
      formatRegion(lobby.region),
      lobby.game_mode,
      formatGameType(lobby.game_mode),
      getVictoryConditionSetting(lobby),
      lobby.speed,
      lobby.starting_resources,
      lobby.map_size,
      lobby.map_visibility,
      lobby.difficulty,
      lobby.raw_mapname,
      participantNames,
    ]
      .join(" ")
      .toLowerCase();

    if (searchText && !searchableText.includes(searchText)) {
      return false;
    }

    if (selectedRegion && lobby.region !== selectedRegion) {
      return false;
    }

    if (selectedMode && formatGameType(lobby.game_mode) !== selectedMode) {
      return false;
    }

    if (selectedMap && formatMapName(lobby.map) !== selectedMap) {
      return false;
    }

    if (hideAiGames?.checked && isAiOrAotgLobby(lobby)) {
      return false;
    }

    if (hideFullLobbies?.checked && Number(lobby.open_human_slots || 0) <= 0) {
      return false;
    }

    if (hidePassworded?.checked && lobby.password_protected) {
      return false;
    }

    if (hideCheats?.checked && lobby.cheats_enabled) {
      return false;
    }

    return true;
  });

  sortLobbies();
  renderTable();
  renderSummary();
  preserveOrResetSelection();
}

function isAiOrAotgLobby(lobby) {
  const hasAiCount = Number(lobby.ai_players || 0) > 0;
  const hasAiParticipant = getParticipants(lobby).some(
    (participant) => participant.type === "AI",
  );

  const textToCheck = [
    lobby.name,
    lobby.host,
    lobby.map,
    lobby.raw_mapname,
    lobby.game_mode,
    lobby.difficulty,
    lobby.starting_resources,
  ]
    .join(" ")
    .toLowerCase();

  const looksLikeArenaOfTheGods =
    textToCheck.includes("arena of the gods") ||
    textToCheck.includes("aotg") ||
    textToCheck.includes("arenaofthegods") ||
    textToCheck.includes("arena_of_the_gods");

  return hasAiCount || hasAiParticipant || looksLikeArenaOfTheGods;
}

function sortLobbies() {
  filteredLobbies.sort((a, b) => {
    const comparison = compareLobbySortValues(a, b, sortKey);
    return sortDirection === "asc" ? comparison : -comparison;
  });
}

function compareLobbySortValues(a, b, key) {
  let comparison = comparePrimitiveSortValues(
    getLobbySortValue(a, key),
    getLobbySortValue(b, key),
  );

  if (comparison !== 0) {
    return comparison;
  }

  return String(a.name || "").localeCompare(String(b.name || ""), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function comparePrimitiveSortValues(aValue, bValue) {
  if (typeof aValue === "number" && typeof bValue === "number") {
    return aValue - bValue;
  }

  if (typeof aValue === "boolean" && typeof bValue === "boolean") {
    return Number(aValue) - Number(bValue);
  }

  const aText = String(aValue ?? "").toLowerCase();
  const bText = String(bValue ?? "").toLowerCase();

  return aText.localeCompare(bText, undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function getLobbySortValue(lobby, key) {
  if (key === "max_players" || key === "max_player_size" || key === "slots") {
    return getConfiguredPlayerSlots(lobby);
  }

  if (key === "players" || key === "occupied_slots") {
    return getOccupiedPlayerSlots(lobby);
  }

  if (key === "open_human_slots" || key === "open_slots") {
    return Number(lobby.open_human_slots || 0);
  }

  if (key === "name" || key === "lobby" || key === "title") {
    return lobby.name || "";
  }

  if (key === "host") {
    return lobby.host || "";
  }

  if (key === "game_mode" || key === "mode" || key === "gameType") {
    return formatGameType(lobby.game_mode);
  }

  if (key === "map" || key === "map_name") {
    return formatMapName(lobby.map);
  }

  if (key === "region" || key === "server") {
    return formatRegion(lobby.region);
  }

  if (key === "password") {
    return Boolean(lobby.password_protected);
  }

  if (key === "cheats") {
    return Boolean(lobby.cheats_enabled);
  }

  return lobby[key] ?? "";
}

function getOccupiedPlayerSlots(lobby) {
  return Number(lobby.occupied_slots ?? calculateOccupiedSlots(lobby) ?? 0);
}

function getConfiguredPlayerSlots(lobby) {
  const occupiedSlots = getOccupiedPlayerSlots(lobby);

  /*
    AoM custom lobbies can expose the full upstream lobby container as 12 slots,
    even when the actual configured match is 2, 4, 6, or 8 players.

    For display and sorting, the useful max size is the active match size:
    humans + open human slots + AI/unknown slots. Closed slots are intentionally
    excluded so a 4-player lobby does not show as x/12.
  */
  const activeSlotCount =
    Number(lobby?.human_players || 0) +
    Number(lobby?.open_human_slots || 0) +
    Number(lobby?.ai_players || 0) +
    Number(lobby?.unknown_slots || 0);

  if (Number.isFinite(activeSlotCount) && activeSlotCount > 0) {
    return Math.max(activeSlotCount, occupiedSlots, 1);
  }

  const participants = getVisibleParticipants(lobby);

  if (participants.length) {
    const nonClosedParticipants = participants.filter((participant) => {
      const type = String(participant?.type || "").trim().toLowerCase();
      const name = String(participant?.name || "").trim().toLowerCase();

      return type !== "closed" && name !== "closed" && name !== "closed slot";
    });

    if (nonClosedParticipants.length) {
      return Math.max(nonClosedParticipants.length, occupiedSlots, 1);
    }
  }

  const configuredValues = [
    lobby?.max_players_configured,
    lobby?.total_active_slots,
    lobby?.player_slots,
    lobby?.num_slots,
    lobby?.slot_count,
  ]
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value > 0);

  if (configuredValues.length) {
    return Math.max(Math.min(...configuredValues), occupiedSlots, 1);
  }

  /*
    Last resort only. These are the fields most likely to be the raw 12-slot
    container, so prefer the smallest credible value instead of blindly using 12.
  */
  const fallbackValues = [
    lobby?.max_players_raw,
    lobby?.max_players,
    lobby?.total_slots,
    lobby?.maxSlots,
    lobby?.max_slots,
    lobby?.slotsMax,
    lobby?.slots_max,
  ]
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value > 0);

  if (fallbackValues.length) {
    return Math.max(Math.min(...fallbackValues), occupiedSlots, 1);
  }

  return Math.max(occupiedSlots, 1);
}

function renderTable() {
  renderLobbyRows(
    lobbyTableBody,
    filteredLobbies,
    "No lobbies match the current filters.",
  );

  updateOpenLobbySortIndicators();
}

function renderLobbyRows(targetBody, lobbyGroup, emptyMessage) {
  if (!targetBody) {
    return;
  }

  targetBody.innerHTML = "";

  if (!lobbyGroup.length) {
    targetBody.innerHTML = `
      <tr>
        <td colspan="5" class="muted">${escapeHtml(emptyMessage)}</td>
      </tr>
    `;
    return;
  }

  for (const lobby of lobbyGroup) {
    const row = document.createElement("tr");
    row.dataset.lobbyId = String(lobby.id);
    row.classList.toggle(
      "selected",
      String(lobby.id) === String(selectedLobbyId),
    );

    row.innerHTML = `
      <td>${renderLobbyCell(lobby)}</td>
      <td>${renderPlayersMeter(lobby)}</td>
      <td>${escapeHtml(formatGameType(lobby.game_mode))}</td>
      <td>${renderMapCell(lobby.map)}</td>
      <td><span class="region-pill">${escapeHtml(formatRegion(lobby.region))}</span></td>
    `;

    row.addEventListener("mouseenter", (event) => {
      hoveredLobby = lobby;
      showTooltip(lobby, event);
    });

    row.addEventListener("mousemove", (event) => {
      moveTooltip(event);
    });

    row.addEventListener("mouseleave", () => {
      hoveredLobby = null;
      hideTooltip();
    });

    row.addEventListener("click", () => {
      selectedLobbyId = lobby.id;
      renderTableSelection();
      renderDetailsSidebar(lobby);
      hideTooltip();
    });

    targetBody.appendChild(row);
  }
}

function renderLobbyCell(lobby) {
  const flags = [];

  if (Number(lobby.open_human_slots || 0) <= 0) {
    flags.push(`<span class="text-flag text-flag-danger">Full</span>`);
  }

  if (lobby.password_protected) {
    flags.push(`<span class="text-flag text-flag-warning">Password</span>`);
  }

  if (isAiOrAotgLobby(lobby)) {
    flags.push(`<span class="text-flag text-flag-danger">AI / AotG</span>`);
  }

  if (lobby.cheats_enabled) {
    flags.push(`<span class="text-flag text-flag-danger">Cheats</span>`);
  }

  return `
    <div class="lobby-cell-title">
      <span class="lobby-name">${escapeHtml(lobby.name || "Unnamed lobby")}</span>
    </div>
    <div class="lobby-cell-meta">
      <span class="lobby-host-name">${escapeHtml(lobby.host || "Unknown")}</span>
      ${flags.join("")}
    </div>
  `;
}

function renderPlayersMeter(lobby) {
  const occupiedSlots = Number(
    lobby.occupied_slots ?? calculateOccupiedSlots(lobby),
  );
  const configuredSlots = Math.max(
    getConfiguredPlayerSlots(lobby),
    occupiedSlots,
    1,
  );
  const percentage = Math.min(
    100,
    Math.max(0, (occupiedSlots / configuredSlots) * 100),
  );

  return `
    <div class="players-meter" title="${occupiedSlots}/${configuredSlots} slots occupied">
      <div class="players-count">${occupiedSlots}/${configuredSlots}</div>
      <div class="meter-track"><div class="meter-fill" style="width: ${percentage}%"></div></div>
    </div>
  `;
}

function renderMapCell(mapName) {
  const displayName = formatMapName(mapName);

  return `
    <div class="map-cell">
      ${renderMapImage(mapName || displayName, "map-thumb")}
      <span class="map-name">${escapeHtml(displayName)}</span>
    </div>
  `;
}

function renderMapImage(mapName, className) {
  const escapedMapName = escapeHtml(mapName || "Unknown");
  const firstPath = getMapImagePath(mapName, 0);

  return `
    <img
      class="${className}"
      src="${escapeHtml(firstPath)}"
      alt="${escapedMapName} map thumbnail"
      loading="lazy"
      data-map-name="${escapedMapName}"
      data-map-path-index="0"
      data-using-fallback-map-icon="false"
      onerror="window.handleMapImageError(this)"
    />
  `;
}

window.handleMapImageError = function handleMapImageError(imageElement) {
  const mapName = imageElement.dataset.mapName || "";
  const currentIndex = Number(imageElement.dataset.mapPathIndex || 0);
  const nextIndex = currentIndex + 1;
  const usingFallbackMapIcon =
    imageElement.dataset.usingFallbackMapIcon === "true";

  if (nextIndex < MAP_IMAGE_BASE_PATHS.length) {
    imageElement.dataset.mapPathIndex = String(nextIndex);
    imageElement.src = usingFallbackMapIcon
      ? getMapImagePath("All Maps", nextIndex)
      : getMapImagePath(mapName, nextIndex);
    return;
  }

  if (!usingFallbackMapIcon) {
    imageElement.dataset.usingFallbackMapIcon = "true";
    imageElement.dataset.mapPathIndex = "0";
    imageElement.src = getMapImagePath("All Maps", 0);
    return;
  }

  imageElement.onerror = null;
  imageElement.src = buildPlaceholderSvg(mapName);
};

function getMapImagePath(mapName, basePathIndex = 0) {
  const fileName = getMapIconFilename(mapName);
  const basePath = MAP_IMAGE_BASE_PATHS[basePathIndex] || MAP_IMAGE_BASE_PATHS[0];
  const extension = basePathIndex < OPTIMIZED_MAP_ICON_BASE_PATHS.length ? "webp" : "png";
  return `${basePath}/${fileName}.${extension}`;
}

function getMapIconFilename(mapName) {
  const normalizedMapName = makeAssetFilename(
    String(mapName || "").replace(/^(rm_|set_)/i, ""),
  );
  const baseMapName = normalizedMapName
    .replace(/_locked_teams$/, "")
    .replace(/_unlocked_teams$/, "");

  const specialMapIcons = {
    all_maps: "all_maps",
    all_map: "all_maps",
    allmaps: "all_maps",
    allmap: "all_maps",
    any_map: "all_maps",
    unknown: "all_maps",
    unknown_map: "all_maps",
    scenario: "all_maps",
    scenarios: "all_maps",
    custom_scenario: "all_maps",
    custom_scenarios: "all_maps",
    custom: "all_maps",
    custom_map: "all_maps",
    custom_maps: "all_maps",
    custom_random_map: "all_maps",
    tenochtitlans_heart: "all_maps",
    sun_serpent_valley: "valley_of_the_sun_serpent",

    standard: "MapThumb_Standard",
    standardmap: "MapThumb_Standard",
    standardmaps: "MapThumb_Standard",
    standard_map: "MapThumb_Standard",
    standard_maps: "MapThumb_Standard",

    quickmatch: "MapThumb_Standard",
    quickmatchmap: "MapThumb_Standard",
    quickmatchmaps: "MapThumb_Standard",
    quick_match: "MapThumb_Standard",
    quick_match_map: "MapThumb_Standard",
    quick_match_maps: "MapThumb_Standard",

    random: "MapThumb_Standard",
    randommap: "MapThumb_Standard",
    randommaps: "MapThumb_Standard",
    random_map: "MapThumb_Standard",
    random_maps: "MapThumb_Standard",
    random_standard: "MapThumb_Standard",
    random_standard_map: "MapThumb_Standard",
    random_standard_maps: "MapThumb_Standard",

    land: "MapThumb_Land",
    landmap: "MapThumb_Land",
    landmaps: "MapThumb_Land",
    land_map: "MapThumb_Land",
    land_maps: "MapThumb_Land",
    random_land: "MapThumb_Land",
    random_land_map: "MapThumb_Land",
    random_land_maps: "MapThumb_Land",

    naval: "MapThumb_Navy",
    navalmap: "MapThumb_Navy",
    navalmaps: "MapThumb_Navy",
    naval_map: "MapThumb_Navy",
    naval_maps: "MapThumb_Navy",
    navy: "MapThumb_Navy",
    navy_map: "MapThumb_Navy",
    navy_maps: "MapThumb_Navy",
    random_naval: "MapThumb_Navy",
    random_naval_map: "MapThumb_Navy",
    random_naval_maps: "MapThumb_Navy",
  };

  if (specialMapIcons[normalizedMapName]) {
    return specialMapIcons[normalizedMapName];
  }

  if (specialMapIcons[baseMapName]) {
    return specialMapIcons[baseMapName];
  }

  if (normalizedMapName.includes("scenario")) {
    return "all_maps";
  }

  if (AVAILABLE_MAP_ICON_FILENAMES.has(normalizedMapName)) {
    return normalizedMapName;
  }

  if (AVAILABLE_MAP_ICON_FILENAMES.has(baseMapName)) {
    return baseMapName;
  }

  return "all_maps";
}

function formatMapName(mapName) {
  const rawValue = String(mapName || "").trim();
  const cleanedRawValue = rawValue.replace(/^(rm_|set_)/i, "");
  const normalized = makeAssetFilename(cleanedRawValue);

  const replacements = {
    allmaps: "All Maps",
    all_maps: "All Maps",
    allmap: "All Maps",
    all_map: "All Maps",

    standard: "Standard Maps",
    standardmap: "Standard Maps",
    standardmaps: "Standard Maps",
    standard_map: "Standard Maps",
    standard_maps: "Standard Maps",

    quickmatch: "Quick Match Maps",
    quickmatchmap: "Quick Match Maps",
    quickmatchmaps: "Quick Match Maps",
    quick_match: "Quick Match Maps",
    quick_match_map: "Quick Match Maps",
    quick_match_maps: "Quick Match Maps",

    random: "Random Maps",
    randommap: "Random Maps",
    randommaps: "Random Maps",
    random_map: "Random Maps",
    random_maps: "Random Maps",
    random_standard: "Random Standard Maps",
    random_standard_map: "Random Standard Maps",
    random_standard_maps: "Random Standard Maps",

    land: "Land Maps",
    landmap: "Land Maps",
    landmaps: "Land Maps",
    land_map: "Land Maps",
    land_maps: "Land Maps",
    random_land: "Random Land Maps",
    random_land_map: "Random Land Maps",
    random_land_maps: "Random Land Maps",

    naval: "Naval Maps",
    navalmap: "Naval Maps",
    navalmaps: "Naval Maps",
    naval_map: "Naval Maps",
    naval_maps: "Naval Maps",
    navy: "Naval Maps",
    navymap: "Naval Maps",
    navymaps: "Naval Maps",
    navy_map: "Naval Maps",
    navy_maps: "Naval Maps",
    random_naval: "Random Naval Maps",
    random_naval_map: "Random Naval Maps",
    random_naval_maps: "Random Naval Maps",

    unknown: "Unknown",
    scenario: "Scenario",
    scenarios: "Scenarios",
  };

  if (replacements[normalized]) {
    return replacements[normalized];
  }

  if (!cleanedRawValue) {
    return "Unknown";
  }

  return cleanedRawValue
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatRegion(region) {
  if (!region) {
    return "Unknown";
  }

  const rawValue = String(region).trim();
  const normalized = makeAssetFilename(rawValue).replace(/_/g, "");

  const replacements = {
    eastus: "US East",
    eastus2: "US East 2",
    westus: "US West",
    westus2: "US West 2",
    westus3: "US West 3",
    centralus: "US Central",
    northcentralus: "US North Central",
    southcentralus: "US South Central",

    westeurope: "EU West",
    northeurope: "EU North",
    uksouth: "UK South",
    ukwest: "UK West",
    francecentral: "France Central",
    germanywestcentral: "Germany West Central",
    italynorth: "Italy North",
    swedencentral: "Sweden Central",

    eastasia: "Asia East",
    southeastasia: "Asia Southeast",
    japaneast: "Japan East",
    japanwest: "Japan West",
    koreacentral: "Korea Central",
    centralindia: "Central India",
    southindia: "South India",

    australiaeast: "Australia East",
    australiasoutheast: "Australia Southeast",

    brazilsouth: "Brazil South",
    southafricanorth: "South Africa North",
  };

  if (replacements[normalized]) {
    return replacements[normalized];
  }

  return rawValue
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatGameType(value) {
  if (!value) {
    return "Unknown";
  }

  const normalized = makeAssetFilename(value);

  const replacements = {
    supremacy: "Supremacy",
    standard: "Standard",
    conquest: "Conquest",
    deathmatch: "Deathmatch",
    death_match: "Deathmatch",
    team_deathmatch: "Team Deathmatch",
    team_death_match: "Team Deathmatch",
    lightning: "Lightning",
    treaty: "Treaty",
    arena_of_the_gods: "Arena of the Gods",
    aotg: "Arena of the Gods",
  };

  if (replacements[normalized]) {
    return replacements[normalized];
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getParticipants(lobby) {
  if (Array.isArray(lobby?.participants)) {
    return lobby.participants;
  }

  if (Array.isArray(lobby?.players)) {
    return lobby.players;
  }

  if (Array.isArray(lobby?.slots)) {
    return lobby.slots;
  }

  return [];
}

function getVisibleParticipants(lobby) {
  return getParticipants(lobby).filter((participant) => {
    const type = String(participant?.type || "").toLowerCase();
    return type !== "closed";
  });
}

function calculateOccupiedSlots(lobby) {
  return getVisibleParticipants(lobby).filter((participant) => {
    const type = String(participant?.type || "").toLowerCase();
    return type && type !== "open" && type !== "closed";
  }).length;
}

function formatSlots(lobby) {
  const occupiedSlots = Number(
    lobby.occupied_slots ?? calculateOccupiedSlots(lobby),
  );
  const configuredSlots = Math.max(
    getConfiguredPlayerSlots(lobby),
    occupiedSlots,
    1,
  );

  return `${occupiedSlots}/${configuredSlots}`;
}

function getGodFallbackText(godName) {
  const cleaned = String(godName || "?")
    .replace(/god/i, "")
    .trim();

  if (!cleaned) {
    return "?";
  }

  if (cleaned.toLowerCase() === "random") {
    return "Rnd";
  }

  return cleaned.slice(0, 3);
}

function getGodIconFilenameCandidates(godName) {
  const normalized = makeAssetFilename(godName);

  const aliases = {
    random: [
      "Gods_List_Random_Icon",
      "Icon_Godicon_Random",
      "random_icon_round",
      "RandomIcon",
      "GodiconRandom",
    ],
    random_god: [
      "Gods_List_Random_Icon",
      "Icon_Godicon_Random",
      "random_icon_round",
      "RandomIcon",
      "GodiconRandom",
    ],
    random_custom_pool: [
      "Gods_List_Random_Icon",
      "Icon_Godicon_Random",
      "random_icon_round",
      "RandomIcon",
      "GodiconRandom",
    ],
    n_wa: ["nuwa_icon_round", "nuwa_icon", "NuwaIcon", "GodiconNuwa"],
  };

  if (aliases[normalized]) {
    return aliases[normalized];
  }

  const pascalName = String(godName || "")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join("");

  return [
    `${normalized}_icon_round`,
    `${normalized}_icon`,
    `Gods_List_${pascalName}_Icon`,
    `Icon_Godicon_${pascalName}`,
    `${pascalName}Icon`,
    `Godicon${pascalName}`,
    normalized,
  ].filter(Boolean);
}

function renderGodIconImage(godName, candidates, fallbackText) {
  const cleanCandidates = Array.isArray(candidates) && candidates.length
    ? candidates
    : getGodIconFilenameCandidates(godName);

  const firstCandidate = cleanCandidates[0] || "random_icon_round";
  const firstPath = `${GOD_ICON_BASE_PATHS[0]}/${firstCandidate}.png`;

  return `
    <img
      class="player-god-icon"
      src="${escapeHtml(firstPath)}"
      alt="${escapeHtml(godName || "Unknown God")} icon"
      loading="lazy"
      data-god-filenames="${escapeHtml(cleanCandidates.join("|"))}"
      data-god-filename-index="0"
      data-god-path-index="0"
      onerror="window.handleGodImageError(this)"
    />
    <span class="player-god-fallback">${escapeHtml(fallbackText || "?")}</span>
  `;
}

window.handleGodImageError = function handleGodImageError(imageElement) {
  const filenames = String(imageElement.dataset.godFilenames || "")
    .split("|")
    .filter(Boolean);

  const currentFilenameIndex = Number(imageElement.dataset.godFilenameIndex || 0);
  const currentPathIndex = Number(imageElement.dataset.godPathIndex || 0);

  const nextFilenameIndex = currentFilenameIndex + 1;

  if (nextFilenameIndex < filenames.length) {
    imageElement.dataset.godFilenameIndex = String(nextFilenameIndex);
    imageElement.src = `${GOD_ICON_BASE_PATHS[currentPathIndex]}/${filenames[nextFilenameIndex]}.png`;
    return;
  }

  const nextPathIndex = currentPathIndex + 1;

  if (nextPathIndex < GOD_ICON_BASE_PATHS.length) {
    imageElement.dataset.godFilenameIndex = "0";
    imageElement.dataset.godPathIndex = String(nextPathIndex);
    imageElement.src = `${GOD_ICON_BASE_PATHS[nextPathIndex]}/${filenames[0]}.png`;
    return;
  }

  imageElement.onerror = null;
  imageElement.style.display = "none";
};

function renderGodIcon(participant) {
  const godName = participant?.god || "Unknown";
  const candidates = getGodIconFilenameCandidates(godName);
  const fallbackText = getGodFallbackText(godName);

  return `
    <div class="player-god-icon-wrap" title="${escapeHtml(godName)}">
      ${renderGodIconImage(godName, candidates, fallbackText)}
    </div>
  `;
}

function renderPlayerRows(lobby) {
  const participants = getVisibleParticipants(lobby);

  if (!participants.length) {
    return `<div class="player-row player-row-empty"><div class="muted">No visible participant data available.</div></div>`;
  }

  return participants
    .map((participant, index) => {
      const isOpenSlot = participant.type === "Open";
      const metaItems = isOpenSlot ? [] : getPlayerMetaItems(participant);
      const leaderboardBadge = isOpenSlot ? "" : renderLeaderboardBadge(participant, lobby);
      const displayName = isOpenSlot ? "Open" : participant.name || "Unknown";

      return `
        <div class="player-row ${isOpenSlot ? "player-row-open" : "player-row-clickable"}" data-player-index="${index}">
          <div class="slot-number">${escapeHtml(participant.slot_number ?? "?")}</div>
          <div class="player-main">
            <div class="player-name">${escapeHtml(displayName)}</div>
            ${
              (metaItems.length || leaderboardBadge)
                ? `
                  <div class="player-meta">
                    ${metaItems.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
                    ${leaderboardBadge}
                  </div>
                `
                : ""
            }
          </div>
          ${isOpenSlot ? `<div class="player-god-spacer" aria-hidden="true"></div>` : renderGodIcon(participant)}
        </div>
      `;
    })
    .join("");
}

function getPlayerMetaItems(participant) {
  const metaItems = [];

  if (participant.type === "AI") {
    metaItems.push("AI");
  }

  const rating = formatRating(participant);

  if (rating && !["AI", "Open", "Unrated"].includes(rating)) {
    metaItems.push(rating);
  }

  if (participant.country) {
    metaItems.push(String(participant.country).toUpperCase());
  }

  return metaItems;
}

function settingRow(label, value, extraClass = "") {
  return `
    <div class="setting-row ${escapeHtml(extraClass)}">
      <span class="setting-label">${escapeHtml(label)}</span>
      <span class="setting-value">${escapeHtml(formatSettingValue(value))}</span>
    </div>
  `;
}

function formatSettingValue(value) {
  if (value === null || value === undefined || value === "") {
    return "Unknown";
  }

  return value;
}

function getTeamModeSetting(lobby) {
  const directValue =
    lobby.team_mode ??
    lobby.teamMode ??
    lobby.team_mode_label ??
    lobby.diplomacy ??
    lobby.diplomacy_setting ??
    lobby.diplomacy_mode;

  if (directValue === null || directValue === undefined || directValue === "") {
    return null;
  }

  const normalized = makeAssetFilename(directValue);
  const teamModeNames = {
    free_for_all: "Free for All",
    ffa: "Free for All",
    diplomacy: "Diplomacy",
    diplomatic: "Diplomacy",
    teams: "Teams",
    team: "Teams",
  };

  return teamModeNames[normalized] || directValue;
}

function getVictoryConditionSetting(lobby) {
  const directValue =
    lobby.victory_condition ??
    lobby.victoryCondition ??
    lobby.win_condition ??
    lobby.winCondition ??
    lobby.victory ??
    lobby.condition;

  if (directValue === null || directValue === undefined || directValue === "") {
    return null;
  }

  const normalized = makeAssetFilename(directValue);
  const victoryNames = {
    standard: "Standard",
    conquest: "Conquest",
    supremacy: "Supremacy",
    wonder: "Wonder",
    deathmatch: "Deathmatch",
    death_match: "Deathmatch",
  };

  return victoryNames[normalized] || directValue;
}

function isNonStandardSetting(labelValue, idValue) {
  const idNumber = Number(idValue);

  if (Number.isFinite(idNumber) && idNumber > 0) {
    return idNumber !== 1;
  }

  const normalized = makeAssetFilename(labelValue);

  if (!normalized || normalized === "unknown") {
    return false;
  }

  return normalized !== "standard";
}

function getMapSizeClass(mapSize) {
  const normalized = makeAssetFilename(mapSize);

  if (normalized === "giant") {
    return "map-size-giant";
  }

  if (normalized === "large") {
    return "map-size-large";
  }

  return "";
}

function renderEmptySidebar() {
  if (!detailsSidebar) {
    return;
  }

  detailsSidebar.innerHTML = `
    ${getWidgetFrameOrnamentsMarkup()}
    <div class="details-sidebar-frame">
      <div class="empty-state">
        <div class="empty-icon">☥</div>
        <h2>No lobby selected</h2>
        <p>Change the filters or refresh the lobby list to see available games.</p>
      </div>
    </div>
  `;
}

function renderDetailsSidebar(lobby, options = {}) {
  if (!detailsSidebar) {
    return;
  }

  if (!lobby) {
    renderEmptySidebar();
    return;
  }

  const mapSize = formatSettingValue(lobby.map_size);
  const teamMode = getTeamModeSetting(lobby);
  const victoryCondition = getVictoryConditionSetting(lobby);
  const cheatsEnabled = Boolean(lobby.cheats_enabled);
  const resourcesNonStandard = isNonStandardSetting(
    lobby.starting_resources,
    lobby.starting_resources_id,
  );
  const visibilityNonStandard = isNonStandardSetting(
    lobby.map_visibility,
    lobby.map_visibility_id,
  );

  detailsSidebar.innerHTML = `
    ${getWidgetFrameOrnamentsMarkup()}

    <div class="details-sidebar-frame">
      <div class="sidebar-title-row">
        <div>
          <h2 class="sidebar-title">${escapeHtml(lobby.name || "Unnamed lobby")}</h2>
          <p class="sidebar-subtitle">
            <span class="sidebar-host-name">${escapeHtml(lobby.host || "Unknown")}</span>
            <span class="sidebar-region-name">· ${escapeHtml(formatRegion(lobby.region))}</span>
          </p>
        </div>
      </div>

      <div class="sidebar-map map-feature">
        ${renderMapImage(lobby.map || "Unknown", "map-thumb large")}
        <div class="sidebar-map-caption">
          <strong>${escapeHtml(formatMapName(lobby.map))}</strong>
          <span>${escapeHtml(formatGameType(lobby.game_mode))}</span>
        </div>
        <div class="map-size-callout ${escapeHtml(getMapSizeClass(mapSize))}">
          <span>Map Size</span>
          <strong>${escapeHtml(mapSize)}</strong>
        </div>
      </div>

      <section class="sidebar-section">
        <h3 class="section-title">Players</h3>
        <div class="player-list">
          ${renderPlayerRows(lobby)}
        </div>
      </section>

      <section class="sidebar-section">
        <h3 class="section-title">Lobby Details</h3>
        <div class="settings-list">
          ${settingRow("Game Type", formatGameType(lobby.game_mode))}
          ${victoryCondition ? settingRow("Victory Condition", victoryCondition) : ""}
          ${teamMode ? settingRow("Team Mode", teamMode) : ""}
          ${settingRow("Region", formatRegion(lobby.region))}
          ${settingRow("Speed", lobby.speed)}
          ${settingRow(
            "Resources",
            lobby.starting_resources,
            resourcesNonStandard ? "setting-row-danger" : "",
          )}
          ${settingRow(
            "Map Visibility",
            lobby.map_visibility,
            visibilityNonStandard ? "setting-row-danger" : "",
          )}
          ${settingRow("Difficulty", lobby.difficulty)}
          ${settingRow(
            "Cheats",
            cheatsEnabled ? "Enabled" : "Disabled",
            cheatsEnabled ? "setting-row-danger" : "",
          )}
          ${settingRow(
            "Password",
            lobby.password_protected ? "Required" : "No",
            lobby.password_protected ? "setting-row-warning" : "",
          )}
          ${settingRow("Slots", formatSlots(lobby))}
        </div>
      </section>
    </div>
  `;

  detailsSidebar.querySelectorAll(".player-row-clickable").forEach((row) => {
    row.addEventListener("click", () => {
      const playerIndex = Number(row.dataset.playerIndex);
      const participant = getVisibleParticipants(lobby)[playerIndex];

      if (participant) {
        openPlayerDetails(participant, lobby);
      }
    });
  });

  if (!options.skipLeaderboardLoad) {
    loadLeaderboardForLobby(lobby).catch((error) => {
      console.warn(error);
    });
  }
}

function preserveOrResetSelection() {
  if (selectedLobbyId === null || selectedLobbyId === undefined) {
    renderEmptySidebar();
    renderTableSelection();
    return;
  }

  const stillVisible = filteredLobbies.find(
    (lobby) => String(lobby.id) === String(selectedLobbyId),
  );

  if (stillVisible) {
    renderDetailsSidebar(stillVisible);
    renderTableSelection();
    return;
  }

  selectedLobbyId = null;
  renderEmptySidebar();
  renderTableSelection();
}

function renderTableSelection() {
  if (!lobbyTableBody) {
    return;
  }

  lobbyTableBody.querySelectorAll("tr").forEach((row) => {
    row.classList.toggle(
      "selected",
      row.dataset.lobbyId === String(selectedLobbyId),
    );
  });
}

function renderSummary() {
  if (!summary) {
    return;
  }

  const total = lobbies.length;
  const visible = filteredLobbies.length;
  const players = filteredLobbies.reduce(
    (sum, lobby) => sum + Number(lobby.occupied_slots ?? calculateOccupiedSlots(lobby)),
    0,
  );

  summary.textContent = `${visible} of ${total} lobbies shown · ${players} player${players === 1 ? "" : "s"} visible`;
}

function showTooltip(lobby, event) {
  if (!hoverTooltip) {
    return;
  }

  const participants = getVisibleParticipants(lobby).filter((participant) => {
    const type = String(participant?.type || "").trim().toLowerCase();
    return type && type !== "open" && type !== "closed";
  });
  const participantRows = participants
    .slice(0, 6)
    .map((participant) => {
      const name = participant.name || (participant.type === "AI" ? "AI Player" : "Unknown");
      const metaItems = getPlayerMetaItems(participant);

      return `
        <div class="tooltip-player-row">
          ${renderGodIcon(participant)}
          <div class="tooltip-player-main">
            <span class="tooltip-player-name">${escapeHtml(name)}</span>
            ${
              metaItems.length
                ? `<span class="tooltip-player-meta">${metaItems.map((item) => escapeHtml(item)).join(" · ")}</span>`
                : ""
            }
          </div>
        </div>
      `;
    })
    .join("");

  const extraCount =
    participants.length > 6
      ? `<div class="muted">+${participants.length - 6} more participant(s)</div>`
      : "";

  hoverTooltip.innerHTML = `
    <div class="tooltip-title">${escapeHtml(lobby.name || "Unnamed lobby")}</div>
    ${lobby.host ? `<div class="tooltip-host">Hosted by ${escapeHtml(lobby.host)}</div>` : ""}
    <div class="tooltip-meta">
      ${tooltipMetaChip("map", formatMapName(lobby.map))}
      ${tooltipMetaChip("mode", formatGameType(lobby.game_mode))}
      ${tooltipMetaChip("players", `${formatSlots(lobby)} players`)}
      ${tooltipMetaChip("region", formatRegion(lobby.region))}
    </div>
    ${participantRows ? `<div class="tooltip-player-list">${participantRows}</div>` : ""}
    ${extraCount}
  `;

  hoverTooltip.style.display = "block";
  moveTooltip(event);
}

function tooltipMetaChip(type, value) {
  const text = String(value || "").trim();

  if (!text || ["unknown", "open", "unrated", "none"].includes(text.toLowerCase())) {
    return "";
  }

  const icons = {
    map: "🗺",
    mode: "⚔",
    players: "👥",
    region: "◎",
  };

  return `
    <span class="tooltip-chip tooltip-chip-${escapeHtml(type)}">
      <span class="tooltip-chip-icon" aria-hidden="true">${icons[type] || "•"}</span>
      <span>${escapeHtml(text)}</span>
    </span>
  `;
}

function moveTooltip(event) {
  if (!hoveredLobby || !hoverTooltip) {
    return;
  }

  const padding = 16;
  const tooltipRect = hoverTooltip.getBoundingClientRect();

  let left = event.clientX + 18;
  let top = event.clientY + 18;

  if (left + tooltipRect.width + padding > window.innerWidth) {
    left = event.clientX - tooltipRect.width - 18;
  }

  if (top + tooltipRect.height + padding > window.innerHeight) {
    top = event.clientY - tooltipRect.height - 18;
  }

  hoverTooltip.style.left = `${Math.max(padding, left)}px`;
  hoverTooltip.style.top = `${Math.max(padding, top)}px`;
}

function hideTooltip() {
  if (!hoverTooltip) {
    return;
  }

  hoverTooltip.style.display = "none";
  hoverTooltip.innerHTML = "";
}

function getOpenLobbySortKeyFromHeader(headerElement) {
  if (!headerElement) {
    return "";
  }

  const explicitSortKey =
    headerElement.dataset.sort ||
    headerElement.dataset.lobbySort ||
    headerElement.dataset.openSort ||
    "";

  const cellIndex = Number(headerElement.cellIndex);
  const headerText = String(headerElement.textContent || "").trim().toLowerCase();

  if (
    cellIndex === 1 &&
    (headerText.includes("player") ||
      explicitSortKey === "players" ||
      explicitSortKey === "occupied_slots" ||
      explicitSortKey === "slots")
  ) {
    return "max_players";
  }

  if (explicitSortKey) {
    return explicitSortKey;
  }

  if (cellIndex === 0) {
    return "name";
  }

  if (cellIndex === 1) {
    return "max_players";
  }

  if (cellIndex === 2) {
    return "game_mode";
  }

  if (cellIndex === 3) {
    return "map";
  }

  if (cellIndex === 4) {
    return "region";
  }

  return "";
}

function updateOpenLobbySortIndicators() {
  const openLobbyTable = lobbyTableBody?.closest("table");

  if (!openLobbyTable) {
    return;
  }

  openLobbyTable.querySelectorAll("thead th").forEach((header) => {
    const headerSortKey = getOpenLobbySortKeyFromHeader(header);
    const isActiveSort = headerSortKey === sortKey;

    header.classList.toggle("sorted-asc", isActiveSort && sortDirection === "asc");
    header.classList.toggle("sorted-desc", isActiveSort && sortDirection === "desc");

    if (headerSortKey) {
      header.dataset.sortActive = isActiveSort ? "true" : "false";
      header.dataset.sortDirection = isActiveSort ? sortDirection : "";
    }
  });
}

function handleSortClick(event) {
  const openLobbyTable = lobbyTableBody?.closest("table");

  if (!openLobbyTable) {
    return;
  }

  const sortableHeader = event.target.closest("th");

  if (!sortableHeader || !openLobbyTable.contains(sortableHeader)) {
    return;
  }

  const clickedKey = getOpenLobbySortKeyFromHeader(sortableHeader);

  if (!clickedKey) {
    return;
  }

  if (sortKey === clickedKey) {
    sortDirection = sortDirection === "asc" ? "desc" : "asc";
  } else {
    sortKey = clickedKey;
    sortDirection =
      clickedKey === "players" ||
      clickedKey === "max_players" ||
      clickedKey === "max_player_size" ||
      clickedKey === "occupied_slots" ||
      clickedKey === "slots"
        ? "desc"
        : "asc";
  }

  applyFiltersAndRender();
}

function shouldLoadActiveMatchesForTab(tabName) {
  return tabName === "inProgressCustom" || tabName === "observable";
}

function ensureActiveMatchesScriptLoaded() {
  if (!ACTIVE_MATCHES_SCRIPT_URL || typeof document === "undefined") {
    return Promise.resolve();
  }

  if (activeMatchesScriptPromise) {
    return activeMatchesScriptPromise;
  }

  const existingScript = Array.from(document.scripts).find((script) => {
    return script.getAttribute("src") === ACTIVE_MATCHES_SCRIPT_URL;
  });

  if (existingScript) {
    activeMatchesScriptPromise = Promise.resolve();
    return activeMatchesScriptPromise;
  }

  activeMatchesScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = ACTIVE_MATCHES_SCRIPT_URL;
    script.defer = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Unable to load active matches."));
    document.body.appendChild(script);
  });

  return activeMatchesScriptPromise;
}

function loadActiveMatchesForTab(tabName) {
  if (!shouldLoadActiveMatchesForTab(tabName)) {
    return;
  }

  ensureActiveMatchesScriptLoaded().catch((error) => {
    console.error(error);
  });
}

function switchTab(tabName) {
  activeTab = tabName;

  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });

  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.remove("active");
  });

  const targetPanel = document.getElementById(`${tabName}Tab`);

  if (targetPanel) {
    targetPanel.classList.add("active");
  }

  loadActiveMatchesForTab(tabName);

  if (tabName === "live" && !liveActivityLoaded) {
    loadLiveActivity().catch((error) => {
      console.error(error);
      renderLiveActivityError(error);
    });
  }

  hideTooltip();
}

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

function attachEventListeners() {
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      switchTab(button.dataset.tab);
    });
  });

  [
    searchInput,
    regionFilter,
    modeFilter,
    mapFilter,
    hideAiGames,
    hideFullLobbies,
    hidePassworded,
    hideCheats,
  ].forEach((element) => {
    if (!element) {
      return;
    }

    element.addEventListener("input", applyFiltersAndRender);
    element.addEventListener("change", applyFiltersAndRender);
  });

  const openLobbyTable = lobbyTableBody?.closest("table");

  if (openLobbyTable) {
    openLobbyTable.querySelectorAll("thead th").forEach((header) => {
      const sortKeyForHeader = getOpenLobbySortKeyFromHeader(header);

      if (sortKeyForHeader) {
        header.dataset.sort = sortKeyForHeader;
        header.classList.add("sortable-header");
        header.setAttribute("role", "button");
        header.setAttribute("tabindex", "0");
      }
    });

    openLobbyTable.querySelector("thead")?.addEventListener("click", handleSortClick);

    openLobbyTable.querySelector("thead")?.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }

      event.preventDefault();
      handleSortClick(event);
    });
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", () => {
      /*
        active_matches.js owns refresh behavior for:
          - inProgressCustom
          - observable
      */
      const isLivePage = document.body?.dataset.page === "live-activity";

      if (!isLivePage && activeTab !== "custom" && activeTab !== "live") {
        return;
      }

      refreshButton.disabled = true;
      refreshButton.textContent = "Refreshing...";

      const refreshRequest = isLivePage || activeTab === "live"
        ? loadLiveActivity(true)
        : loadLobbies(true);

      refreshRequest
        .catch((error) => {
          console.error(error);

          if (isLivePage || activeTab === "live") {
            renderLiveActivityError(error);
          } else {
            if (summary) {
              summary.textContent = error.message;
            }

            renderEmptySidebar();
          }
        })
        .finally(() => {
          refreshButton.disabled = false;
          refreshButton.textContent = "Refresh";
        });
    });
  }


  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideTooltip();
      closePlayerDetails();
    }
  });
}

function applyTopLogo() {
  const selectors = [
    ".brand-title",
    ".app-title",
    ".site-title",
    ".logo-title",
    ".top-title",
    ".header-title",
    "header h1",
    ".app-header h1",
    ".topbar h1",
    ".hero h1",
  ];

  let target = null;

  for (const selector of selectors) {
    const candidate = document.querySelector(selector);

    if (
      candidate &&
      /age\s+of\s+mythology|lobby\s+browser|retold/i.test(candidate.textContent || "")
    ) {
      target = candidate;
      break;
    }
  }

  if (!target) {
    return;
  }

  target.classList.add("top-logo-title");
  target.innerHTML = `
    <img
      class="top-logo-image"
      src="${STATIC_URL}assets/optimized/images/Top_Logo.webp"
      alt="Age of Mythology Retold"
      loading="eager"
      onerror="this.onerror=null;this.src='${STATIC_URL}assets/images/Top_Logo.png';"
    />
  `;
}
function initializeSiteMenu() {
  const menu = document.querySelector(".site-menu");
  const button = document.getElementById("siteMenuButton");
  const dropdown = document.getElementById("siteMenuDropdown");

  if (!menu || !button || !dropdown) {
    return;
  }

  function closeMenu() {
    menu.classList.remove("is-open");
    button.setAttribute("aria-expanded", "false");
  }

  function toggleMenu() {
    const isOpen = menu.classList.toggle("is-open");
    button.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }

  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    toggleMenu();
  });

  dropdown.addEventListener("click", (event) => {
    event.stopPropagation();

    if (event.target.closest("a")) {
      closeMenu();
    }
  });

  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target)) {
      closeMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
    }
  });
}

const currentPage = document.body?.dataset.page || "lobby-browser";

if (currentPage === "lobby-browser") {
  ensureLobbyPanelSections();
  ensurePlayerDetailsModal();
}

attachEventListeners();

if (currentPage === "live-activity") {
  initializeLiveMapLandMask();
  bindLiveMapDevControls();

  window.addEventListener("resize", () => {
    window.clearTimeout(window.liveActivityResizeTimer);
    window.liveActivityResizeTimer = window.setTimeout(redrawLiveActivityMap, 180);
  });

  loadLiveActivity(false)
    .then(() => startLiveActivityAutoRefresh())
    .catch((error) => {
      console.error(error);
      renderLiveActivityError(error);
      startLiveActivityAutoRefresh();
    });
} else {
  loadLobbies().catch((error) => {
    console.error(error);

    if (summary) {
      summary.textContent = error.message;
    }

    if (filterNote) {
      filterNote.textContent =
        "Make sure the Django lobby API is reachable at /api/lobbies/.";
    }

    renderEmptySidebar();
  });
}
