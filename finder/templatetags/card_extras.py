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
