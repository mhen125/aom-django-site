# Placeholder Inventory

This file tracks temporary content, fake assets, disabled pages, and dummy surfaces that should be replaced or wired up before they are treated as finished product areas.

Last reviewed: 2026-06-11

## Homepage

- Fresh update fallback art uses `static/assets/optimized/images/homepage/Gods_Portrait_Window_Multi.webp` when the Steam feed item has no image.
- Community Pulse cards are placeholder content. They currently use god portrait cards as temporary media:
  - `static/assets/optimized/images/gods/zeus_portrait.card.webp`
  - `static/assets/optimized/images/gods/odin_portrait.card.webp`
  - `static/assets/optimized/images/gods/Huitzilopochtli_portrait.card.webp`
- Community Pulse copy is placeholder text for future creator, video, ranked, and event feeds.
- Explore Prostagma includes disabled future areas:
  - Leaderboards
  - Compendium
  - Combat Simulator

## Header And Navigation

- Leaderboards is shown as a disabled "Coming soon" item.
- Tools dropdown contains disabled future pages:
  - Compendium
  - Combat Simulator
  - Username Styling Tool

## Data And Content

- `static/js/data.js` still provides fallback/sample build-order data for local and empty-database states.
- Build-order editor placeholder text uses example values such as "3:30 Athena Rush" and example resource/action rows.

## Notes

- The homepage map dev panel is available only with `?homeMapDev=1` or `?mapDev=1`.
- The full live activity map dev panel remains available on the live activity surface with `?mapDev=1`.
