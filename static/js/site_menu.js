(function initializeSiteMenus() {
  function bindFooterShake() {
    const options = Array.from(document.querySelectorAll("[data-site-footer-shake-option]"));

    if (!options.length) {
      return;
    }

    const isCompactViewport = window.matchMedia("(max-width: 460px)").matches;
    const eligibleOptions = isCompactViewport
      ? options.filter((option) => option.classList.contains("site-footer-shake-looking"))
      : options;

    options.forEach((option) => option.classList.remove("is-active"));
    eligibleOptions[Math.floor(Math.random() * eligibleOptions.length)]?.classList.add("is-active");
  }

  function closeMenu(menu) {
    if (!menu) {
      return;
    }

    const button = menu.querySelector("[data-site-menu-button], .site-menu-button");
    const dropdown = menu.querySelector("[data-site-menu-dropdown], .site-menu-dropdown");

    menu.classList.remove("is-open");
    dropdown?.classList.remove("is-open");
    button?.setAttribute("aria-expanded", "false");
  }

  function openMenu(menu) {
    if (!menu) {
      return;
    }

    const button = menu.querySelector("[data-site-menu-button], .site-menu-button");
    const dropdown = menu.querySelector("[data-site-menu-dropdown], .site-menu-dropdown");

    document.querySelectorAll(".site-menu.is-open").forEach((otherMenu) => {
      if (otherMenu !== menu) {
        closeMenu(otherMenu);
      }
    });

    menu.classList.add("is-open");
    dropdown?.classList.add("is-open");
    button?.setAttribute("aria-expanded", "true");
  }

  function toggleMenu(menu) {
    if (!menu) {
      return;
    }

    if (menu.classList.contains("is-open")) {
      closeMenu(menu);
    } else {
      openMenu(menu);
    }
  }

  function bindMenus() {
    document.querySelectorAll(".site-menu").forEach((menu) => {
      if (menu.dataset.siteMenuBound === "true") {
        return;
      }

      menu.dataset.siteMenuBound = "true";

      const button = menu.querySelector("[data-site-menu-button], .site-menu-button");
      const dropdown = menu.querySelector("[data-site-menu-dropdown], .site-menu-dropdown");

      button?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleMenu(menu);
      });

      dropdown?.addEventListener("click", (event) => {
        if (event.target.closest("a")) {
          closeMenu(menu);
        }
      });
    });

    bindFooterShake();
  }

  document.addEventListener("click", (event) => {
    document.querySelectorAll(".site-menu.is-open").forEach((menu) => {
      if (!menu.contains(event.target)) {
        closeMenu(menu);
      }
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }

    document.querySelectorAll(".site-menu.is-open").forEach(closeMenu);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindMenus);
  } else {
    bindMenus();
  }
})();
