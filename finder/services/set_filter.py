from .oracle_patterns import get_oracle_pattern_map


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

            elif category == 'Supertype':
                if name in card.get('supertypes', []):
                    matched.append(f'Supertype:{name}')

            elif category == 'Oracle Pattern':
                text = (card.get('text') or '').lower()
                if text and _matches_oracle_pattern(name, text):
                    matched.append(f'Oracle Pattern:{name}')

            elif category == 'Stat Profile':
                if _matches_stats(name, card):
                    matched.append(f'Stat Profile:{name}')

        if matched:
            results.append((card, matched, len(matched)))

    # Sort by match count descending, then name ascending
    results.sort(key=lambda x: (-x[2], x[0].get('name', '')))

    return results


def _matches_stats(stat_name, card):
    """Check if a card's numeric P/T matches a stat profile."""
    power_raw = card.get('power')
    toughness_raw = card.get('toughness')
    if power_raw is None or toughness_raw is None:
        return False
    try:
        power = int(float(power_raw))
        toughness = int(float(toughness_raw))
    except (ValueError, TypeError):
        return False
    if stat_name == 'High Power':
        return power >= 4
    elif stat_name == 'High Toughness':
        return toughness >= 4
    elif stat_name == 'Toughness > Power':
        return toughness >= power + 3
    elif stat_name == 'Low Power':
        return power <= 2
    return False


def _matches_oracle_pattern(pattern_label, text_lower):
    """Check if oracle text matches a named pattern."""
    compiled_re = get_oracle_pattern_map().get(pattern_label)
    if compiled_re:
        return bool(compiled_re.search(text_lower))
    return False
