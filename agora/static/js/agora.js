(() => {
  const messagesUrl = window.AOM_AGORA_MESSAGES_URL || "/agora/api/messages/";
  const postUrl = window.AOM_AGORA_POST_URL || "/agora/api/messages/post/";
  const currentUser = window.AOM_AGORA_USER || { isAuthenticated: false };

  const messagesElement = document.getElementById("agoraMessages");
  const form = document.getElementById("agoraForm");
  const nameInput = document.getElementById("agoraDisplayName");
  const bodyInput = document.getElementById("agoraMessageBody");
  const characterCount = document.getElementById("agoraCharacterCount");
  const formStatus = document.getElementById("agoraFormStatus");
  const sendButton = document.getElementById("agoraSendButton");

  const CLIENT_ID_KEY = "prostagma_agora_client_id";
  const DISPLAY_NAME_KEY = "prostagma_agora_display_name";
  const GUEST_NAME_LOCK_KEY = "prostagma_agora_guest_name_assigned";
  const POLL_MS = 3000;

  let lastRenderedSignature = "";
  let isPosting = false;
  let pollTimer = null;

  function getClientId() {
    let clientId = localStorage.getItem(CLIENT_ID_KEY);

    if (!clientId) {
      clientId = `${Date.now()}-${Math.random().toString(16).slice(2)}-${cryptoRandomPart()}`;
      localStorage.setItem(CLIENT_ID_KEY, clientId);
    }

    return clientId;
  }

  function cryptoRandomPart() {
    if (window.crypto && window.crypto.getRandomValues) {
      const bytes = new Uint32Array(2);
      window.crypto.getRandomValues(bytes);
      return Array.from(bytes).map((value) => value.toString(16)).join("");
    }

    return Math.random().toString(16).slice(2);
  }


  function getGuestNamePool() {
    return Array.isArray(window.AOM_AGORA_GUEST_NAMES)
      ? window.AOM_AGORA_GUEST_NAMES.filter((name) => String(name || "").trim())
      : [];
  }

  function hashString(value) {
    const text = String(value || "");
    let hash = 2166136261;

    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }

    return hash >>> 0;
  }

  function assignGuestDisplayName() {
    const savedName = localStorage.getItem(DISPLAY_NAME_KEY);
    const alreadyAssigned = localStorage.getItem(GUEST_NAME_LOCK_KEY) === "true";

    if (savedName && alreadyAssigned) {
      return savedName;
    }

    const guestNames = getGuestNamePool();

    if (!guestNames.length) {
      return savedName || "Villager";
    }

    const clientId = getClientId();
    const index = hashString(clientId) % guestNames.length;
    const assignedName = guestNames[index];

    localStorage.setItem(DISPLAY_NAME_KEY, assignedName);
    localStorage.setItem(GUEST_NAME_LOCK_KEY, "true");

    return assignedName;
  }

  function getCsrfToken() {
    const csrfInput = form?.querySelector("input[name='csrfmiddlewaretoken']");
    if (csrfInput?.value) {
      return csrfInput.value;
    }

    const cookieMatch = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return cookieMatch ? decodeURIComponent(cookieMatch[1]) : "";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatMessageTime(value) {
    if (!value) {
      return "";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function setStatus(message, type = "") {
    if (!formStatus) {
      return;
    }

    formStatus.textContent = message || "";
    formStatus.dataset.statusType = type;
  }

  function updateCharacterCount() {
    if (!characterCount || !bodyInput) {
      return;
    }

    characterCount.textContent = `${bodyInput.value.length} / ${bodyInput.maxLength || 500}`;
  }

  function setFormDisabled(disabled) {
    isPosting = disabled;
    if (sendButton) {
      sendButton.disabled = disabled;
    }
  }

  function initializeDisplayName() {
    if (!nameInput) {
      return;
    }

    if (currentUser.isAuthenticated) {
      nameInput.readOnly = true;
      if (currentUser.displayName && !nameInput.value) {
        nameInput.value = currentUser.displayName;
      }
      return;
    }

    if (!nameInput.value) {
      nameInput.value = assignGuestDisplayName();
    }
  }

  function renderMessages(messages) {
    if (!messagesElement) {
      return;
    }

    const signature = JSON.stringify(messages.map((message) => [message.id, message.body, message.wasFiltered]));
    if (signature === lastRenderedSignature) {
      return;
    }

    lastRenderedSignature = signature;

    if (!messages.length) {
      messagesElement.innerHTML = `<div class="agora-empty-state">No messages yet. Be the first villager in the room.</div>`;
      return;
    }

    messagesElement.innerHTML = messages.map((message) => {
      const avatarMarkup = message.avatarUrl
        ? `<img class="agora-message-avatar" src="${escapeHtml(message.avatarUrl)}" alt="" loading="lazy">`
        : `<div class="agora-message-avatar agora-message-avatar-fallback">${escapeHtml(String(message.displayName || "?").slice(0, 1).toUpperCase())}</div>`;

      const steamBadge = message.isSteamUser ? `<span class="agora-steam-badge">Steam</span>` : "";
      const filteredBadge = message.wasFiltered ? `<span class="agora-filtered-badge">Filtered</span>` : "";

      return `
        <article class="agora-message ${message.isSteamUser ? "is-steam-user" : ""}">
          ${avatarMarkup}
          <div class="agora-message-body-wrap">
            <header class="agora-message-meta">
              <strong>${escapeHtml(message.displayName || "Villager")}</strong>
              ${steamBadge}
              <time datetime="${escapeHtml(message.createdAt || "")}">${escapeHtml(formatMessageTime(message.createdAt))}</time>
              ${filteredBadge}
            </header>
            <div class="agora-message-body">${escapeHtml(message.body || "")}</div>
          </div>
        </article>
      `;
    }).join("");

    messagesElement.scrollTop = messagesElement.scrollHeight;
  }

  async function loadMessages() {
    const response = await fetch(messagesUrl, {
      headers: {
        "Accept": "application/json",
        "X-Agora-Client-Id": getClientId(),
      },
    });

    if (!response.ok) {
      throw new Error(`Could not load Agora messages: ${response.status}`);
    }

    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.error || "Could not load Agora messages.");
    }

    renderMessages(Array.isArray(payload.messages) ? payload.messages : []);
  }

  async function postMessage() {
    if (!form || !bodyInput || isPosting) {
      return;
    }

    const body = bodyInput.value.trim();
    if (!body) {
      setStatus("Type a message first.", "error");
      return;
    }

    const displayName = nameInput?.value.trim() || assignGuestDisplayName();

    if (!currentUser.isAuthenticated && nameInput) {
      localStorage.setItem(DISPLAY_NAME_KEY, displayName);
    }

    setFormDisabled(true);
    setStatus("Sending...", "pending");

    try {
      const response = await fetch(postUrl, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Agora-Client-Id": getClientId(),
        },
        body: JSON.stringify({
          displayName,
          body,
          clientId: getClientId(),
        }),
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Message failed: ${response.status}`);
      }

      bodyInput.value = "";
      updateCharacterCount();
      setStatus("Sent.", "success");
      await loadMessages();

      setTimeout(() => {
        if (formStatus?.dataset.statusType === "success") {
          setStatus("");
        }
      }, 1200);
    } catch (error) {
      console.warn(error);
      setStatus(error.message || "Could not send message.", "error");
    } finally {
      setFormDisabled(false);
      bodyInput.focus();
    }
  }

  function bindEvents() {
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        postMessage();
      });
    }

    if (bodyInput) {
      bodyInput.addEventListener("input", updateCharacterCount);
      bodyInput.addEventListener("keydown", (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
          event.preventDefault();
          postMessage();
        }
      });
    }

    if (nameInput && !currentUser.isAuthenticated) {
      nameInput.addEventListener("change", () => {
        const value = nameInput.value.trim();
        if (value) {
          localStorage.setItem(DISPLAY_NAME_KEY, value);
        }
      });
    }
  }

  function startPolling() {
    if (pollTimer) {
      window.clearInterval(pollTimer);
    }

    pollTimer = window.setInterval(() => {
      loadMessages().catch((error) => {
        console.warn(error);
        setStatus("Connection hiccup. Retrying...", "error");
      });
    }, POLL_MS);
  }

  function init() {
    if (!messagesElement || !form) {
      return;
    }

    initializeDisplayName();
    updateCharacterCount();
    bindEvents();

    loadMessages().catch((error) => {
      console.warn(error);
      if (messagesElement) {
        messagesElement.innerHTML = `<div class="agora-empty-state">Could not load messages.</div>`;
      }
      setStatus("Could not connect to Agora.", "error");
    });

    startPolling();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
