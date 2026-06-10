(function initializeAgoraSiteMenu() {
  function closeMenu(button, dropdown) {
    button.setAttribute("aria-expanded", "false");
    dropdown.classList.remove("is-open");
  }

  function openMenu(button, dropdown) {
    button.setAttribute("aria-expanded", "true");
    dropdown.classList.add("is-open");
  }

  function bindMenu() {
    const button = document.getElementById("siteMenuButton");
    const dropdown = document.getElementById("siteMenuDropdown");

    if (!button || !dropdown || button.dataset.agoraMenuBound === "true") {
      return;
    }

    button.dataset.agoraMenuBound = "true";

    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();

      const isOpen = button.getAttribute("aria-expanded") === "true";

      if (isOpen) {
        closeMenu(button, dropdown);
      } else {
        openMenu(button, dropdown);
      }
    });

    dropdown.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    document.addEventListener("click", (event) => {
      if (!dropdown.contains(event.target) && !button.contains(event.target)) {
        closeMenu(button, dropdown);
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu(button, dropdown);
        button.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindMenu);
  } else {
    bindMenu();
  }
})();
