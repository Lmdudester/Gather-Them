# Magic: The Gathering Card Data Sources

An analysis of free, publicly available APIs and databases for accessing Magic: The Gathering card information.

---

## The Two Clear Leaders

### 1. Scryfall API (Live REST API)

**How it works:** Real-time REST API you query over the network. No API key needed — just set a `User-Agent` header.

**Base URL:** `https://api.scryfall.com/`

**Data available:**

- 70+ fields per card: name, oracle text, mana cost, colors, color identity, type line, keywords, power/toughness/loyalty
- Format legality across 21+ formats (standard, modern, commander, etc.)
- Card images in 6 sizes (PNG, JPG — from thumbnails to high-res scans)
- Prices (USD, EUR, MTGO tix — updated daily)
- All printings across all languages
- Rulings, artist info, watermarks, promo types, Reserved List status
- EDHREC rank, cross-platform IDs (Arena, MTGO, TCGPlayer, Cardmarket)
- Set metadata, tokens, emblems

**Search:** Extremely powerful query syntax — filter by color, type, oracle text, mana value, format, price, keywords, regex, and combine with boolean logic. Example: `c:red t:instant mv<=2 f:modern`

**Key Search Syntax:**

| Filter         | Syntax              | Example                     |
|----------------|---------------------|-----------------------------|
| Name           | bare words or `!"exact name"` | `lightning bolt` or `!"Lightning Bolt"` |
| Colors         | `c:` or `color:`    | `c:rg` (red and green)      |
| Color identity | `id:` or `identity:`| `id:mardu`                  |
| Type           | `t:` or `type:`     | `t:merfolk t:legend`        |
| Oracle text    | `o:` or `oracle:`   | `o:"draw a card"`           |
| Mana cost      | `m:` or `mana:`     | `m:{2}{W}{W}`               |
| Mana value     | `mv=` / `mv>=`      | `mv<=3`                     |
| Power/Toughness| `pow=`, `tou>=`     | `pow>=8 tou<=2`             |
| Set            | `s:` or `set:`      | `s:mkm`                     |
| Rarity         | `r:`                | `r:mythic`                  |
| Format legality| `f:` or `format:`   | `f:modern`                  |
| Price          | `usd>`, `eur<`      | `usd>50`                    |
| Artist         | `a:`                | `a:"john avon"`             |
| Keywords       | `keyword:` or `kw:` | `kw:flying`                 |

Operators: `>`, `<`, `>=`, `<=`, `!=`, `=`
Boolean logic: `or`, `(parentheses)`, `-` prefix for negation
Regex: `name:/pattern/`, `type:/pattern/`, `oracle:/pattern/`

**Key API Endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `GET /cards/search?q={query}` | Full-text search with filters |
| `GET /cards/named?exact={name}` | Exact name lookup |
| `GET /cards/named?fuzzy={name}` | Fuzzy name lookup |
| `GET /cards/autocomplete?q={partial}` | Name autocomplete (up to 20 suggestions) |
| `GET /cards/random` | Random card (accepts optional `q` filter) |
| `POST /cards/collection` | Batch lookup (up to 75 cards per request) |
| `GET /cards/{id}` | Lookup by Scryfall UUID |
| `GET /cards/{set_code}/{collector_number}` | Lookup by set + collector number |
| `GET /cards/multiverse/{id}` | Lookup by Gatherer Multiverse ID |
| `GET /sets` | List all sets |
| `GET /bulk-data` | Bulk data download catalog |

**Rate limits:** ~10 requests/second (50-100ms delay requested). Images have no rate limit.

**Bulk downloads:** JSON files regenerated every 12 hours:

| File | Size | Contents |
|------|------|----------|
| Oracle Cards | ~161 MB | One entry per unique card |
| Unique Artwork | ~233 MB | One entry per unique illustration |
| Default Cards | ~501 MB | Every English printing |
| All Cards | ~2.3 GB | Every printing in every language |
| Rulings | ~23 MB | All official rulings |

**Update process for bulk data:** Query `/bulk-data` endpoint to get the current download URL, then re-download. Files change every 12 hours.

**Pros:**

- No authentication whatsoever
- Best-in-class search syntax — powerful enough for complex queries
- Card images included (and no rate limit on images)
- Near-real-time updates (new spoilers appear within hours)
- Most widely used MTG API — huge community and ecosystem
- Bulk downloads available if you want local data

**Cons:**

- Online API requires network access for queries (unless you use bulk downloads)
- Bulk downloads are JSON-only (no SQL/SQLite/CSV)
- Price data is limited (one price per card per day, from a few sources)
- Terms require you to add "genuine original value" — can't just mirror the data
- Bulk files require re-downloading the whole file (no incremental updates)

**Keeping up to date:**

- API: Always current, nothing to do
- Bulk data: Poll `/bulk-data` for new URLs, re-download every 12-24 hours. Compressed files are manageable (~70-80 MB for the default set)

**Terms of use:** Falls under the Wizards of the Coast Fan Content Policy. Must not paywall the data, must not imply endorsement, must add genuine original value. Card images remain WotC intellectual property.

---

### 2. MTGJSON (Downloadable Database)

**How it works:** Pre-built database files you download to your machine. MIT licensed.

**Website:** https://mtgjson.com/
**Download URL pattern:** `https://mtgjson.com/api/v5/{filename}`

**Data available:**

- Comparable card data to Scryfall (70+ fields per printing)
- **No card images** (but provides Scryfall IDs to construct image URLs)
- **Superior pricing data:** 5 providers (Card Kingdom, TCGPlayer, Cardmarket, Cardsphere, Cardhoarder), with **90 days of historical prices**, separated by buylist/retail and finish type
- EDHREC rank and saltiness scores
- Cross-references to Scryfall, TCGPlayer, Cardmarket, MTGO, Arena, Card Kingdom, and many other retailer IDs
- Full set metadata including booster pack probability breakdowns
- Preconstructed deck lists

**Download formats:**

| Format | Use Case |
|--------|----------|
| JSON | Direct parsing |
| **SQLite** | Query with SQL locally — great for apps |
| SQL | Import into MySQL |
| PostgreSQL | Import into Postgres |
| CSV | Spreadsheets / data analysis |
| Parquet | Analytics tools (Pandas, DuckDB, Spark) |

**Key file sizes:**

| File | Size |
|------|------|
| AllPrintings.json | ~515 MB |
| AllPrintings.sqlite | ~498 MB |
| AtomicCards.json (unique cards only) | ~143 MB |
| AllPrices.json (90-day history) | ~1.1 GB |
| AllPricesToday.json | ~50 MB |

Format-specific subsets are also available: `Standard.json`, `Modern.json`, `Pioneer.json`, `Legacy.json`, `Vintage.json`, `Pauper.json`.

**Pros:**

- **SQLite database** — query locally with SQL, no network dependency
- MIT license — use for anything, including commercial projects
- Best pricing data of any free source (multi-vendor, 90-day history)
- Multiple output formats (JSON, SQLite, SQL, CSV, Parquet)
- Format-specific subsets available
- No rate limits — it's your local database
- `Meta.json` endpoint to check if updates are available before re-downloading

**Cons:**

- No card images (must use Scryfall IDs to fetch them separately)
- No live search API (free tier) — you must download and query locally
- GraphQL API exists but is Patreon-only (beta)
- Full re-download required for updates (no incremental diffs)
- Larger storage footprint than just using an API

**Keeping up to date:**

- Files rebuild daily (1 AM EST, live by 9 AM EST)
- Check `https://mtgjson.com/api/v5/Meta.json` for the current version/date, compare to your local copy
- Re-download the file(s) you need. Compressed versions are ~15-30% of full size
- Simple to automate with a daily cron job / scheduled task

**Terms of use:** MIT License — very permissive. Free to use, modify, and distribute including for commercial projects.

---

## Other Options (Generally Not Recommended)

### 3. magicthegathering.io (MTG SDK)

**Website:** https://magicthegathering.io/
**Base URL:** `https://api.magicthegathering.io/v1/`

- Free, no auth, SDKs in 10+ languages (Python, Ruby, JS, Java, C#, Go, Swift, etc.)
- 5,000 requests/hour rate limit
- **Frozen since February 2022** — missing 3+ years of sets (everything after Kamigawa: Neon Dynasty)
- No pricing data

**Verdict: Do not use.** Data is critically out of date.

### 4. Gatherer (Official WotC)

**Website:** https://gatherer.wizards.com/

- Authoritative source for Oracle text and rulings
- **No API exists** — web-only, scraping is fragile and likely against ToS
- Scryfall and MTGJSON both aggregate Gatherer data already

**Verdict: Not viable as a data source.**

### 5. Pricing-Focused APIs

| Service | Free Tier | Focus |
|---------|-----------|-------|
| JustTCG (justtcg.com) | 1,000 req/month | Multi-TCG pricing with trend analysis |
| TCGAPIs (tcgapis.com) | 100 req/day + free CSV downloads | TCGPlayer marketplace pricing |
| EchoMTG (echomtg.com) | Partial free access | Collection management + pricing |

These are only relevant if you need specialized pricing beyond what MTGJSON provides.

### 6. MTGGraphQL (MTGJSON's GraphQL API)

- Built on MTGJSON's full dataset
- Currently in beta, restricted to **Patreon subscribers only**
- Bearer token authentication, 500 requests/hr per token
- Not free/public — included here for completeness

### 7. TCGPlayer Developer API

- OAuth-based, must apply for access
- **Closed to new developers** — no longer accepting new applications
- Not recommended for new projects

---

## Recommendation Summary

| Need | Best Choice |
|------|-------------|
| Live search + card images | **Scryfall API** |
| Local database you can query with SQL | **MTGJSON (SQLite)** |
| Detailed price history (multi-vendor) | **MTGJSON** |
| Simplest integration (just make HTTP calls) | **Scryfall API** |
| Offline-first / no network dependency | **MTGJSON** |
| Both card data AND images in one source | **Scryfall API** |
| Most permissive license | **MTGJSON** (MIT) |

**For most personal projects, the best approach is to use both together:** MTGJSON's SQLite database as your local data store (for fast queries, pricing, and offline access), and Scryfall's image endpoints for card images (using the `scryfallId` that MTGJSON provides). This gives you the best of both worlds with no API key requirements and simple daily updates.

---

*Analysis compiled February 2026.*
