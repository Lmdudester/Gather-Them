# Moxfield API Access

## Overview

Moxfield does **not** have an official, publicly documented API. The website uses internal endpoints at `api2.moxfield.com` that are not officially supported for third-party use.

## Terms of Service

- Moxfield **prohibits scraping** per their Terms of Service.
- Authorized programmatic access is available by contacting **support@moxfield.com** to request a custom User-Agent.

## robots.txt

- Blocks: `/account/*`, `/collection/*`, `/search/*`, `/binders/*`
- Does **not** block: `/decks/*`
- Sitemap: https://moxfield.com/sitemap.xml

## Known Unofficial Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET api2.moxfield.com/v2/decks/all/{deckId}` | Fetch a public deck by ID |
| `GET api2.moxfield.com/v2/cards/search` | Search cards |
| `GET api2.moxfield.com/v2/decks/search` | Search decks |

The deck ID is the string at the end of a Moxfield deck URL (e.g., `moxfield.com/decks/oEWXWHM5eEGMmopExLWRCA`).

## Authentication

- Public decks can be fetched without authentication.
- Private decks require authentication; the auth flow is not publicly documented.
- Cloudflare anti-bot protection may block direct HTTP requests.

## Community Libraries

| Project | Language | Link |
|---------|----------|------|
| MarioMH8/moxfield-api | TypeScript | https://github.com/MarioMH8/moxfield-api |
| Aleqsd/moxfield-api | Python (FastAPI) | https://github.com/Aleqsd/moxfield-api |
| spoved/moxfield.cr | Crystal | https://github.com/spoved/moxfield.cr |
| rossgayler/moxfield_api | — | https://github.com/rossgayler/moxfield_api |

## Built-in Export

Moxfield offers manual deck export via the **More** menu on each deck page. Format is plain text card lists (name + quantity only, no JSON/CSV).

## Recommended Approach

1. **Email `support@moxfield.com`** requesting a custom User-Agent for personal API access to your own decks.
2. Alternatively, export decks manually and store locally as JSON, using **Scryfall API** for all card/set data.
3. **Archidekt** (https://archidekt.com/api) is an alternative platform with a fully public, documented API.
