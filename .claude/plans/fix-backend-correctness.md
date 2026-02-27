# Fix Backend Correctness Issues

**Branch:** `fix/backend-correctness`
**Issues addressed:** #37, #36

---

## Issue #37: Broken double-checked locking in `oracle_patterns.py`

### Problem

The pattern cache in `finder/services/oracle_patterns.py` uses a mutable `dict` (`_cache`) with three sequential key assignments to publish new data:

```python
_cache['patterns'] = patterns
_cache['pattern_map'] = pattern_map
_cache['exclude_types'] = exclude_types
```

This happens in both `_ensure_loaded()` (lines 78-80) and `refresh_cache()` (lines 87-89). The double-checked locking in `_ensure_loaded()` checks `_cache['patterns'] is None` *outside* the lock (line 74). After a `refresh_cache()` call, there is a window between the first assignment (`_cache['patterns'] = ...`) and the third (`_cache['exclude_types'] = ...`) where a concurrent reader could see:

- A new `patterns` list but a **stale** `pattern_map` or `exclude_types`

This is a classic torn-read on a multi-field update. Python's GIL makes individual dict writes atomic, but it does *not* guarantee that all three writes are seen together by another thread.

### Files to change

**`finder/services/oracle_patterns.py`**

### Implementation approach

Replace the mutable dict cache with an **immutable snapshot** reference swap. The idea: pack all three fields into a single immutable object (a `namedtuple` or a frozen dataclass), and swap the module-level reference in one atomic assignment. Readers never hold the lock; they just read a single reference, which is always a consistent snapshot.

Concrete changes:

1. **Define a `_CacheEntry` namedtuple** (or use `typing.NamedTuple`) with fields `patterns`, `pattern_map`, `exclude_types`.

2. **Replace `_cache` dict** with a single module-level variable:
   ```python
   _cache: Optional[_CacheEntry] = None
   ```

3. **Rewrite `_ensure_loaded()`** to use the atomic-swap pattern:
   ```python
   def _ensure_loaded():
       global _cache
       if _cache is None:
           with _lock:
               if _cache is None:
                   patterns, pattern_map, exclude_types = _load_patterns()
                   _cache = _CacheEntry(patterns, pattern_map, exclude_types)
   ```
   The double-checked locking now works correctly: the outer `_cache is None` check reads a single reference (atomic under CPython), and the inner check under the lock prevents duplicate loading.

4. **Rewrite `refresh_cache()`** to build outside the lock, then swap:
   ```python
   def refresh_cache():
       global _cache
       patterns, pattern_map, exclude_types = _load_patterns()
       _cache = _CacheEntry(patterns, pattern_map, exclude_types)
       logger.info(...)
   ```
   The lock is no longer needed in `refresh_cache()` since the single-reference swap is atomic. However, keeping the lock is harmless and could be retained for clarity — the critical fix is that readers see either the old or the new snapshot, never a mix.

5. **Update getter functions** to read from the snapshot:
   ```python
   def get_oracle_patterns():
       _ensure_loaded()
       return _cache.patterns
   ```
   (Same for `get_oracle_pattern_map` and `get_oracle_pattern_exclude_types`.)

### Risks and edge cases

- **Callers holding references:** Callers like `theme_extractor.py` (line 41-42) call `get_oracle_patterns()` and `get_oracle_pattern_exclude_types()` in two separate calls. If `refresh_cache()` runs between those calls, the caller gets patterns from one generation and exclude_types from another. This is a pre-existing issue and is *not* worsened by this fix — before the fix the same race existed within the dict. To fully fix this, callers would need to fetch the entire snapshot at once, but that's a larger refactor out of scope for this issue.
- **No behavioral change for single-threaded use:** The fix is purely about thread-safety; functional behavior is identical.
- **`refresh_cache` lock removal:** Removing the lock from `refresh_cache()` is safe because the assignment `_cache = _CacheEntry(...)` is a single reference swap. If two concurrent `refresh_cache()` calls race, last-writer-wins, which is acceptable (the result is still a consistent snapshot).

---

## Issue #36: MaintenanceMiddleware blocks `random_flavor` API during DB updates

### Problem

The `MaintenanceMiddleware` in `finder/middleware.py` (line 107) returns a 503 for **all** paths except `/update-db/`:

```python
if is_maintenance_mode() and request.path != '/update-db/':
    html = render_to_string('finder/maintenance.html', request=request)
    return HttpResponse(html, status=503)
```

The loading overlay on `index.html` (line 349) and `analysis.html` (line 487) fetches flavor text from `/api/random-flavor/` during form submission. If a DB update starts while a user is on those pages, the flavor fetch gets a 503 HTML response instead of JSON. The `fetch().then(r => r.json())` call fails, which is caught by `.catch(function(){})` so it doesn't crash, but:

1. The loading overlay shows "Gathering cards..." instead of a flavor quote — minor UX issue.
2. More importantly, the maintenance page *itself* doesn't fetch flavor text, so this is specifically about the case where a user is on the index/analysis page and hits submit right as maintenance mode kicks in. The flavor fetch fails, but then `form.submit()` also gets a 503 maintenance page — so the real impact is only if maintenance starts and ends within the ~4s loading window. Still worth fixing for correctness.

The real issue is that `/api/random-flavor/` is a pure read from in-memory data (SQLite) that doesn't write anything and doesn't conflict with the DB update. It should be allowed through.

### Files to change

**`finder/middleware.py`**

### Implementation approach

Add `/api/random-flavor/` to the allowed paths in the maintenance mode check:

```python
_MAINTENANCE_ALLOWED_PATHS = {'/update-db/', '/api/random-flavor/'}

# In __call__:
if is_maintenance_mode() and request.path not in _MAINTENANCE_ALLOWED_PATHS:
```

This is a minimal, targeted fix. A more general approach (e.g., allowing all `/api/` paths) would be over-engineering since `random_flavor` is currently the only API endpoint.

### Alternative considered

Using `request.path.startswith('/api/')` — rejected because future API endpoints might involve DB writes that genuinely should be blocked during maintenance. Explicit allowlisting is safer.

### Risks and edge cases

- **URL path must match exactly:** The path registered in `finder/urls.py` is `api/random-flavor/` under the `finder/` app namespace. Since the app is included at the root (`/`), the full path is `/api/random-flavor/`. If the URL prefix changes, this allowlist must be updated. Using `reverse()` at module level is not safe (URL conf may not be loaded yet), so a hardcoded path is the pragmatic choice.
- **No security concern:** The `random_flavor` endpoint is a public, read-only, idempotent JSON API with no authentication requirements. Allowing it through maintenance mode introduces no risk.
- **DB consistency during update:** `random_flavor` calls `get_random_flavor_text()` which reads from the SQLite DB. If the DB file is being replaced during the update, SQLite's file-level locking handles this safely — readers either see the old data or block briefly. The update process uses a download-then-rename pattern (checked in `db_updater.py`), so the window for contention is minimal.

---

## Issues to skip

None — both issues are straightforward, low-risk fixes. Both should be included.

---

## Summary of changes

| File | Change | Issue |
|------|--------|-------|
| `finder/services/oracle_patterns.py` | Replace mutable `_cache` dict with immutable `_CacheEntry` namedtuple and single-reference swap | #37 |
| `finder/middleware.py` | Add `/api/random-flavor/` to maintenance mode allowlist | #36 |

## Testing considerations

- **Issue #37:** Verify that `get_oracle_patterns()`, `get_oracle_pattern_map()`, and `get_oracle_pattern_exclude_types()` still return correct data after both initial load and `refresh_cache()`. Existing tests (if any) should pass without modification.
- **Issue #36:** Verify that hitting `/api/random-flavor/` during maintenance mode returns a 200 JSON response instead of 503. Verify that other paths still get 503.
