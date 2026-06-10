const activeMatchInstances = {};

const activeMatchShared = {
  clockTimer: null,
};

function escapeActiveMatchHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function titleCaseFromSlug(value) {
  const cleaned = String(value ?? "")
    .replace(/^rm_/, "")
    .replace(/^map_/, "")
    .replace(/^god_/, "")
    .replace(/_/g, " ")
    .trim();

  if (!cleaned) {
    return "Unknown";
  }

  return cleaned.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function activeFormatMapName(mapName) {
  if (typeof window.formatMapName === "function") {
    return window.formatMapName(mapName);
  }

  return titleCaseFromSlug(mapName);
}

function formatServerName(server) {
  const raw = String(server ?? "").trim();

  if (!raw) {
    return "Unknown";
  }

  return raw
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/-/g, " ")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function activeFormatRegion(region) {
  if (typeof window.formatRegion === "function") {
    return window.formatRegion(region);
  }

  return formatServerName(region);
}

function activeRenderMapImage(mapName, className) {
  if (typeof window.renderMapImage === "function") {
    return window.renderMapImage(mapName, className);
  }

  return `
    <div class="${escapeActiveMatchHtml(className)} map-thumb-fallback">
      ${escapeActiveMatchHtml(activeFormatMapName(mapName))}
    </div>
  `;
}

function activeGetWidgetFrameOrnamentsMarkup() {
  if (typeof window.getWidgetFrameOrnamentsMarkup === "function") {
    return window.getWidgetFrameOrnamentsMarkup();
  }

  return "";
}

function activeSettingRow(label, value, extraClass = "") {
  if (typeof window.settingRow === "function") {
    return window.settingRow(label, value, extraClass);
  }

  return `
    <div class="setting-row ${escapeActiveMatchHtml(extraClass)}">
      <span class="setting-label">${escapeActiveMatchHtml(label)}</span>
      <span class="setting-value">${escapeActiveMatchHtml(value ?? "Unknown")}</span>
    </div>
  `;
}

function ensureActiveMatchPanelSections() {
  document.querySelectorAll(".active-matches-tab .lobby-panel").forEach((lobbyPanel) => {
    if (lobbyPanel.querySelector(":scope > .lobby-controls-frame")) {
      return;
    }

    const controlsFrame = document.createElement("section");
    controlsFrame.className = "lobby-subpanel lobby-controls-frame";
    controlsFrame.insertAdjacentHTML("afterbegin", activeGetWidgetFrameOrnamentsMarkup());

    const listFrame = document.createElement("section");
    listFrame.className = "lobby-subpanel lobby-list-frame";
    listFrame.insertAdjacentHTML("afterbegin", activeGetWidgetFrameOrnamentsMarkup());

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
  });
}

function parseMatchStartDate(startgametime) {
  if (!startgametime) {
    return null;
  }

  let date;

  if (typeof startgametime === "number") {
    const milliseconds = startgametime < 10000000000
      ? startgametime * 1000
      : startgametime;

    date = new Date(milliseconds);
  } else {
    date = new Date(startgametime);
  }

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date;
}

function getMatchAgeSeconds(match) {
  const date = parseMatchStartDate(match.startgametime);

  if (!date) {
    return 0;
  }

  const elapsedMilliseconds = Date.now() - date.getTime();
  return Math.max(0, Math.floor(elapsedMilliseconds / 1000));
}

function formatMatchDuration(match) {
  const totalSeconds = getMatchAgeSeconds(match);

  if (totalSeconds < 1) {
    return "0:00";
  }

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function getActiveTabName() {
  const activeTabButton = document.querySelector(".tab-button.active");
  return activeTabButton?.dataset?.tab || "custom";
}

function getPlayers(match) {
  return Array.isArray(match.players) ? match.players : [];
}

function getSortedTeamEntries(match) {
  const teams = match.teams || {};

  return Object.entries(teams).sort(([teamA], [teamB]) => {
    const numberA = Number(teamA);
    const numberB = Number(teamB);

    if (Number.isNaN(numberA) || Number.isNaN(numberB)) {
      return String(teamA).localeCompare(String(teamB));
    }

    return numberA - numberB;
  });
}

function getMatchQueueType(match) {
  if (match.source === "custom") {
    return "custom";
  }

  const leaderboardId = Number(match.leaderboard_id ?? match.matchtype_id ?? 0);
  const title = String(match.title ?? "").toUpperCase();
  const playerCount = getPlayers(match).length;

  if (leaderboardId === 1) {
    return "standard";
  }

  if (leaderboardId === 2) {
    return "team_standard";
  }

  if (leaderboardId === 3) {
    return "deathmatch";
  }

  if (leaderboardId === 4) {
    return "team_deathmatch";
  }

  const isDeathmatch =
    title.includes("DEATHMATCH") ||
    title.includes("DEATH MATCH") ||
    title.includes(" DM ") ||
    title.endsWith(" DM");

  const isTeam =
    title.includes("TEAM") ||
    title.includes("2V2") ||
    title.includes("3V3") ||
    title.includes("4V4") ||
    playerCount > 2;

  if (isDeathmatch && isTeam) {
    return "team_deathmatch";
  }

  if (isDeathmatch) {
    return "deathmatch";
  }

  if (isTeam) {
    return "team_standard";
  }

  if (title.includes("STANDARD") || title.includes("AUTOMATCH")) {
    return "standard";
  }

  return "other";
}

function getMatchQueueLabel(match) {
  const queueType = getMatchQueueType(match);

  if (queueType === "custom") {
    return "Custom";
  }

  if (queueType === "standard") {
    return "1v1 Standard";
  }

  if (queueType === "team_standard") {
    return "Team Standard";
  }

  if (queueType === "deathmatch") {
    return "Deathmatch";
  }

  if (queueType === "team_deathmatch") {
    return "Team Deathmatch";
  }

  return "Other";
}

function getMatchTitle(match) {
  const rawTitle = String(match.title ?? "").trim();

  if (rawTitle && rawTitle.toUpperCase() !== "AUTOMATCH") {
    return rawTitle;
  }

  if (match.source === "custom") {
    const players = getPlayers(match);

    if (players.length >= 2) {
      return `Custom - ${players[0].alias || "Player 1"} VS ${players[1].alias || "Player 2"}`;
    }

    return "Custom Match";
  }

  const teamEntries = getSortedTeamEntries(match);

  if (teamEntries.length >= 2) {
    const teamOneName = teamEntries[0][1][0]?.alias || "Team 1";
    const teamTwoName = teamEntries[1][1][0]?.alias || "Team 2";
    return `Ranked - ${teamOneName} VS ${teamTwoName}`;
  }

  const players = getPlayers(match);

  if (players.length >= 2) {
    return `Ranked - ${players[0].alias || "Player 1"} VS ${players[1].alias || "Player 2"}`;
  }

  return "Ranked";
}

function getAverageRating(players) {
  if (!Array.isArray(players) || players.length === 0) {
    return "1000";
  }

  const ratings = players.map((player) => {
    const rating = Number(player.rating);

    if (!Number.isFinite(rating) || rating <= 0) {
      return 1000;
    }

    return rating;
  });

  const total = ratings.reduce((sum, rating) => sum + rating, 0);
  return String(Math.round(total / ratings.length));
}

function getAverageRatingNumber(match) {
  return Number(getAverageRating(getPlayers(match))) || 1000;
}

function getObserverCount(match) {
  const value = Number(match.spectators ?? match.observers ?? match.observer_count ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function normalizeActiveMatchParticipant(player, index) {
  const teamNumber = Number(player.team);
  const slotNumber = index + 1;

  return {
    slot_number: slotNumber,
    type: "Human",
    name: player.alias || "Unknown Player",
    god: player.god || "Unknown",
    rating: player.rating,
    profile_id: player.profile_id,
    leaderboard_id: player.profile_id,
    team: Number.isFinite(teamNumber) ? teamNumber : player.team,
    country: player.country || "",
    platform: player.platform || "",
  };
}

function getActiveMatchParticipants(match) {
  return getPlayers(match).map(normalizeActiveMatchParticipant);
}

function renderGodIconForActiveParticipant(participant) {
  if (typeof window.renderGodIcon === "function") {
    return window.renderGodIcon(participant);
  }

  return `<div class="player-god-spacer" aria-hidden="true"></div>`;
}

function renderActiveMatchPlayerRows(instance, match) {
  const participants = getActiveMatchParticipants(match);

  if (!participants.length) {
    return `
      <div class="player-row player-row-empty">
        <div class="muted">No visible participant data available.</div>
      </div>
    `;
  }

  return participants
    .map((participant, index) => {
      const isAi = String(participant.type || "").toLowerCase() === "ai";
      const metaItems = [];

      if (isAi) {
        metaItems.push("AI");
      } else if (participant.rating) {
        metaItems.push(String(participant.rating));
      }

      if (participant.team !== null && participant.team !== undefined && participant.team !== "") {
        const teamNumber = Number(participant.team);
        metaItems.push(Number.isFinite(teamNumber) ? `Team ${teamNumber + 1}` : `Team ${participant.team}`);
      }

      return `
        <div class="player-row ${isAi ? "" : "player-row-clickable"}" data-match-kind="${escapeActiveMatchHtml(instance.kind)}" data-player-index="${index}">
          <div class="slot-number">${escapeActiveMatchHtml(participant.slot_number ?? "?")}</div>
          <div class="player-main">
            <div class="player-name">${escapeActiveMatchHtml(participant.name || "Unknown")}</div>
            ${
              metaItems.length
                ? `
                  <div class="player-meta">
                    ${metaItems.map((item) => `<span>${escapeActiveMatchHtml(item)}</span>`).join("")}
                  </div>
                `
                : ""
            }
          </div>
          ${isAi ? `<div class="player-god-spacer" aria-hidden="true"></div>` : renderGodIconForActiveParticipant(participant)}
        </div>
      `;
    })
    .join("");
}

function buildActiveMatchSearchText(match) {
  const players = getPlayers(match);

  return [
    match.match_id,
    match.mapname,
    match.server,
    match.title,
    match.leaderboard_id,
    match.matchtype_id,
    getMatchTitle(match),
    getMatchQueueLabel(match),
    ...players.flatMap((player) => [
      player.alias,
      player.god,
      player.profile_id,
      player.rating,
      player.team,
    ]),
  ]
    .filter((value) => value !== null && value !== undefined)
    .join(" ")
    .toLowerCase();
}

function getActiveMatchSortValue(match, key) {
  switch (key) {
    case "match":
      return getMatchTitle(match).toLowerCase();

    case "players":
      return getPlayers(match).length;

    case "elo":
      return getAverageRatingNumber(match);

    case "time":
      return getMatchAgeSeconds(match);

    case "observers":
      return getObserverCount(match);

    case "map":
      return activeFormatMapName(match.mapname).toLowerCase();

    case "region":
      return activeFormatRegion(match.server).toLowerCase();

    default:
      return "";
  }
}

function renderActiveMatchLobbyCell(match) {
  const title = getMatchTitle(match);
  const queueLabel = getMatchQueueLabel(match);

  return `
    <div class="lobby-cell-title">
      <span class="lobby-name active-match-name-truncate" title="${escapeActiveMatchHtml(title)}">
        ${escapeActiveMatchHtml(title)}
      </span>
    </div>
    <div class="lobby-cell-meta">
      <span class="lobby-host-name">${escapeActiveMatchHtml(queueLabel)}</span>
    </div>
  `;
}

function renderActiveMatchPlayersMeter(match) {
  const occupiedSlots = getPlayers(match).length;
  const configuredSlots = Math.max(occupiedSlots, 1);
  const percentage = Math.min(
    100,
    Math.max(0, (occupiedSlots / configuredSlots) * 100),
  );

  return `
    <div class="players-meter" title="${occupiedSlots}/${configuredSlots} players active">
      <div class="players-count">${occupiedSlots}/${configuredSlots}</div>
      <div class="meter-track">
        <div class="meter-fill" style="width: ${percentage}%"></div>
      </div>
    </div>
  `;
}

function renderActiveMatchMapCell(match) {
  const displayName = activeFormatMapName(match.mapname);

  return `
    <div class="map-cell">
      ${activeRenderMapImage(match.mapname || displayName, "map-thumb")}
      <span class="map-name">${escapeActiveMatchHtml(displayName)}</span>
    </div>
  `;
}

function createActiveMatchInstance(config) {
  const instance = {
    kind: config.kind,
    tabName: config.tabName,
    endpoint: config.endpoint,
    sortAttribute: config.sortAttribute,
    defaultQueue: config.defaultQueue ?? "",
    labelSingular: config.labelSingular,
    labelPlural: config.labelPlural,
    matches: [],
    filteredMatches: [],
    selectedMatchId: null,
    search: "",
    queue: config.defaultQueue ?? "",
    server: "",
    map: "",
    sortKey: "elo",
    sortDirection: "desc",
    elements: {
      tableBody: document.getElementById(config.tableBodyId),
      status: document.getElementById(config.statusId),
      searchInput: document.getElementById(config.searchInputId),
      queueFilter: config.queueFilterId ? document.getElementById(config.queueFilterId) : null,
      serverFilter: document.getElementById(config.serverFilterId),
      mapFilter: document.getElementById(config.mapFilterId),
      sidebar: document.getElementById(config.sidebarId),
    },
  };

  activeMatchInstances[instance.kind] = instance;

  return instance;
}

function filterActiveMatches(instance) {
  const search = instance.search.trim().toLowerCase();

  instance.filteredMatches = instance.matches.filter((match) => {
    if (instance.queue && getMatchQueueType(match) !== instance.queue) {
      return false;
    }

    if (instance.server && String(match.server ?? "") !== instance.server) {
      return false;
    }

    if (instance.map && String(match.mapname ?? "") !== instance.map) {
      return false;
    }

    if (search && !buildActiveMatchSearchText(match).includes(search)) {
      return false;
    }

    return true;
  });

  sortActiveMatches(instance);
}

function sortActiveMatches(instance) {
  const directionMultiplier = instance.sortDirection === "asc" ? 1 : -1;
  const sortKey = instance.sortKey;

  instance.filteredMatches.sort((matchA, matchB) => {
    const valueA = getActiveMatchSortValue(matchA, sortKey);
    const valueB = getActiveMatchSortValue(matchB, sortKey);

    if (typeof valueA === "number" && typeof valueB === "number") {
      return (valueA - valueB) * directionMultiplier;
    }

    return String(valueA).localeCompare(String(valueB)) * directionMultiplier;
  });
}

function updateActiveSortHeaders(instance) {
  document.querySelectorAll(`[${instance.sortAttribute}]`).forEach((header) => {
    const isActive = header.getAttribute(instance.sortAttribute) === instance.sortKey;

    header.classList.toggle("sorted", isActive);
    header.classList.toggle("sorted-asc", isActive && instance.sortDirection === "asc");
    header.classList.toggle("sorted-desc", isActive && instance.sortDirection === "desc");
  });
}

function renderActiveMatchesTable(instance) {
  filterActiveMatches(instance);
  updateActiveSortHeaders(instance);

  const matches = instance.filteredMatches;

  if (instance.elements.status) {
    instance.elements.status.textContent = `${matches.length} ${instance.labelPlural}`;
  }

  if (!instance.elements.tableBody) {
    return;
  }

  if (!matches.length) {
    instance.elements.tableBody.innerHTML = `
      <tr>
        <td colspan="7" class="muted">No ${escapeActiveMatchHtml(instance.labelPlural.toLowerCase())} found.</td>
      </tr>
    `;
    renderActiveMatchEmptySidebar(instance);
    return;
  }

  instance.elements.tableBody.innerHTML = "";

  for (const match of matches) {
    const row = document.createElement("tr");
    row.dataset.activeMatchId = String(match.match_id);
    row.classList.toggle(
      "selected",
      String(instance.selectedMatchId) === String(match.match_id),
    );

    row.innerHTML = `
      <td>${renderActiveMatchLobbyCell(match)}</td>
      <td>${renderActiveMatchPlayersMeter(match)}</td>
      <td>
        <strong>${escapeActiveMatchHtml(getAverageRating(getPlayers(match)))}</strong>
      </td>
      <td>
        <strong class="active-match-time" data-match-kind="${escapeActiveMatchHtml(instance.kind)}" data-active-match-time="${escapeActiveMatchHtml(match.match_id)}">
          ${escapeActiveMatchHtml(formatMatchDuration(match))}
        </strong>
      </td>
      <td>
        <strong>${escapeActiveMatchHtml(getObserverCount(match))}</strong>
      </td>
      <td>${renderActiveMatchMapCell(match)}</td>
      <td>
        <span class="region-pill">
          ${escapeActiveMatchHtml(activeFormatRegion(match.server))}
        </span>
      </td>
    `;

    row.addEventListener("click", () => {
      selectActiveMatch(instance, match.match_id);
    });

    instance.elements.tableBody.appendChild(row);
  }
}

function renderActiveMatchEmptySidebar(instance) {
  const sidebar = instance.elements.sidebar;

  if (!sidebar) {
    return;
  }

  sidebar.innerHTML = `
    ${activeGetWidgetFrameOrnamentsMarkup()}

    <div class="details-sidebar-frame active-match-details-frame">
      <div class="empty-state">
        <div class="empty-icon">⚔</div>
        <h2>No match selected</h2>
        <p>Change the filters or refresh the match list to see active games.</p>
      </div>
    </div>
  `;
}

function renderActiveMatchDetails(instance, match) {
  const sidebar = instance.elements.sidebar;

  if (!sidebar) {
    return;
  }

  const players = getPlayers(match);
  const mapName = activeFormatMapName(match.mapname);
  const regionName = activeFormatRegion(match.server);
  const queueLabel = getMatchQueueLabel(match);
  const averageRating = getAverageRating(players);

  sidebar.innerHTML = `
    ${activeGetWidgetFrameOrnamentsMarkup()}

    <div class="details-sidebar-frame active-match-details-frame">
      <div class="sidebar-title-row">
        <div>
          <h2 class="sidebar-title">${escapeActiveMatchHtml(getMatchTitle(match))}</h2>
          <p class="sidebar-subtitle">
            <span class="sidebar-host-name">${escapeActiveMatchHtml(queueLabel)}</span>
            <span class="sidebar-region-name">· ${escapeActiveMatchHtml(regionName)}</span>
          </p>
        </div>
      </div>

      <div class="sidebar-map map-feature">
        ${activeRenderMapImage(match.mapname || "Unknown", "map-thumb large")}
        <div class="sidebar-map-caption">
          <strong>${escapeActiveMatchHtml(mapName)}</strong>
          <span>${escapeActiveMatchHtml(queueLabel)}</span>
        </div>
        <div class="map-size-callout">
          <span>ELO</span>
          <strong>${escapeActiveMatchHtml(averageRating)}</strong>
        </div>
      </div>

      <section class="sidebar-section">
        <h3 class="section-title">Players</h3>
        <div class="player-list">
          ${renderActiveMatchPlayerRows(instance, match)}
        </div>
      </section>

      <section class="sidebar-section">
        <h3 class="section-title">Match Details</h3>
        <div class="settings-list">
          ${activeSettingRow("ELO", averageRating)}
          ${activeSettingRow("Type", queueLabel)}
          ${activeSettingRow("Region", regionName)}
          ${activeSettingRow("Map", mapName)}
          ${activeSettingRow("Players", players.length)}
          ${activeSettingRow("Observers", getObserverCount(match))}
          ${activeSettingRow("Time", formatMatchDuration(match))}
          ${activeSettingRow("Match ID", match.match_id ?? "Unknown")}
          ${activeSettingRow("Leaderboard ID", match.leaderboard_id ?? "Unknown")}
          ${activeSettingRow("Match Type", match.matchtype_id ?? "Unknown")}
        </div>
      </section>
    </div>
  `;
}

function selectActiveMatch(instance, matchId) {
  const match = instance.matches.find((item) => {
    return String(item.match_id) === String(matchId);
  });

  if (!match) {
    return;
  }

  instance.selectedMatchId = matchId;
  renderActiveMatchesTable(instance);
  renderActiveMatchDetails(instance, match);
}

function populateActiveMatchFilter(selectElement, values, formatter, defaultLabel) {
  if (!selectElement) {
    return;
  }

  const currentValue = selectElement.value;

  selectElement.innerHTML = `
    <option value="">${escapeActiveMatchHtml(defaultLabel)}</option>
    ${values.map((value) => {
      return `
        <option value="${escapeActiveMatchHtml(value)}">
          ${escapeActiveMatchHtml(formatter(value))}
        </option>
      `;
    }).join("")}
  `;

  if (values.includes(currentValue)) {
    selectElement.value = currentValue;
  }
}

function populateActiveMatchFilters(instance) {
  const matches = instance.matches;

  const servers = [...new Set(
    matches
      .map((match) => match.server)
      .filter(Boolean)
  )].sort((a, b) => activeFormatRegion(a).localeCompare(activeFormatRegion(b)));

  const maps = [...new Set(
    matches
      .map((match) => match.mapname)
      .filter(Boolean)
  )].sort((a, b) => activeFormatMapName(a).localeCompare(activeFormatMapName(b)));

  populateActiveMatchFilter(
    instance.elements.serverFilter,
    servers,
    activeFormatRegion,
    "All servers",
  );

  populateActiveMatchFilter(
    instance.elements.mapFilter,
    maps,
    activeFormatMapName,
    "All maps",
  );
}

async function loadActiveMatches(instance, forceRefresh = false) {
  if (!instance.endpoint) {
    return;
  }

  if (instance.elements.status) {
    instance.elements.status.textContent = forceRefresh
      ? `Refreshing ${instance.labelPlural.toLowerCase()}...`
      : `Loading ${instance.labelPlural.toLowerCase()}...`;
  }

  const url = new URL(instance.endpoint, window.location.origin);

  if (forceRefresh) {
    url.searchParams.set("refresh", "true");
  }

  try {
    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok || !data.ok) {
      throw new Error(data.error || `Request failed with status ${response.status}`);
    }

    instance.matches = Array.isArray(data.matches) ? data.matches : [];

    populateActiveMatchFilters(instance);
    renderActiveMatchesTable(instance);

    if (instance.filteredMatches.length) {
      const selectedStillVisible = instance.filteredMatches.some((match) => {
        return String(match.match_id) === String(instance.selectedMatchId);
      });

      if (!selectedStillVisible) {
        instance.selectedMatchId = instance.filteredMatches[0].match_id;
      }

      selectActiveMatch(instance, instance.selectedMatchId);
    } else {
      renderActiveMatchEmptySidebar(instance);
    }
  } catch (error) {
    console.error(`Failed to load ${instance.kind} matches.`, error);

    instance.matches = [];
    instance.filteredMatches = [];

    if (instance.elements.status) {
      instance.elements.status.textContent = `Could not load ${instance.labelPlural.toLowerCase()}: ${error.message}`;
    }

    if (instance.elements.tableBody) {
      instance.elements.tableBody.innerHTML = `
        <tr>
          <td colspan="7" class="muted">Could not load ${escapeActiveMatchHtml(instance.labelPlural.toLowerCase())}.</td>
        </tr>
      `;
    }

    renderActiveMatchEmptySidebar(instance);
  }
}

function selectFirstVisibleActiveMatchOrEmpty(instance) {
  const firstVisibleMatch = instance.filteredMatches[0];

  if (firstVisibleMatch) {
    selectActiveMatch(instance, firstVisibleMatch.match_id);
  } else {
    renderActiveMatchEmptySidebar(instance);
  }
}

function openActiveMatchPlayerDetails(instance, playerIndex) {
  const match = instance.matches.find((item) => {
    return String(item.match_id) === String(instance.selectedMatchId);
  });

  if (!match) {
    return;
  }

  const participant = getActiveMatchParticipants(match)[playerIndex];

  if (!participant) {
    return;
  }

  const lobbyLikeMatch = {
    id: `${instance.kind}-${match.match_id}`,
    host: "",
    host_profile_id: null,
    participants: getActiveMatchParticipants(match),
  };

  if (typeof window.openPlayerDetails === "function") {
    window.openPlayerDetails(participant, lobbyLikeMatch);
  }
}

function updateVisibleMatchTimes() {
  for (const timeElement of document.querySelectorAll("[data-active-match-time]")) {
    const kind = timeElement.dataset.matchKind;
    const instance = activeMatchInstances[kind];

    if (!instance) {
      continue;
    }

    const matchId = timeElement.dataset.activeMatchTime;
    const match = instance.matches.find((item) => {
      return String(item.match_id) === String(matchId);
    });

    if (match) {
      timeElement.textContent = formatMatchDuration(match);
    }
  }
}

function startActiveMatchClock() {
  if (activeMatchShared.clockTimer) {
    return;
  }

  activeMatchShared.clockTimer = window.setInterval(() => {
    const activeTab = getActiveTabName();

    if (activeTab === "observable" || activeTab === "inProgressCustom") {
      updateVisibleMatchTimes();
    }
  }, 1000);
}

function setupInstanceEvents(instance) {
  if (instance.elements.queueFilter) {
    instance.queue = instance.elements.queueFilter.value || instance.defaultQueue || "";

    instance.elements.queueFilter.addEventListener("change", (event) => {
      instance.queue = event.target.value;
      renderActiveMatchesTable(instance);
      selectFirstVisibleActiveMatchOrEmpty(instance);
    });
  }

  if (instance.elements.searchInput) {
    instance.elements.searchInput.addEventListener("input", (event) => {
      instance.search = event.target.value;
      renderActiveMatchesTable(instance);
      selectFirstVisibleActiveMatchOrEmpty(instance);
    });
  }

  if (instance.elements.serverFilter) {
    instance.elements.serverFilter.addEventListener("change", (event) => {
      instance.server = event.target.value;
      renderActiveMatchesTable(instance);
      selectFirstVisibleActiveMatchOrEmpty(instance);
    });
  }

  if (instance.elements.mapFilter) {
    instance.elements.mapFilter.addEventListener("change", (event) => {
      instance.map = event.target.value;
      renderActiveMatchesTable(instance);
      selectFirstVisibleActiveMatchOrEmpty(instance);
    });
  }

  if (instance.elements.sidebar) {
    instance.elements.sidebar.addEventListener("click", (event) => {
      const playerRow = event.target.closest(".player-row-clickable");

      if (!playerRow) {
        return;
      }

      const playerIndex = Number(playerRow.dataset.playerIndex);

      if (Number.isFinite(playerIndex)) {
        openActiveMatchPlayerDetails(instance, playerIndex);
      }
    });
  }

  document.querySelectorAll(`[${instance.sortAttribute}]`).forEach((header) => {
    header.addEventListener("click", () => {
      const sortKey = header.getAttribute(instance.sortAttribute);

      if (instance.sortKey === sortKey) {
        instance.sortDirection = instance.sortDirection === "asc" ? "desc" : "asc";
      } else {
        instance.sortKey = sortKey;
        instance.sortDirection = sortKey === "match" || sortKey === "map" || sortKey === "region"
          ? "asc"
          : "desc";
      }

      renderActiveMatchesTable(instance);
      selectFirstVisibleActiveMatchOrEmpty(instance);
    });
  });
}

function setupGlobalActiveMatchEvents(customInstance, rankedInstance) {
  const globalRefreshButton = document.getElementById("refreshButton");

  if (globalRefreshButton) {
    globalRefreshButton.addEventListener("click", () => {
      const activeTab = getActiveTabName();

      if (activeTab === "observable") {
        loadActiveMatches(rankedInstance, true);
      }

      if (activeTab === "inProgressCustom") {
        loadActiveMatches(customInstance, true);
      }
    });
  }

  document.addEventListener("click", (event) => {
    const tabButton = event.target.closest(".tab-button");

    if (!tabButton) {
      return;
    }

    if (tabButton.dataset.tab === "observable" && rankedInstance.matches.length === 0) {
      loadActiveMatches(rankedInstance, false);
    }

    if (tabButton.dataset.tab === "inProgressCustom" && customInstance.matches.length === 0) {
      loadActiveMatches(customInstance, false);
    }
  });
}

function initializeActiveMatches() {
  ensureActiveMatchPanelSections();

  const customInstance = createActiveMatchInstance({
    kind: "custom",
    tabName: "inProgressCustom",
    endpoint: window.AOM_ACTIVE_CUSTOM_MATCHES_API_URL || "/api/active-custom-matches/",
    sortAttribute: "data-custom-sort",
    tableBodyId: "customMatchesTableBody",
    statusId: "customMatchesStatus",
    searchInputId: "customMatchSearchInput",
    serverFilterId: "customMatchServerFilter",
    mapFilterId: "customMatchMapFilter",
    sidebarId: "customMatchDetailsSidebar",
    labelSingular: "custom match",
    labelPlural: "custom matches",
  });

  const rankedInstance = createActiveMatchInstance({
    kind: "ranked",
    tabName: "observable",
    endpoint: window.AOM_ACTIVE_MATCHES_API_URL || "/api/active-matches/",
    sortAttribute: "data-active-sort",
    tableBodyId: "activeMatchesTableBody",
    statusId: "activeMatchesStatus",
    searchInputId: "activeMatchSearchInput",
    queueFilterId: "activeMatchQueueFilter",
    serverFilterId: "activeMatchServerFilter",
    mapFilterId: "activeMatchMapFilter",
    sidebarId: "activeMatchDetailsSidebar",
    defaultQueue: "",
    labelSingular: "ranked match",
    labelPlural: "ranked matches",
  });

  setupInstanceEvents(customInstance);
  setupInstanceEvents(rankedInstance);
  setupGlobalActiveMatchEvents(customInstance, rankedInstance);
  startActiveMatchClock();

  const activeTab = getActiveTabName();

  if (activeTab === "inProgressCustom") {
    loadActiveMatches(customInstance, false);
  }

  if (activeTab === "observable") {
    loadActiveMatches(rankedInstance, false);
  }
}

initializeActiveMatches();
