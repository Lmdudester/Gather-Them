import re
from collections import Counter

from .oracle_patterns import ORACLE_PATTERNS, ORACLE_PATTERN_EXCLUDE_TYPES


# Keywords that are non-thematic / not useful for deck-building discovery
_SKIP_KEYWORDS = {
    'Transform', 'Aftermath', 'Meld', 'Daybound', 'Nightbound',
    'Disturb', 'More Than Meets the Eye', 'Living Metal',
    'Convert', 'Specialize', 'Fuse', 'Split second',
}

# Basic land subtypes — too common to be useful as deck themes
_SKIP_SUBTYPES = {'Plains', 'Island', 'Swamp', 'Mountain', 'Forest'}


def extract_themes(cards_with_qty):
    """Extract and rank themes from a deck's cards.

    Args:
        cards_with_qty: List of (quantity, card_data_dict) tuples.

    Returns:
        dict with keys 'Subtype', 'Keyword', 'Card Type', 'Oracle Pattern',
        each mapping to a list of (theme_name, count) sorted by count descending.
        Also returns 'color_identity' as the union of all cards' color identities.
    """
    subtype_counts = Counter()
    keyword_counts = Counter()
    card_type_counts = Counter()
    oracle_counts = Counter()
    color_identity = set()

    total_cards = sum(qty for qty, _ in cards_with_qty)

    for qty, card in cards_with_qty:
        # Subtypes (skip basic land subtypes)
        for st in card.get('subtypes', []):
            if st not in _SKIP_SUBTYPES:
                subtype_counts[st] += qty

        # Keywords (skip non-thematic ones)
        for kw in card.get('keywords', []):
            if kw not in _SKIP_KEYWORDS:
                keyword_counts[kw] += qty

        # Card types (skip "Land" — handled separately)
        for ct in card.get('types', []):
            if ct != 'Land':
                card_type_counts[ct] += qty

        # Color identity
        for c in card.get('colorIdentity', []):
            color_identity.add(c)

        # Oracle text patterns
        text = card.get('text') or ''
        if text:
            text_lower = text.lower()
            card_types = set(card.get('types', []))
            for pattern, label in ORACLE_PATTERNS:
                excluded = ORACLE_PATTERN_EXCLUDE_TYPES.get(label)
                if excluded and card_types & excluded:
                    continue
                if re.search(pattern, text_lower):
                    oracle_counts[label] += qty

    # Filter out themes appearing only once when deck has 10+ cards
    min_count = 2 if total_cards >= 10 else 1

    def _filter_and_sort(counter):
        return sorted(
            [(name, count) for name, count in counter.items() if count >= min_count],
            key=lambda x: (-x[1], x[0]),
        )

    return {
        'Subtype': _filter_and_sort(subtype_counts),
        'Keyword': _filter_and_sort(keyword_counts),
        'Card Type': _filter_and_sort(card_type_counts),
        'Oracle Pattern': _filter_and_sort(oracle_counts),
        'color_identity': sorted(color_identity),
    }
