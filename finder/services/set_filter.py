import re

from .oracle_patterns import ORACLE_PATTERN_MAP


def filter_cards_by_tags(cards, selected_tags):
    """Filter and rank set cards by selected theme tags.

    Args:
        cards: List of card dicts (from card_lookup.get_set_cards).
        selected_tags: List of tag strings in "Category:Name" format,
                      e.g., ["Subtype:Goblin", "Keyword:Flying"].

    Returns:
        List of (card_dict, matched_tags, match_count) tuples,
        sorted by match count descending then name ascending.
    """
    if not selected_tags or not cards:
        return []

    # Parse tags into lookup structures
    parsed_tags = []
    for tag in selected_tags:
        if ':' not in tag:
            continue
        category, name = tag.split(':', 1)
        parsed_tags.append((category.strip(), name.strip()))

    if not parsed_tags:
        return []

    results = []

    for card in cards:
        matched = []

        for category, name in parsed_tags:
            if category == 'Subtype':
                if name in card.get('subtypes', []):
                    matched.append(f'Subtype:{name}')

            elif category == 'Keyword':
                if name in card.get('keywords', []):
                    matched.append(f'Keyword:{name}')

            elif category == 'Card Type':
                if name in card.get('types', []):
                    matched.append(f'Card Type:{name}')

            elif category == 'Oracle Pattern':
                text = (card.get('text') or '').lower()
                if text and _matches_oracle_pattern(name, text):
                    matched.append(f'Oracle Pattern:{name}')

        if matched:
            results.append((card, matched, len(matched)))

    # Sort by match count descending, then name ascending
    results.sort(key=lambda x: (-x[2], x[0].get('name', '')))

    return results


def _matches_oracle_pattern(pattern_label, text_lower):
    """Check if oracle text matches a named pattern."""
    regex = ORACLE_PATTERN_MAP.get(pattern_label)
    if regex:
        return bool(re.search(regex, text_lower))
    return False
