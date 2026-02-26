# Fix Form Submission State

**Branch:** `fix/form-submission-state`

**Issues addressed:**
- #32 — Form becomes unsubmittable after browser back navigation (bfcache)
- #34 — Loading overlay Cancel button does not fully reset state for re-submission
- #35 — Decklist validation error message is not visible without scrolling on long decklists

---

## Files to Change

1. `finder/templates/finder/index.html`
2. `finder/templates/finder/analysis.html`

---

## Approach: Generation Counter (Issues #32 + #34)

Both `index.html` and `analysis.html` share the same loading-overlay submission pattern. The current code uses two boolean flags (`submitting` and `cancelled`) inside a closure, which creates two problems:

1. **bfcache (#32):** `submitting` is set to `true` on submit and never reset on `pageshow`, permanently blocking re-submission.
2. **Cancel race (#34):** After cancel, `cancelled = true` guards the old `doSubmit`, but a new submission resets `cancelled = false` at the outer scope, allowing stale callbacks from the previous attempt to fire.

**Solution: Replace both booleans with a single `submitGeneration` counter.**

Each submit increments the counter and captures its value as `myGen`. Each cancel also increments the counter. Stale callbacks compare their captured `myGen` against the current counter and silently bail out if they don't match. This eliminates both bugs with a single mechanism.

### Refactored pattern (applies to both files)

```js
// Loading overlay on form submit
(function () {
    var form = document.querySelector('.deck-form');  // or '.theme-form'
    var submitGeneration = 0;

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        // --- validation (unchanged) ---

        var myGen = ++submitGeneration;

        var overlay = document.getElementById('loading-overlay');
        var cancelBtn = document.getElementById('loading-cancel');
        overlay.classList.add('active');

        var minDelay = new Promise(function (r) { setTimeout(r, 800); });

        function doSubmit() {
            if (myGen !== submitGeneration) return;  // stale — cancelled or superseded
            submitGeneration++;  // prevent any other callback from also firing
            form.submit();
        }

        function handleCancel() {
            if (myGen !== submitGeneration) return;  // already stale
            submitGeneration++;  // invalidate this generation's callbacks
            overlay.classList.remove('active');
        }

        cancelBtn.addEventListener('click', handleCancel, { once: true });

        var flavorDone = fetch(/* url */)
            .then(/* flavor text logic */)
            .catch(function () {});

        Promise.all([flavorDone, minDelay]).then(doSubmit);
        setTimeout(doSubmit, 4000);
    });
})();
```

**Key behavioral changes:**
- `e.preventDefault()` is now always called (no early `if (submitting) return` that skips `preventDefault`). The guard is the generation check inside `doSubmit`.
- Cancel increments the generation, so *all* pending callbacks from that submission (both the `Promise.all` and the `setTimeout`) are invalidated.
- After `form.submit()` fires, the generation is incremented so the redundant fallback `setTimeout` callback is also invalidated.
- No `submitting` boolean exists to get stuck — the `pageshow` handler no longer needs any JS-level reset.

### `pageshow` handler update

The `pageshow` handler only needs to hide the overlay (already does). Since there is no `submitting` flag, bfcache restoration automatically leaves the form in a submittable state.

However, we should also reset the overlay flavor text back to the default on bfcache restore, so a stale flavor quote doesn't flash if the user submits again:

```js
window.addEventListener('pageshow', function (e) {
    if (e.persisted) {
        document.getElementById('loading-overlay').classList.remove('active');
        document.getElementById('loading-flavor').textContent = 'Gathering cards...';
    }
});
```

### Scope change for `index.html`

Currently the `pageshow` handler is **outside** the IIFE where `submitting` lives (line 292 vs. the IIFE on line 218). With the generation-counter approach, the `pageshow` handler no longer needs access to any submission state, so it can stay outside the IIFE. No scope restructuring is needed.

### Scope for `analysis.html`

Same situation — `pageshow` handler at line 505 is outside the IIFE at line 439. No scope change needed.

---

## Approach: Scroll to Error (Issue #35)

When the server returns a validation error on the decklist field, the error `<div class="field-errors">` is rendered below the 20-row textarea and may be off-screen.

**Solution:** Add a small script block that runs on page load, finds the first `.field-errors` element inside `.deck-form`, and scrolls it into view.

### Implementation in `index.html`

Add to the existing "invalid class" IIFE (lines 190-215) which already iterates over `.field-errors` elements:

```js
// Scroll to first validation error if present (server-rendered errors after POST)
var firstError = document.querySelector('.deck-form .field-errors');
if (firstError) {
    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
```

This runs on initial page load only (not dynamically on JS validation), which is exactly when server-side errors appear. The `block: 'center'` option positions the error message in the center of the viewport rather than at the edge, giving the user context.

**Note:** The client-side JS validation errors (empty decklist, no set selected) don't need this treatment because they are shown without a page reload and the user is already looking at the form. However, for consistency, the client-side decklist error in the submit handler (line 238-248) could also benefit from a scroll. We will add `scrollIntoView` there as well:

```js
decklistError.scrollIntoView({ behavior: 'smooth', block: 'center' });
```

And for the set-code error:

```js
setError.scrollIntoView({ behavior: 'smooth', block: 'center' });
```

---

## Detailed Change List

### `finder/templates/finder/index.html`

1. **Lines 218-288 (loading overlay IIFE):** Replace `submitting`/`cancelled` booleans with generation counter pattern as described above. Remove the `if (submitting) return;` guard at the top of the submit handler. Add `var myGen = ++submitGeneration;` after validation. Replace `doSubmit` and `handleCancel` with generation-aware versions.

2. **Lines 230-233 (set validation error):** After `setError.style.display = '';`, add `setError.scrollIntoView({ behavior: 'smooth', block: 'center' });`.

3. **Lines 238-248 (decklist client-side validation error):** After setting `decklistError.innerHTML` and `decklistField.classList.add('invalid')`, add `decklistError.scrollIntoView({ behavior: 'smooth', block: 'center' });`.

4. **Lines 292-296 (`pageshow` handler):** Add `document.getElementById('loading-flavor').textContent = 'Gathering cards...';` inside the `if (e.persisted)` block. No `submitting` reset needed since the variable no longer exists.

5. **Lines 190-215 (invalid-class IIFE):** After the existing logic, add scroll-into-view for server-rendered errors:
   ```js
   var firstError = document.querySelector('.deck-form .field-errors');
   if (firstError) {
       firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
   }
   ```

### `finder/templates/finder/analysis.html`

1. **Lines 439-501 (loading overlay IIFE):** Same generation-counter refactor as `index.html`. Replace `submitting`/`cancelled` with `submitGeneration`. Update `doSubmit` and `handleCancel`.

2. **Lines 505-509 (`pageshow` handler):** Add flavor text reset: `document.getElementById('loading-flavor').textContent = 'Gathering cards...';`.

---

## Risks and Edge Cases

1. **Double form submission:** The generation counter guards against this. After `form.submit()` is called, the generation is immediately incremented, so the redundant `setTimeout` fallback's `doSubmit` will see a stale generation and bail out. This is strictly better than the current approach where `submitting = true` does the same job but gets stuck.

2. **Rapid cancel-resubmit-cancel cycles:** Each cancel increments the generation, invalidating all prior callbacks. Each new submit also increments. There is no accumulation of stale state — each generation is independent.

3. **`scrollIntoView` on non-error pages:** The scroll logic is guarded by the presence of `.field-errors` elements, so it's a no-op on successful page loads or when no validation errors exist.

4. **`scrollIntoView` browser support:** `scrollIntoView` with `behavior: 'smooth'` is supported in all modern browsers. In older browsers that don't support the options argument, it falls back to an instant scroll — still functional, just not animated.

5. **Flavor text reset on bfcache restore:** Resetting to "Gathering cards..." is cosmetic polish. If the flavor text fetch fails on a subsequent submission, the default text is already visible, which is correct.

6. **Analysis page has no decklist error:** Issue #35 only affects `index.html`. The analysis page (`analysis.html`) has its own validation (theme selection) which is handled client-side and is already near the submit button, so no scroll-into-view is needed there.
