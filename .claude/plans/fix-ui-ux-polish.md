# UI/UX Polish Fixes

- **Branch:** `fix/ui-ux-polish`
- **Issues addressed:** #42, #44, #41

---

## Issue #42: Empty decklist shows browser tooltip instead of styled inline error

### Problem

The `decklist` field in `DecklistForm` (`finder/forms.py:25`) is a `CharField`, which is `required=True` by default. Django renders the `<textarea>` with the HTML `required` attribute. When a user clicks "Analyze Deck" with an empty textarea, the browser's native required-field validation fires **before** the JavaScript `submit` event handler (in `index.html:298`) can call `e.preventDefault()`. The result: the browser shows its own tooltip ("Please fill out this field") and the custom inline JS error (lines 311-325) never runs.

The JS already has proper empty-decklist validation (lines 311-325 of `index.html`) that creates a styled `.field-errors` div, adds the `invalid` class to the textarea, and scrolls to the error. This code is unreachable when the HTML `required` attribute is present.

### Root cause

The HTML `required` attribute on the `<textarea>` triggers browser-native validation at form submission time, which preempts the JS `submit` event handler.

### Fix

**File: `finder/forms.py`**

Add `'required': False` to the widget attrs for the `decklist` field — **or** override the field-level required via the widget by not using `required` on the widget but instead removing the HTML attribute. The cleanest approach: keep Django's server-side `required=True` (so the form still validates on POST) but suppress the HTML attribute that triggers browser-native validation.

Django doesn't have a direct way to keep `required=True` on the field while omitting the HTML attribute, but we can set `'required': False` as a widget attribute to suppress it:

```python
decklist = forms.CharField(
    widget=forms.Textarea(attrs={
        'rows': 20,
        'placeholder': '...',
    }),
    label='Decklist',
)
```

Actually, Django auto-adds `required` to the HTML because the field is required. The simplest solution: **override the widget attribute at render time**. The best approach is to add `use_required_attribute = False` to the form class or remove the attribute in `__init__`.

**Recommended approach — add one line in `DecklistForm.__init__`:**

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['set_code'].choices = get_sets_for_dropdown()
    self.fields['decklist'].widget.attrs.pop('required', None)
```

However, Django adds `required` at render time via `BoundField.build_widget_attrs`, not through `widget.attrs`. So popping from `widget.attrs` won't work.

**Correct approach — set `use_required_attribute = False` on the form:**

```python
class DecklistForm(forms.Form):
    use_required_attribute = False
    # ...
```

This tells Django not to add `required` to **any** field's HTML output. This is safe because:
- The `decklist` JS validation handles empty-field errors inline.
- The `set_code` field already has `required` removed in JS (line 101 of `index.html`).
- The `format_name` field is a `<select>` with a default value, so `required` is irrelevant.
- Server-side validation (`form.is_valid()`) still enforces all required fields.

**Files changed:**
- `finder/forms.py` — add `use_required_attribute = False` to `DecklistForm`

**No other files need changes.** The JS validation and styled error display already work correctly once the browser stops intercepting.

### Risks / edge cases

- **Users with JS disabled**: They lose client-side validation for the empty decklist field. However, Django's server-side validation still catches it and re-renders the form with `.field-errors`, so the user still sees a styled error message. No regression.
- **`set_code` field**: Already has `required` stripped in JS (`index.html:101`). Setting `use_required_attribute = False` on the form means it won't even be added in the first place. No behavioral change — just cleaner.

---

## Issue #44: "Include All Lands" toggle lacks visual active/checked state indicator

### Problem

On the analysis page (`analysis.html:61-64`), the "Include All Lands" toggle is a `<label class="lands-toggle">` wrapping a hidden checkbox. The CSS uses `:has(input:checked)` (lines 610-613, 625-627 of `styles.css`) to change the background from red-tinted to green-tinted when checked.

The `:has()` CSS pseudo-class is well-supported in modern browsers (Chrome 105+, Safari 15.4+, Firefox 121+). However, the visual change (red accent background to green accent background) is subtle — both states have similar opacity and border weight. There's no icon, no text change, and no checkmark to reinforce the toggle state.

Since the checkbox `input` itself has `display: none`, there is no native checkbox indicator visible. The entire UX depends on a subtle background color shift.

### Fix

Add a CSS pseudo-element checkmark indicator to the `.lands-toggle-label` when checked, providing a clear visual cue. Also add a JS fallback that toggles a class for browsers that don't support `:has()`.

**File: `finder/static/finder/css/styles.css`**

Add a `::before` pseudo-element on `.lands-toggle-label` that shows a checkmark when the parent label has a checked input:

```css
/* Checkmark indicator for lands toggle */
.lands-toggle-label::before {
    content: '';
    display: inline-block;
    width: 1rem;
    height: 1rem;
    border: 2px solid var(--accent);
    border-radius: 3px;
    margin-right: 0.5rem;
    vertical-align: middle;
    transition: background 0.2s, border-color 0.2s;
    flex-shrink: 0;
}

.lands-toggle:has(input:checked) .lands-toggle-label::before {
    background: var(--success);
    border-color: var(--success);
    /* Unicode checkmark via background or content won't work on ::before
       with content already set. Use a different approach: */
}
```

Actually, cleaner approach — use a **toggle switch** style or simply show a visible custom checkbox square that fills with color + checkmark:

```css
.lands-toggle-label::before {
    content: '\2610';  /* empty ballot box */
    margin-right: 0.4rem;
    font-size: 1.1rem;
}

.lands-toggle:has(input:checked) .lands-toggle-label::before {
    content: '\2611';  /* checked ballot box */
}
```

**Recommended final approach** — combine the color shift (which already exists) with a visible checkbox icon using `::before` content:

```css
.lands-toggle-label::before {
    content: '';
    display: inline-block;
    width: 1rem;
    height: 1rem;
    border: 2px solid currentColor;
    border-radius: 3px;
    margin-right: 0.5rem;
    vertical-align: text-bottom;
    position: relative;
}

.lands-toggle:has(input:checked) .lands-toggle-label::before {
    content: '\2713';  /* checkmark */
    background: var(--success);
    border-color: var(--success);
    color: white;
    font-size: 0.75rem;
    line-height: 1rem;
    text-align: center;
    font-weight: 700;
}
```

**File: `finder/templates/finder/analysis.html`**

Add a JS fallback for `:has()` — toggle a class on the label when the checkbox changes:

```javascript
// Lands toggle fallback for browsers without :has() support
(function() {
    var toggle = document.querySelector('.lands-toggle input[type="checkbox"]');
    if (!toggle) return;
    var label = toggle.closest('.lands-toggle');
    function sync() {
        label.classList.toggle('lands-toggle-checked', toggle.checked);
    }
    toggle.addEventListener('change', sync);
    sync(); // initial state
})();
```

Then add CSS rules using the fallback class alongside `:has()`:

```css
.lands-toggle:has(input:checked),
.lands-toggle.lands-toggle-checked {
    background: rgba(76, 175, 80, 0.15);
    border-color: var(--success);
}

.lands-toggle:has(input:checked) .lands-toggle-label,
.lands-toggle.lands-toggle-checked .lands-toggle-label {
    color: #81c784;
}

.lands-toggle:has(input:checked) .lands-toggle-label::before,
.lands-toggle.lands-toggle-checked .lands-toggle-label::before {
    content: '\2713';
    background: var(--success);
    border-color: var(--success);
    color: white;
    font-size: 0.75rem;
    line-height: 1rem;
    text-align: center;
    font-weight: 700;
}
```

**Files changed:**
- `finder/static/finder/css/styles.css` — add `::before` pseudo-element checkbox indicator to `.lands-toggle-label`, duplicate `:has()` rules with `.lands-toggle-checked` fallback class
- `finder/templates/finder/analysis.html` — add JS fallback that toggles `.lands-toggle-checked` class on checkbox change

### Risks / edge cases

- **`:has()` browser support**: The JS fallback class handles older browsers. Both selectors are combined with commas so either path triggers the same styles.
- **Existing checked restoration**: The `{% if include_lands %}` block (line 153-155 of `analysis.html`) already sets `checked = true` on the checkbox. The JS fallback's `sync()` call on init will apply the class for restored state.
- **Mobile**: The `::before` pseudo-element may need slight sizing adjustment on mobile. The existing `@media (max-width: 768px)` block already adjusts `.select-controls .lands-toggle`. Test to confirm the `::before` looks good on small screens.

---

## Issue #41: Duplicate tag display names on result cards

### Problem

In `results.html:169-173`, each card's matched tags are rendered with `{{ tag|tag_display }}`. The `tag_display` filter (`card_extras.py:34`) strips the category prefix: `Subtype:Equipment` and `Oracle Pattern:Equipment` both become `Equipment`. When a card matches both tags, two identical "Equipment" pills appear on the card.

The `data-tags` attribute (line 157) stores the full qualified tags (`Subtype:Equipment,Oracle Pattern:Equipment`) for filtering purposes, and the filter bar needs these distinct values. So deduplication should only affect the **display** in the card's tag pills, not the underlying data.

### Fix

Create a new custom template filter `unique_tag_displays` that takes the list of matched tags, applies the `tag_display` logic (strip prefix), and returns a deduplicated list preserving order.

**File: `finder/templatetags/card_extras.py`**

Add a new filter:

```python
@register.filter
def unique_tag_displays(tags):
    """Deduplicate tags by their display name (prefix stripped).

    Given ['Subtype:Equipment', 'Oracle Pattern:Equipment', 'Subtype:Aura'],
    returns ['Equipment', 'Aura'].
    """
    seen = set()
    result = []
    for tag in tags:
        display = tag.split(':', 1)[1] if ':' in tag else tag
        if display not in seen:
            seen.add(display)
            result.append(display)
    return result
```

**File: `finder/templates/finder/results.html`**

Change the card matched tags loop from:

```html
<div class="card-matched-tags">
    {% for tag in matched_tags %}
    <span class="tag tag-small">{{ tag|tag_display }}</span>
    {% endfor %}
</div>
```

To:

```html
<div class="card-matched-tags">
    {% for display_name in matched_tags|unique_tag_displays %}
    <span class="tag tag-small">{{ display_name }}</span>
    {% endfor %}
</div>
```

**Files changed:**
- `finder/templatetags/card_extras.py` — add `unique_tag_displays` filter
- `finder/templates/finder/results.html` — use `unique_tag_displays` filter in the card tag loop

### Risks / edge cases

- **Ordering**: `unique_tag_displays` preserves the order of first occurrence, which matches the existing display order (tags come sorted by relevance from the view).
- **Filter bar still works**: The `data-tags` attribute on the `<a>` element (line 157) still contains the full qualified tags (`matched_tags|join:','`), so filtering by tag in the JS filter bar is unaffected.
- **"Selected tags" summary**: The `selected-tags-summary` section (lines 31-38) shows the user's selected theme tags (not per-card matched tags). These come from `selected_tags` which are the qualified tag names, and each is displayed with `tag|tag_display`. Duplicates here are unlikely (user selects distinct tags) but theoretically possible if different categories had the same name. This is a separate concern and not in scope for this fix.
- **The `tag_display` filter on its own is not removed** — it's still used in the selected tags summary and filter bar buttons. Only the per-card display loop changes.

---

## Summary of all file changes

| File | Changes |
|------|---------|
| `finder/forms.py` | Add `use_required_attribute = False` to `DecklistForm` |
| `finder/static/finder/css/styles.css` | Add `::before` checkbox indicator on `.lands-toggle-label`; add `.lands-toggle-checked` fallback class rules |
| `finder/templates/finder/analysis.html` | Add JS fallback for lands toggle `:has()` support |
| `finder/templatetags/card_extras.py` | Add `unique_tag_displays` template filter |
| `finder/templates/finder/results.html` | Use `unique_tag_displays` filter in card tag display loop |

## Issues to skip

None — all three issues are feasible and well-scoped.
