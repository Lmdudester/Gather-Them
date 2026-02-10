# Gather Them

A Django web app that helps Magic: The Gathering players discover relevant cards from new sets for their existing decks. Paste a decklist, select a target set, and find cards that match your deck's themes.

## How It Works

**Three-step flow:**

1. **Paste your decklist** — supports common formats (`1 Card Name`, `1x Card Name`), section headers (Commander, Sideboard, etc.), and 100-card singleton decks
2. **Review extracted themes** — the app analyzes your deck and extracts themes across four categories (subtypes, keywords, card types, oracle text patterns), organized into tiers by frequency
3. **Browse matching cards** — see cards from the target set that match your selected themes, filtered by format legality and color identity, with Scryfall card images

## Features

- **92 oracle text patterns** covering archetypes like tokens, sacrifice, blink, copy, ramp, aristocrats, spellslinger, landfall, and more
- **14 format filters** — Commander, Standard, Modern, Pioneer, Legacy, Vintage, Pauper, Oathbreaker, and others
- **Color identity enforcement** — results only include cards within your deck's color identity
- **Tiered theme ranking** — themes are sorted into Core / Strong / Moderate / Minor / Fringe columns based on how prevalent they are in your deck
- **3-step card name lookup** — exact name, then front face name (for DFCs/adventures like Bonecrusher Giant), then prefix match
- **272 playable sets** in the dropdown, sorted by release date

## Requirements

- Python 3.12+
- Django 5.2+
- MTGJSON AllPrintings SQLite database

## Setup

1. Download the AllPrintings SQLite database from [mtgjson.com/downloads/all-files](https://mtgjson.com/downloads/all-files/) and place it somewhere accessible.

2. Update `MTGJSON_DB_PATH` in `gather_them/settings.py` to point to your database file:
   ```python
   MTGJSON_DB_PATH = '/path/to/AllPrintings.sqlite'
   ```

3. Run the development server:
   ```
   python manage.py runserver
   ```

4. Open http://localhost:8000/

## Project Structure

```
gather_them/          Django project settings and URL config
finder/
  services/
    card_lookup.py    SQLite queries (card lookup, set listing, set card retrieval)
    deck_parser.py    Decklist text parsing
    theme_extractor.py  Theme extraction and frequency ranking
    oracle_patterns.py  92 regex patterns for oracle text theme detection
    set_filter.py     Filter set cards by selected theme tags
  templatetags/
    card_extras.py    Scryfall image URL template filter
  templates/finder/   Server-rendered HTML templates
  static/finder/css/  Dark theme responsive CSS
  forms.py            Decklist form with set and format dropdowns
  views.py            Three views: index, analyze, results
```

## Data Sources

- **[MTGJSON](https://mtgjson.com)** — card data (108K+ cards, 850+ sets)
- **[Scryfall](https://scryfall.com)** — card images via CDN
