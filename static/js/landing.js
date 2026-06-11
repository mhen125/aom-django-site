(function () {
  "use strict";

  const config = window.PROSTAGMA_HOME || {};
  const activityUrl = config.activityUrl || "/api/activity/live";
  const newsUrl = config.newsUrl || "/api/home/news/";
  const fallbackNewsImage = config.fallbackNewsImage || "";

  const numberFormatter = new Intl.NumberFormat("en-US");
  const dateFormatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const fallbackRegions = [
    { id: "us-east", label: "US East", lat: 39.0, lon: -77.0, players: 28, lobbies: 6 },
    { id: "us-west", label: "US West", lat: 37.8, lon: -122.4, players: 18, lobbies: 4 },
    { id: "brazil", label: "Brazil", lat: -23.5, lon: -46.6, players: 10, lobbies: 2 },
    { id: "europe", label: "Europe", lat: 50.1, lon: 8.6, players: 36, lobbies: 8 },
    { id: "asia", label: "Asia", lat: 35.7, lon: 139.7, players: 24, lobbies: 5 },
    { id: "australia", label: "Australia", lat: -33.9, lon: 151.2, players: 8, lobbies: 2 },
  ];

  const ambientClusters = [
    { lat: 39, lon: -98, spreadLat: 12, spreadLon: 28, count: 80 },
    { lat: 48, lon: 10, spreadLat: 9, spreadLon: 22, count: 84 },
    { lat: 35, lon: 138, spreadLat: 8, spreadLon: 18, count: 46 },
    { lat: 22, lon: 78, spreadLat: 10, spreadLon: 18, count: 26 },
    { lat: -23, lon: -46, spreadLat: 8, spreadLon: 14, count: 18 },
    { lat: -32, lon: 145, spreadLat: 8, spreadLon: 18, count: 14 },
  ];

  function formatNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? numberFormatter.format(number) : "--";
  }

  function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
      element.textContent = value;
    }
  }

  function projectPoint(lat, lon, width, height) {
    return {
      x: ((Number(lon) + 180) / 360) * width,
      y: ((90 - Number(lat)) / 180) * height,
    };
  }

  function createSeededRandom(seed) {
    let hash = 2166136261;
    const text = String(seed);

    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }

    return function random() {
      hash += hash << 13;
      hash ^= hash >>> 7;
      hash += hash << 3;
      hash ^= hash >>> 17;
      hash += hash << 5;
      return ((hash >>> 0) % 10000) / 10000;
    };
  }

  function drawGlow(context, x, y, radius, alpha, pulse = 1) {
    const outer = radius * (6 + pulse * 2.2);
    const gradient = context.createRadialGradient(x, y, 0, x, y, outer);
    gradient.addColorStop(0, `rgba(255, 242, 166, ${alpha})`);
    gradient.addColorStop(0.16, `rgba(247, 203, 84, ${alpha * 0.78})`);
    gradient.addColorStop(0.38, `rgba(214, 155, 45, ${alpha * 0.32})`);
    gradient.addColorStop(1, "rgba(214, 155, 45, 0)");

    context.fillStyle = gradient;
    context.beginPath();
    context.arc(x, y, outer, 0, Math.PI * 2);
    context.fill();

    context.fillStyle = `rgba(255, 235, 139, ${Math.min(1, alpha * 1.45)})`;
    context.beginPath();
    context.arc(x, y, Math.max(1, radius * 0.74), 0, Math.PI * 2);
    context.fill();
  }

  function getActivityRegions(payload) {
    const regions = Array.isArray(payload?.regions) ? payload.regions : [];

    if (regions.length) {
      const summary = payload.summary || {};
      const totalSignals = Math.max(
        1,
        Number(summary.activePlayers || 0)
          || Number(summary.playersInMatches || 0)
          || Number(summary.playersInLobbies || 0)
          || Number(summary.steamPlayersOnline || 0) / 80
          || 1
      );

      return regions
        .filter((region) => region && region.id !== "unknown")
        .map((region, index) => {
          const direct = Number(region.players || 0) + Number(region.lobbies || 0) * 4;
          const fallback = Number(region.isServerArea ? totalSignals / Math.max(1, regions.length) : 0);
          return {
            ...region,
            activityWeight: Math.max(4, direct || fallback || (index + 1) * 3),
          };
        });
    }

    return fallbackRegions.map((region) => ({
      ...region,
      activityWeight: Number(region.players || 0) + Number(region.lobbies || 0) * 4,
    }));
  }

  function createBeaconPoints(regions, width, height) {
    const points = [];
    const totalWeight = regions.reduce((total, region) => total + Math.max(0, Number(region.activityWeight || 0)), 0) || 1;

    for (const region of regions) {
      const share = Math.max(0.06, Number(region.activityWeight || 0) / totalWeight);
      const count = Math.max(10, Math.min(62, Math.round(share * 180)));
      const anchor = projectPoint(region.lat, region.lon, width, height);
      const random = createSeededRandom(`home-region:${region.id || region.label}:${count}`);

      for (let index = 0; index < count; index += 1) {
        const spreadX = width * (0.025 + share * 0.038);
        const spreadY = height * (0.018 + share * 0.026);
        const x = anchor.x + (random() - 0.5) * spreadX;
        const y = anchor.y + (random() - 0.5) * spreadY;
        points.push({
          x,
          y,
          radius: 0.75 + random() * 1.25,
          alpha: 0.34 + random() * 0.42,
          phase: random() * Math.PI * 2,
        });
      }
    }

    return points;
  }

  function createAmbientPoints(width, height) {
    const points = [];

    for (const cluster of ambientClusters) {
      const random = createSeededRandom(`home-ambient:${cluster.lat}:${cluster.lon}`);

      for (let index = 0; index < cluster.count; index += 1) {
        const lat = cluster.lat + (random() - 0.5) * cluster.spreadLat;
        const lon = cluster.lon + (random() - 0.5) * cluster.spreadLon;
        const point = projectPoint(lat, lon, width, height);
        points.push({
          ...point,
          radius: 0.45 + random() * 0.8,
          alpha: 0.13 + random() * 0.22,
          phase: random() * Math.PI * 2,
        });
      }
    }

    return points;
  }

  function initHomeMap(payload) {
    const canvas = document.getElementById("homeActivityCanvas");
    const frame = canvas?.parentElement;

    if (!canvas || !frame) {
      return;
    }

    const context = canvas.getContext("2d");
    let width = 0;
    let height = 0;
    let ambientPoints = [];
    let beaconPoints = [];

    function resize() {
      const rect = frame.getBoundingClientRect();
      const nextWidth = Math.max(1, Math.round(rect.width));
      const nextHeight = Math.max(1, Math.round(rect.height));
      const ratio = Math.min(2, window.devicePixelRatio || 1);

      if (nextWidth === width && nextHeight === height) {
        return;
      }

      width = nextWidth;
      height = nextHeight;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);

      const regions = getActivityRegions(payload);
      ambientPoints = createAmbientPoints(width, height);
      beaconPoints = createBeaconPoints(regions, width, height);
    }

    function render(time) {
      resize();
      context.clearRect(0, 0, width, height);
      context.globalCompositeOperation = "lighter";

      for (const point of ambientPoints) {
        const pulse = 0.84 + Math.sin(time * 0.0012 + point.phase) * 0.16;
        drawGlow(context, point.x, point.y, point.radius, point.alpha * pulse, pulse);
      }

      for (const point of beaconPoints) {
        const pulse = 1 + Math.sin(time * 0.0018 + point.phase) * 0.22;
        drawGlow(context, point.x, point.y, point.radius * pulse, point.alpha, pulse);
      }

      context.globalCompositeOperation = "source-over";
      window.requestAnimationFrame(render);
    }

    resize();
    window.requestAnimationFrame(render);
    window.addEventListener("resize", resize, { passive: true });
  }

  async function loadActivity() {
    try {
      const response = await fetch(activityUrl, { headers: { Accept: "application/json" } });

      if (!response.ok) {
        throw new Error(`Activity request failed: ${response.status}`);
      }

      const payload = await response.json();
      const summary = payload.summary || {};

      setText("homePlayersOnline", formatNumber(summary.steamPlayersOnline));
      setText("homePlayersInMatches", formatNumber(summary.playersInMatches || summary.playersInLobbies || summary.activePlayers));
      setText("homeOpenLobbies", formatNumber(summary.openLobbies || summary.publicMpLobbies));
      setText("homePlayersInQueue", formatNumber(summary.playersInQueue || summary.queueSignals || 0));
      initHomeMap(payload);
    } catch (_error) {
      setText("homePlayersOnline", "--");
      setText("homePlayersInMatches", "--");
      setText("homeOpenLobbies", "--");
      setText("homePlayersInQueue", "--");
      initHomeMap({ regions: fallbackRegions, summary: {} });
    }
  }

  function formatDate(value) {
    if (!value) {
      return "Official Feed";
    }

    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Official Feed" : dateFormatter.format(date);
  }

  function cleanNewsTitle(value) {
    return String(value || "Age of Mythology: Retold News")
      .replace(/^Age of Mythology:\s*Retold\s*[–-]\s*/i, "")
      .trim();
  }

  function setImage(element, src) {
    if (!element || !src) {
      return;
    }

    element.src = src;
  }

  function renderFeaturedNews(item) {
    if (!item) {
      return;
    }

    const badge = document.getElementById("homeFeaturedNewsBadge");
    const date = document.getElementById("homeFeaturedNewsDate");
    const title = document.getElementById("homeFeaturedNewsTitle");
    const summary = document.getElementById("homeFeaturedNewsSummary");
    const link = document.getElementById("homeFeaturedNewsLink");
    const image = document.getElementById("homeFeaturedNewsImage");

    if (badge) badge.textContent = item.isFresh ? "Fresh Update" : "Latest News";
    if (date) {
      date.textContent = formatDate(item.publishedAt);
      date.dateTime = item.publishedAt || "";
    }
    if (title) title.textContent = cleanNewsTitle(item.title);
    if (summary) summary.textContent = item.summary || "Read the latest official update from Steam.";
    if (link && item.url) link.href = item.url;
    setImage(image, item.imageUrl);
  }

  function createNewsCard(item) {
    const article = document.createElement("article");
    article.className = "landing-news-card landing-panel";

    const media = document.createElement("a");
    media.className = "landing-news-card-image";
    media.href = item.url || "https://steamcommunity.com/games/1934680/announcements/";
    media.target = "_blank";
    media.rel = "noopener noreferrer";

    const image = document.createElement("img");
    image.alt = "";
    image.loading = "lazy";
    image.src = item.imageUrl || fallbackNewsImage;
    media.appendChild(image);

    const body = document.createElement("div");
    body.className = "landing-news-card-body";

    const date = document.createElement("span");
    date.className = "landing-news-date";
    date.textContent = formatDate(item.publishedAt);

    const title = document.createElement("h3");
    title.textContent = cleanNewsTitle(item.title);

    const summary = document.createElement("p");
    summary.textContent = item.summary || "Read the latest official announcement.";

    const link = document.createElement("a");
    link.className = "landing-news-link";
    link.href = item.url || "https://steamcommunity.com/games/1934680/announcements/";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Read More";

    body.append(date, title, summary, link);
    article.append(media, body);
    return article;
  }

  function renderNews(payload) {
    const items = Array.isArray(payload?.items) ? payload.items : [];
    const featured = payload?.featured || items[0] || null;

    renderFeaturedNews(featured);

    const grid = document.getElementById("homeNewsGrid");

    if (!grid) {
      return;
    }

    const rowItems = items
      .filter((item) => !featured || item.url !== featured.url)
      .slice(0, 3);

    const cards = (rowItems.length ? rowItems : items.slice(0, 3)).map(createNewsCard);

    if (!cards.length) {
      return;
    }

    grid.replaceChildren(...cards);
  }

  async function loadNews() {
    try {
      const response = await fetch(newsUrl, { headers: { Accept: "application/json" } });

      if (!response.ok) {
        throw new Error(`News request failed: ${response.status}`);
      }

      renderNews(await response.json());
    } catch (_error) {
      renderFeaturedNews(null);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    loadActivity();
    loadNews();
  });
}());
