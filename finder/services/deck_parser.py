import re


# Section headers found in Commander/other decklists
_SECTION_HEADERS = re.compile(
    r'^(//\s*|)(Commander|Companion|Mainboard|Sideboard|Maybeboard|'
    r'Deck|Creatures?|Lands?|Instants?|Sorcery|Sorceries|Enchantments?|'
    r'Artifacts?|Planeswalkers?|Battle|Other)\s*$',
    re.IGNORECASE,
)

# Matches lines like "1 Card Name", "1x Card Name", "4x Lightning Bolt"
_CARD_LINE = re.compile(
    r'^\s*(\d+)\s*[xX]?\s+(.+?)\s*$'
)

# Alternate: just a card name with no quantity (assume 1)
_NAME_ONLY = re.compile(
    r'^\s*([A-Z][^\d].{1,80}?)\s*$'
)


def parse_decklist(text):
    """Parse a decklist string into a list of (quantity, card_name) tuples.

    Handles common decklist formats:
    - "1 Card Name"
    - "1x Card Name"
    - Section headers (skipped)
    - Blank lines (skipped)
    - Sideboard separation via empty line or "Sideboard" header

    Returns:
        List of (quantity: int, card_name: str) tuples.
    """
    entries = []
    if not text or not text.strip():
        return entries

    for line in text.splitlines():
        line = line.strip()

        # Skip blank lines
        if not line:
            continue

        # Skip section headers
        if _SECTION_HEADERS.match(line):
            continue

        # Skip comment lines
        if line.startswith('#'):
            continue

        # Try "quantity card_name" format
        match = _CARD_LINE.match(line)
        if match:
            qty = int(match.group(1))
            name = match.group(2).strip()
            # Strip set code in parentheses at end, e.g. "Lightning Bolt (M21)"
            name = re.sub(r'\s*\([A-Z0-9]{2,5}\)\s*$', '', name)
            # Strip collector number after set code, e.g. "Lightning Bolt (M21) 123"
            name = re.sub(r'\s+\d+\s*$', '', name)
            if name:
                entries.append((qty, name))
            continue

        # Try name-only format (assume quantity 1)
        match = _NAME_ONLY.match(line)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s*\([A-Z0-9]{2,5}\)\s*$', '', name)
            name = re.sub(r'\s+\d+\s*$', '', name)
            if name and not name.isdigit():
                entries.append((1, name))

    return entries
