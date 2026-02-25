# Plan: Fix Loading Overlay UX

**Branch:** `fix/loading-overlay-ux`
**Issues:** #25, #26

---

## Issue #25: Remove unnecessary 3-second minimum delay on form submissions

### Problem

Both `index.html` (line 240) and `analysis.html` (line 472) enforce a 3-second minimum delay before form submission via:

```js
var minDelay = new Promise(function(r) { setTimeout(r, 3000); });
Promise.all([flavorDone, minDelay]).then(doSubmit);
```

The flavor text fetch (`/api/random-flavor/`) is a simple DB lookup that returns nearly instantly (~50ms). The `minDelay` forces users to stare at the loading overlay for 3 full seconds even when the flavor text has already loaded. The actual server processing (deck analysis, card matching) happens *after* the form submits — so the overlay is pure wait-for-nothing time.

### Fix

**Replace the 3-second `minDelay` with a short 800ms delay** — just enough for the flavor text to render and be readable before the page navigates away. This preserves the "flavor text moment" without artificially blocking the user.

Why 800ms instead of 0: The overlay fetches a random flavor text quote and displays it. With zero delay, on fast connections the flavor text would flash for a fraction of a second before navigation. 800ms gives the user just enough time to see it, while being significantly faster than 3s. The 6-second fallback timeout is also reduced to 4s proportionally.

### Files to change

#### `finder/templates/finder/index.html`
- **Line 240:** Change `setTimeout(r, 3000)` → `setTimeout(r, 800)`
- **Line 268:** Change fallback `setTimeout(doSubmit, 6000)` → `setTimeout(doSubmit, 4000)`

#### `finder/templates/finder/analysis.html`
- **Line 472:** Change `setTimeout(r, 3000)` → `setTimeout(r, 800)`
- **Line 497:** Change fallback `setTimeout(doSubmit, 6000)` → `setTimeout(doSubmit, 4000)`

---

## Issue #26: Add client-side pre-validation before showing the overlay

### Problem

When a user submits an invalid decklist on the index page (e.g., empty textarea, or text that doesn't parse into any valid card entries), the loading overlay still appears and they wait through the delay + flavor text fetch — only to land on the same page with a validation error. The overlay masks the fact that nothing useful is happening.

The root cause is that the `submit` event handler in `index.html` calls `e.preventDefault()`, which bypasses the browser's native HTML5 `required` attribute validation. It then shows the overlay and eventually calls `form.submit()` programmatically (which also skips HTML5 validation).

### Current client-side validation

| Page | What's already validated client-side |
|------|--------------------------------------|
| `index.html` | At least one set selected (lines 228-233) |
| `analysis.html` | At least one theme or "Include Lands" checked (lines 448-462) |

### Missing client-side validation (index.html only)

The decklist `<textarea>` has no JS validation. Server-side, two checks can fail:
1. **`form.is_valid()`** — Django's `required` check on the `decklist` CharField (empty/whitespace textarea)
2. **`parse_decklist()` returns empty** — textarea has content but no parseable card lines (e.g., just "hello world")

Only check #1 (empty/whitespace) is worth replicating client-side. Check #2 (unparseable content) is rare and would require duplicating the Python parsing regex in JavaScript, which adds complexity for minimal benefit. Users who type gibberish into the decklist field are a small edge case — letting them hit the server is acceptable.

### Fix

**Add a decklist-not-empty check to the `index.html` submit handler**, before the overlay is shown. This mirrors the server-side `required` validation. If the textarea is empty or whitespace-only, show the existing error UI pattern inline and don't show the overlay.

The `analysis.html` page does **not** need this fix — it has no free-text user input that could fail validation. All its inputs are hidden fields pre-populated from the previous step and checkboxes. Its existing client-side check (at least one theme selected) is sufficient.

### Files to change

#### `finder/templates/finder/index.html`

In the submit handler (inside the `(function () { ... })()` IIFE starting at line 218), add a decklist validation check **before** the overlay is shown (before line 236). Specifically, insert after the set-code validation block (after line 233):

```js
// Validate that decklist is not empty
var decklistField = document.getElementById('id_decklist');
var decklistError = decklistField.closest('.form-group').querySelector('.field-errors');
if (!decklistField.value.trim()) {
    // Show error using same pattern as server-rendered errors
    if (!decklistError) {
        decklistError = document.createElement('div');
        decklistError.className = 'field-errors';
        decklistField.closest('.form-group').appendChild(decklistError);
    }
    decklistError.innerHTML = '<p>This field is required.</p>';
    decklistError.style.display = '';
    decklistField.classList.add('invalid');
    return;
}
```

This uses the same `.field-errors` CSS class and `.invalid` input styling that the server-side validation errors already use (visible in lines 18-24 and the error-class IIFE at lines 190-214), so it will look consistent.

---

## Summary of all changes

| File | Change | Issue |
|------|--------|-------|
| `finder/templates/finder/index.html:240` | `setTimeout(r, 3000)` → `setTimeout(r, 800)` | #25 |
| `finder/templates/finder/index.html:268` | `setTimeout(doSubmit, 6000)` → `setTimeout(doSubmit, 4000)` | #25 |
| `finder/templates/finder/index.html:223-233` | Add decklist-not-empty validation before overlay shows | #26 |
| `finder/templates/finder/analysis.html:472` | `setTimeout(r, 3000)` → `setTimeout(r, 800)` | #25 |
| `finder/templates/finder/analysis.html:497` | `setTimeout(doSubmit, 6000)` → `setTimeout(doSubmit, 4000)` | #25 |

**No changes needed to:** `views.py`, `forms.py`, `urls.py`, `base.html`, or any CSS/static files.

---

## Risks and considerations

1. **Flavor text readability at 800ms:** On slow connections, the flavor text fetch may not complete in 800ms. This is fine — the `Promise.all` still waits for both the fetch *and* the delay, so on slow connections the fetch time dominates and the user sees the flavor text for however long the fetch takes. The 800ms is just a *minimum*, not a maximum.

2. **Client-side validation message wording:** Using "This field is required." matches Django's default required-field error message, ensuring consistency if the user somehow bypasses JS and hits the server-side check.

3. **No parse validation client-side:** Intentionally not replicating the `parse_decklist` regex in JavaScript. The cost (code duplication, maintenance burden, regex divergence risk) outweighs the benefit (catching the rare user who pastes non-card text). The server-side check remains as the backstop, and now the overlay delay is only 800ms instead of 3s, so the wait is minimal.

4. **analysis.html already has sufficient validation:** The analysis page's form only contains hidden fields (pre-populated from the prior step) and checkboxes. The existing JS check for "at least one theme or lands" is the only validation needed. No overlay-masking issue exists here.
