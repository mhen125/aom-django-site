# Placeholder Inventory

This file tracks temporary content, fake assets, disabled pages, and dummy surfaces that should be replaced or wired up before they are treated as finished product areas.

Last reviewed: 2026-06-13

## Homepage

- Fresh update fallback art uses `static/assets/optimized/images/homepage/Gods_Portrait_Window_Multi.webp` when the Steam feed item has no image.
- Community spotlight falls back to static art when Twitch credentials are missing or the Twitch API returns no videos.
- Explore Prostagma includes disabled future areas:
  - Compendium
  - Combat Simulator

## Header And Navigation

- Tools dropdown contains disabled future pages:
  - Compendium
  - Combat Simulator
  - Username Styling Tool

## Footer

- Footer is intentionally minimal for now.
- The current footer note is placeholder copy until final footer links, community credits, and legal/support destinations are chosen.

## Data And Content

- `static/js/data.js` still provides fallback/sample build-order data for local and empty-database states.
- Build-order editor placeholder text uses example values such as "3:30 Athena Rush" and example resource/action rows.

## Stats And Leaderboards

- Stats and leaderboards now use returned live API data when available. Any empty states should describe missing returned data directly rather than implying estimated or inferred community trends.

## Notes

- The homepage map dev panel is available with `?homeMapDev=1` or `?mapDev=1`. After opening once, that dev access is remembered in local storage.
- The full live activity map dev panel remains available on the live activity surface with `?mapDev=1`.
