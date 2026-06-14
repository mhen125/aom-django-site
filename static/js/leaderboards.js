(function initializeLeaderboardsPage() {
  const config = window.PROSTAGMA_LEADERBOARDS;

  if (!config) {
    return;
  }

  const metadata = JSON.parse(document.getElementById("leaderboardMetadata")?.textContent || "{}");
  const defaultQueues = JSON.parse(document.getElementById("leaderboardDefaultQueues")?.textContent || "[]");

  const state = {
    browseMatchType: Number(defaultQueues[0]?.id || 1),
    browsePage: 1,
    browseCount: 25,
  };

  const lookupInput = document.getElementById("leaderboardLookupInput");
  const queueChips = document.getElementById("leaderboardQueueChips");
  const browseBody = document.getElementById("leaderboardBrowseTableBody");
  const browseMeta = document.getElementById("leaderboardBrowseMeta");
  const searchForm = document.getElementById("leaderboardSearchForm");
  const searchReset = document.getElementById("leaderboardSearchReset");
  const searchFeedback = document.getElementById("leaderboardSearchFeedback");
  const refreshBrowseButton = document.getElementById("leaderboardRefreshBrowse");
  const prevPageButton = document.getElementById("leaderboardPrevPage");
  const nextPageButton = document.getElementById("leaderboardNextPage");
  const pageLabel = document.getElementById("leaderboardPageLabel");
  const searchResultsPanel = document.getElementById("leaderboardSearchResultsPanel");
  const searchResultsMeta = document.getElementById("leaderboardSearchResultsMeta");
  const searchResultsBody = document.getElementById("leaderboardSearchResultsBody");
  state.loadedProfile = null;
  state.browseRequestId = 0;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatNumber(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toLocaleString() : "-";
  }

  function formatPercent(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${numeric.toFixed(1)}%` : "-";
  }

  function formatDate(value) {
    if (!value) {
      return "-";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  function buildUrl(base, params) {
    const url = new URL(base, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
    return url.toString();
  }

  function buildProfileUrl(profile) {
    const profileId = profile?.profileId ?? profile?.profile_id;
    const player = profile?.player ?? profile?.name;

    if (profileId) {
      const base = String(config.playerStatsProfileBaseUrl || "/stats/players/");
      const normalizedBase = base.endsWith("/") ? base : `${base}/`;
      const url = new URL(`${normalizedBase}${encodeURIComponent(String(profileId).trim())}/`, window.location.origin);
      if (player) {
        url.searchParams.set("player", player);
      }
      if (state.browseMatchType) {
        url.searchParams.set("match_type", String(state.browseMatchType));
      }
      return url.toString();
    }

    return buildUrl(config.playerStatsUrl || "/stats/player/", {
      profile_id: profileId,
      player,
      match_type: state.browseMatchType,
    });
  }

  function openPlayerProfile({ player, profileId }) {
    window.location.assign(buildProfileUrl({ player, profileId }));
  }

  async function fetchJson(url) {
    const response = await fetch(url, {
      headers: {
        accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    return response.json();
  }

  function getRankedQueues() {
    return Array.isArray(metadata?.ranked_queues) && metadata.ranked_queues.length
      ? metadata.ranked_queues
      : defaultQueues;
  }

  function getQueueLabel(matchType) {
    const found = getRankedQueues().find((item) => Number(item.id) === Number(matchType));
    return found?.label || `Queue ${matchType}`;
  }

  function getRatingQueueId(rating) {
    return Number(rating?.queue_id ?? rating?.leaderboard_id ?? rating?.match_type);
  }

  function getDisplayText(value, fallback = "-") {
    const text = String(value ?? "").trim();
    if (!text || text.toLowerCase() === "unknown") {
      return fallback;
    }
    return text;
  }

  function renderQueueOptions() {
    const queues = getRankedQueues();
    queueChips.innerHTML = queues
      .slice(0, 8)
      .map(
        (queue) => `
          <button
            class="leaderboards-queue-chip${Number(queue.id) === state.browseMatchType ? " is-active" : ""}"
            type="button"
            data-match-type="${queue.id}"
          >
            ${escapeHtml(queue.label)}
          </button>
        `,
      )
      .join("");
  }

  function renderBrowseRows(rows) {
    if (!rows.length) {
      browseBody.innerHTML = `
        <tr>
          <td colspan="5" class="leaderboards-table-empty">No leaderboard rows came back for this queue.</td>
        </tr>
      `;
      return;
    }

    browseBody.innerHTML = rows
      .map(
        (row) => `
          <tr data-player-name="${escapeHtml(row.name || "")}" data-profile-id="${escapeHtml(row.profile_id || "")}">
            <td><span class="leaderboards-rank">#${escapeHtml(row.rank ?? "-")}</span></td>
            <td>
              <div class="leaderboards-player-cell">
                <strong>${escapeHtml(row.name || "Unknown")}</strong>
                <small>${escapeHtml(row.country ? String(row.country).toUpperCase() : row.profile_id ? `ID ${row.profile_id}` : "Unspecified region")}</small>
              </div>
            </td>
            <td>${escapeHtml(formatNumber(row.rating))}</td>
            <td>
              ${escapeHtml(formatNumber(row.wins))} - ${escapeHtml(formatNumber(row.losses))}
              <div class="leaderboards-record-meta">${escapeHtml(formatPercent(row.win_rate))}</div>
            </td>
            <td>${escapeHtml(formatNumber(row.highest_rating))}</td>
          </tr>
        `,
      )
      .join("");
  }

  function renderPlayerCandidates(rows, query) {
    if (!searchResultsPanel || !searchResultsBody || !searchResultsMeta) {
      return;
    }

    searchResultsPanel.hidden = false;
    searchResultsMeta.textContent = `${formatNumber(rows.length)} candidate profile${rows.length === 1 ? "" : "s"} returned for "${query}"`;

    if (!rows.length) {
      searchResultsBody.innerHTML = `
        <tr>
          <td colspan="5" class="leaderboards-table-empty">No matching players came back for this search.</td>
        </tr>
      `;
      return;
    }

    searchResultsBody.innerHTML = rows
      .map(
        (row) => `
          <tr data-select-profile="true" data-player-name="${escapeHtml(row.name || "")}" data-profile-id="${escapeHtml(row.profile_id || "")}">
            <td>
              <div class="leaderboards-player-cell">
                <strong>${escapeHtml(row.name || "Unknown")}</strong>
                <small>${escapeHtml(row.country ? String(row.country).toUpperCase() : getQueueLabel(state.browseMatchType))}</small>
              </div>
            </td>
            <td>${escapeHtml(row.profile_id || "-")}</td>
            <td>${escapeHtml(formatNumber(row.rating))}</td>
            <td>${escapeHtml(row.rank ? `#${row.rank}` : "-")}</td>
            <td>
              ${escapeHtml(formatNumber(row.wins))} - ${escapeHtml(formatNumber(row.losses))}
              <div class="leaderboards-record-meta">${escapeHtml(formatPercent(row.win_rate))}</div>
            </td>
          </tr>
        `,
      )
      .join("");
  }

  async function loadPlayerCandidates(query) {
    if (!searchResultsPanel || !searchResultsBody || !searchResultsMeta) {
      return [];
    }

    searchResultsPanel.hidden = false;
    searchResultsMeta.textContent = `Searching "${query}"`;
    searchResultsBody.innerHTML = `
      <tr>
        <td colspan="5" class="leaderboards-table-empty">Loading matching profiles...</td>
      </tr>
    `;
    state.loadedProfile = null;

    const payload = await fetchJson(
      buildUrl(config.browseUrl, {
        player: query,
        match_type: state.browseMatchType,
        page: 1,
        count: 25,
      }),
    );
    const rows = Array.isArray(payload?.matches) ? payload.matches : [];
    renderPlayerCandidates(rows, query);
    return rows;
  }

  async function loadBrowseLeaderboard({ refresh = false } = {}) {
    const requestId = ++state.browseRequestId;
    browseMeta.textContent = "Loading rankings...";
    pageLabel.textContent = `Page ${state.browsePage}`;
    browseBody.innerHTML = `
      <tr>
        <td colspan="5" class="leaderboards-table-empty">Loading leaderboard rows...</td>
      </tr>
    `;

    try {
      const payload = await fetchJson(
        buildUrl(config.browseUrl, {
          match_type: state.browseMatchType,
          page: state.browsePage,
          count: state.browseCount,
          refresh: refresh ? 1 : "",
        }),
      );

      if (requestId !== state.browseRequestId) {
        return;
      }

      const rows = Array.isArray(payload?.matches) ? payload.matches : [];
      renderBrowseRows(rows);
      browseMeta.textContent = `${getQueueLabel(state.browseMatchType)} · ${formatNumber(payload?.match_count || 0)} rows`;
      pageLabel.textContent = `Page ${state.browsePage}`;
      prevPageButton.disabled = state.browsePage <= 1;
      nextPageButton.disabled = rows.length < state.browseCount;
    } catch (error) {
      if (requestId !== state.browseRequestId) {
        return;
      }

      browseBody.innerHTML = `
        <tr>
          <td colspan="5" class="leaderboards-table-empty">Unable to load leaderboard rows right now.</td>
        </tr>
      `;
      browseMeta.textContent = "Leaderboard unavailable";
      pageLabel.textContent = `Page ${state.browsePage}`;
      console.error(error);
    }
  }

  function handleQueueChipClick(event) {
    const chip = event.target.closest("[data-match-type]");
    if (!chip) {
      return;
    }

    state.browseMatchType = Number(chip.dataset.matchType || 1);
    renderQueueOptions();
    loadBrowseLeaderboard().catch((error) => console.error(error));
  }

  async function handleSearchSubmit(event) {
    event.preventDefault();

    const lookup = lookupInput?.value.trim() || "";
    const isNumericLookup = /^\d+$/.test(lookup);
    const player = isNumericLookup ? "" : lookup;
    const profileId = isNumericLookup ? lookup : "";
    renderQueueOptions();

    if (!lookup) {
      searchFeedback.textContent = "Enter a player name or a profile ID first.";
      return;
    }

    try {
      if (profileId) {
        if (searchResultsPanel) {
          searchResultsPanel.hidden = true;
        }
        openPlayerProfile({ player, profileId });
      } else {
        await loadPlayerCandidates(player);
        searchFeedback.textContent = "Select a matching profile to open player stats.";
      }
    } catch (error) {
      searchFeedback.textContent = error instanceof Error ? error.message : "Unable to load that player right now.";
      console.error(error);
    }
  }

  function handleReset() {
    searchForm.reset();
    searchFeedback.textContent = "Search for a player to open player stats.";
    if (searchResultsPanel) {
      searchResultsPanel.hidden = true;
    }
    state.loadedProfile = null;
  }

  function handleCandidateRowClick(event) {
    const row = event.target.closest("tr[data-select-profile]");
    if (!row) {
      return;
    }

    const player = row.dataset.playerName || "";
    const profileId = row.dataset.profileId || "";

    if (lookupInput) {
      lookupInput.value = player || profileId;
    }

    openPlayerProfile({
      player,
      profileId,
    });
  }

  function handleBrowseRowClick(event) {
    const row = event.target.closest("tr[data-player-name]");
    if (!row) {
      return;
    }

    const player = row.dataset.playerName || "";
    const profileId = row.dataset.profileId || "";

    if (lookupInput) {
      lookupInput.value = player || profileId;
    }

    renderQueueOptions();

    openPlayerProfile({
      player,
      profileId,
    });
  }

  queueChips?.addEventListener("click", handleQueueChipClick);
  browseBody?.addEventListener("click", handleBrowseRowClick);
  searchResultsBody?.addEventListener("click", handleCandidateRowClick);
  searchForm?.addEventListener("submit", handleSearchSubmit);
  searchReset?.addEventListener("click", handleReset);
  refreshBrowseButton?.addEventListener("click", () => {
    loadBrowseLeaderboard({ refresh: true }).catch((error) => console.error(error));
  });
  prevPageButton?.addEventListener("click", () => {
    if (state.browsePage <= 1) {
      return;
    }
    state.browsePage -= 1;
    loadBrowseLeaderboard().catch((error) => console.error(error));
  });
  nextPageButton?.addEventListener("click", () => {
    state.browsePage += 1;
    loadBrowseLeaderboard().catch((error) => console.error(error));
  });
  renderQueueOptions();
  loadBrowseLeaderboard().catch((error) => console.error(error));
})();
