# Public Release Checklist

Use this before making the repository public.

## Security

- [ ] Confirm `.env` is not committed.
- [ ] Confirm `DJANGO_SECRET_KEY` is not hardcoded for production.
- [ ] Confirm `DEBUG=False` for production.
- [ ] Confirm `ALLOWED_HOSTS` is set in production.
- [ ] Remove local databases, logs, `.saz`, `.har`, and debug snapshots.
- [ ] Review any upstream API/session data before committing.

## Project Setup

- [ ] Run migrations from a fresh clone.
- [ ] Confirm `/` loads Global Activity.
- [ ] Confirm `/lobbies/` loads the Lobby Browser.
- [ ] Confirm `/agora/` loads Agora Chat Browser.
- [ ] Confirm `/build_orders/` loads Build Orders.
- [ ] Confirm `/robots.txt` loads.
- [ ] Confirm `/sitemap.xml` loads.

## UI Smoke Test

- [ ] Header/nav works on desktop.
- [ ] Header/nav works on mobile.
- [ ] Lobby inspector sidebars stay sticky.
- [ ] Open lobby sorting uses max configured player size.
- [ ] Build-order editor saves/imports/exports.
- [ ] Agora messages send with button.
- [ ] Agora messages send with Cmd/Ctrl + Return.
- [ ] Agora moderation messages display correctly.

## Public README

- [ ] Include project screenshots.
- [ ] Include setup instructions.
- [ ] Include feature list.
- [ ] Include data-source notes.
- [ ] Include unofficial/fan-project disclaimer.
- [ ] Decide whether to add a license.

## Nice-to-Have Before Public

- [ ] Add screenshots under `docs/screenshots/`.
- [ ] Add `.env.example`.
- [ ] Add deployment notes.
- [ ] Add known limitations section.
- [ ] Add roadmap section.
