import json
import logging
import math
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import FORMAT_CHOICES, DecklistForm, SetAnalysisForm
from .middleware import is_maintenance_mode, set_maintenance_mode, set_update_result
from .services.card_lookup import (
    DatabaseUnavailableError,
    check_set_flow_database,
    get_random_flavor_text,
    get_set_cards,
    get_set_lands,
    get_sets_for_dropdown,
    invalidate_sets_cache,
    lookup_cards,
)
from .services.db_updater import DatabaseUpdateError, update_database
from .services.deck_parser import parse_decklist
from .services.oracle_patterns import get_oracle_patterns
from .services.set_filter import filter_cards_by_tags
from .services.set_selection import MAX_SET_SELECTIONS, normalize_set_codes
from .services.theme_extractor import extract_oracle_patterns, extract_themes

logger = logging.getLogger(__name__)

_DATABASE_ERRORS = (DatabaseUnavailableError, sqlite3.Error, OSError, TypeError, ValueError)
COLOR_FILTER_OPTIONS = (
    ('W', 'White'),
    ('U', 'Blue'),
    ('B', 'Black'),
    ('R', 'Red'),
    ('G', 'Green'),
    ('C', 'Colorless'),
)


def _run_update():
    """Background worker for database update."""
    try:
        update_database()
        invalidate_sets_cache()
        set_update_result('success', 'Database updated successfully.')
    except DatabaseUpdateError as e:
        logger.error('Database update failed: %s', e)
        set_update_result('error', f'Database update failed: {e}')
    finally:
        set_maintenance_mode(False)


@require_POST
def refresh_patterns(request):
    """Reload oracle text patterns; this maintenance action is public."""
    from .services.oracle_patterns import refresh_cache
    try:
        refresh_cache()
        messages.success(request, 'Oracle patterns refreshed successfully.')
    except Exception as e:
        messages.error(request, f'Failed to refresh oracle patterns: {e}')
    return redirect(reverse('finder:index'))


@require_POST
def update_db(request):
    """Start a public background database update and redirect home."""
    url = reverse('finder:index')
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
    """Split a sorted (name, count) list into tier columns."""
    if not theme_list:
        return []

    counts = [count for _, count in theme_list]
    max_count = counts[0]
    min_count = counts[-1]
    if max_count == min_count:
        return [(TIER_LABELS[0], 1, list(theme_list))]

    log_max = math.log(max_count + 1)
    log_min = math.log(min_count)
    band = (log_max - log_min) / NUM_TIERS
    thresholds = [
        math.exp(log_max - band * (i + 1))
        for i in range(NUM_TIERS)
    ]

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

    return [
        (TIER_LABELS[i], i + 1, items)
        for i, items in enumerate(tiers)
        if items
    ]


def _database_unavailable_response(request):
    """Render the database-independent recovery page."""
    return render(request, 'finder/database-unavailable.html', status=503)


def _database_guard(request):
    """Return a 503 response when the set-flow database probe fails."""
    try:
        check_set_flow_database()
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable')
        return _database_unavailable_response(request)
    return None


def _set_display_names(set_codes):
    sets_lookup = dict(get_sets_for_dropdown())
    return [sets_lookup.get(code, code.upper()) for code in set_codes]


def _format_display(format_name):
    for value, label in FORMAT_CHOICES:
        if value == format_name:
            return label
    return format_name


def _canonical_set_oracle_tags(raw_tags):
    """Keep known oracle-pattern tags, deduplicated in submitted order."""
    valid_labels = {label for _, label in get_oracle_patterns()}
    canonical = []
    seen = set()
    for raw_tag in raw_tags:
        if not isinstance(raw_tag, str) or ':' not in raw_tag:
            continue
        category, label = raw_tag.split(':', 1)
        if category.strip() != 'Oracle Pattern':
            continue
        label = label.strip()
        if label not in valid_labels:
            continue
        tag = f'Oracle Pattern:{label}'
        if tag not in seen:
            seen.add(tag)
            canonical.append(tag)
    return canonical


def _set_analysis_context(request, set_codes, set_cards, selected_tags=None, error=None):
    """Build the mode-specific context for the shared analysis template."""
    oracle_themes = extract_oracle_patterns(set_cards)
    merged_themes = [
        (f'Oracle Pattern:{name}', count)
        for name, count in oracle_themes
    ]
    max_count = oracle_themes[0][1] if oracle_themes else 0
    return {
        'analysis_mode': 'set',
        'set_mode': True,
        'set_cards': set_cards,
        'total_set_cards': len(set_cards),
        'set_codes': set_codes,
        'set_codes_json': json.dumps(set_codes),
        'set_displays': _set_display_names(set_codes),
        'merged_tiers': _tier_themes(merged_themes),
        'max_concept_count': max_count,
        'set_relevance_max': max_count + 1 if max_count else 1,
        'selected_tags_data': selected_tags or [],
        'analysis_error': error,
    }


def index(request):
    """Step 1: Paste decklist, select set and format."""
    database_error = _database_guard(request)
    if database_error:
        return database_error
    try:
        form = DecklistForm()
        db_path = Path(settings.MTGJSON_DB_PATH)
        db_updated = None
        if db_path.exists():
            db_updated = datetime.fromtimestamp(db_path.stat().st_mtime)
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable while rendering homepage')
        return _database_unavailable_response(request)
    return render(request, 'finder/index.html', {
        'form': form,
        'db_updated': db_updated,
    })


def set_index(request):
    """Render the direct set-only analysis entry page."""
    database_error = _database_guard(request)
    if database_error:
        return database_error
    try:
        form = SetAnalysisForm()
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable while rendering set entry')
        return _database_unavailable_response(request)
    return render(request, 'finder/set_index.html', {'form': form})


def analyze(request):
    """Step 2: Parse decklist, extract themes, show checkboxes."""
    if request.method != 'POST':
        try:
            return render(request, 'finder/index.html', {'form': DecklistForm()})
        except _DATABASE_ERRORS:
            logger.exception('MTGJSON database unavailable while rendering deck entry')
            return _database_unavailable_response(request)

    try:
        form = DecklistForm(request.POST)
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable while validating deck entry')
        return _database_unavailable_response(request)
    if not form.is_valid():
        return render(request, 'finder/index.html', {'form': form})

    decklist_text = form.cleaned_data['decklist']
    set_codes = form.cleaned_data['set_code']
    format_name = form.cleaned_data['format_name']
    entries = parse_decklist(decklist_text)
    if not entries:
        form.add_error('decklist', 'Could not parse any cards from the decklist.')
        return render(request, 'finder/index.html', {'form': form})

    try:
        found_cards, unfound_names = lookup_cards([name for _, name in entries])
        cards_with_qty = [
            (qty, found_cards[name])
            for qty, name in entries
            if name in found_cards
        ]
        themes = extract_themes(cards_with_qty)
        color_identity = themes.pop('color_identity')
        set_displays = _set_display_names(set_codes)
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable during deck analysis')
        return _database_unavailable_response(request)

    tiered_themes = {
        category: _tier_themes(theme_list)
        for category, theme_list in themes.items()
    }
    merged_themes = []
    for category, theme_list in themes.items():
        for name, count in theme_list:
            merged_themes.append((f'{category}:{name}', count))
    merged_themes.sort(key=lambda item: (-item[1], item[0]))
    deck_card_names = [card['name'] for card in found_cards.values()]

    context = {
        'analysis_mode': 'deck',
        'set_mode': False,
        'tiered_themes': tiered_themes,
        'merged_tiers': _tier_themes(merged_themes),
        'max_concept_count': merged_themes[0][1] if merged_themes else 2,
        'set_codes': set_codes,
        'set_codes_json': json.dumps(set_codes),
        'set_displays': set_displays,
        'format_name': format_name,
        'format_display': _format_display(format_name),
        'color_identity': color_identity,
        'color_identity_json': json.dumps(color_identity),
        'deck_card_names': deck_card_names,
        'deck_card_names_json': json.dumps(deck_card_names),
        'total_in_list': len(entries),
        'total_found': len(found_cards),
        'unfound_names': unfound_names,
        'decklist_text': decklist_text,
        'decklist_text_json': json.dumps(decklist_text),
        'selected_tags_data': request.POST.getlist('selected_tags'),
        'include_lands': request.POST.get('include_lands') == '1',
    }
    return render(request, 'finder/analysis.html', context)


def set_analyze(request):
    """Analyze the oracle text of a validated aggregate set selection."""
    if request.method != 'POST':
        return redirect('finder:set_index')
    database_error = _database_guard(request)
    if database_error:
        return database_error
    try:
        form = SetAnalysisForm(request.POST)
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable while validating set entry')
        return _database_unavailable_response(request)
    if not form.is_valid():
        return render(request, 'finder/set_index.html', {'form': form})

    set_codes = form.cleaned_data['set_code']
    selected_tags = _canonical_set_oracle_tags(request.POST.getlist('selected_tags'))
    try:
        set_cards = get_set_cards(set_codes, max_set_codes=MAX_SET_SELECTIONS)
        context = _set_analysis_context(
            request,
            set_codes,
            set_cards,
            selected_tags=selected_tags,
        )
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable during set analysis')
        invalidate_sets_cache()
        return _database_unavailable_response(request)
    return render(request, 'finder/analysis.html', context)


def _load_json_list(raw_value):
    try:
        value = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, list) else None


def _prepare_results_context(
    request,
    *,
    matched_results,
    selected_tags,
    set_codes,
    set_cards,
    set_mode=False,
    include_lands=False,
    format_name='',
    color_identity=None,
    deck_card_names_json='[]',
    decklist_text='',
):
    """Prepare filter metadata shared by deck and set-mode card viewers."""
    color_identity = color_identity or []
    rarity_order = ['common', 'uncommon', 'rare', 'mythic']
    filter_types_set = set()
    filter_rarities_set = set()
    filter_mv_set = set()
    filter_power_set = set()
    filter_toughness_set = set()
    filter_colors_set = set()
    filter_tags_by_category = {}

    for card, matched_tags, _ in matched_results:
        filter_types_set.update(card.get('types', []))
        card_colors = card.get('colorIdentity') or []
        if isinstance(card_colors, str):
            card_colors = [card_colors]
        card_colors = [str(color).upper() for color in card_colors]
        card['colorIdentity'] = [
            color for color, _ in COLOR_FILTER_OPTIONS if color != 'C' and color in card_colors
        ]
        if card['colorIdentity']:
            filter_colors_set.update(card['colorIdentity'])
        else:
            filter_colors_set.add('C')
        rarity = (card.get('rarity') or '').lower()
        if rarity:
            filter_rarities_set.add(rarity)
        mv_raw = int(float(card.get('manaValue') or 0))
        card['mv_display'] = '7+' if mv_raw >= 7 else str(mv_raw)
        filter_mv_set.add(card['mv_display'])

        power_raw = card.get('power')
        toughness_raw = card.get('toughness')
        if power_raw is not None:
            try:
                power = int(float(power_raw))
                card['power_display'] = '7+' if power >= 7 else str(power)
            except (ValueError, TypeError):
                card['power_display'] = '*'
            filter_power_set.add(card['power_display'])
        else:
            card['power_display'] = ''
        if toughness_raw is not None:
            try:
                toughness = int(float(toughness_raw))
                card['toughness_display'] = '7+' if toughness >= 7 else str(toughness)
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
    filter_mvs = sorted(
        filter_mv_set,
        key=lambda value: (value == '7+', int(value.rstrip('+'))),
    )

    def _pt_sort_key(value):
        if value == '*':
            return (0, 0)
        if value == '7+':
            return (2, 7)
        return (1, int(value))

    filter_powers = sorted(filter_power_set, key=_pt_sort_key)
    filter_toughnesses = sorted(filter_toughness_set, key=_pt_sort_key)
    filter_colors = [
        option for option in COLOR_FILTER_OPTIONS
        if option[0] in filter_colors_set
    ]
    category_order = [
        'Subtype', 'Keyword', 'Supertype', 'Oracle Pattern', 'Stat Profile',
    ]
    filter_tags_grouped = []
    for category in category_order:
        if category in filter_tags_by_category:
            filter_tags_grouped.append(
                (category, sorted(filter_tags_by_category[category]))
            )
    for category in sorted(filter_tags_by_category):
        if category not in category_order and category != 'Card Type':
            filter_tags_grouped.append(
                (category, sorted(filter_tags_by_category[category]))
            )

    return {
        'results': matched_results,
        'selected_tags': selected_tags,
        'selected_tags_data': selected_tags,
        'include_lands': include_lands,
        'set_mode': set_mode,
        'analysis_mode': 'set' if set_mode else 'deck',
        'set_codes': set_codes,
        'set_displays': _set_display_names(set_codes),
        'format_name': format_name,
        'format_display': _format_display(format_name),
        'color_identity': color_identity,
        'total_set_cards': len(set_cards),
        'total_matched': len(matched_results),
        'filter_types': filter_types,
        'filter_rarities': filter_rarities,
        'filter_mvs': filter_mvs,
        'filter_powers': filter_powers,
        'filter_toughnesses': filter_toughnesses,
        'filter_colors': filter_colors,
        'filter_tags_grouped': filter_tags_grouped,
        'deck_card_names_json': deck_card_names_json,
        'decklist_text': decklist_text,
    }


def set_results(request):
    """Render set-mode results from validated hidden set/tag state."""
    if request.method != 'POST':
        return redirect('finder:set_index')
    database_error = _database_guard(request)
    if database_error:
        return database_error

    raw_set_codes = _load_json_list(request.POST.get('set_codes', ''))
    if raw_set_codes is None:
        messages.error(request, 'That set analysis state is invalid. Choose your sets again.')
        return redirect('finder:set_index')
    try:
        set_form = SetAnalysisForm({'set_code': raw_set_codes})
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable while validating set results')
        return _database_unavailable_response(request)
    if not set_form.is_valid():
        messages.error(request, 'Those sets are no longer available. Choose your sets again.')
        return redirect('finder:set_index')

    set_codes = set_form.cleaned_data['set_code']
    selected_tags = _canonical_set_oracle_tags(request.POST.getlist('tags'))
    try:
        set_cards = get_set_cards(set_codes, max_set_codes=MAX_SET_SELECTIONS)
        if not selected_tags:
            context = _set_analysis_context(
                request,
                set_codes,
                set_cards,
                error=(
                    'The selected oracle tags are no longer available. '
                    'Choose at least one current tag to continue.'
                ),
            )
            return render(request, 'finder/analysis.html', context)

        matched_results = filter_cards_by_tags(
            set_cards,
            selected_tags,
            apply_oracle_exclusions=True,
        )
        context = _prepare_results_context(
            request,
            matched_results=matched_results,
            selected_tags=selected_tags,
            set_codes=set_codes,
            set_cards=set_cards,
            set_mode=True,
        )
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable during set results')
        invalidate_sets_cache()
        return _database_unavailable_response(request)
    return render(request, 'finder/results.html', context)


def results(request):
    """Step 3: Show matching cards from target set for deck mode."""
    if request.method != 'POST':
        return index(request)

    selected_tags = request.POST.getlist('tags')
    include_lands = request.POST.get('include_lands') == '1'
    try:
        decklist_text = json.loads(request.POST.get('decklist_text', '""'))
    except (json.JSONDecodeError, TypeError):
        decklist_text = ''
    if not isinstance(decklist_text, str):
        decklist_text = ''
    set_codes = _load_json_list(request.POST.get('set_codes', '[]'))
    color_identity = _load_json_list(request.POST.get('color_identity', '[]')) or []
    color_identity = [value for value in color_identity if isinstance(value, str)]
    deck_card_names = _load_json_list(request.POST.get('deck_card_names', '[]')) or []
    deck_card_names = {name for name in deck_card_names if isinstance(name, str)}
    format_name = request.POST.get('format_name', '')

    if set_codes is None:
        messages.error(request, 'That deck analysis state is invalid. Start over.')
        return redirect('finder:index')
    try:
        # No max_count here: the set-mode cap must not change deck behavior.
        set_codes = normalize_set_codes(set_codes)
    except ValueError:
        messages.error(request, 'That deck analysis state is invalid. Start over.')
        return redirect('finder:index')
    if (not selected_tags and not include_lands) or not set_codes:
        messages.error(request, 'Please select at least one theme tag or include lands.')
        return redirect('finder:index')

    try:
        set_cards = get_set_cards(
            set_codes,
            format_name=format_name or None,
            deck_color_identity=color_identity if color_identity else None,
        )
        matched_results = filter_cards_by_tags(set_cards, selected_tags)
        matched_results = [
            (card, tags, count)
            for card, tags, count in matched_results
            if 'Basic' not in card.get('supertypes', [])
        ]
        if deck_card_names:
            matched_results = [
                (card, tags, count)
                for card, tags, count in matched_results
                if card.get('name') not in deck_card_names
            ]

        if include_lands:
            land_cards = get_set_lands(
                set_codes,
                format_name=format_name or None,
                deck_color_identity=color_identity if color_identity else None,
            )
            if deck_card_names:
                land_cards = [
                    card for card in land_cards
                    if card.get('name') not in deck_card_names
                ]
            matched_names = {card.get('name') for card, _, _ in matched_results}
            for land in land_cards:
                name = land.get('name')
                if name in matched_names:
                    for i, (card, tags, count) in enumerate(matched_results):
                        if card.get('name') == name and 'Land' not in tags:
                            tags.append('Land')
                            matched_results[i] = (card, tags, count + 1)
                            break
                else:
                    matched_results.append((land, ['Land'], 1))
                    matched_names.add(name)
            matched_results.sort(key=lambda item: (-item[2], item[0].get('name', '')))

        context = _prepare_results_context(
            request,
            matched_results=matched_results,
            selected_tags=selected_tags,
            set_codes=set_codes,
            set_cards=set_cards,
            set_mode=False,
            include_lands=include_lands,
            format_name=format_name,
            color_identity=color_identity,
            deck_card_names_json=request.POST.get('deck_card_names', '[]'),
            decklist_text=decklist_text,
        )
    except _DATABASE_ERRORS:
        logger.exception('MTGJSON database unavailable while rendering deck results')
        invalidate_sets_cache()
        return _database_unavailable_response(request)
    return render(request, 'finder/results.html', context)
