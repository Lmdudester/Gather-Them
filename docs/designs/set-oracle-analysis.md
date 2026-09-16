# Set Oracle Analysis and Card Viewer

**Status:** Approved — ready for user testing

## Original enhancement

Gather Them currently requires a decklist before it can extract oracle themes and
send matching cards to the card viewer. Add a parallel workflow where a user
selects one or more sets, the app analyzes the oracle text of the cards in those
sets directly, and the user selects the oracle tags they want to use in the
existing card viewer.

The selected sets are treated as one combined card pool. This is a set-focused
discovery flow, not a per-deck recommendation flow.

## Goals

- Let a user start an analysis with only one or more selected sets.
- Rank the existing oracle-pattern tags by the number of distinct cards in the
  selected set pool that contain each pattern.
- Let the user choose which ranked oracle tags to view.
- Reuse the existing card-grid viewer, filtering it to cards from the selected
  sets that match at least one selected tag and ranking cards by the number of
  selected tags matched.
- Preserve the current decklist → deck analysis → results workflow and its
  format, color-identity, land, and deck-card exclusion behavior.

## Non-goals

- No saved searches, accounts, database models, or new persistence.
- No comparative chart or separate ranking for each selected set; selected sets
  are aggregated into one analysis.
- No deck format or color-identity query filter in set mode. The set flow
  analyzes and displays the selected set pool directly; the shared results
  viewer may still filter the returned cards by their color identity.
- No new image provider or separate card-grid implementation. The existing
  results viewer remains the presentation layer.
- No change to the set list, oracle-pattern definitions, or database update
  process beyond making their existing data available to this flow.

## Assumptions and rules

- `get_set_cards()` is the source of truth for the set pool. Its current
  `GROUP BY c.name` behavior means a card name appearing in multiple selected
  sets is analyzed and displayed once, consistent with the existing multi-set
  results behavior.
- Each distinct card contributes one occurrence to an oracle tag in set mode;
  there are no deck quantities to multiply.
- Set mode exposes all oracle patterns found at least once. The existing tier
  layout ranks them, and its minimum-count control can hide low-frequency tags
  interactively. The highest tier uses the same default selection behavior as
  deck analysis.
- In set mode, oracle-pattern exclusions (for example, patterns excluded from
  lands or other card types) apply identically during analysis and result
  matching, so a tag's count and the cards it produces cannot disagree. The
  existing deck-mode matcher semantics remain unchanged; do not apply the new
  set-mode exclusion flag globally because that could remove oracle-matching
  non-basic lands from existing deck results.
- User selections are carried through the existing POST/hidden JSON flow. No
  user-submitted deck or set analysis is stored server-side. The selected
  oracle tags are treated as a set for matching; duplicate submitted values
  have no effect.
- In set mode, selected set codes are normalized to unique values in submitted
  order and capped at 100, a documented maximum below SQLite's bind-variable
  limit.
  The same normalization and limit apply to the set-mode visible form and
  every set-mode hidden-state result boundary. The existing deck workflow is
  not subject to this new set-mode cap.

## Acceptance criteria

1. The homepage offers a clearly labeled entry point such as **Analyze Set(s)**
   that opens the set-only workflow without requiring a decklist.
2. The set entry page contains the existing searchable, keyboard-accessible
   multi-set picker, validates that at least one set is selected, and shows a
   loading state while the analysis request is submitted.
3. A valid set selection produces a **Set Oracle Analysis** page showing the
   selected set names, the number of cards analyzed, and only oracle-pattern
   tags ranked by occurrence count.
4. The analysis page exposes native checkbox controls for the tags, select all /
   deselect all controls, and the existing relevance control where applicable.
   The user cannot submit with no oracle tag selected; the submit action is
    disabled or rejected with an inline, actionable message when no tags exist or
    none are selected. That message is an associated `role="alert"`/live region,
    and rejected submission moves focus to the tag controls.
5. Submitting selected tags displays the existing card viewer with cards from
   the selected set pool. A card is included when it matches any selected oracle
   tag, its matched tags are visible, and relevance is based on the number of
   selected tags matched. The shared viewer exposes a color filter based on card
   color identity, including a Colorless option when applicable. Its default
   **INCLUDES** mode matches cards containing any selected color; **ONLY** mode
   matches cards whose complete color identity is exactly the selected set.
6. Returning from the set-mode viewer restores the selected sets and selected
   oracle tags on the set analysis page. Starting over returns to the homepage.
7. Empty and failure states are explicit: a set selection yielding no cards, a
   card pool yielding no oracle patterns, and a tag selection yielding no cards
   each explain what happened and expose a visible recovery action such as
   **Choose Different Sets**, **Back to Set Analysis**, or **Start Over**;
   database access failures show an accessible 503 recovery page.
8. Existing deck analysis and results behavior continues to pass its current
   tests and manual flow checks.
9. The feature works with the existing responsive layout and keyboard/screen
   reader interaction patterns, without exposing raw unescaped user input.

## Current implementation and data flow

The repository is a Django 5.2 server-rendered app with no application models.
The relevant current path is:

1. `finder/templates/finder/index.html` renders `DecklistForm`, including the
   searchable multi-select set picker.
2. `finder/views.py:analyze` parses the decklist with
   `finder/services/deck_parser.py`, resolves names with
   `finder/services/card_lookup.py`, and extracts all theme categories with
   `finder/services/theme_extractor.py`.
3. `finder/templates/finder/analysis.html` renders tiered theme checkboxes and
   posts selected tags plus analysis state to `finder/views.py:results`.
4. `results` calls `get_set_cards()`, filters cards through
   `finder/services/set_filter.py`, and renders
   `finder/templates/finder/results.html`, which is the current card viewer with
   client-side filtering and sorting.

`theme_extractor.py` already applies the oracle-pattern cache and card-type
    exclusions from `oracle_patterns.py`. `set_filter.py` already matches
oracle-pattern labels from the same cached pattern map, but its matcher will be
aligned with the extractor's exclusions as part of this feature.

The test suite is currently in `finder/tests.py`; it covers maintenance controls
and card-name lookup but has no set-analysis or results-view tests. The working
tree contains an unrelated modification to
`scripts/entrypoint-autoupdate.sh`; it must remain untouched.

## User experience

### Entry point and set selection

Keep the existing deck workflow prominent on the homepage and add a secondary
**Analyze Set(s)** action. It opens a dedicated set-selection page so the two
forms do not share duplicate field IDs or mix deck-only options into set mode.

The set-selection page uses the same searchable set picker behavior as the
homepage: an explicitly labeled combobox, listbox results, keyboard
arrows/Enter/Escape, selected removable chips, and a native hidden
multi-select as the submitted source of truth. Its primary action is
**Analyze Set(s)**. The page does not show a decklist field or format selector.
The visible search input has a stable `id`, the label is associated with it,
and the listbox/options expose the active option through the existing
combobox ARIA attributes. Each chip remove button has an accessible name that
includes the set name. The set validation message is associated with the
combobox, announced as an error, and moves focus to the picker; scrolling to
the message may supplement focus but must not replace it.
When a chip is removed by keyboard, focus moves to the stable search combobox
after the chip is rebuilt (or to a surviving adjacent chip if that is the
chosen implementation); it must never remain on the removed button.
Adding or removing a set also updates a polite live status with the selected
set count (and the set name where useful), so screen-reader users receive
feedback even while focus remains in the combobox.

States:

- **Initial:** short explanation that tags are ranked from oracle text in the
  selected sets; no set is selected.
- **Selected:** chips show every selected set; the primary action is available.
- **No selection:** inline error asks the user to select at least one set and
  focuses/scrolls to the picker using the existing form behavior.
- The set-selection error remains visible and announced while the picker has
  focus; the shared invalid-field focus handler must not dismiss it until a
  valid set is selected or the next validation succeeds.
- **Loading:** reuse the existing full-screen loading overlay and cancel action;
  use copy appropriate to set analysis, such as “Analyzing selected cards…”.
- **Loading accessibility:** give the reused full-screen overlay dialog/status
  semantics (`role="dialog"`, an accessible label, `aria-modal="true"`, and a
  live status region), make the Cancel button visible before moving focus to
  it and before the earliest auto-submit, keep keyboard focus within the
  active overlay, and return focus to the submit button when cancellation
  closes it. The existing one-second delayed opacity animation must be removed
  or changed so the button is usable immediately; reduced-motion behavior must
  also leave it visible and disable the loading-logo pulse and validation-error
  shake animations. Reset the active/hidden ARIA state and focus appropriately
  on back-forward-cache restoration.
- **Database failure:** show the dedicated accessible 503 database-unavailable
  page with **Try Again** and **Start Over** actions; distinguish this from
  the existing active-update maintenance page and do not expose internal
  database details.

### Set Oracle Analysis

The analysis page is a mode-aware version of the existing theme-selection
surface, titled **Set Oracle Analysis**. Its summary shows “Analyzed N cards”
and chips for the selected sets. It does not show deck color identity, format,
unfound deck cards, non-oracle theme categories, or **Include All Lands**.

The main content is labeled **Oracle Tags**. It uses the current tier-column
visual language, tag counts, checkbox styling, select-all/deselect-all controls,
and relevance slider. Only oracle-pattern tags are rendered; the by-category
toggle is hidden because there is only one category in this mode. The set-mode
form posts to the dedicated set-results endpoint and its client script
initializes only set-mode controls: it must not dereference the hidden
deck-only view toggle, land checkbox, or category view, and its validation
requires an oracle tag rather than a deck-land combination. Counts are
described as cards containing the tag, not copies or printings. When the
relevance control is shown in set mode, its minimum and default are 1 so
singleton tags remain visible, and its maximum is one above the highest tag
count so the all-hidden guidance state is reachable. Deck mode retains its
current slider range and minimum/default of 2.

If the source contains no cards, show an explanatory empty state with visible
**Choose Different Sets** and **Start Over** actions. If the source contains no
patterns, show an explanatory recovery state with those same actions and keep
the viewer action unavailable. If patterns exist but the user deselects all tags,
show an associated `role="alert"`/live-region error near the controls, move
focus to the first visible tag control, and do not navigate away. If the
relevance slider hides all tags, keep the slider and its “lower the minimum
count” guidance focusable; a rejected submit focuses the slider (or a
focusable recovery action when no slider is rendered) rather than a nonexistent
tag control, and keeps the selected-tag state predictable.
If a result POST contains only stale/invalid tags, re-render this analysis page
for the validated sets with an associated alert explaining that the tags are
no longer available, and move focus to the alert, the first valid tag, or a
visible recovery action.

### Set-mode card viewer

Reuse `results.html` and its existing card-grid viewer, filters, sorting, Scryfall
links, responsive layout, and lazy-loaded images. In set mode:

- The summary copy says cards match the selected oracle tags and lists the
  selected sets.
- No format or color-identity chip is shown.
- No deck-card exclusion or land-merging control is applied.
- The shared Color filter defaults to **INCLUDES** and can switch to **ONLY**.
  INCLUDES returns cards whose color identity contains any selected color;
  ONLY returns cards with an exact color identity match, including an exact
  Colorless match when Colorless is selected.
- The selected-tag disclosure and matched-tag badges remain available.
- The primary navigation actions are **Start Over** and **Back to Set
  Analysis**.
- The empty result state names the selected sets, suggests different tags or
  sets, and keeps **Back to Set Analysis** and **Start Over** available so the
  user has a recovery path.

The viewer's client-side Color/Type/Rarity/Mana Value/Power/Toughness/Matched
Tags filters and sorting remain unchanged. The Color filter uses card
`colorIdentity`, is limited to colors present in the current result set, and
defaults to INCLUDES semantics for multiple selected colors. ONLY mode requires
the complete identity set to match exactly. Native buttons and links retain visible
focus states, meaningful accessible text, and the existing mobile behavior.
The shared Color INCLUDES/ONLY and Type and Matched Tags OR/AND controls must remain keyboard and
screen-reader operable: use focusable visually-hidden checkbox controls with
associated labels, or buttons with synchronized `aria-pressed` state, while
preserving their documented default and filtering behavior. Their accessible
names must include the category and current state, such as “Type filter mode:
OR” and “Matched Tags filter mode: OR,” and update when toggled.

### Responsive and accessibility behavior

Reuse the current dark theme, accent colors, tier labels, chips, buttons, grid,
loading overlay, and breakpoint rules. The set picker and checkboxes remain
keyboard operable, labels remain associated with inputs, and validation is
visible without relying on color alone. New mode-specific status/error text is
rendered as normal semantic content and should not expose raw JSON or unescaped
input. The shared results viewer must retain visible focus indicators and
announce filter-mode state changes to assistive technology.

## Technical plan

### Forms and routes

- Add a small `SetAnalysisForm` in `finder/forms.py` containing the existing
  validated `set_code` multiple-choice field and choices. If practical, factor
  the shared set-choice construction from `DecklistForm` so both forms use one
  source of truth. Define `MAX_SET_SELECTIONS = 100`; its cleaning step
  preserves order, removes duplicate set codes, and rejects more than that
  safe maximum with an actionable validation error. Set the form's
  `use_required_attribute = False` so the hidden multi-select does not block
  the custom empty-selection error/focus path; server-side required validation
  remains authoritative.
- Add routes in `finder/urls.py` for the set-selection page, set analysis POST,
  and set-mode results POST. Keep the existing route names and POST contracts
  working for deck mode.
- Add `set_index` and `set_analyze` views in `finder/views.py`. `set_analyze`
  validates the form, loads the selected set pool with `get_set_cards`, runs the
  oracle-only extractor, builds the existing tier data, and renders the
  mode-aware analysis surface.
- Add set-mode result handling either as a small mode branch around the shared
  result-building code or as a shared helper used by both `results` and the new
  set-results view. The set branch must validate/normalize posted set codes,
  accept only oracle-pattern tags, canonicalize/deduplicate valid tags while
  preserving their order, omit deck-only filters, and call the same shared card
  matcher with an explicit set-mode oracle-exclusion option; the deck branch
  keeps its current matcher semantics. An all-invalid tag submission rebuilds
  the set-analysis context from the validated set codes and re-renders that
  page with an associated alert, focus transfer, and actionable error instead
  of falling through to an empty viewer.
- Keep hidden state JSON in Django's `json_script`/escaped hidden-field patterns;
  do not interpolate raw user strings into executable JavaScript.

### Oracle analysis and matching

- Extend `finder/services/theme_extractor.py` with a focused oracle-only
  extraction helper (or a clearly scoped optional mode) that accepts card data,
  counts each card once, preserves the existing compiled-pattern and excluded
  card-type logic, returns sorted `(label, count)` pairs, and retains singleton
  tags for set mode.
- Refactor shared pattern matching as needed so
  `finder/services/set_filter.py` can apply the same exclusions during
  set-mode result matching as during set-mode analysis. Keep the matcher’s
  current deck-mode behavior as its default (for example via an explicit
  `apply_oracle_exclusions` option), and do not change the meaning of
  non-oracle deck tags or remove oracle-matching non-basic lands from existing
  deck results.
- Continue using `oracle_patterns.py`'s cached/hot-reloadable definitions; no
  pattern data migration is needed.
- Keep a set-mode-only normalization/max-set guard at the card-query boundary
  as a second line of defense for `get_set_cards()` and `get_set_lands()` before
  building SQL placeholders; expose it as an explicit option or normalized
  input so the default deck-mode calls retain their current behavior.

### Templates and styling

- Update `finder/templates/finder/index.html` with the new entry point.
- Add a set-selection template, reusing the set-picker partial/script and the
  existing loading/error styling where possible. Give this page a deck-free
  loading submit handler that validates only selected sets and shares the
  generation/cancel and accessible-overlay behavior without reading
  `#id_decklist` or requiring `.deck-form`; cover its first submission and
  cancellation paths separately from the deck form. Include a polite live
  status for selected-set count changes.
- Add `finder/templates/finder/database-unavailable.html` for the 503 state,
  using semantic alert/status content, keyboard-focusable recovery links, and
  copy that does not expose database internals.
- Make `analysis.html` mode-aware (or extract the shared tag-selection markup and
  behavior into a reusable partial) so deck mode remains unchanged while set
  mode renders only Oracle Pattern tags and set-specific copy/state. Guard all
  shared initialization and event handlers by mode/element presence: deck-only
  code may access `view-toggle`, `category-view`, and `include_lands` only in
  deck mode, while set mode uses its own oracle-only submit validation and
  dedicated set-results form action. Set mode renders the relevance slider with
  `min=1`, `value=1`, and `max=(highest count + 1)` when patterns exist; deck
  mode retains its current slider attributes.
- Make `results.html` mode-aware for summary copy, hidden state, and the
  **Back to Set Analysis** action; keep the existing viewer markup and filtering
  behavior shared.
- Extend the shared results filter metadata and card data attributes with
  `colorIdentity`. Render only the color options present in the current result
  set, in W/U/B/R/G order with Colorless last, and filter cards client-side by
  color identity without changing set or deck query behavior. Add a focusable
  Color mode control labeled INCLUDES/ONLY, defaulting to INCLUDES, and expose
  its current state to assistive technology.
- In the shared results filter markup, make the Type and Matched Tags OR/AND
  controls focusable and expose their current OR/AND state to assistive
  technology without changing the client-side filter contract.
- Move the shared results **Clear** button out of the filter `<summary>` into
  the expanded filter content or a sibling actions region, leaving the summary
  as a disclosure trigger only. Preserve clear behavior and add keyboard and
  screen-reader coverage for opening the filter and activating Clear.
- Build the shared results filter active-summary text with DOM nodes and
  `textContent` rather than `innerHTML`; card types, tag labels, and other
  database/config-derived values must not be interpolated into HTML.
- Update the shared set-picker script so database-sourced set labels and codes
  are never interpolated into `innerHTML` or selector strings. Build options
  and chips with DOM nodes, `textContent`, and safe attribute/property
  assignment (or explicit escaping), and resolve selected options by exact
  value rather than an unescaped CSS selector.
- Add only the CSS needed for the set entry call-to-action, any mode-specific
  empty/status content, and the loading Cancel visibility/focus contract. The
  Cancel button must not have the current one-second delayed opacity when the
  overlay opens; if a non-reduced-motion fade is retained, it may begin after
  the button is already visible. Add an explicit `prefers-reduced-motion`
  override that disables the logo pulse and validation-error shake while
  forcing the Cancel button visible, and bump the static stylesheet cache
  version if the current convention requires it.
- Update `README.md` project structure, workflow, and feature list to describe
  direct set oracle analysis.

### State, validation, and errors

- Preserve the current deck endpoint contract: a GET to the existing
  `analyze` or `results` endpoint continues to render the homepage with its
  current status. A GET to either new set-only POST endpoint redirects to the
  set-selection start page.
- Catch expected database access/schema errors at the homepage as well as each
  new set-flow endpoint (set selection, set analysis, and set results). This is
  required because constructing the existing deck form loads set choices. Log
  the exception without exposing paths or SQL, and render a dedicated
  database-independent accessible `database-unavailable.html` response with
  HTTP 503. That page explains that card data is temporarily unavailable and
  offers **Try Again** to the set start page plus **Start Over** to the
  homepage; both targets must remain recovery-safe and return the same 503 page
  rather than a 500 while the database is unavailable. It must not show a
  spinner implying an active update. The availability guard must bypass the
  in-memory set-choice cache and probe every schema dependency used by the set
  flow (`sets`, `cards`, and `cardIdentifiers`) for existence/readability; it
  must execute representative query shapes with the required columns,
  including the set-choice columns and the card-plus-`scryfallId` join, rather
  than only `SELECT 1`. A successful `sets` lookup alone is insufficient. Any database exception must
  invalidate the set-choice cache before rendering the error so a warmed cache
  cannot turn either recovery link into a misleading HTTP 200.
- Validate a set selection with Django's choice field before querying. In the
  set-results POST, parse hidden JSON defensively, revalidate, deduplicate, and
  enforce the same safe maximum on set codes before querying; malformed or
  over-limit set-mode state returns a user-facing error and safe redirect
  rather than a server error. Do not apply that new maximum to deck results.
- Require at least one valid oracle tag in set results. Ignore malformed or
  unknown tag strings rather than treating them as executable or database
  input, and canonicalize/deduplicate the remaining valid tags before matching
  so repeated POST values cannot change match counts. If no valid tag remains,
  re-render set analysis for the validated set selection with an actionable
  alert and do not render the viewer; malformed set state instead redirects
  safely to set selection.
- If the selected set pool is empty, render the set analysis page with a clear
  empty state. If matching returns no cards, render the existing viewer empty
  state rather than failing.
- Set-mode analysis must never assume deck-only DOM controls exist. Its POST
  boundary accepts only validated set codes and oracle-pattern tags, and its
  no-tag error is handled before the loading overlay or navigation is started.
  Client validation focuses the first visible tag checkbox; when relevance has
  hidden every tag, it focuses the slider or a visible recovery action instead.
- Do not add sessions, database writes, or migrations. The only mutable external
  data remains the existing public database/pattern maintenance controls.

### Security, privacy, and performance

- Continue using parameterized set-code SQL. Set-mode format handling does not
  interpolate a user-provided column name.
- Use Django escaping and JSON-safe script data for set names, tag labels, and
  validation messages. Treat hidden fields as untrusted and validate them again
  at the result boundary. Add a hostile set-label/code regression case proving
  picker rendering cannot execute or emit raw database HTML, plus a hostile
  result-field case covering the client-side filter summary.
- No decklists or set selections are persisted or logged as user identity data.
- Set analysis performs one existing set-card query plus one in-process pass over
  the returned cards using cached regexes. The loading overlay communicates that
  large multi-set selections may take a moment. Avoid N+1 card lookups or a new
  per-card database query.

### Observability and compatibility

- Reuse existing logger/maintenance behavior for database errors, with the new
  database-unavailable response covering cold-cache and warmed-cache failures.
  No analytics or telemetry is required for this local/public utility feature.
- No schema or migration changes are expected.
- Existing deck URLs, template state, card viewer filters, and public maintenance
  controls must remain compatible.

## Test strategy

### Automated tests

Add tests in `finder/tests.py` or a new `finder/tests/` module following the
current Django test setup:

- Oracle-only extraction counts each distinct set card once, sorts by count, and
  retains singleton tags in set mode.
- A two-set fixture includes cards unique to each set and one shared card name;
  analysis and results include cards from both sets and count/display the shared
  name once.
- Set-mode oracle exclusion rules are applied consistently by extraction and
  result matching, while deck-mode matcher behavior remains covered by the
  deck regression tests.
- The set-selection page renders for anonymous users and rejects a missing or
  invalid set selection without querying cards.
- Static/template checks assert the hidden multi-select has no native required
  attribute, and the Django form still rejects the empty server POST; the
  browser custom announced error/focus path is manual.
- Repeated valid set codes are normalized to one code, and an over-limit
  selection is rejected before SQL construction.
- Static/template checks cover the polite selected-set live-region markup and
  focus-restoration hooks; runtime announcement and focus behavior after
  add/remove interactions are manual browser checks.
- Static/template checks assert the no-selection picker error's alert/live
  association and the deck-free handler's set-only field references; runtime
  focus, first submission, and cancellation behavior are manual browser checks.
- Static source checks assert database-sourced set labels/codes are rendered via
  DOM text/attributes rather than HTML interpolation; manual browser checks
  with hostile set values verify that no markup executes.
- Simulated database open/query/schema failures at each new set-flow endpoint
  and the homepage return HTTP 503 with the accessible database-unavailable
  recovery page; following both recovery links during the outage remains 503,
  never 500, and does not leak SQL or filesystem details. Include a warm-cache
  case where `sets` is readable but `cards` or `cardIdentifiers` fails, plus a
  missing-required-column case, proving the full dependency probe still
  reports the outage.
- Static source checks assert hostile card type/tag values are assigned with
  DOM text APIs in the results filter summary; manual browser checks with
  hostile result values verify that no markup executes when filters change.
- Client tests assert the existing `analyze` and `results` GET requests still
  render the homepage with HTTP 200, while GET requests to both new set-only
  POST endpoints return HTTP 302 to set selection.
- Set analysis requests load the selected set codes, render only Oracle Pattern
  tags, show the analyzed-card count, and handle an empty pool/no-pattern case
  with asserted explanatory copy plus visible **Choose Different Sets** and
  **Start Over** recovery actions; singleton tags remain rendered at the
  set-mode relevance minimum/default of 1.
- Static/template checks assert that set mode allows a threshold above the
  highest count and keeps the slider or recovery action focusable in the
  all-hidden state; runtime focus behavior is covered by the manual browser
  check.
- Set results accept selected oracle tags without decklist/color/format state,
  render matching cards, and render a safe empty viewer state for valid
  selections that match no cards. Malformed hidden state redirects safely to
  set selection with a user-facing error; the no-match state keeps both
  recovery actions available.
- Set-results fixtures include one card matching two selected oracle tags and
  another matching only one; the first exposes both matched tags, has match
  count 2, and sorts ahead of the single-match card.
- Repeated valid oracle tags in a crafted set-results POST are canonicalized
  to one occurrence before matching and cannot inflate match counts or
  relevance ordering.
- A crafted set-results POST containing only malformed or unknown tags
  re-renders set analysis for the validated sets with an associated alert,
  focus target, and actionable message, and never renders the viewer.
- Template/static checks assert that set analysis points at the set-results
  action, omits deck-only controls, includes the mode guard and no-tag alert
  association, and uses the set-mode relevance threshold. Runtime JavaScript
  initialization, no-tag focus/announcement, and loading timing are manual
  browser checks because the repository has no browser test harness.
- Template/static checks assert category-specific accessible names and state
  updates for the Type and Matched Tags OR/AND controls.
- Static/template checks assert that the Color filter renders the available
  color identity options, includes Colorless for colorless cards, exposes the
  INCLUDES/ONLY control with an accessible default, and places escaped color
  identity data on each result card. Manual browser checks cover single-color,
  multicolor, colorless, multiple-selection INCLUDES/ONLY behavior, and
  interaction with another active filter.
- Back navigation preserves selected set codes and tags.
- Add unconditional deck regression coverage for the existing results contract:
  selected format and color identity are passed to set-card/land queries,
  basic lands and cards already in the deck remain excluded, and
  **Include All Lands** still merges eligible lands. Do not make this coverage
  conditional on whether a helper is refactored; it is required to verify the
  mode-aware changes preserve the deck workflow. Include a fixture where a
  non-basic land matches an oracle pattern excluded for lands: it must remain
  in deck-mode results but be excluded from set-mode oracle results.
  A deck fixture with more than 100 valid selected set codes remains accepted
  by the existing deck form/query path and is not rejected by the set-mode cap.
  Include representative non-oracle deck tags (subtype, keyword, card type,
  supertype, and stat profile) with expected matched tags/counts so the shared
  matcher refactor cannot drop those existing results.
- Add unconditional deck-analysis regression coverage for the existing
  extraction path: a quantity-weighted fixture preserves oracle and non-oracle
  category counts, tier data, and the computed color identity when rendered by
  the deck analysis flow.
- Template/static checks cover the associated picker label, named chip removal,
  announced validation markup, mode-specific script guards, and the set-mode
  relevance threshold. Runtime focus, reduced-motion, screen-reader, and
  keyboard/announced state behavior are manual browser checks because the
  repository has no browser test harness.

### Manual verification

With a configured MTGJSON database:

1. Open the homepage and confirm the existing deck flow is unchanged; open the
   new set-analysis entry point.
2. Use mouse and keyboard to select one set, remove it and verify focus returns
    to the picker, verify a screen reader announces the selected-set count,
    select multiple sets, submit with no selection, and cancel the loading
    overlay.
3. Confirm set names/card count and oracle tags are ranked correctly; verify
   singleton tags and the relevance control; raise the set-mode threshold above
   the highest count to exercise the all-hidden guidance/focus recovery; then
   select/deselect tags.
4. Open the viewer, inspect matched tags, card images/Scryfall links, sorting,
    client-side filters including Color, the disclosure and **Clear** controls, empty results,
    and **Back to Set Analysis** restoration; verify the Color mode control
    announces INCLUDES/ONLY and the Type and Matched Tags controls announce
    their category and OR/AND state.
5. Repeat at mobile breakpoints and with a set selection producing no cards or
   no oracle tags. Submit a stale/unknown-tag result POST and verify the
   analysis-page alert is announced, focus moves to the alert/tag/recovery
   target, and the viewer is not opened.
6. In a normal browser, verify there are no set-mode JavaScript errors, the
   Cancel button is visibly usable before the fast-loading auto-submit path,
    focus reaches it and returns after cancellation, reduced-motion behavior
    remains usable with the logo pulse and validation shake disabled, the
    picker and OR/AND controls work from the keyboard, the no-tag error is
    announced and focuses the tag controls (or the slider when all tags are
    hidden), and a screen reader announces the validation/status/state changes.
    With hostile fixture labels/types/tags, verify values remain text and no
    markup executes when picker or filter summaries update.
7. During a simulated database outage, verify **Try Again** and **Start Over**
   return the accessible 503 page rather than a server error.
8. Run `python manage.py test` and verify the unrelated
   `scripts/entrypoint-autoupdate.sh` change is still present and untouched.

## Rollout and fallback

The feature is additive and requires no migration or external service. If a
regression appears, disable/remove the new entry point and routes while retaining
the existing deck path; the existing card viewer and database schema remain
usable. The design and implementation should be shipped together so the new
route does not point at missing templates.

## Unresolved decisions

- This design assumes “set(s)” means one aggregated union, not separate
  per-set analyses. If a per-set comparison is desired, the analysis data model
  and UX need a material expansion.
- This design assumes set mode should omit deck format/color filters. If the
  intended set workflow should still filter by a format or color identity, that
  choice should be made before implementation because it changes the form,
  summary, and result query contract.
