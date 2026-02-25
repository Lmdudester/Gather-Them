# Plan: Fix Results Filters and Add Sorting

**Branch:** `fix/results-filters-and-sorting`
**Issues addressed:** #13 (AND filter bug), #9 (Add sort options)

---

## Issue #13: AND filter mode produces impossible matches for single-value attributes

### Problem

In `finder/templates/finder/results.html`, the `filterCards()` JavaScript function applies AND logic to single-value attributes (rarity, mana value, power, toughness). A card can only have ONE value for these attributes, so requiring a card to match ALL selected values (AND) always yields zero results when 2+ values are selected.

**Buggy code pattern (lines 371-376 and similar):**
```js
if (isAnd) {
    categoryMatch = [...values].every(v => v === item.dataset.rarity);
}
```

### Fix approach: Hide AND/OR toggle for single-value categories

The AND toggle is meaningless for single-value attributes — there is no scenario where AND makes sense. The cleanest fix is to **remove the AND/OR toggle entirely** for rarity, mv, power, and toughness, and always use OR logic for those categories.

This approach (option 1 from the issue) is preferred over silently falling back to OR (option 2) because it avoids user confusion — showing an AND toggle that doesn't actually do AND would be misleading.

### Changes

#### 1. `finder/templates/finder/results.html` — Remove AND/OR toggle for single-value filter sections

**Lines 67-80 (rarity section):** Remove the `<label class="filter-mode-toggle" ...>` element from the rarity filter section. Repeat for:
- **Lines 82-95** (mv section)
- **Lines 97-110** (power section)
- **Lines 112-125** (toughness section)

Keep the toggle for **types** (multi-value: a card can be "Creature,Artifact") and **tags** (multi-value: a card matches multiple tags).

**Lines 352-416 (filterCards function):** Simplify the rarity/mv/power/toughness branches to always use OR logic (remove the `if (isAnd)` branch for these categories). The simplified code for each single-value category becomes:
```js
} else if (category === 'rarity') {
    categoryMatch = values.has(item.dataset.rarity);
} else if (category === 'mv') {
    categoryMatch = values.has(item.dataset.mv);
} else if (category === 'power') {
    categoryMatch = values.has(item.dataset.power);
} else if (category === 'toughness') {
    categoryMatch = values.has(item.dataset.toughness);
}
```

**`updateActiveSummary()` function (lines 328-350):** The summary display reads `filterModes[category]` to decide whether to show "AND" or "OR" badge. Since these categories will never have AND mode, the existing code will naturally default to OR display (since `filterModes[category]` will be undefined/falsy). No changes needed here.

---

## Issue #9: Add sort options to results page

### Problem

Cards are sorted by match count (relevance) descending server-side with no way for users to re-sort.

### Fix approach: Client-side sort controls above card grid

Add a sort dropdown/button group between the filter bar and the card grid. Sort options: Relevance (default), Name (A-Z), Mana Value (low-high), Rarity (mythic-common). Sorting reorders DOM elements client-side using the existing `data-*` attributes.

### Changes

#### 1. `finder/templates/finder/results.html` — Add `data-match-count` to card items

**Line 153-162 (card-item anchor):** Add a `data-match-count="{{ match_count }}"` attribute so the JS can sort by relevance without parsing DOM text content.

```html
<a class="card-item"
   ...
   data-match-count="{{ match_count }}"
   data-tags="{{ matched_tags|join:',' }}">
```

#### 2. `finder/templates/finder/results.html` — Add sort controls HTML

**Line 151 (before `<div class="card-grid">`):** Insert sort control markup:

```html
<div class="sort-bar">
    <span class="sort-label">Sort by</span>
    <div class="sort-options">
        <button type="button" class="sort-btn active" data-sort="relevance">Relevance</button>
        <button type="button" class="sort-btn" data-sort="name">Name</button>
        <button type="button" class="sort-btn" data-sort="mv">Mana Value</button>
        <button type="button" class="sort-btn" data-sort="rarity">Rarity</button>
    </div>
</div>
```

The sort bar is placed inside the `{% if results %}` block so it only renders when there are results.

#### 3. `finder/templates/finder/results.html` — Add sort JavaScript

Add in the `<script>` block (after the filter IIFE or inside it):

- Query all `.sort-btn` elements
- On click, set `active` class, read `data-sort` value
- Get all `.card-item` elements, convert to array, sort using a compare function:
  - **relevance:** `data-match-count` descending, then card name ascending
  - **name:** `.card-name` textContent ascending (locale-aware)
  - **mv:** `data-mv` ascending numerically (`7+` → 7), then name
  - **rarity:** map rarity to numeric rank (mythic=4, rare=3, uncommon=2, common=1), sort descending, then name
- Re-append sorted elements to `.card-grid` (DOM reorder, no cloning)

**Key implementation detail:** The sort function must respect the current filter state — hidden cards (`display: none`) should remain in-place but maintain their relative sort order so they appear correctly if filters change. Simplest approach: sort ALL card items (hidden and visible) and re-append them all. Filter state is preserved via inline `display` style.

#### 4. `finder/static/finder/css/styles.css` — Add sort bar styles

Add new CSS after the filter bar styles (around line 912, before "Card Grid" section):

```css
/* === Sort Bar === */
.sort-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
}

.sort-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.sort-options {
    display: flex;
    gap: 0.3rem;
}

.sort-btn {
    display: inline-block;
    padding: 0.25rem 0.6rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    font-size: 0.78rem;
    color: var(--text-muted);
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s, color 0.2s;
    font-family: inherit;
}

.sort-btn:hover {
    border-color: var(--accent);
    color: var(--text);
    background: rgba(233, 69, 96, 0.08);
}

.sort-btn.active {
    background: rgba(233, 69, 96, 0.15);
    border-color: var(--accent);
    color: var(--accent-hover);
}
```

These styles intentionally mirror the `.filter-btn` styles for visual consistency.

#### 5. Mobile responsiveness

In the `@media (max-width: 768px)` block, add:
```css
.sort-bar { flex-wrap: wrap; }
.sort-btn { padding: 0.4rem 0.7rem; font-size: 0.82rem; }
```

This mirrors the existing mobile filter button overrides.

---

## Files Changed (Summary)

| File | Changes |
|------|---------|
| `finder/templates/finder/results.html` | Remove AND toggle from 4 single-value filter sections; simplify filterCards() for those categories; add `data-match-count` attribute; add sort bar HTML; add sort JS |
| `finder/static/finder/css/styles.css` | Add `.sort-bar`, `.sort-label`, `.sort-options`, `.sort-btn` styles + mobile overrides |

No backend (views.py) changes needed. Both fixes are purely client-side.

---

## Risks and Considerations

1. **DOM reorder performance:** Re-appending ~100-300 card elements is fast. No virtual DOM or optimization needed for these volumes.
2. **Sort + Filter interaction:** Sorting re-appends all elements (including hidden ones). Filter state is preserved via inline `display` style, which is unaffected by DOM reorder. After sorting, a re-filter is NOT needed.
3. **No new dependencies:** All changes are vanilla JS/CSS.
4. **Backward compatibility:** Removing the AND toggle changes UI behavior, but the old AND behavior for single-value attributes was broken (always showed 0 results), so this is strictly an improvement.
