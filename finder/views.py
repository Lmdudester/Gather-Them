import json
import logging
import math
import threading
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import DecklistForm
from .middleware import is_maintenance_mode, set_maintenance_mode, set_update_result
from .services.card_lookup import (
    get_random_flavor_text, get_set_cards, get_set_lands, lookup_cards,
)
from .services.db_updater import DatabaseUpdateError, update_database
from .services.deck_parser import parse_decklist
from .services.set_filter import filter_cards_by_tags
from .services.theme_extractor import extract_themes

logger = logging.getLogger(__name__)


def _is_admin(request):
    """Check whether the current request has admin privileges."""
    if request.user.is_authenticated and request.user.is_staff:
        return True
    admin_secret = getattr(settings, 'ADMIN_SECRET', '')
    if admin_secret and request.GET.get('admin') == admin_secret:
        return True
    return False


def _run_update():
    """Background worker for database update."""
    try:
        update_database()
        set_update_result('success', 'Database updated successfully.')
    except DatabaseUpdateError as e:
        logger.error('Database update failed: %s', e)
        set_update_result('error', f'Database update failed: {e}')
    finally:
        set_maintenance_mode(False)


@require_POST
def refresh_patterns(request):
    """Reload oracle text patterns from the JSON config file."""
    if not _is_admin(request):
        return HttpResponse('Forbidden', status=403)
    from .services.oracle_patterns import refresh_cache
    try:
        refresh_cache()
        messages.success(request, 'Oracle patterns refreshed successfully.')
    except Exception as e:
        messages.error(request, f'Failed to refresh oracle patterns: {e}')
    url = reverse('finder:index')
    admin_token = request.GET.get('admin', '')
    if admin_token:
        url = f"{url}?admin={admin_token}"
    return redirect(url)


@require_POST
def update_db(request):
    """Kick off a background database update and redirect to maintenance page."""
    if not _is_admin(request):
        return HttpResponse('Forbidden', status=403)

    url = reverse('finder:index')
    admin_token = request.GET.get('admin', '')
    if admin_token:
        url = f"{url}?admin={admin_token}"

    if is_maintenance_mode():
        messages.warning(request, 'A database update is already in progress.')
        return redirect(url)

    set_maintenance_mode(True)
    threading.Thread(target=_run_update, daemon=True).start()
    return redirect(url)


def random_flavor(request):
    """API endpoint returning a random card flavor text as JSON."""
    result = get_random_flavor_text()
    if result:
        return JsonResponse(result)
    return JsonResponse({'error': 'No flavor text found'}, status=404)


TIER_LABELS = ['Core', 'Strong', 'Moderate', 'Minor', 'Fringe']
NUM_TIERS = len(TIER_LABELS)


def _tier_themes(theme_list):
    """Split a sorted (name, count) list into tier columns.

    Uses dynamic thresholds based on the count distribution so that
    higher tiers are harder to reach (exponential spacing). Returns a
    list of (label, min_count, items) tuples, omitting empty tiers.
    """
    if not theme_list:
        return []

    counts = [c for _, c in theme_list]
    max_count = counts[0]
    min_count = counts[-1]

    if max_count == min_count:
        # Everything has the same count — single tier
        return [(TIER_LABELS[0], 1, list(theme_list))]

    # Build thresholds using exponential spacing so top tiers are selective.
    # Tier 0 (Core):     >= ~70% of max
    # Tier 1 (Strong):   >= ~45% of max
    # Tier 2 (Moderate): >= ~25% of max
    # Tier 3 (Minor):    >= ~12% of max
    # Tier 4 (Fringe):   the rest
    #
    # We use a log-based approach: map counts into log-space, divide
    # that range evenly into NUM_TIERS bands. This naturally makes the
    # upper tiers narrower (harder to reach) and lower tiers wider.
    log_max = math.log(max_count + 1)
    log_min = math.log(min_count)
    band = (log_max - log_min) / NUM_TIERS

    thresholds = []
    for i in range(NUM_TIERS):
        t = math.exp(log_max - band * (i + 1))
        thresholds.append(t)

    # Assign items to tiers
    tiers = [[] for _ in range(NUM_TIERS)]
    for name, count in theme_list:
        placed = False
        for i in range(NUM_TIERS - 1):
            if count >= thresholds[i]:
                tiers[i].append((name, count))
                placed = True
                break
        if not placed:
            tiers[NUM_TIERS - 1].append((name, count))

    # Build result, skipping empty tiers. Include 1-based tier index for CSS.
    result = []
    for i, items in enumerate(tiers):
        if items:
            result.append((TIER_LABELS[i], i + 1, items))
    return result


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


def analyze(request):
    """Step 2: Parse decklist, extract themes, show checkboxes."""
    if request.method != 'POST':
        return render(request, 'finder/index.html', {'form': DecklistForm()})

    form = DecklistForm(request.POST)
    if not form.is_valid():
        return render(request, 'finder/index.html', {'form': form})

    decklist_text = form.cleaned_data['decklist']
    set_codes = form.cleaned_data['set_code']  # now a list
    format_name = form.cleaned_data['format_name']

    # Parse the decklist
    entries = parse_decklist(decklist_text)
    if not entries:
        form.add_error('decklist', 'Could not parse any cards from the decklist.')
        return render(request, 'finder/index.html', {'form': form})

    # Look up cards in database
    card_names = [name for _, name in entries]
    found_cards, unfound_names = lookup_cards(card_names)

    # Build cards_with_qty for theme extraction
    cards_with_qty = []
    for qty, name in entries:
        if name in found_cards:
            cards_with_qty.append((qty, found_cards[name]))

    # Extract themes
    themes = extract_themes(cards_with_qty)
    color_identity = themes.pop('color_identity')

    # Stats
    total_in_list = len(entries)
    total_found = len(found_cards)

    # Get set display names
    from .services.card_lookup import get_sets_for_dropdown
    sets_lookup = dict(get_sets_for_dropdown())
    set_displays = [sets_lookup.get(code, code.upper()) for code in set_codes]

    # Get format display name
    from .forms import FORMAT_CHOICES
    format_display = format_name
    for val, label in FORMAT_CHOICES:
        if val == format_name:
            format_display = label
            break

    # Tier themes into columns per category
    tiered_themes = {}
    for category, theme_list in themes.items():
        tiered_themes[category] = _tier_themes(theme_list)

    # Merge all themes into a single list for the combined view
    merged_themes = []
    for category, theme_list in themes.items():
        for name, count in theme_list:
            merged_themes.append((f'{category}:{name}', count))
    merged_themes.sort(key=lambda x: (-x[1], x[0]))
    merged_tiers = _tier_themes(merged_themes)
    max_concept_count = merged_themes[0][1] if merged_themes else 2

    deck_card_names = [card['name'] for card in found_cards.values()]

    context = {
        'tiered_themes': tiered_themes,
        'merged_tiers': merged_tiers,
        'max_concept_count': max_concept_count,
        'set_codes_json': json.dumps(set_codes),
        'set_displays': set_displays,
        'format_name': format_name,
        'format_display': format_display,
        'color_identity': color_identity,
        'color_identity_json': json.dumps(color_identity),
        'deck_card_names_json': json.dumps(deck_card_names),
        'total_in_list': total_in_list,
        'total_found': total_found,
        'unfound_names': unfound_names,
        'decklist_text': decklist_text,
        'selected_tags_json': json.dumps(request.POST.getlist('selected_tags')).replace('</', '<\\/'),
        'include_lands': request.POST.get('include_lands') == '1',
    }
    return render(request, 'finder/analysis.html', context)


def results(request):
    """Step 3: Show matching cards from target set."""
    if request.method != 'POST':
        return render(request, 'finder/index.html', {'form': DecklistForm()})

    selected_tags = request.POST.getlist('tags')
    include_lands = request.POST.get('include_lands') == '1'
    decklist_text = request.POST.get('decklist_text', '')
    set_codes_json = request.POST.get('set_codes', '[]')
    format_name = request.POST.get('format_name', '')
    color_identity_json = request.POST.get('color_identity', '[]')
    deck_card_names_json = request.POST.get('deck_card_names', '[]')

    try:
        set_codes = json.loads(set_codes_json)
    except (json.JSONDecodeError, TypeError):
        set_codes = []

    try:
        color_identity = json.loads(color_identity_json)
    except (json.JSONDecodeError, TypeError):
        color_identity = []

    try:
        deck_card_names = set(json.loads(deck_card_names_json))
    except (json.JSONDecodeError, TypeError):
        deck_card_names = set()

    if (not selected_tags and not include_lands) or not set_codes:
        messages.error(request, 'Please select at least one theme tag or include lands.')
        return redirect('finder:index')

    # Get cards from target sets with format + color filtering
    set_cards = get_set_cards(
        set_codes,
        format_name=format_name or None,
        deck_color_identity=color_identity if color_identity else None,
    )

    # Filter by selected tags
    matched_results = filter_cards_by_tags(set_cards, selected_tags)

    # Exclude basic lands
    matched_results = [
        (card, tags, count) for card, tags, count in matched_results
        if 'Basic' not in card.get('supertypes', [])
    ]

    # Exclude cards already in the user's deck
    if deck_card_names:
        matched_results = [
            (card, tags, count) for card, tags, count in matched_results
            if card.get('name') not in deck_card_names
        ]

    # Merge lands if requested
    if include_lands:
        land_cards = get_set_lands(
            set_codes,
            format_name=format_name or None,
            deck_color_identity=color_identity if color_identity else None,
        )

        # Exclude deck cards from lands too
        if deck_card_names:
            land_cards = [c for c in land_cards if c.get('name') not in deck_card_names]

        # Build lookup of already-matched card names for dedup
        matched_names = {card.get('name') for card, _, _ in matched_results}

        for land in land_cards:
            name = land.get('name')
            if name in matched_names:
                # Already in results — add "Land" to its matched tags
                for i, (card, tags, count) in enumerate(matched_results):
                    if card.get('name') == name and 'Land' not in tags:
                        tags.append('Land')
                        matched_results[i] = (card, tags, count + 1)
                        break
            else:
                # New result with "Land" tag
                matched_results.append((land, ['Land'], 1))
                matched_names.add(name)

        # Re-sort after merging
        matched_results.sort(key=lambda x: (-x[2], x[0].get('name', '')))

    # Pre-compute filter data attributes on each card and collect distinct values
    rarity_order = ['common', 'uncommon', 'rare', 'mythic']
    filter_types_set = set()
    filter_rarities_set = set()
    filter_mv_set = set()
    filter_power_set = set()
    filter_toughness_set = set()
    filter_tags_by_category = {}
    for card, matched_tags, _ in matched_results:
        for t in card.get('types', []):
            filter_types_set.add(t)
        rarity = (card.get('rarity') or '').lower()
        if rarity:
            filter_rarities_set.add(rarity)
        mv_raw = int(float(card.get('manaValue') or 0))
        mv_display = '7+' if mv_raw >= 7 else str(mv_raw)
        card['mv_display'] = mv_display
        filter_mv_set.add(mv_display)

        # Power/Toughness bucketing
        power_raw = card.get('power')
        toughness_raw = card.get('toughness')
        if power_raw is not None:
            try:
                p = int(float(power_raw))
                card['power_display'] = '7+' if p >= 7 else str(p)
            except (ValueError, TypeError):
                card['power_display'] = '*'
            filter_power_set.add(card['power_display'])
        else:
            card['power_display'] = ''

        if toughness_raw is not None:
            try:
                t_val = int(float(toughness_raw))
                card['toughness_display'] = '7+' if t_val >= 7 else str(t_val)
            except (ValueError, TypeError):
                card['toughness_display'] = '*'
            filter_toughness_set.add(card['toughness_display'])
        else:
            card['toughness_display'] = ''

        for tag in matched_tags:
            category = tag.split(':', 1)[0] if ':' in tag else 'Other'
            filter_tags_by_category.setdefault(category, set()).add(tag)

    filter_types = sorted(filter_types_set)
    filter_rarities = [r for r in rarity_order if r in filter_rarities_set]
    # Sort MV values: numeric first, then 7+
    filter_mvs = sorted(filter_mv_set, key=lambda x: (x == '7+', int(x.rstrip('+'))))
    # Sort P/T values: * first, then numeric, then 7+
    def _pt_sort_key(x):
        if x == '*':
            return (0, 0)
        if x == '7+':
            return (2, 7)
        return (1, int(x))
    filter_powers = sorted(filter_power_set, key=_pt_sort_key)
    filter_toughnesses = sorted(filter_toughness_set, key=_pt_sort_key)

    # Group tags by category in a stable order, skipping categories
    # that already have their own dedicated filter section
    skip_categories = {'Card Type'}  # covered by the Type filter
    category_order = ['Subtype', 'Keyword', 'Supertype', 'Oracle Pattern', 'Stat Profile']
    filter_tags_grouped = []
    for cat in category_order:
        if cat in filter_tags_by_category:
            filter_tags_grouped.append((cat, sorted(filter_tags_by_category[cat])))
    for cat in sorted(filter_tags_by_category):
        if cat not in category_order and cat not in skip_categories:
            filter_tags_grouped.append((cat, sorted(filter_tags_by_category[cat])))

    # Get set display names
    from .services.card_lookup import get_sets_for_dropdown
    sets_lookup = dict(get_sets_for_dropdown())
    set_displays = [sets_lookup.get(code, code.upper()) for code in set_codes]

    # Format display
    from .forms import FORMAT_CHOICES
    format_display = format_name
    for val, label in FORMAT_CHOICES:
        if val == format_name:
            format_display = label
            break

    context = {
        'results': matched_results,
        'selected_tags': selected_tags,
        'include_lands': include_lands,
        'set_codes_json': json.dumps(set_codes),
        'set_displays': set_displays,
        'format_name': format_name,
        'format_display': format_display,
        'color_identity': color_identity,
        'total_set_cards': len(set_cards),
        'total_matched': len(matched_results),
        'filter_types': filter_types,
        'filter_rarities': filter_rarities,
        'filter_mvs': filter_mvs,
        'filter_powers': filter_powers,
        'filter_toughnesses': filter_toughnesses,
        'filter_tags_grouped': filter_tags_grouped,
        'deck_card_names_json': deck_card_names_json,
        'decklist_text_json': json.dumps(decklist_text).replace('</', '<\\/'),
        'selected_tags_json': json.dumps(selected_tags).replace('</', '<\\/'),
    }
    return render(request, 'finder/results.html', context)
