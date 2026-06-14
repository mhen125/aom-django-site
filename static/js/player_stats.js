(function initializePlayerStatsPage() {
  const config = window.PROSTAGMA_PLAYER_STATS;

  if (!config) {
    return;
  }

  const metadata = JSON.parse(document.getElementById("playerStatsMetadata")?.textContent || "{}");
  const defaultQueues = JSON.parse(document.getElementById("playerStatsDefaultQueues")?.textContent || "[]");
  const initialPlayer = JSON.parse(document.getElementById("playerStatsInitialPlayer")?.textContent || '""');
  const initialProfileId = JSON.parse(document.getElementById("playerStatsInitialProfileId")?.textContent || '""');
  const initialMatchType = Number(JSON.parse(document.getElementById("playerStatsInitialMatchType")?.textContent || '"1"') || 1);

  const MATCHES_PER_PAGE = 12;

  const state = {
    activeMatchType: initialMatchType || Number(defaultQueues[0]?.id || 1),
    loadedProfile: null,
    loadedMatches: [],
    matchesPage: 1,
    requestId: 0,
  };

  const searchForm = document.getElementById("playerStatsSearchForm");
  const lookupInput = document.getElementById("playerStatsLookupInput");
  const resetButton = document.getElementById("playerStatsReset");
  const feedback = document.getElementById("playerStatsFeedback");
  const title = document.getElementById("playerStatsPageTitle");
  const lead = document.getElementById("playerStatsLead");
  const searchResultsPanel = document.getElementById("playerStatsSearchResultsPanel");
  const searchResultsMeta = document.getElementById("playerStatsSearchResultsMeta");
  const searchResultsBody = document.getElementById("playerStatsSearchResultsBody");
  const profilePanel = document.getElementById("playerStatsProfilePanel");
  const profileName = document.getElementById("playerStatsName");
  const profileMeta = document.getElementById("playerStatsMeta");
  const avatar = document.getElementById("playerStatsAvatar");
  const queueBadge = document.getElementById("playerStatsQueueBadge");
  const sourceBadge = document.getElementById("playerStatsSourceBadge");
  const identityLine = document.getElementById("playerStatsIdentityLine");
  const queueChips = document.getElementById("playerStatsQueueChips");
  const ratingsBody = document.getElementById("playerStatsRatingsBody");
  const profileCards = document.getElementById("playerStatsCards");
  const verdictTitle = document.getElementById("playerStatsVerdictTitle");
  const verdictMeta = document.getElementById("playerStatsVerdictMeta");
  const verdictBody = document.getElementById("playerStatsVerdictBody");
  const verdictBadges = document.getElementById("playerStatsVerdictBadges");
  const verdictEvidence = document.getElementById("playerStatsVerdictEvidence");
  const matchesMeta = document.getElementById("playerStatsMatchesMeta");
  const prevMatchesButton = document.getElementById("playerStatsPrevMatches");
  const nextMatchesButton = document.getElementById("playerStatsNextMatches");
  const matchesPageLabel = document.getElementById("playerStatsMatchesPageLabel");
  const godsMeta = document.getElementById("playerStatsGodsMeta");
  const godsList = document.getElementById("playerStatsGodsList");
  const matchesBody = document.getElementById("playerStatsMatchesBody");

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

  function formatRecord(wins, losses) {
    const hasWins = Number.isFinite(Number(wins));
    const hasLosses = Number.isFinite(Number(losses));
    if (!hasWins && !hasLosses) {
      return "-";
    }
    return `${formatNumber(wins)} - ${formatNumber(losses)}`;
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

  function getDisplayText(value, fallback = "-") {
    const text = String(value ?? "").trim();
    if (!text || text.toLowerCase() === "unknown") {
      return fallback;
    }
    return text;
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

  function buildCanonicalProfileUrl(player, profileId, matchType) {
    const normalizedProfileId = profileId ? String(profileId).trim() : "";
    if (normalizedProfileId) {
      const base = String(config.canonicalProfileBaseUrl || "/stats/players/");
      const normalizedBase = base.endsWith("/") ? base : `${base}/`;
      const url = new URL(`${normalizedBase}${encodeURIComponent(normalizedProfileId)}/`, window.location.origin);
      if (player) {
        url.searchParams.set("player", player);
      }
      if (matchType) {
        url.searchParams.set("match_type", String(matchType));
      }
      return url.toString();
    }

    return buildUrl(config.canonicalProfileUrl || "/stats/player/", {
      player,
      profile_id: profileId,
      match_type: matchType,
    });
  }

  function getInitials(value) {
    const parts = String(value || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2);
    const initials = parts.map((part) => part.charAt(0).toUpperCase()).join("");
    return initials || "PS";
  }

  function getSourceLabel(value) {
    const key = String(value || "").trim().toLowerCase();
    if (key === "imported_stats") {
      return "Imported stats";
    }
    if (key === "leaderboard") {
      return "Leaderboard lookup";
    }
    if (key === "personal_stat") {
      return "Live ladder";
    }
    if (key === "full_stats") {
      return "Live profile";
    }
    return "Player data";
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

  function syncQueueChips() {
    const queues = getRankedQueues();
    queueChips.innerHTML = queues
      .map(
        (queue) => `
          <button
            class="leaderboards-queue-chip${Number(queue.id) === Number(state.activeMatchType) ? " is-active" : ""}"
            type="button"
            data-match-type="${queue.id}"
          >
            ${escapeHtml(queue.label)}
          </button>
        `,
      )
      .join("");
  }

  function updatePageUrl(player, profileId, matchType) {
    window.history.replaceState({}, "", buildCanonicalProfileUrl(player, profileId, matchType));
  }

  function renderCards(summaryPayload, statsPayload, ratingPayload) {
    const ratings = Array.isArray(summaryPayload?.ratings) ? summaryPayload.ratings.filter((item) => item?.rating) : [];
    const primaryRatingBucket = ratings.find((item) => Number(item.match_type) === Number(state.activeMatchType));
    const ratingPayloadRecord = getRatingQueueId(ratingPayload?.rating) === Number(state.activeMatchType) ? ratingPayload?.rating : null;
    const primaryRating = primaryRatingBucket?.rating || ratingPayloadRecord || null;
    const summary = statsPayload?.summary || {};

    const cards = [
      { label: "Current ELO", value: primaryRating?.rating ?? "-" },
      { label: "Rank", value: primaryRating?.rank ? `#${primaryRating.rank}` : "-" },
      { label: "Peak", value: primaryRating?.highest_rating ?? "-" },
      { label: "Games", value: primaryRating?.games ?? "-" },
      { label: "Win Rate", value: formatPercent(primaryRating?.win_rate) },
      { label: "Wins", value: formatNumber(primaryRating?.wins ?? summary.wins) },
      { label: "Losses", value: formatNumber(primaryRating?.losses ?? summary.losses) },
    ];

    profileCards.innerHTML = cards
      .map(
        (card) => `
          <article class="leaderboards-stat-card">
            <span>${escapeHtml(card.label)}</span>
            <strong>${escapeHtml(card.value)}</strong>
          </article>
        `,
      )
      .join("");
  }

  function sumRecentRatingChange(matches, limit = 8) {
    return matches
      .slice(0, limit)
      .reduce((total, match) => {
        const value = Number(match?.rating_change);
        return Number.isFinite(value) ? total + value : total;
      }, 0);
  }

  function countRecentResolved(matches, limit = 10) {
    const sample = matches.slice(0, limit);
    const wins = sample.filter((match) => String(match?.result || "").toLowerCase() === "win").length;
    const losses = sample.filter((match) => String(match?.result || "").toLowerCase() === "loss").length;
    return {
      sample,
      wins,
      losses,
      resolved: wins + losses,
      winRate: wins + losses > 0 ? (wins / (wins + losses)) * 100 : 0,
    };
  }

  function buildVerdict(summaryPayload, statsPayload, ratingPayload) {
    const ratings = Array.isArray(summaryPayload?.ratings) ? summaryPayload.ratings.filter((item) => item?.rating) : [];
    const primaryRatingBucket = ratings.find((item) => Number(item.match_type) === Number(state.activeMatchType));
    const ratingPayloadRecord = getRatingQueueId(ratingPayload?.rating) === Number(state.activeMatchType) ? ratingPayload?.rating : null;
    const primaryRating = primaryRatingBucket?.rating || ratingPayloadRecord || null;
    const matches = Array.isArray(state.loadedMatches) ? state.loadedMatches : [];
    const gods = Array.isArray(statsPayload?.gods) ? statsPayload.gods : [];
    const recent = countRecentResolved(matches, 10);
    const queueLabel = getQueueLabel(state.activeMatchType);
    const displayName = summaryPayload?.display_name || state.loadedProfile?.player || "This player";
    const rating = Number(primaryRating?.rating);
    const games = Number(primaryRating?.games);
    const topGod = gods[0] || null;
    const trend = sumRecentRatingChange(matches, 8);

    const badges = [];

    if (Number.isFinite(rating) && rating >= 1400) {
      badges.push("LADDER THREAT");
    } else if (Number.isFinite(rating) && rating >= 1200) {
      badges.push("COMPETITIVE");
    } else if (Number.isFinite(rating) && rating < 1000) {
      badges.push("DEVELOPING");
    }

    if (recent.resolved >= 6 && recent.winRate >= 70) {
      badges.push("HEATING UP");
    } else if (recent.resolved >= 6 && recent.winRate <= 35) {
      badges.push("SLIPPING");
    }

    if (trend >= 40) {
      badges.push("RISING");
    } else if (trend <= -40) {
      badges.push("FALLING");
    }

    if (topGod && Number(topGod.percent) >= 50 && Number(topGod.count) >= 5) {
      badges.push(`${String(topGod.name || "GOD").toUpperCase()} SPECIALIST`);
    } else if (topGod && Number(topGod.percent) <= 30 && gods.length >= 3) {
      badges.push("WIDE GOD POOL");
    }

    if (Number.isFinite(games) && games >= 200) {
      badges.push("GRINDER");
    }

    const uniqueBadges = [...new Set(badges)].slice(0, 4);

    let titleText = `${displayName} is still taking shape in ${queueLabel}.`;
    let bodyText = `${displayName} does not yet have a dominant current-queue signal, so the page leans on recent form, god choice, and map habits.`;

    if (recent.resolved >= 6 && recent.winRate >= 70 && trend >= 20) {
      titleText = `${displayName} is climbing in ${queueLabel}.`;
      bodyText = `The recent sample points to real momentum: wins are stacking up, rating is moving in the right direction, and this queue looks live for them right now.`;
    } else if (recent.resolved >= 6 && recent.winRate <= 35 && trend <= -20) {
      titleText = `${displayName} is in a rough stretch in ${queueLabel}.`;
      bodyText = `Recent results and rating movement both point the same way. This profile is cooling off right now, not quietly holding steady.`;
    } else if (topGod && Number(topGod.percent) >= 55 && Number(topGod.count) >= 5) {
      titleText = `${displayName} is leaning hard on ${topGod.name}.`;
      bodyText = `${topGod.name} is not just the most-played god here. It is the center of gravity for this player’s recent queue sample.`;
    } else if (Number.isFinite(rating) && rating >= 1400) {
      titleText = `${displayName} looks dangerous in ${queueLabel}.`;
      bodyText = `The rating profile puts this player in serious ladder territory, and the page has enough recent evidence to treat this as a real queue presence.`;
    } else if (Number.isFinite(games) && games >= 200) {
      titleText = `${displayName} is a real ladder regular in ${queueLabel}.`;
      bodyText = `This is not a one-week blip profile. There is enough volume here to trust the general shape of the queue record.`;
    }

    const evidence = [
      {
        label: "Recent form",
        strong: recent.resolved ? `${recent.wins}-${recent.losses} in last ${recent.resolved}` : "Recent form open",
      body: recent.resolved ? `${formatPercent(recent.winRate)} win rate across the latest resolved matches.` : "Recent results are light for this queue.",
      },
      {
        label: "Queue strength",
        strong: Number.isFinite(rating) ? `${formatNumber(rating)} ELO in ${queueLabel}` : `No returned ${queueLabel} rating`,
        body: primaryRating?.rank ? `Current listed rank: #${formatNumber(primaryRating.rank)}.` : "Queue rank is not listed.",
      },
      {
        label: "Signature god",
        strong: topGod ? `${topGod.name} in ${formatPercent(topGod.percent)}` : "Mixed god pool",
        body: topGod ? `${formatNumber(topGod.count)} recent matches with ${topGod.name} at ${formatPercent(topGod.win_rate)} win rate.` : "No single god is dominating this profile view.",
      },
    ];

    return {
      badges: uniqueBadges.length ? uniqueBadges : ["PLAYER READ"],
      titleText,
      bodyText,
      evidence,
      metaText: `Built from ${queueLabel} ladder data, recent matches, and returned profile breakdowns.`,
    };
  }

  function renderVerdict(summaryPayload, statsPayload, ratingPayload) {
    const verdict = buildVerdict(summaryPayload, statsPayload, ratingPayload);

    verdictTitle.textContent = verdict.titleText;
    verdictMeta.textContent = verdict.metaText;
    verdictBody.textContent = verdict.bodyText;
    verdictBadges.innerHTML = verdict.badges
      .map((badge) => `<span class="player-stats-badge">${escapeHtml(badge)}</span>`)
      .join("");
    verdictEvidence.innerHTML = verdict.evidence
      .map(
        (item) => `
          <article class="leaderboards-list-card">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.strong)}</strong>
            <p>${escapeHtml(item.body)}</p>
          </article>
        `,
      )
      .join("");
  }

  function renderRatingsTable(summaryPayload, ratingPayload) {
    const ratings = Array.isArray(summaryPayload?.ratings) ? summaryPayload.ratings : [];
    const rows = ratings;

    if (!rows.length) {
      ratingsBody.innerHTML = `
        <tr>
          <td colspan="5" class="leaderboards-table-empty">No queue ratings were returned for this player.</td>
        </tr>
      `;
      return;
    }

    ratingsBody.innerHTML = rows
      .map((bucket) => {
        const rating = bucket.rating || null;
        const isActive = Number(bucket.match_type) === Number(state.activeMatchType);
        const sourceLabel = rating ? getSourceLabel(bucket.source || summaryPayload?.source || ratingPayload?.source) : "No returned ladder row";
        return `
          <tr${isActive ? ' class="is-active-row"' : ""}>
            <td>
              <div class="leaderboards-player-cell">
                <strong>${escapeHtml(bucket.match_type_label || getQueueLabel(bucket.match_type))}</strong>
                <small>${escapeHtml(sourceLabel)}</small>
              </div>
            </td>
            <td>${escapeHtml(rating ? formatNumber(rating.rating) : "-")}</td>
            <td>${escapeHtml(rating?.rank ? `#${rating.rank}` : "-")}</td>
            <td>${escapeHtml(rating ? formatRecord(rating.wins, rating.losses) : "-")}</td>
            <td>${escapeHtml(rating ? formatNumber(rating.highest_rating) : "-")}</td>
          </tr>
        `;
      })
      .join("");
  }

  function renderGods(statsPayload) {
    const gods = Array.isArray(statsPayload?.gods) ? statsPayload.gods.slice(0, 8) : [];
    godsMeta.textContent = `${formatNumber(statsPayload?.total_matches || 0)} recent matches returned`;

    if (!gods.length) {
      godsList.innerHTML = `<article class="leaderboards-list-card"><strong>No recent god data</strong><p>Try another player or queue.</p></article>`;
      return;
    }

    godsList.innerHTML = gods
      .map(
        (god) => `
          <article class="leaderboards-list-card">
            <span>${escapeHtml(god.name)}</span>
            <strong>${escapeHtml(formatNumber(god.count))} matches</strong>
            <p>${escapeHtml(formatPercent(god.win_rate))} win rate · ${escapeHtml(formatPercent(god.percent))} of returned recent matches</p>
          </article>
        `,
      )
      .join("");
  }

  function renderMatches() {
    const matches = Array.isArray(state.loadedMatches) ? state.loadedMatches : [];
    const totalPages = Math.max(1, Math.ceil(matches.length / MATCHES_PER_PAGE));
    state.matchesPage = Math.min(state.matchesPage, totalPages);
    const startIndex = (state.matchesPage - 1) * MATCHES_PER_PAGE;
    const visibleMatches = matches.slice(startIndex, startIndex + MATCHES_PER_PAGE);

    matchesMeta.textContent = `${formatNumber(matches.length)} recent matches returned`;
    matchesPageLabel.textContent = `Page ${state.matchesPage} of ${totalPages}`;
    prevMatchesButton.disabled = state.matchesPage <= 1;
    nextMatchesButton.disabled = state.matchesPage >= totalPages;

    if (!visibleMatches.length) {
      matchesBody.innerHTML = `
        <tr>
          <td colspan="6" class="leaderboards-table-empty">No recent matches were returned for this player.</td>
        </tr>
      `;
      return;
    }

    matchesBody.innerHTML = visibleMatches
      .map((match) => {
        const result = String(match.result || "-");
        const resultClass = result.toLowerCase() === "win" ? " is-win" : result.toLowerCase() === "loss" ? " is-loss" : "";
        const queueLabel = getDisplayText(match.match_type_label || (match.match_type ? getQueueLabel(match.match_type) : ""), "-");
        const civilization = getDisplayText(match.civilization, "-");
        const mapName = getDisplayText(match.map, "-");
        const eloValue = Number(match.rating_change);
        const eloText = Number.isFinite(eloValue) && eloValue !== 0
          ? `${formatNumber(match.rating)} (${eloValue > 0 ? "+" : ""}${formatNumber(eloValue)})`
          : formatNumber(match.rating);

        return `
          <tr>
            <td>${escapeHtml(formatDate(match.date_time))}</td>
            <td>${escapeHtml(queueLabel)}</td>
            <td>${escapeHtml(civilization)}</td>
            <td>${escapeHtml(mapName)}</td>
            <td><span class="leaderboards-result-pill${resultClass}">${escapeHtml(result)}</span></td>
            <td>${escapeHtml(eloText)}</td>
          </tr>
        `;
      })
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
                <small>${escapeHtml(row.country ? String(row.country).toUpperCase() : getQueueLabel(state.activeMatchType))}</small>
              </div>
            </td>
            <td>${escapeHtml(row.profile_id || "-")}</td>
            <td>${escapeHtml(formatNumber(row.rating))}</td>
            <td>${escapeHtml(row.rank ? `#${row.rank}` : "-")}</td>
            <td>${escapeHtml(formatRecord(row.wins, row.losses))}</td>
          </tr>
        `,
      )
      .join("");
  }

  async function loadPlayerCandidates(query) {
    if (!config.playerSearchUrl || !searchResultsPanel || !searchResultsBody || !searchResultsMeta) {
      return [];
    }

    searchResultsPanel.hidden = false;
    searchResultsMeta.textContent = `Searching "${query}"`;
    searchResultsBody.innerHTML = `
      <tr>
        <td colspan="5" class="leaderboards-table-empty">Loading matching profiles...</td>
      </tr>
    `;
    profilePanel.hidden = true;
    state.loadedProfile = null;
    updatePageUrl(query, "", state.activeMatchType);

    const payload = await fetchJson(
      buildUrl(config.playerSearchUrl, {
        player: query,
        match_type: state.activeMatchType,
        page: 1,
        count: 25,
      }),
    );
    const rows = Array.isArray(payload?.matches) ? payload.matches : [];
    renderPlayerCandidates(rows, query);
    return rows;
  }

  async function loadProfile({ player, profileId, matchType }) {
    const requestId = ++state.requestId;
    if (searchResultsPanel) {
      searchResultsPanel.hidden = true;
    }
    profilePanel.hidden = false;
    feedback.textContent = state.loadedProfile ? "Refreshing profile..." : "Loading profile...";
    profileName.textContent = state.loadedProfile ? profileName.textContent : "Loading...";
    profileMeta.textContent = "Fetching rating and match history";

    if (!state.loadedProfile) {
      profileCards.innerHTML = "";
      godsList.innerHTML = "";
      ratingsBody.innerHTML = `
        <tr>
          <td colspan="5" class="leaderboards-table-empty">Loading ladder rows...</td>
        </tr>
      `;
      matchesBody.innerHTML = `
        <tr>
          <td colspan="6" class="leaderboards-table-empty">Loading recent matches...</td>
        </tr>
      `;
    }

    let ratingPayload = null;

    if (player || profileId) {
      ratingPayload = await fetchJson(
        buildUrl(config.ratingUrl, {
          player,
          profile_id: profileId,
          match_type: matchType,
        }),
      );
    }

    const resolvedProfileId = Number(ratingPayload?.rating?.profile_id || profileId || 0);
    const resolvedPlayer = ratingPayload?.rating?.name || player || ratingPayload?.player || "Unknown player";

    if (!resolvedProfileId) {
      throw new Error(ratingPayload?.reason || "No usable profile ID was returned.");
    }

    const [summaryPayload, statsPayload] = await Promise.all([
      fetchJson(
        buildUrl(config.summaryUrl, {
          profile_id: resolvedProfileId,
          player: resolvedPlayer,
          recent_match_type: matchType,
          recent_count: 40,
        }),
      ),
      fetchJson(
        buildUrl(config.godStatsUrl, {
          profile_id: resolvedProfileId,
          player: resolvedPlayer,
          recent_count: 40,
          match_type: matchType,
        }),
      ),
    ]);

    if (requestId !== state.requestId) {
      return;
    }

    profileName.textContent = summaryPayload?.display_name || resolvedPlayer;
    profileMeta.textContent = `Profile ID ${resolvedProfileId} · ${getQueueLabel(matchType)}`;
    title.textContent = `${summaryPayload?.display_name || resolvedPlayer} Stats Hub`;
    lead.textContent = `Dedicated stats view for ${summaryPayload?.display_name || resolvedPlayer}. Switch ladders to compare queue-specific ladder rows, recent matches, and deeper breakdowns.`;
    avatar.textContent = getInitials(summaryPayload?.display_name || resolvedPlayer);
    queueBadge.textContent = getQueueLabel(matchType);
    sourceBadge.textContent = getSourceLabel(summaryPayload?.source || ratingPayload?.source);
    identityLine.textContent = `${summaryPayload?.display_name || resolvedPlayer} · Profile ID ${resolvedProfileId}`;

    state.loadedMatches = Array.isArray(summaryPayload?.recent_matches?.matches) ? summaryPayload.recent_matches.matches : [];
    state.matchesPage = 1;
    syncQueueChips();
    renderCards(summaryPayload, statsPayload, ratingPayload);
    renderVerdict(summaryPayload, statsPayload, ratingPayload);
    renderRatingsTable(summaryPayload, ratingPayload);
    renderMatches();
    renderGods(statsPayload);
    feedback.textContent = `Loaded ${summaryPayload?.display_name || resolvedPlayer}.`;

    state.loadedProfile = {
      player: resolvedPlayer,
      profileId: String(resolvedProfileId),
    };
    updatePageUrl(resolvedPlayer, resolvedProfileId, matchType);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const lookup = lookupInput?.value.trim() || "";
    const isNumericLookup = /^\d+$/.test(lookup);
    const player = isNumericLookup ? "" : lookup;
    const profileId = isNumericLookup ? lookup : "";

    if (!lookup) {
      feedback.textContent = "Enter a player name or a profile ID first.";
      return;
    }

    try {
      if (profileId) {
        await loadProfile({ player, profileId, matchType: state.activeMatchType });
      } else {
        await loadPlayerCandidates(player);
        feedback.textContent = "Select a matching profile to open player stats.";
      }
    } catch (error) {
      feedback.textContent = error instanceof Error ? error.message : "Unable to load that player right now.";
      console.error(error);
    }
  }

  function handleReset() {
    searchForm.reset();
    feedback.textContent = "Enter a player name or profile ID.";
    title.textContent = "Player Stats Hub";
    lead.textContent = "Look up an Age of Mythology: Retold player profile with queue ratings, recent results, favorite gods, and map tendencies in one place.";
    profilePanel.hidden = true;
    if (searchResultsPanel) {
      searchResultsPanel.hidden = true;
    }
    avatar.textContent = "PS";
    queueBadge.textContent = "Queue";
    sourceBadge.textContent = "Source";
    identityLine.textContent = "Profile view for ladder tracking, recent results, and queue comparisons.";
    verdictTitle.textContent = "Load a player to generate a profile read";
    verdictMeta.textContent = "Queue read";
    verdictBody.textContent = "Search a player to see their current ladder shape, best signals, and recent profile story.";
    verdictBadges.innerHTML = '<span class="player-stats-badge">PLAYER READ</span>';
    verdictEvidence.innerHTML = `
      <article class="leaderboards-list-card">
        <span>Recent form</span>
        <strong>Search a profile</strong>
        <p>Recent wins, losses, ratings, gods, and maps will appear here.</p>
      </article>
    `;
    matchesMeta.textContent = "Recent matches";
    matchesPageLabel.textContent = "Page 1";
    prevMatchesButton.disabled = true;
    nextMatchesButton.disabled = true;
    queueChips.innerHTML = "";
    ratingsBody.innerHTML = `
      <tr>
        <td colspan="5" class="leaderboards-table-empty">Search for a player to compare ladder rows.</td>
      </tr>
    `;
    state.loadedMatches = [];
    state.matchesPage = 1;
    state.loadedProfile = null;
    updatePageUrl("", "", state.activeMatchType);
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

    loadProfile({
      player,
      profileId,
      matchType: state.activeMatchType,
    }).catch((error) => {
      feedback.textContent = error instanceof Error ? error.message : "Unable to load that player right now.";
      console.error(error);
    });
  }

  searchForm?.addEventListener("submit", handleSubmit);
  resetButton?.addEventListener("click", handleReset);
  searchResultsBody?.addEventListener("click", handleCandidateRowClick);
  queueChips?.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-match-type]") : null;
    if (!button) {
      return;
    }

    state.activeMatchType = Number(button.getAttribute("data-match-type") || 1);
    if (!state.loadedProfile) {
      syncQueueChips();
      return;
    }

    loadProfile({
      player: state.loadedProfile.player,
      profileId: state.loadedProfile.profileId,
      matchType: state.activeMatchType,
    }).catch((error) => {
      feedback.textContent = error instanceof Error ? error.message : "Unable to reload that player right now.";
      console.error(error);
    });
  });
  prevMatchesButton?.addEventListener("click", () => {
    if (state.matchesPage <= 1) {
      return;
    }
    state.matchesPage -= 1;
    renderMatches();
  });
  nextMatchesButton?.addEventListener("click", () => {
    state.matchesPage += 1;
    renderMatches();
  });

  if (initialProfileId) {
    loadProfile({
      player: initialPlayer,
      profileId: initialProfileId,
      matchType: state.activeMatchType,
    }).catch((error) => {
      feedback.textContent = error instanceof Error ? error.message : "Unable to load that player right now.";
      console.error(error);
    });
  } else if (initialPlayer) {
    loadPlayerCandidates(initialPlayer).catch((error) => {
      feedback.textContent = error instanceof Error ? error.message : "Unable to search for that player right now.";
      console.error(error);
    });
  }
})();
