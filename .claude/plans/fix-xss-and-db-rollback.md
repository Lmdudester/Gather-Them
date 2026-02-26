# Implementation Plan: XSS Fix & DB Rollback

**Branch:** `fix/xss-and-db-rollback`
**Issues:** #27 (XSS vulnerability), #30 (Database rollback)

---

## Issue #27: XSS — unescaped `decklist_text` in hidden form field

### Problem

In `finder/templates/finder/analysis.html:45`, the user's raw decklist text is rendered into a hidden input:

```html
<input type="hidden" name="decklist_text" value="{{ decklist_text }}">
```

Django auto-escaping currently mitigates this (escaping `"`, `<`, `>`, `&`), but:
- Every other hidden field on the same form uses `json.dumps()` serialization (`set_codes_json`, `color_identity_json`, `deck_card_names_json`)
- The `decklist_text` field is the only one passed raw
- If anyone adds `{% autoescape off %}` or `|safe` during refactoring, this becomes an exploitable stored XSS

### Approach

Serialize `decklist_text` with `json.dumps()` in the view, matching the pattern used by all other hidden fields. Update the results view to deserialize it.

### Files to change

#### 1. `finder/views.py`

**Line 251 — analysis view context (in `analyze()`):**

Change:
```python
'decklist_text': decklist_text,
```
To:
```python
'decklist_text_json': json.dumps(decklist_text).replace('</', '<\\/'),
```

This matches the existing pattern used on lines 241, 246-247, 252 for other fields, and the pattern already used in the results view at line 448.

**Line 265 — results view POST reading (in `results()`):**

Change:
```python
decklist_text = request.POST.get('decklist_text', '')
```
To:
```python
try:
    decklist_text = json.loads(request.POST.get('decklist_text', '""'))
except (json.JSONDecodeError, TypeError):
    decklist_text = ''
```

This matches the existing defensive parsing pattern used on lines 271-284 for `set_codes`, `color_identity`, and `deck_card_names`.

#### 2. `finder/templates/finder/analysis.html`

**Line 45:**

Change:
```html
<input type="hidden" name="decklist_text" value="{{ decklist_text }}">
```
To:
```html
<input type="hidden" name="decklist_text" value="{{ decklist_text_json }}">
```

### Risks & edge cases

- **Newlines in decklist text:** `json.dumps()` encodes `\n` as `\\n` inside the JSON string. When the browser POSTs the form, it sends the literal `\"...\n...\"` (with real newlines resolved from the HTML attribute). The results view will `json.loads()` it back to the original string with real newlines. This is the same mechanism already working for `deck_card_names_json`.
- **Empty decklist:** `json.dumps('')` produces `""`. The `json.loads('""')` fallback in results will produce `''`. The default fallback `'""'` ensures `json.loads` always has valid JSON even when the POST field is missing.
- **`<\/` escaping:** The `.replace('</', '<\\/')` prevents `</script>` injection if the value is ever used inside a `<script>` tag. This matches the existing pattern on lines 252 and 448-449.

---

## Issue #30: Database update has no rollback on failed atomic swap

### Problem

In `finder/services/db_updater.py:58-63`, the "atomic swap" has a dangerous gap:

```python
# Step A: rename current DB to .old
db_path.rename(old_db_path)
# Step B: rename .new to final path
new_db_path.rename(db_path)
```

If Step B fails (permissions, disk full, crash), the site has no database:
- The old DB was renamed to `.old` (Step A succeeded)
- The new DB is still at `.new` (Step B failed)
- The `finally` block (line 76) then **deletes** `.new`, destroying the downloaded replacement too
- Result: no database file exists at `db_path`, site is broken

### Approach

1. Wrap Step B in a `try/except OSError` with rollback logic that restores `.old` back to the original path
2. Make the `finally` block only clean up `.new` if it still exists AND the swap succeeded (i.e., `db_path` exists)

### Files to change

#### 1. `finder/services/db_updater.py`

**Lines 57-68 — Replace the atomic swap and cleanup block:**

Change (lines 57-68):
```python
        # Atomic swap: old -> .old backup, new -> final
        if db_path.exists():
            if old_db_path.exists():
                os.remove(old_db_path)
            db_path.rename(old_db_path)

        new_db_path.rename(db_path)
        os.utime(db_path)

        # Clean up old backup
        if old_db_path.exists():
            os.remove(old_db_path)
```

To:
```python
        # Atomic swap: old -> .old backup, new -> final
        if db_path.exists():
            if old_db_path.exists():
                os.remove(old_db_path)
            db_path.rename(old_db_path)

        try:
            new_db_path.rename(db_path)
        except OSError:
            # Rollback: restore the old database so the site keeps working
            if old_db_path.exists() and not db_path.exists():
                old_db_path.rename(db_path)
            raise

        os.utime(db_path)

        # Clean up old backup
        if old_db_path.exists():
            os.remove(old_db_path)
```

**Lines 74-78 — Make `finally` cleanup conditional:**

Change (lines 74-78):
```python
    finally:
        # Clean up temp files
        for temp in (zip_path, new_db_path):
            if temp.exists():
                os.remove(temp)
```

To:
```python
    finally:
        # Clean up temp files (only remove .new if swap succeeded)
        if zip_path.exists():
            os.remove(zip_path)
        if new_db_path.exists() and db_path.exists():
            os.remove(new_db_path)
```

The key change in `finally`: we only delete `new_db_path` if `db_path` already exists (meaning the swap succeeded). If the swap failed and rollback happened, `db_path` is restored from `.old` and `.new` is safe to remove. If the swap failed and rollback also failed somehow, we preserve `.new` as a recovery option rather than destroying it.

### Risks & edge cases

- **Rollback itself fails:** If `old_db_path.rename(db_path)` also throws, the original `OSError` from the failed swap propagates (via `raise`). The `.old` file survives on disk for manual recovery — this is better than the current behavior where `.new` is deleted.
- **Race condition with concurrent updates:** The function is called from a management command or admin action. There's no file locking, but this is an existing limitation and not in scope for this fix.
- **`os.utime` failure:** If `os.utime(db_path)` fails after a successful rename, the DB is in place and functional — the timestamp update is cosmetic. The existing exception handler on line 72-73 will catch and wrap this.
- **`finally` conditional logic:** The condition `new_db_path.exists() and db_path.exists()` is safe:
  - Happy path: `.new` was renamed to `db_path`, so `.new` doesn't exist → no-op (correct)
  - Swap failed + rollback succeeded: `db_path` exists (restored), `.new` exists → cleaned up (correct)
  - Swap failed + rollback failed: `db_path` doesn't exist, `.new` exists → preserved for manual recovery (correct)

---

## Issues to skip

None. Both issues are straightforward and well-scoped.

## Testing notes

- **XSS fix:** Verify by submitting a decklist containing `" onmouseover="alert(1)` and inspecting the analysis page HTML source — the value should be JSON-encoded with escaped quotes.
- **DB rollback:** Verify by unit testing the swap logic or manually simulating a rename failure (e.g., read-only target directory).
