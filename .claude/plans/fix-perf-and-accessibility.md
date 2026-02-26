# Implementation Plan: Performance & Accessibility Fixes

**Branch:** `fix/perf-and-accessibility`
**Issues:** #31 (slow `get_random_flavor_text`), #33 (set picker keyboard navigation)

---

## Issue #31: Optimize `get_random_flavor_text`

### Problem

`finder/services/card_lookup.py:20-40` runs two queries on every loading screen request:

1. `SELECT COUNT(*) FROM cards c WHERE ...` — full scan of filtered rows
2. `SELECT ... FROM cards c WHERE ... LIMIT 1 OFFSET ?` — scans up to ~54K rows to reach the offset

This is called via AJAX on every page transition (index→analyze, analyze→results).

### Solution: Single query using `ORDER BY RANDOM() LIMIT 1`

Replace the two-query COUNT + OFFSET approach with:

```python
def get_random_flavor_text():
    """Return a random card name + flavor text from the database."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT c.name, c.flavorText
            FROM cards c
            WHERE c.language = 'English'
              AND c.flavorText IS NOT NULL
              AND c.flavorText != ''
            ORDER BY RANDOM()
            LIMIT 1
        """).fetchone()
    if row:
        return {'name': row['name'], 'flavorText': row['flavorText']}
    return None
```

### Why `ORDER BY RANDOM()` and not `rowid`-based

The issue suggests a `rowid >= ABS(RANDOM()) % MAX(rowid)` approach for O(1) performance. However:

- **Gap bias:** If rowids have gaps (from deletions or filtered rows), the distribution is skewed — rows immediately after large gaps are disproportionately selected.
- **Filter interaction:** The WHERE clause filters for English cards with non-null flavor text, which is a subset of all rows. A rowid-based approach would need a fallback query when the random rowid lands on a filtered-out row, adding complexity.
- **`ORDER BY RANDOM() LIMIT 1` is sufficient:** It does a single full scan (~108K rows) instead of two scans. For an AJAX call on a loading screen that already has an 800ms minimum delay, this is fast enough. SQLite can scan 108K rows in well under 100ms on any modern hardware.

### File changes

**`finder/services/card_lookup.py`** (lines 20-40):
- Replace the entire `get_random_flavor_text()` function body
- Remove the `filter_clause` string variable, `count` query, `offset` calculation, and `OFFSET` query
- Replace with a single `ORDER BY RANDOM() LIMIT 1` query

### Risks and edge cases

- **Empty database:** The `if row:` guard handles this — returns `None` just like before.
- **Performance regression risk:** None. Single scan is strictly fewer operations than COUNT + OFFSET scan.
- **Existing tests:** `finder/tests.py` does not test `get_random_flavor_text` directly, so no test changes needed. The function signature and return format are unchanged.

---

## Issue #33: Set Picker Keyboard Navigation

### Problem

The custom set picker dropdown (`finder/templates/finder/index.html:91-187`) only responds to mouse clicks. Arrow keys don't navigate items, Enter doesn't select items, and there are no ARIA attributes for assistive technology. This is a WCAG 2.1 Level A violation (2.1.1 Keyboard).

### Solution: Add keyboard navigation and ARIA attributes

#### HTML changes (in the template, lines 30-33)

Add ARIA attributes to the set picker markup:

```html
<div class="set-picker">
    <input type="text" class="set-search" placeholder="Search sets..."
           autocomplete="off"
           role="combobox"
           aria-expanded="false"
           aria-controls="set-dropdown-listbox"
           aria-autocomplete="list"
           aria-activedescendant="">
    <div class="set-dropdown" id="set-dropdown-listbox" role="listbox"></div>
</div>
```

#### JavaScript changes (lines 93-187)

1. **Track active index:** Add an `activeIndex` variable (`-1` = no selection).

2. **Update `renderDropdown()`** to:
   - Generate items with `role="option"`, unique `id` attributes (e.g., `set-option-0`, `set-option-1`, ...), and `aria-selected` attribute.
   - Apply an `.active` class to the item at `activeIndex`.
   - Update `aria-expanded` on the search input.
   - Update `aria-activedescendant` on the search input to point to the active item's id.
   - Reset `activeIndex` to `-1` when the dropdown re-renders (new filter results).

3. **Add `keydown` handler on `searchInput`** for:
   - **ArrowDown:** Increment `activeIndex` (clamped to last item), update active styling and `aria-activedescendant`. Prevent default to avoid cursor movement. If dropdown is closed, open it.
   - **ArrowUp:** Decrement `activeIndex` (clamped to `-1`), update active styling and `aria-activedescendant`. Prevent default.
   - **Enter:** If `activeIndex >= 0`, select the active item (call `selectSet` with its value). Prevent default to avoid form submission. If `activeIndex === -1` and dropdown is open with items, select the first item.
   - **Escape:** Already handled globally — closes dropdown. (Keep existing behavior.)

4. **Update `selectSet()`** to:
   - Reset `activeIndex` to `-1`.
   - Set `aria-expanded="false"` on input.
   - Clear `aria-activedescendant`.
   - Keep focus on `searchInput` (already the case since we don't blur).

5. **Update the close-on-outside-click handler** to also set `aria-expanded="false"`.

6. **Update the existing Escape handler** to also set `aria-expanded="false"` and clear `aria-activedescendant`.

#### CSS changes (`finder/static/finder/css/styles.css`)

Add a style for the active/highlighted dropdown item:

```css
.set-dropdown-item.active {
    background: rgba(233, 69, 96, 0.12);
    color: var(--accent-hover);
}
```

This reuses the same visual treatment as the existing `:hover` style, so keyboard-highlighted and mouse-hovered items look identical.

### File changes

**`finder/templates/finder/index.html`:**
- Lines 30-33: Add ARIA attributes to the `<input>` and `.set-dropdown` div
- Lines 93-183: Rewrite the set picker IIFE JavaScript to add:
  - `activeIndex` state variable
  - Updated `renderDropdown()` with ARIA attributes on items
  - `keydown` event listener on `searchInput` for ArrowDown, ArrowUp, Enter
  - Updated `selectSet()` to reset ARIA state
  - Updated close handlers to sync `aria-expanded`

**`finder/static/finder/css/styles.css`:**
- Add `.set-dropdown-item.active` rule (after the existing `.set-dropdown-item:hover` rule, ~line 310)

### Keyboard interaction summary

| Key | Dropdown closed | Dropdown open |
|-----|----------------|---------------|
| ArrowDown | Opens dropdown, highlights first item | Moves highlight down |
| ArrowUp | No action | Moves highlight up (stops at top) |
| Enter | Normal form behavior | Selects highlighted item (or first if none highlighted) |
| Escape | No action | Closes dropdown, blurs input |
| Any character | Opens dropdown with filtered results | Filters results, resets highlight |

### Risks and edge cases

- **Enter with no dropdown open:** Must not interfere with normal form submission. Only intercept Enter when dropdown is open and has items.
- **Empty dropdown:** If filter produces no matches, ArrowDown/Enter should be no-ops (dropdown is closed when empty, per existing `renderDropdown` logic).
- **Scroll into view:** If the dropdown has many items, the active item should be scrolled into view. Use `element.scrollIntoView({ block: 'nearest' })` when updating the active index.
- **Pre-selected values on re-render:** The existing `renderChips()` call at the end handles this; no changes needed.
- **Mouse and keyboard interaction:** If the user hovers with mouse after using arrow keys, the hover CSS applies independently. The `.active` class from keyboard and `:hover` from mouse can coexist without conflict.

---

## Files Changed Summary

| File | Change |
|------|--------|
| `finder/services/card_lookup.py` | Replace `get_random_flavor_text()` with single `ORDER BY RANDOM()` query |
| `finder/templates/finder/index.html` | Add ARIA attributes to set picker HTML; add keyboard navigation JS |
| `finder/static/finder/css/styles.css` | Add `.set-dropdown-item.active` style |

## Testing Strategy

- **Manual:** Verify flavor text still loads on the loading overlay. Test keyboard navigation: Tab to search input, type to filter, ArrowDown/Up to navigate, Enter to select, Escape to close. Verify chips appear. Verify form still submits normally when dropdown is closed.
- **Accessibility:** Test with a screen reader to verify ARIA roles are announced correctly (combobox, listbox, option).
