# Plan: Fix Admin & Startup Critical Issues

**Branch:** `fix/admin-and-startup-critical`
**Issues:** #20 (CRITICAL), #21, #22

---

## Summary

Three interrelated bugs prevent the admin functionality from working at all:
1. The app crashes on startup due to a missing import (`set_maintenance_mode`)
2. Even if it didn't crash, the admin UI is never rendered (missing `is_admin` context)
3. Even if the UI were shown, the admin endpoints have no auth protection

These must be fixed together since they form a single broken feature chain.

---

## Issue #20 (CRITICAL): ImportError — `set_maintenance_mode` does not exist

### Root Cause
`finder/views.py:15` imports `set_maintenance_mode` from `finder.middleware`, but `middleware.py` only defines `enter_maintenance_mode()` and `exit_maintenance_mode()`. The app cannot start.

### Usage Analysis
- `views.py:58` — `set_maintenance_mode(True)` in `update_db()` to enter maintenance
- `views.py:36` — `set_maintenance_mode(False)` in `_run_update()` to exit after background update

### Fix: Add `set_maintenance_mode()` to `middleware.py`

**File: `finder/middleware.py`** — Add a new function after `exit_maintenance_mode()`:

```python
def set_maintenance_mode(enabled):
    """Enter or exit maintenance mode based on a boolean flag."""
    if enabled:
        enter_maintenance_mode()
    else:
        exit_maintenance_mode()
```

This is the correct approach because:
- It preserves the existing `enter_maintenance_mode()` / `exit_maintenance_mode()` API (used nowhere else currently, but semantically meaningful)
- It satisfies the import in `views.py` without changing any call sites
- `set_maintenance_mode(True)` and `set_maintenance_mode(False)` map cleanly to the underlying lock-file operations
- The alternative (rewriting views.py to call enter/exit directly) would touch more code for no benefit

**No changes needed in `views.py`** — the import and call sites are already correct once the function exists.

---

## Issue #21: Admin UI never shown — `is_admin` not in template context

### Root Cause
`finder/templates/finder/index.html:58` checks `{% if is_admin %}` to conditionally render the Database Management section. The `index()` view at `views.py:132-139` never passes `is_admin` in its context dict.

### Design Decision: What determines "admin"?

The project already has Django's full auth stack installed (`django.contrib.auth`, `AuthenticationMiddleware`, `django.contrib.admin`). The standard Django convention is to use `request.user.is_staff` for admin-level access.

However, this is a small single-purpose app that may not have user accounts set up. We need a mechanism that works both:
- **With Django auth** (if a superuser/staff user is logged in)
- **With a simple secret token** (for deployments without user accounts)

**Approach: Dual-mode admin detection**

1. Add an `ADMIN_SECRET` setting (read from env var) to `settings.py`
2. Create a helper function `_is_admin(request)` in `views.py` that returns `True` if:
   - `request.user.is_authenticated and request.user.is_staff` (Django auth), **OR**
   - `request.GET.get('admin') == settings.ADMIN_SECRET` (when `ADMIN_SECRET` is set and non-empty)
3. Pass `'is_admin': _is_admin(request)` in the `index()` view context

### File Changes

**File: `gather_them/settings.py`** — Add after the `ORACLE_PATTERNS_PATH` line:

```python
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', '')
```

**File: `.env.example`** — Add:

```
# Optional: secret token for admin access (e.g. ?admin=your-secret-here)
# If not set, only Django staff users can access admin features.
ADMIN_SECRET=
```

**File: `finder/views.py`** — Add helper and update `index()`:

```python
def _is_admin(request):
    """Check whether the current request has admin privileges."""
    if request.user.is_authenticated and request.user.is_staff:
        return True
    admin_secret = getattr(settings, 'ADMIN_SECRET', '')
    if admin_secret and request.GET.get('admin') == admin_secret:
        return True
    return False
```

Update `index()` to pass `is_admin`:

```python
def index(request):
    """Step 1: Paste decklist, select set and format."""
    form = DecklistForm()
    db_path = Path(settings.MTGJSON_DB_PATH)
    db_updated = None
    if db_path.exists():
        db_updated = datetime.fromtimestamp(db_path.stat().st_mtime)
    return render(request, 'finder/index.html', {
        'form': form,
        'db_updated': db_updated,
        'is_admin': _is_admin(request),
    })
```

---

## Issue #22: `update_db` and `refresh_patterns` lack authentication

### Root Cause
Both `update_db()` and `refresh_patterns()` are protected only by `@require_POST`. Any user who can reach the URL can trigger a database update (causing maintenance mode / DoS) or refresh patterns.

### Fix: Add admin check to both endpoints

**File: `finder/views.py`** — Add an admin-required check at the top of both view functions. Since these are function-based views (not class-based), the cleanest approach is to check `_is_admin(request)` and return 403 if not authorized.

For `update_db()`:
```python
@require_POST
def update_db(request):
    """Kick off a background database update and redirect to maintenance page."""
    if not _is_admin(request):
        return HttpResponse('Forbidden', status=403)
    # ... rest unchanged
```

For `refresh_patterns()`:
```python
@require_POST
def refresh_patterns(request):
    """Reload oracle text patterns from the JSON config file."""
    if not _is_admin(request):
        return HttpResponse('Forbidden', status=403)
    # ... rest unchanged
```

**Why not use Django's `@login_required` or `@staff_member_required`?**
Because we support the `ADMIN_SECRET` token mode for deployments without user accounts. The `_is_admin()` helper already encapsulates both auth strategies, so we use it directly.

**Note on POST + token auth:** The `ADMIN_SECRET` check uses `request.GET` even for POST requests. This is intentional — the admin UI form on index.html will need to include the token as a query parameter in its action URL. The token is used only for gating access, not as a CSRF substitute (Django's CSRF middleware handles that separately). We need to update the template to pass the admin query parameter through the form action URLs.

**File: `finder/templates/finder/index.html`** — Update form action URLs to preserve the admin query parameter:

```html
<form method="post" action="{% url 'finder:update_db' %}{% if request.GET.admin %}?admin={{ request.GET.admin }}{% endif %}" ...>
```

```html
<form method="post" action="{% url 'finder:refresh_patterns' %}{% if request.GET.admin %}?admin={{ request.GET.admin }}{% endif %}">
```

This ensures the admin secret token is forwarded when the forms are submitted. For Django-auth users (staff), the token is not needed so the URLs remain clean.

---

## Complete File Change Summary

| File | Changes |
|------|---------|
| `finder/middleware.py` | Add `set_maintenance_mode(enabled)` function |
| `gather_them/settings.py` | Add `ADMIN_SECRET` setting |
| `.env.example` | Add `ADMIN_SECRET` documentation |
| `finder/views.py` | Add `_is_admin()` helper; update `index()` context; add auth checks to `update_db()` and `refresh_patterns()` |
| `finder/templates/finder/index.html` | Pass `?admin=` token through form action URLs |

## Implementation Order

1. **`middleware.py`** — Add `set_maintenance_mode()` (fixes #20, unblocks startup)
2. **`settings.py`** + **`.env.example`** — Add `ADMIN_SECRET` setting
3. **`views.py`** — Add `_is_admin()`, update `index()` context (fixes #21), add auth guards (fixes #22)
4. **`index.html`** — Forward admin token in form actions (completes #22)
5. **Test** — Run `python manage.py check` and verify the app starts

## Risks & Considerations

- **`ADMIN_SECRET` in query string:** Query parameters can appear in server logs and browser history. This is acceptable for a small self-hosted tool but should be documented. For production deployments, Django staff auth is preferred.
- **`enter_maintenance_mode()` return value ignored:** `set_maintenance_mode(True)` delegates to `enter_maintenance_mode()` which returns `False` if already locked. The current `update_db()` view already checks `is_maintenance_mode()` before calling `set_maintenance_mode(True)`, so this is fine. We don't need to propagate the return value.
- **No new dependencies** — all fixes use existing Django functionality.
- **Thread safety of `_run_update`:** The background thread calls `set_maintenance_mode(False)` in `finally`. This is the existing design and is safe because the lock file operations are atomic at the OS level.
