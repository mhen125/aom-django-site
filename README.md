# Prostagma? — Age of Mythology: Retold Tools

**Prostagma?** is an unofficial Age of Mythology: Retold companion site built with Django. It combines a live multiplayer activity dashboard, a custom lobby browser, a build-order archive/editor, and a small public community chat called Agora.

The project started as a build-order site and grew into a broader AoM Retold utility hub.

> This project is unofficial and is not affiliated with, endorsed by, or sponsored by Microsoft, World's Edge, Xbox Game Studios, or the Age of Empires / Age of Mythology teams.

## Features

### Global Activity

The home page shows a live activity snapshot for AoM Retold, including Steam player activity, queue/lobby signals, and a global night-map style activity visualization.

### Lobby Browser

The lobby browser shows open custom lobbies, active custom matches, and ranked activity in a themed interface.

Current lobby-browser features include:

- Open lobby search and filters
- Hide AI / Arena of the Gods games
- Hide full lobbies
- Hide passworded lobbies
- Hide cheat-enabled lobbies
- Sticky lobby inspector/sidebar
- Map thumbnails
- Player slot details
- God/player icons where available
- Custom and ranked match tabs

### Build Order Archive

The build-order section lets users browse build orders by pantheon and major god.

Current build-order features include:

- Pantheon selection page
- Major god pages
- Build-order detail pages
- Build-order editor
- JSON export/import helper
- Resource icons and villager distribution display
- Internal links between builds, lobbies, and Agora

### Agora Chat Browser

Agora is a single public chat room for AoM Retold discussion.

Current Agora features include:

- Public message room
- Display names stored per browser
- Cmd + Return / Ctrl + Enter to send
- Basic message cooldown
- Name-change cooldown
- Temporary spam restrictions
- Severe slur filtering and moderation metadata
- Django admin moderation actions

## Tech Stack

- Python
- Django
- JavaScript
- HTML
- CSS
- SQLite for local development
- httpx for upstream API requests

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/mhen125/aom-django-site.git
cd aom-django-site
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create environment variables

Copy the example file:

```bash
cp .env.example .env
```

Then update values as needed.

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Start the development server

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

## Main Routes

```text
/                  Global Activity
/lobbies/          Lobby Browser
/agora/            Agora Chat Browser
/build_orders/     Build Order Archive
/build-orders/     Build Order Archive alias
/gods/<god>/       Major God build-order page
/builds/<build>/   Build-order detail page
/editor/           Build-order editor
/robots.txt        Robots file
/sitemap.xml       Sitemap
```

## Environment Variables

The project can run locally with the defaults, but production deployments should define environment variables.

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
```

See `.env.example` for details.

## Data Sources

This project uses publicly available and/or reverse-engineered AoM Retold related data sources. Some data may be incomplete, delayed, inferred, or unavailable depending on upstream behavior.

Known external sources and references include:

- AoM Retold lobby/activity endpoints
- aomstats.io APIs and database dump metadata
- Steam public player-count data where available

Please avoid excessive polling or repeated downloads from third-party sources.

## Notes on aomstats Database Dumps

aomstats.io provides weekly gzipped CSV database dumps for match data and leaderboard snapshots. Those dumps are a good future source for global god statistics, pick rates, win rates, matchup data, and patch-based trend analysis.

A future stats pipeline could:

1. Fetch the dump list from `https://aomstats.io/api/db_dumps`.
2. Download only files with new/changed checksums.
3. Import match rows into local Django models.
4. Deduplicate matches by `match_id`.
5. Aggregate god play percentage, win rate, map usage, and queue-specific stats.

## Development Notes

Useful commands:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Check Python syntax quickly:

```bash
python -m py_compile config/urls.py builds/views.py lobbies/views.py agora/views.py
```

Check JavaScript syntax for key frontend files:

```bash
node --check static/js/site_menu.js
node --check static/js/home.js
node --check static/js/build_detail.js
node --check static/js/editor.js
node --check lobbies/static/js/lobbies.js
node --check agora/static/js/agora.js
```

## Project Status

This is an active personal project. Some features are experimental, and upstream AoM Retold data can change without notice.

## License

No license has been selected yet. Until a license is added, all rights are reserved by the repository owner.

## Disclaimer

Prostagma? is an unofficial fan-made project. Age of Mythology, Age of Mythology: Retold, Age of Empires, Microsoft, World's Edge, Xbox Game Studios, and related names, artwork, icons, and trademarks belong to their respective owners.
