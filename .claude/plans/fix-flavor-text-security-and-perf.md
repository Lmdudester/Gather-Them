# Plan: Fix Flavor Text XSS and Slow Random Query

**Branch:** `fix/flavor-text-security-and-perf`
**Issues:** #23 (XSS via innerHTML), #24 (slow ORDER BY RANDOM() query)

---

## Issue #23: XSS via innerHTML with unsanitized flavor text

### Problem

Both `index.html` (line 259) and `analysis.html` (line 491) use `innerHTML` to
insert flavor text received from the `/api/random-flavor/` JSON endpoint:

```js
el.innerHTML = '\u201C' + data.flavorText + '\u201D'
    + '<span class="flavor-source">\u2014 ' + data.name + '</span>';
```

The `data.flavorText` and `data.name` values come from the MTGJSON database and
are inserted without sanitization. If the database ever contains HTML or script
content (e.g. `<img onerror=alert(1)>`), it would execute as arbitrary JS in the
user's browser.

### Fix

Replace the `innerHTML` assignment with safe DOM manipulation using
`textContent` for user data and `createElement` for the HTML structure.

### Files to change

#### 1. `finder/templates/finder/index.html` (lines 257-260)

Replace:
```js
var el = document.getElementById('loading-flavor');
el.innerHTML = '\u201C' + data.flavorText + '\u201D'
    + '<span class="flavor-source">\u2014 ' + data.name + '</span>';
```

With:
```js
var el = document.getElementById('loading-flavor');
el.textContent = '\u201C' + data.flavorText + '\u201D';
var source = document.createElement('span');
source.className = 'flavor-source';
source.textContent = '\u2014 ' + data.name;
el.appendChild(source);
```

#### 2. `finder/templates/finder/analysis.html` (lines 489-492)

Apply the identical change (same code pattern, same loading overlay).

Replace:
```js
var el = document.getElementById('loading-flavor');
el.innerHTML = '\u201C' + data.flavorText + '\u201D'
    + '<span class="flavor-source">\u2014 ' + data.name + '</span>';
```

With:
```js
var el = document.getElementById('loading-flavor');
el.textContent = '\u201C' + data.flavorText + '\u201D';
var source = document.createElement('span');
source.className = 'flavor-source';
source.textContent = '\u2014 ' + data.name;
el.appendChild(source);
```

---

## Issue #24: Slow random flavor text query

### Problem

`card_lookup.py:19-33` (`get_random_flavor_text`) runs:

```sql
SELECT c.name, c.flavorText
FROM cards c
WHERE c.language = 'English'
  AND c.flavorText IS NOT NULL
  AND c.flavorText != ''
ORDER BY RANDOM()
LIMIT 1
```

`ORDER BY RANDOM() LIMIT 1` forces SQLite to assign a random value to every
matching row (~108K+ rows), sort them all, then return one. This is O(n log n)
and runs on every page transition (the loading overlay fetches a new flavor text
each time the form is submitted).

### Fix

Use a two-query approach with `COUNT` + random `OFFSET`:

1. First query: `SELECT COUNT(*) FROM cards WHERE ...` (same filter)
2. Pick a random offset in Python: `random.randint(0, count - 1)`
3. Second query: `SELECT ... FROM cards WHERE ... LIMIT 1 OFFSET ?`

This avoids the sort entirely. SQLite's `OFFSET` still scans rows sequentially
(O(n) worst case), but for a single random row it's far cheaper than sorting
the entire result set. Two simple queries with no sort operation will be
substantially faster than one `ORDER BY RANDOM()` query.

**Why not random rowid?** The MTGJSON `cards` table uses `uuid TEXT PRIMARY KEY`,
so rowids are not guaranteed to be contiguous. A random rowid approach would
require knowing the rowid range and handling gaps, adding complexity for minimal
benefit over the `COUNT`/`OFFSET` approach.

### Files to change

#### 1. `finder/services/card_lookup.py` (lines 19-34)

Replace `get_random_flavor_text()`:

```python
def get_random_flavor_text():
    """Return a random card name + flavor text from the database."""
    import random

    filter_clause = """
        WHERE c.language = 'English'
          AND c.flavorText IS NOT NULL
          AND c.flavorText != ''
    """
    with get_db() as conn:
        count = conn.execute(
            f"SELECT COUNT(*) FROM cards c {filter_clause}"
        ).fetchone()[0]
        if count == 0:
            return None
        offset = random.randint(0, count - 1)
        row = conn.execute(
            f"SELECT c.name, c.flavorText FROM cards c {filter_clause} LIMIT 1 OFFSET ?",
            (offset,),
        ).fetchone()
    if row:
        return {'name': row['name'], 'flavorText': row['flavorText']}
    return None
```

The `import random` is moved to the top of the function (or to the module-level
imports) -- module-level is preferred for cleanliness.

---

## Summary of all file changes

| File | Change | Issue |
|------|--------|-------|
| `finder/templates/finder/index.html` | Replace `innerHTML` with `textContent` + `createElement` | #23 |
| `finder/templates/finder/analysis.html` | Replace `innerHTML` with `textContent` + `createElement` | #23 |
| `finder/services/card_lookup.py` | Replace `ORDER BY RANDOM()` with `COUNT` + random `OFFSET` | #24 |

## Risks and considerations

- **Correctness of OFFSET approach:** The `OFFSET` approach returns a uniformly
  random row from the filtered result set, same as `ORDER BY RANDOM()`. The
  two-query pattern is not atomic, but since the cards table is read-only during
  normal operation (only updated via the admin "Update Database" action which
  sets maintenance mode), there's no race condition risk in practice.

- **Visual regression from textContent:** The `textContent` approach produces
  identical visible output to `innerHTML` for normal text. The only difference
  is that any HTML in the database would render as literal text (angle brackets
  visible) instead of being interpreted -- which is the desired security behavior.
  MTG flavor text is plain text by nature, so this should cause no visual change.

- **No issues skipped:** Both issues are straightforward and low-risk. Both will
  be addressed in this branch.
