# Security Fix Plan: XSS, Admin Token, and Decklist Size Limit

- **Branch:** `fix/security-xss-and-admin-token`
- **Issues addressed:** #43, #39, #45

---

## Issue #43: Admin secret token exposed in URL query parameters

### Problem

The `_is_admin()` function in `finder/views.py:28-35` checks `request.GET.get('admin')` against `settings.ADMIN_SECRET`. This means the secret travels in URL query parameters, exposing it in:
- Browser history and address bar
- Server access logs
- HTTP `Referer` headers sent to external sites
- Proxy / CDN logs

Additionally, `refresh_patterns()` (line 62-64) and `update_db()` (line 74-77) propagate the token back into redirect URLs as `?admin=...`, perpetuating the exposure. The `index.html` template also forwards `request.GET.admin` into form action URLs (lines 69, 81).

### Implementation approach

**Move to session-based auth.** When a valid `ADMIN_SECRET` is provided (via a one-time login), store the admin status in `request.session` so subsequent requests need no token in the URL.

#### Files to change

1. **`finder/views.py`**
   - Add a new `admin_login` view that accepts a POST with the admin secret (in the request body, not the URL), validates it against `settings.ADMIN_SECRET`, sets `request.session['is_admin'] = True`, and redirects to the index page.
   - Modify `_is_admin()` to check `request.session.get('is_admin')` instead of `request.GET.get('admin')`. Keep the `request.user.is_staff` check.
   - Remove the `request.GET.get('admin')` check entirely from `_is_admin()`.
   - In `refresh_patterns()`: remove the admin token propagation logic (lines 62-64). Just redirect to `reverse('finder:index')`.
   - In `update_db()`: remove the admin token propagation logic (lines 74-77). Just redirect to `reverse('finder:index')`.
   - Optionally add an `admin_logout` view that clears `request.session['is_admin']`.

2. **`finder/urls.py`**
   - Add `path('admin-login/', views.admin_login, name='admin_login')`.
   - Optionally add `path('admin-logout/', views.admin_logout, name='admin_logout')`.

3. **`finder/templates/finder/index.html`**
   - Remove `{% if request.GET.admin %}?admin={{ request.GET.admin }}{% endif %}` from the "Update Database" form action (line 69) and "Refresh Oracle Patterns" form action (line 81).
   - Add a small admin login form (shown when not yet authed as admin) with a password field that POSTs to `admin_login`.
   - Optionally add a logout button in the admin section.

### Risks and edge cases

- **Session backend required:** The project already has `django.contrib.sessions.middleware.SessionMiddleware` in MIDDLEWARE (settings.py line 65) and `django.contrib.sessions` in INSTALLED_APPS (implied by default Django setup with `db.sqlite3`). Sessions are already functional.
- **CSRF:** The login form must include `{% csrf_token %}`. The existing POST views already require CSRF.
- **Migration path:** Anyone currently using `?admin=<secret>` bookmarks will need to use the new login form. This is an intentional breaking change for security.
- **Empty ADMIN_SECRET:** When `ADMIN_SECRET` is empty/unset, the login form should either be hidden or reject all attempts. The current behavior (`if admin_secret and ...`) already handles this.

---

## Issue #39: XSS risk from `|safe` filter with user-influenced JSON

### Problem

Multiple templates inject JSON data into `<script>` blocks using `{{ ...|safe }}`. The values originate from user input (decklist text, selected tags). The current mitigation in `views.py` is `.replace('</', '<\\/')` which only guards against `</script>` injection but misses other vectors (e.g., `<!--`, or encoding tricks).

**Affected locations:**

- `analysis.html:142` — `{{ selected_tags_json|safe }}` inside `<script>`
- `analysis.html:153` — `{% if include_lands %}` (not JSON, but uses a boolean from POST; low risk)
- `results.html:204` — `{{ decklist_text_json|safe }}` inside `<script>`
- `results.html:208` — `{{ set_codes_json|safe }}` inside `<script>`
- `results.html:224` — `{{ selected_tags_json|safe }}` inside `<script>`
- `analysis.html:45` — `{{ decklist_text_json }}` in an HTML attribute `value="..."` (auto-escaped by Django, but the JSON was pre-serialized server-side; the `|safe` is not used here, but the data is still injected)

### Implementation approach

**Use Django's `json_script` template filter.** This is the Django-recommended approach for safely embedding JSON in HTML. It outputs a `<script type="application/json" id="...">` element with proper escaping of `<`, `>`, `&`, etc.

#### Files to change

1. **`finder/views.py`**
   - In `analyze()` (around line 237-254): Stop pre-serializing JSON with `json.dumps()` and remove the `.replace('</', '<\\/')` calls. Instead, pass raw Python data to the template context:
     - `set_codes` instead of `set_codes_json`
     - `color_identity` directly (already passed)
     - `deck_card_names` as a list instead of `deck_card_names_json`
     - `decklist_text` directly (already available as `decklist_text`)
     - `selected_tags` as a list (from `request.POST.getlist('selected_tags')`)
   - In `results()` (around line 433-453): Same approach:
     - `set_codes` instead of `set_codes_json`
     - `deck_card_names` as a list (or keep the JSON string for the hidden form field but use `json_script` for the script block)
     - `decklist_text` instead of `decklist_text_json`
     - `selected_tags` instead of `selected_tags_json`

2. **`finder/templates/finder/analysis.html`**
   - Replace `{{ selected_tags_json|safe }}` with a `json_script` block:
     ```django
     {{ selected_tags|json_script:"selected-tags-data" }}
     ```
     Then in the `<script>`, read it:
     ```javascript
     var restoredTags = JSON.parse(document.getElementById('selected-tags-data').textContent);
     ```
   - For hidden form fields that carry JSON to the next step (`set_codes`, `color_identity`, `deck_card_names`, `decklist_text`): use `json_script` to render them safely, then populate hidden inputs via JS, OR keep them as hidden input values but use `{{ ...|json_script }}` for the `<script>` blocks and keep the hidden inputs auto-escaped (Django auto-escapes attribute values by default when not using `|safe`).
   - The hidden input `value="{{ decklist_text_json }}"` (line 45) does NOT use `|safe`, so Django's auto-escaping handles it. However, the value is a JSON-encoded string (double-quoted), which works because Django escapes `"` to `&quot;`. This is correct as-is.

3. **`finder/templates/finder/results.html`**
   - Replace `{{ decklist_text_json|safe }}` (line 204), `{{ set_codes_json|safe }}` (line 208), and `{{ selected_tags_json|safe }}` (line 224) with `json_script` blocks read via `JSON.parse(document.getElementById(...).textContent)`.

### Detailed template changes

**analysis.html:**
- Before the `<script>` block, add:
  ```django
  {{ selected_tags_data|json_script:"selected-tags-data" }}
  ```
- In `<script>`, change:
  ```javascript
  var restoredTags = {{ selected_tags_json|safe }};
  ```
  to:
  ```javascript
  var restoredTags = JSON.parse(document.getElementById('selected-tags-data').textContent);
  ```

**results.html:**
- Before the `<script>` block, add:
  ```django
  {{ decklist_text|json_script:"decklist-text-data" }}
  {{ set_codes|json_script:"set-codes-data" }}
  {{ selected_tags|json_script:"selected-tags-data" }}
  ```
- In `<script>`, change:
  ```javascript
  decklist.value = {{ decklist_text_json|safe }};
  ```
  to:
  ```javascript
  decklist.value = JSON.parse(document.getElementById('decklist-text-data').textContent);
  ```
- Change:
  ```javascript
  {{ set_codes_json|safe }}.forEach(function(code) {
  ```
  to:
  ```javascript
  JSON.parse(document.getElementById('set-codes-data').textContent).forEach(function(code) {
  ```
- Change:
  ```javascript
  var selectedTags = {{ selected_tags_json|safe }};
  ```
  to:
  ```javascript
  var selectedTags = JSON.parse(document.getElementById('selected-tags-data').textContent);
  ```

### Risks and edge cases

- **Django version:** `json_script` was added in Django 2.1. The project uses Django 5.x, so this is available.
- **Hidden form fields:** The hidden inputs in `analysis.html` that carry JSON to the results view (lines 41-45) currently use Django's auto-escaping for attribute values. These are safe as-is because `|safe` is NOT used on them. We should verify they still work correctly. The values like `{{ set_codes_json }}` (without `|safe`) will have `"` escaped to `&quot;` in the HTML attribute, which is correct behavior — when the form submits, the browser sends the unescaped value.
- **`include_lands` boolean in template:** `{% if include_lands %}` (analysis.html line 153) is not a JSON/XSS issue — it's a Django template conditional on a Python boolean. Safe to leave as-is.

---

## Issue #45: No decklist size limit

### Problem

The `DecklistForm` in `finder/forms.py` defines the `decklist` field as `forms.CharField` with no `max_length` or custom validation. A user could submit an extremely large decklist (multi-MB), causing:
- Memory pressure during parsing
- Slow database lookups
- Potential denial-of-service

### Implementation approach

**Add `max_length` and a custom validator to the form field.**

#### Files to change

1. **`finder/forms.py`**
   - Add `max_length` to the `decklist` field. A typical Commander decklist is ~100 lines of ~30 chars = ~3,000 chars. A generous limit of 20,000 characters accommodates large lists with sideboard, maybeboard, etc.
     ```python
     decklist = forms.CharField(
         max_length=20000,
         widget=forms.Textarea(attrs={
             'rows': 20,
             'maxlength': '20000',  # client-side hint
             'placeholder': '...',
         }),
         label='Decklist',
     )
     ```
   - Optionally add a `clean_decklist` method that counts lines and raises `ValidationError` if over a reasonable line count (e.g., 1000 lines), as a secondary check.

### Risks and edge cases

- **Legitimate large decklists:** A Commander deck is 100 cards. Even with sideboard and considering sections, 20,000 characters is very generous. 1,000 lines is also generous.
- **Django's `DATA_UPLOAD_MAX_MEMORY_SIZE`:** Django defaults to 2.5 MB for POST data. This is an additional layer of protection at the framework level, but it applies to the entire POST body (including CSRF token, set codes, etc.), not just the decklist field. The per-field `max_length` is more precise.
- **User experience:** When `max_length` is exceeded, Django's form validation returns a clear error message automatically. Adding `maxlength` to the `<textarea>` attrs provides client-side feedback too.

---

## Summary of all files to change

| File | Changes |
|------|---------|
| `finder/views.py` | Add `admin_login` view; modify `_is_admin()` to use sessions; remove token propagation from redirects; stop pre-serializing JSON with `json.dumps()` for template `|safe` usage; pass raw Python objects for `json_script` |
| `finder/forms.py` | Add `max_length=20000` to `decklist` field; add `maxlength` HTML attribute; optionally add `clean_decklist` line-count validator |
| `finder/urls.py` | Add `admin-login/` URL route (and optionally `admin-logout/`) |
| `finder/templates/finder/index.html` | Remove `?admin=` query string from form actions; add admin login form; optionally add logout button |
| `finder/templates/finder/analysis.html` | Replace `{{ selected_tags_json\|safe }}` with `json_script` + `JSON.parse()` |
| `finder/templates/finder/results.html` | Replace `{{ decklist_text_json\|safe }}`, `{{ set_codes_json\|safe }}`, `{{ selected_tags_json\|safe }}` with `json_script` + `JSON.parse()` |
| `gather_them/settings.py` | No changes needed (sessions already configured) |
| `finder/middleware.py` | No changes needed |

## Issues to skip

None. All three issues are feasible and should be addressed.

## Implementation order

1. **Issue #45 (decklist size limit)** — smallest, most isolated change. Good warmup.
2. **Issue #39 (XSS fix)** — moderate scope, template + view changes. No new URL routes.
3. **Issue #43 (admin token)** — largest scope, introduces new views/routes and changes auth flow.
