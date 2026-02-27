# Performance Fix Plan

- **Branch:** `fix/query-performance`
- **Issues addressed:** #40, #38

---

## Issue #40: Cache `get_sets_for_dropdown()` results

### Problem

`get_sets_for_dropdown()` issues a SQLite query every time it is called.
It is called from three places:

| Call site | When |
|-----------|------|
| `forms.py:50` — `DecklistForm.__init__` | Every form instantiation (index, analyze fallback, results fallback) |
| `views.py:210` — `analyze()` | Building set display names |
| `views.py:422` — `results()` | Building set display names |

A single page request that renders a `DecklistForm` and then proceeds to `analyze()` or `results()` triggers 2-3 identical queries. The underlying data only changes when an admin triggers a full database update via `update_db()`.

### Approach

Add a module-level, thread-safe in-memory cache to `card_lookup.py`, following the same double-checked locking pattern already used in `oracle_patterns.py`.

**Changes in `finder/services/card_lookup.py`:**

1. Add module-level cache state:
   ```python
   import threading

   _sets_lock = threading.Lock()
   _sets_cache = None  # list of (code, display_label) tuples
   ```

2. Modify `get_sets_for_dropdown()` to read from `_sets_cache`, populating it lazily on first call:
   ```python
   def get_sets_for_dropdown():
       global _sets_cache
       if _sets_cache is not None:
           return list(_sets_cache)  # return a copy
       with _sets_lock:
           if _sets_cache is not None:
               return list(_sets_cache)
           # ... existing query ...
           _sets_cache = result
           return list(result)
   ```

3. Add a public `invalidate_sets_cache()` function:
   ```python
   def invalidate_sets_cache():
       global _sets_cache
       with _sets_lock:
           _sets_cache = None
   ```

**Changes in `finder/views.py`:**

4. In `_run_update()` (the background DB update worker), call `invalidate_sets_cache()` after a successful `update_database()` so the next request picks up the new set list:
   ```python
   from .services.card_lookup import invalidate_sets_cache
   # ... after update_database() succeeds:
   invalidate_sets_cache()
   ```

### Why not Django's cache framework?

- No `CACHES` backend is configured in settings; adding one just for this is unnecessary.
- The data is small (~300 tuples), process-local memory is fine.
- The existing `oracle_patterns.py` already establishes this pattern in the codebase.

### Risks and edge cases

- **Multi-process deployments (gunicorn prefork):** Each worker gets its own cache — acceptable since the data is small and read-only. Cache miss costs one query, same as today.
- **Race on first request:** Two threads could both enter the lock — only one will execute the query; the second sees the populated cache. No correctness issue.
- **Returning a copy:** `list(_sets_cache)` prevents callers from mutating the cached list. Cheap for ~300 tuples.
- **DB update while serving:** `invalidate_sets_cache()` is called in `_run_update()` which runs on a background thread; the lock makes the reset atomic. Next request will re-query.

---

## Issue #38: Push filtering into SQL for `get_set_cards` and `get_set_lands`

### Problem

Both functions currently:
1. Fetch **all** cards from the requested sets (potentially thousands of rows).
2. Deserialize every row with `_row_to_card()` (parsing JSON/CSV columns).
3. Filter in Python: land-type check, basic-land exclusion, deduplication.

This wastes memory and CPU, especially for large sets or multi-set queries.

### Approach

Add SQL `WHERE` clauses and a `GROUP BY` to push as much filtering as possible into SQLite, reducing the number of rows returned and deserialized.

**Changes in `finder/services/card_lookup.py`:**

#### `get_set_lands()` (lines 220-297)

The current Python filtering does three things that can be moved to SQL:

| Python filter | SQL replacement |
|---------------|-----------------|
| `if 'Land' not in card.get('types', [])` | `AND (c.types LIKE '%Land%')` |
| `if 'Basic' in card.get('supertypes', [])` | `AND (c.supertypes IS NULL OR c.supertypes NOT LIKE '%Basic%')` |
| Deduplication via `seen_names` set | `GROUP BY c.name` |

Revised query structure:
```sql
SELECT c.*, ci.scryfallId
FROM cards c
LEFT JOIN cardIdentifiers ci ON c.uuid = ci.uuid
[LEFT JOIN cardLegalities ...]
WHERE c.setCode IN (...)
  AND c.language = 'English'
  AND c.types LIKE '%Land%'
  AND (c.supertypes IS NULL OR c.supertypes NOT LIKE '%Basic%')
GROUP BY c.name
```

After this, the Python loop still needs to:
- Apply color-identity intersection filtering (requires parsing `colorIdentity` per row — can't be done reliably in SQL due to CSV/JSON dual format).

Remove the now-redundant Python checks for land type, basic exclusion, and dedup.

#### `get_set_cards()` (lines 300-366)

The current Python filtering does one thing that can be moved to SQL:

| Python filter | SQL replacement |
|---------------|-----------------|
| Deduplication via `seen_names` set | `GROUP BY c.name` |

Revised query:
```sql
SELECT c.*, ci.scryfallId
FROM cards c
LEFT JOIN cardIdentifiers ci ON c.uuid = ci.uuid
[LEFT JOIN cardLegalities ...]
WHERE c.setCode IN (...)
  AND c.language = 'English'
GROUP BY c.name
```

After this, the Python loop still needs to:
- Apply color-identity subset filtering (same parsing limitation as above).

Remove the now-redundant `seen_names` dedup logic.

### Why not push color identity filtering into SQL?

The `colorIdentity` column stores data in two possible formats:
- JSON array: `["R", "W"]`
- Comma-separated string: `R, W`

The `_parse_json_col()` function handles both. Replicating this dual-format parsing in SQLite would require complex `CASE`/`LIKE` expressions that are fragile and hard to maintain. The color identity filter is applied *after* the heavier filters (land type, basic exclusion, dedup) have already reduced the row count significantly, so the marginal cost of doing it in Python is low.

### `LIKE` correctness for type/supertype matching

- `types LIKE '%Land%'` is safe because MTG type values are single words and "Land" does not appear as a substring of any other type (e.g., there is no type "Landfall" or "Homeland").
- `supertypes NOT LIKE '%Basic%'` is safe for the same reason — "Basic" is a distinct supertype with no substring collisions in the MTG type system.
- Both columns use consistent delimiters (comma-separated or JSON array), so `LIKE '%Land%'` matches both `"Land"` in JSON and `Land` or `Creature, Land` in CSV.

### Risks and edge cases

- **`GROUP BY c.name` determinism:** SQLite's `GROUP BY` with `SELECT *` returns values from an arbitrary row in the group. This is acceptable here because we only need one representative printing per card name, and the current Python dedup (`seen_names`) also keeps whichever row it sees first (arbitrary order).
- **Performance of `LIKE`:** `LIKE '%Land%'` cannot use indexes, but it operates only on rows already filtered by `setCode` and `language`, which is a small subset. The I/O savings from not transferring non-land rows dwarfs the `LIKE` cost.
- **Future format changes in MTGJSON:** If MTGJSON changes how `types`/`supertypes` are stored, the `LIKE` clauses would need updating — but so would the existing `_parse_json_col()` function, so this is not a new risk.

---

## Files to change (summary)

| File | Changes |
|------|---------|
| `finder/services/card_lookup.py` | (1) Add `_sets_lock`, `_sets_cache`, and `invalidate_sets_cache()`. (2) Modify `get_sets_for_dropdown()` to use cache. (3) Add SQL filters to `get_set_lands()`: `LIKE '%Land%'`, `NOT LIKE '%Basic%'`, `GROUP BY c.name`. (4) Add `GROUP BY c.name` to `get_set_cards()`. (5) Remove redundant Python filtering in both functions. |
| `finder/views.py` | Call `invalidate_sets_cache()` in `_run_update()` after successful DB update. |

`forms.py` requires **no changes** — it already calls `get_sets_for_dropdown()` which will transparently benefit from the cache.

---

## Out of scope / not changing

- **Django cache framework setup:** Not needed; module-level cache is simpler and consistent with the existing caching pattern in `oracle_patterns.py`.
- **Color identity SQL filtering:** Too fragile given the dual CSV/JSON format. Kept in Python.
- **Index creation on the MTGJSON database:** The DB is a third-party download replaced wholesale on updates; custom indexes would be lost on every update.
- **Caching `get_set_cards` / `get_set_lands` results:** These vary by set code, format, and color identity — the parameter space is too large for simple caching to be effective. The SQL optimization is the right approach here.

---

## Testing notes

- Existing tests in `finder/tests.py` use mock in-memory SQLite databases. The `_build_test_db()` helper creates the schema.
- After implementation, verify that:
  - `get_sets_for_dropdown()` returns the same results (and returns a fresh copy each call).
  - `invalidate_sets_cache()` causes the next call to re-query.
  - `get_set_lands()` excludes basic lands, includes only lands, and deduplicates — same output as before.
  - `get_set_cards()` deduplicates by name — same output as before.
  - Color identity filtering still works correctly for both functions.
