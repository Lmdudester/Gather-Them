# Gather Them - MTG Card Finder

A Django web app that helps Magic: The Gathering players discover relevant cards from new sets for their existing decks. Paste a decklist, select one or more target sets, and find cards that match your deck's themes.

**Note:** This is mostly a pet project for me, but I wanted to do something I'd actually consider using myself. I'm experimenting with practical uses for Claude Code to advance my knowledge in the area.

## How It Works

**Three-step flow:**

1. **Paste your decklist** — supports common formats (`1 Card Name`, `1x Card Name`), section headers (Commander, Sideboard, etc.), and 100-card singleton decks
2. **Review extracted themes** — the app analyzes your deck and extracts themes across four categories (subtypes, keywords, card types, oracle text patterns), organized into tiers by frequency
3. **Browse matching cards** — see cards from the target sets that match your selected themes, filtered by format legality and color identity, with Scryfall card images. Cards already in your deck are automatically excluded.

## Features

- **161 oracle text patterns** covering archetypes like tokens, sacrifice, blink, copy, ramp, aristocrats, spellslinger, landfall, untap, enchantress, artifacts matter, wheels, pillowfort, and more
- **14 format filters** — Commander, Standard, Modern, Pioneer, Legacy, Vintage, Pauper, Oathbreaker, and others
- **Color identity enforcement** — results only include cards within your deck's color identity
- **Tiered theme ranking** — themes are sorted into Core / Strong / Moderate / Minor / Fringe columns based on how prevalent they are in your deck
- **3-step card name lookup** — exact name, then front face name (for DFCs/adventures like Bonecrusher Giant), then prefix match
- **Dedicated land discovery** — "Include All Lands" toggle finds non-basic lands using intersection-based color identity (lands sharing at least one color with your deck), separate from theme analysis
- **Deck card exclusion** — cards already in your decklist are filtered out of results
- **Multi-set search** — select multiple target sets via a searchable picker
- **272 playable sets** sorted by release date
- **One-click database update** — download the latest MTGJSON data from within the app, with a maintenance page shown during the update

## Requirements

- Python 3.12+
- Django 5.2+
- python-dotenv 1.0+
- MTGJSON AllPrintings SQLite database

## Setup

1. Download the AllPrintings SQLite database from [mtgjson.com/downloads/all-files](https://mtgjson.com/downloads/all-files/) and place it somewhere accessible. (You can also use the in-app "Update Database" button after setup.)

2. Create a `.env` file in the project root:
   ```
   MTGJSON_DB_PATH=/path/to/AllPrintings.sqlite
   PORT=8000  # optional, defaults to Django's 8000
   # MTGJSON_DOWNLOAD_URL=https://mtgjson.com/api/v5/AllPrintings.sqlite.zip  # optional override
   ```

3. Run the development server:
   ```
   python manage.py runserver
   ```

4. Open http://localhost:8000/

## Docker Deployment

The app can be hosted in a Docker container with automatic updates — every container restart pulls the latest code from GitHub.

### Quick Start

1. Copy the example compose file and set your MTGJSON database path:
   ```
   cp docker-compose.autoupdate.example.yml docker-compose.autoupdate.yml
   ```
   Edit `docker-compose.autoupdate.yml` and update the volume path to your local MTGJSON database directory.

2. Build and start:
   ```
   docker compose -f docker-compose.autoupdate.yml build
   docker compose -f docker-compose.autoupdate.yml up -d
   ```

3. Open http://localhost:3007/

### Updating

Restart the container to pull the latest code:
```
docker restart gather-them
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MTGJSON_DB_PATH` | `/mtgjson-data/AllPrintings.sqlite` | Path to MTGJSON database inside the container |
| `DEBUG` | `True` | Django debug mode |
| `PORT` | `3007` | Server port |
| `GIT_BRANCH` | `main` | Git branch to clone |
| `GIT_REPO_URL` | `https://github.com/Lmdudester/Gather-Them.git` | Repository URL |
| `SECRET_KEY` | (insecure default) | Django secret key |
| `ALLOWED_HOSTS` | (empty) | Comma-separated allowed hosts (use `*` to allow all, e.g. for Tailscale access) |

## Project Structure

```
gather_them/          Django project settings and URL config
finder/
  services/
    card_lookup.py    SQLite queries (card lookup, set listing, set card retrieval)
    db_updater.py     MTGJSON database download and atomic replacement
    deck_parser.py    Decklist text parsing
    theme_extractor.py  Theme extraction and frequency ranking
    oracle_patterns.py  161 regex patterns for oracle text theme detection
    set_filter.py     Filter set cards by selected theme tags
  templatetags/
    card_extras.py    Template filters (Scryfall URLs, tag display)
  templates/finder/   Server-rendered HTML templates
  static/finder/css/  Dark theme responsive CSS
  static/finder/img/  Site logo (favicon + header)
  middleware.py       Maintenance mode middleware for database updates
  forms.py            Decklist form with set and format dropdowns
  views.py            Views: index, analyze, results, update_db
```

## Data Sources

- **[MTGJSON](https://mtgjson.com)** — card data (108K+ cards, 850+ sets)
- **[Scryfall](https://scryfall.com)** — card images via CDN
