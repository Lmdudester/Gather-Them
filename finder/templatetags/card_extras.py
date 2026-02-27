from django import template

register = template.Library()


@register.filter
def scryfall_image_url(scryfall_id, version='normal'):
    """Build a Scryfall card image URL from a scryfallId.

    Usage in template:
        {{ card.scryfallId|scryfall_image_url }}
        {{ card.scryfallId|scryfall_image_url:"small" }}
    """
    if not scryfall_id:
        return ''
    return f'https://api.scryfall.com/cards/{scryfall_id}?format=image&version={version}'


@register.filter
def scryfall_page_url(card):
    """Build a Scryfall card page URL from a card dict.

    Usage in template:
        {{ card|scryfall_page_url }}
    """
    set_code = (card.get('setCode') or '').lower()
    number = card.get('number') or ''
    if not set_code or not number:
        return ''
    return f'https://scryfall.com/card/{set_code}/{number}'


@register.filter
def tag_display(value):
    """Strip category prefix from tag for display: 'Subtype:Goblin' -> 'Goblin'."""
    return value.split(':', 1)[1] if ':' in value else value


@register.filter
def tag_category(value):
    """Extract category prefix: 'Subtype:Goblin' -> 'Subtype'."""
    return value.split(':', 1)[0] if ':' in value else value


@register.filter
def unique_tag_displays(tags):
    """Deduplicate tags by their display name (prefix stripped).

    Given ['Subtype:Equipment', 'Oracle Pattern:Equipment', 'Subtype:Aura'],
    returns ['Equipment', 'Aura'].
    """
    seen = set()
    result = []
    for tag in tags:
        display = tag.split(':', 1)[1] if ':' in tag else tag
        if display not in seen:
            seen.add(display)
            result.append(display)
    return result
