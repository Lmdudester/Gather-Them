import json
import math

from django.shortcuts import render

from .forms import DecklistForm
from .services.card_lookup import get_set_cards, lookup_cards
from .services.deck_parser import parse_decklist
from .services.set_filter import filter_cards_by_tags
from .services.theme_extractor import extract_themes

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
    return render(request, 'finder/index.html', {'form': form})


def analyze(request):
    """Step 2: Parse decklist, extract themes, show checkboxes."""
    if request.method != 'POST':
        return render(request, 'finder/index.html', {'form': DecklistForm()})

    form = DecklistForm(request.POST)
    if not form.is_valid():
        return render(request, 'finder/index.html', {'form': form})

    decklist_text = form.cleaned_data['decklist']
    set_code = form.cleaned_data['set_code']
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

    # Get the set name for display
    from .services.card_lookup import get_sets_for_dropdown
    sets_list = get_sets_for_dropdown()
    set_display = set_code.upper()
    for code, display in sets_list:
        if code == set_code:
            set_display = display
            break

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

    context = {
        'tiered_themes': tiered_themes,
        'set_code': set_code,
        'set_display': set_display,
        'format_name': format_name,
        'format_display': format_display,
        'color_identity': color_identity,
        'color_identity_json': json.dumps(color_identity),
        'total_in_list': total_in_list,
        'total_found': total_found,
        'unfound_names': unfound_names,
    }
    return render(request, 'finder/analysis.html', context)


def results(request):
    """Step 3: Show matching cards from target set."""
    if request.method != 'POST':
        return render(request, 'finder/index.html', {'form': DecklistForm()})

    selected_tags = request.POST.getlist('tags')
    set_code = request.POST.get('set_code', '')
    format_name = request.POST.get('format_name', '')
    color_identity_json = request.POST.get('color_identity', '[]')

    try:
        color_identity = json.loads(color_identity_json)
    except (json.JSONDecodeError, TypeError):
        color_identity = []

    if not selected_tags or not set_code:
        return render(request, 'finder/index.html', {
            'form': DecklistForm(),
            'error': 'Please select at least one theme tag.',
        })

    # Get cards from target set with format + color filtering
    set_cards = get_set_cards(
        set_code,
        format_name=format_name or None,
        deck_color_identity=color_identity if color_identity else None,
    )

    # Filter by selected tags
    matched_results = filter_cards_by_tags(set_cards, selected_tags)

    # Get set display name
    from .services.card_lookup import get_sets_for_dropdown
    sets_list = get_sets_for_dropdown()
    set_display = set_code.upper()
    for code, display in sets_list:
        if code == set_code:
            set_display = display
            break

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
        'set_code': set_code,
        'set_display': set_display,
        'format_name': format_name,
        'format_display': format_display,
        'color_identity': color_identity,
        'total_set_cards': len(set_cards),
        'total_matched': len(matched_results),
    }
    return render(request, 'finder/results.html', context)
