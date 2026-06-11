const API_BASE_URL = window.AOM_API_BASE_URL || "";
const STATIC_URL = window.AOM_STATIC_URL || "/static/";
const ACTIVE_MATCHES_SCRIPT_URL = window.AOM_ACTIVE_MATCHES_SCRIPT_URL || "";
const INITIAL_LOBBY_PAGE_COUNT = 2;
const FULL_LOBBY_PAGE_COUNT = 4;

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
let pendingLobbyHydration = null;

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

let liveActivityScriptPromise = null;
let liveActivityStylesheetPromise = null;


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

async function loadLobbies(forceRefresh = false, options = {}) {
  const pageCount = options.pageCount ?? (
    forceRefresh ? FULL_LOBBY_PAGE_COUNT : INITIAL_LOBBY_PAGE_COUNT
  );
  const isBackground = Boolean(options.isBackground);

  if (summary && !isBackground) {
    summary.textContent = "Loading lobbies...";
  }

  if (filterNote && !isBackground) {
    filterNote.textContent = "";
  }

  const params = new URLSearchParams();

  if (forceRefresh) {
    params.set("refresh", "1");
  }

  params.set("pages", String(pageCount));

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

  if (
    !forceRefresh &&
    !isBackground &&
    pageCount < FULL_LOBBY_PAGE_COUNT &&
    lobbies.length >= pageCount * 25
  ) {
    scheduleFullLobbyHydration();
  }
}

function scheduleFullLobbyHydration() {
  if (pendingLobbyHydration) {
    return;
  }

  const hydrate = () => {
    pendingLobbyHydration = loadLobbies(false, {
      pageCount: FULL_LOBBY_PAGE_COUNT,
      isBackground: true,
    })
      .catch((error) => {
        console.warn(error);
      })
      .finally(() => {
        pendingLobbyHydration = null;
      });
  };

  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(hydrate, { timeout: 2500 });
  } else {
    window.setTimeout(hydrate, 900);
  }
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

function ensureLiveActivityScriptLoaded() {
  const liveActivity = window.ProstagmaLiveActivity;

  if (liveActivity) {
    return Promise.resolve(liveActivity);
  }

  const scriptUrl = window.AOM_LIVE_ACTIVITY_SCRIPT_URL || "";

  if (!scriptUrl) {
    return Promise.reject(new Error("Live activity script URL is not configured."));
  }

  if (liveActivityScriptPromise) {
    return liveActivityScriptPromise;
  }

  const existingScript = Array.from(document.scripts).find((script) => {
    return script.getAttribute("src") === scriptUrl;
  });

  if (existingScript) {
    liveActivityScriptPromise = new Promise((resolve, reject) => {
      if (window.ProstagmaLiveActivity) {
        resolve(window.ProstagmaLiveActivity);
        return;
      }

      existingScript.addEventListener("load", () => resolve(window.ProstagmaLiveActivity));
      existingScript.addEventListener("error", () => reject(new Error("Unable to load live activity.")));
    });
    return liveActivityScriptPromise;
  }

  liveActivityScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = scriptUrl;
    script.defer = true;
    script.onload = () => resolve(window.ProstagmaLiveActivity);
    script.onerror = () => reject(new Error("Unable to load live activity."));
    document.body.appendChild(script);
  });

  return liveActivityScriptPromise;
}

function ensureLiveActivityStylesheetLoaded() {
  const stylesheetUrl = window.AOM_LIVE_ACTIVITY_STYLESHEET_URL || "";

  if (!stylesheetUrl) {
    return Promise.resolve();
  }

  const normalizedStylesheetUrl = new URL(stylesheetUrl, window.location.href).href;
  const existingLink = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).find((link) => {
    return link.href === normalizedStylesheetUrl;
  });

  if (existingLink) {
    liveActivityStylesheetPromise = Promise.resolve();
    return liveActivityStylesheetPromise;
  }

  if (liveActivityStylesheetPromise) {
    return liveActivityStylesheetPromise;
  }

  liveActivityStylesheetPromise = new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = stylesheetUrl;
    link.onload = resolve;
    link.onerror = () => reject(new Error("Unable to load live activity styles."));
    document.head.appendChild(link);
  });

  return liveActivityStylesheetPromise;
}

async function loadLiveActivityForTab(forceRefresh = false) {
  const [liveActivity] = await Promise.all([
    ensureLiveActivityScriptLoaded(),
    ensureLiveActivityStylesheetLoaded(),
  ]);

  if (!liveActivity?.loadAndStart) {
    throw new Error("Live activity runtime did not initialize.");
  }

  if (forceRefresh || !liveActivity.isLoaded?.()) {
    return liveActivity.loadAndStart(forceRefresh);
  }

  liveActivity.startAutoRefresh?.();
  return undefined;
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

  if (tabName === "live") {
    loadLiveActivityForTab().catch((error) => {
      console.error(error);
      window.ProstagmaLiveActivity?.renderError?.(error);
    });
  }

  hideTooltip();
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
        ? loadLiveActivityForTab(true)
        : loadLobbies(true);

      refreshRequest
        .catch((error) => {
          console.error(error);

          if (isLivePage || activeTab === "live") {
            window.ProstagmaLiveActivity?.renderError?.(error);
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

if (currentPage === "lobby-browser") {
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
