import json
import sqlite3
from contextlib import contextmanager

from django.conf import settings


@contextmanager
def get_db():
    """Context manager for read-only MTGJSON database connection."""
    conn = sqlite3.connect(f'file:{settings.MTGJSON_DB_PATH}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_sets_for_dropdown():
    """Return sets suitable for the dropdown, recent first.

    Filters to playable set types (expansions, core sets, commander, etc.)
    and excludes online-only sets.
    """
    playable_types = (
        'expansion', 'core', 'draft_innovation', 'masters', 'commander',
        'starter', 'archenemy', 'duel_deck', 'arsenal', 'spellbook',
    )
    placeholders = ','.join('?' for _ in playable_types)
    query = f"""
        SELECT code, name, releaseDate, type
        FROM sets
        WHERE type IN ({placeholders})
          AND isOnlineOnly = 0
        ORDER BY releaseDate DESC, name ASC
    """
    with get_db() as conn:
        rows = conn.execute(query, playable_types).fetchall()
    return [(row['code'], f"{row['name']} ({row['code'].upper()})") for row in rows]


def _parse_json_col(value):
    """Parse a list column stored as TEXT, returning a list.

    MTGJSON stores these as comma-separated strings (e.g. 'Kor, Cleric')
    but older versions used JSON arrays. Handle both formats.
    """
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        # Comma-separated string format
        return [item.strip() for item in value.split(',') if item.strip()]


def _row_to_card(row):
    """Convert a database Row to a card dict with parsed JSON fields."""
    card = dict(row)
    for field in ('types', 'subtypes', 'supertypes', 'colors',
                  'colorIdentity', 'keywords', 'printings'):
        card[field] = _parse_json_col(card.get(field))
    return card


def lookup_cards(card_names):
    """Look up a list of card names, returning found cards and unfound names.

    Uses a 3-step fallback:
    1. Exact match on `name`
    2. Match on `faceName` (for DFC/adventure front faces)
    3. LIKE prefix match

    Returns:
        (found_cards, unfound_names) where found_cards is a dict mapping
        the original requested name to the card data dict.
    """
    if not card_names:
        return {}, []

    found = {}
    remaining = set(card_names)

    with get_db() as conn:
        # Step 1: Batch exact match on `name`
        placeholders = ','.join('?' for _ in remaining)
        query = f"""
            SELECT c.*, ci.scryfallId
            FROM cards c
            LEFT JOIN cardIdentifiers ci ON c.uuid = ci.uuid
            WHERE c.name IN ({placeholders})
              AND c.language = 'English'
        """
        rows = conn.execute(query, list(remaining)).fetchall()

        # Group by name, prefer non-reprint
        for row in rows:
            name = row['name']
            if name in remaining and name not in found:
                found[name] = _row_to_card(row)
                found[name]['scryfallId'] = row['scryfallId']

        remaining -= set(found.keys())

        if not remaining:
            return found, []

        # Step 2: Match on `faceName` for DFC/adventure cards
        placeholders = ','.join('?' for _ in remaining)
        query = f"""
            SELECT c.*, ci.scryfallId
            FROM cards c
            LEFT JOIN cardIdentifiers ci ON c.uuid = ci.uuid
            WHERE c.faceName IN ({placeholders})
              AND c.language = 'English'
        """
        rows = conn.execute(query, list(remaining)).fetchall()

        for row in rows:
            face_name = row['faceName']
            if face_name in remaining and face_name not in found:
                found[face_name] = _row_to_card(row)
                found[face_name]['scryfallId'] = row['scryfallId']

        remaining -= set(found.keys())

        if not remaining:
            return found, []

        # Step 3: LIKE prefix match (individual queries for remaining)
        for name in list(remaining):
            query = """
                SELECT c.*, ci.scryfallId
                FROM cards c
                LEFT JOIN cardIdentifiers ci ON c.uuid = ci.uuid
                WHERE c.name LIKE ?
                  AND c.language = 'English'
                LIMIT 1
            """
            row = conn.execute(query, (f'{name}%',)).fetchone()
            if row:
                found[name] = _row_to_card(row)
                found[name]['scryfallId'] = row['scryfallId']
                remaining.discard(name)

    return found, list(remaining)


def _aggregate_multi_face(cards_by_name):
    """For multi-face cards with the same name, aggregate data from all faces.

    Unions subtypes, keywords, and concatenates oracle text.
    """
    # Group by card name
    name_groups = {}
    for name, card in cards_by_name.items():
        base_name = card.get('name', name)
        if base_name not in name_groups:
            name_groups[base_name] = []
        name_groups[base_name].append((name, card))

    result = {}
    for base_name, entries in name_groups.items():
        if len(entries) == 1:
            result[entries[0][0]] = entries[0][1]
            continue
        # Merge faces
        merged = dict(entries[0][1])
        for _, face in entries[1:]:
            for field in ('subtypes', 'keywords', 'types'):
                merged[field] = list(set(merged[field]) | set(face.get(field, [])))
            if face.get('text'):
                merged['text'] = (merged.get('text') or '') + '\n// \n' + face['text']
        result[entries[0][0]] = merged

    return result


def get_set_lands(set_codes, format_name=None, deck_color_identity=None):
    """Get non-basic lands from sets using intersection-based color identity.

    Unlike get_set_cards (subset check), this includes a land if it shares
    at least one color with the deck's identity. Colorless lands are always
    included.

    Args:
        set_codes: A set code string or list of set codes.
        format_name: Format column name for legality filtering.
        deck_color_identity: List of colors for intersection-based CI filtering.

    Returns:
        List of card dicts (non-basic lands only).
    """
    if isinstance(set_codes, str):
        set_codes = [set_codes]

    query = """
        SELECT c.*, ci.scryfallId
        FROM cards c
        LEFT JOIN cardIdentifiers ci ON c.uuid = ci.uuid
    """
    placeholders = ','.join('?' for _ in set_codes)
    params = list(set_codes)
    conditions = [
        f"c.setCode IN ({placeholders})",
        "c.language = 'English'",
    ]

    # Format legality filter
    if format_name:
        valid_formats = {
            'commander', 'standard', 'modern', 'pioneer', 'legacy', 'vintage',
            'pauper', 'historic', 'alchemy', 'brawl', 'oathbreaker', 'duel',
            'penny', 'gladiator', 'oldschool', 'premodern', 'paupercommander',
            'standardbrawl', 'timeless', 'future',
        }
        if format_name in valid_formats:
            query += " LEFT JOIN cardLegalities cl ON c.uuid = cl.uuid"
            conditions.append(f"cl.{format_name} IN ('Legal', 'Restricted')")

    query += " WHERE " + " AND ".join(conditions)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    cards = []
    seen_names = set()
    for row in rows:
        card = _row_to_card(row)
        card['scryfallId'] = row['scryfallId']

        # Only lands
        if 'Land' not in card.get('types', []):
            continue

        # Exclude basic lands
        if 'Basic' in card.get('supertypes', []):
            continue

        # Deduplicate by name
        name = card['name']
        if name in seen_names:
            continue
        seen_names.add(name)

        # Intersection-based color identity: colorless always included,
        # otherwise at least one color must overlap with the deck's CI
        if deck_color_identity is not None:
            card_ci = set(card.get('colorIdentity', []))
            deck_ci = set(deck_color_identity)
            if card_ci and not card_ci & deck_ci:
                continue

        cards.append(card)

    return cards


def get_set_cards(set_codes, format_name=None, deck_color_identity=None):
    """Get all cards from one or more sets, with optional format/color filtering.

    Args:
        set_codes: A set code string or list of set codes (e.g., ['MKM', 'MKC'])
        format_name: Format column name for legality filtering (e.g., 'commander')
        deck_color_identity: List of colors (e.g., ['R', 'W']) for color identity filtering.
                           Only cards whose colorIdentity is a subset will be included.

    Returns:
        List of card dicts with parsed JSON fields and scryfallId.
    """
    if isinstance(set_codes, str):
        set_codes = [set_codes]

    query = """
        SELECT c.*, ci.scryfallId
        FROM cards c
        LEFT JOIN cardIdentifiers ci ON c.uuid = ci.uuid
    """
    placeholders = ','.join('?' for _ in set_codes)
    params = list(set_codes)
    conditions = [
        f"c.setCode IN ({placeholders})",
        "c.language = 'English'",
    ]

    # Format legality filter
    if format_name:
        # Validate format_name to prevent SQL injection (it's used as a column name)
        valid_formats = {
            'commander', 'standard', 'modern', 'pioneer', 'legacy', 'vintage',
            'pauper', 'historic', 'alchemy', 'brawl', 'oathbreaker', 'duel',
            'penny', 'gladiator', 'oldschool', 'premodern', 'paupercommander',
            'standardbrawl', 'timeless', 'future',
        }
        if format_name in valid_formats:
            query += " LEFT JOIN cardLegalities cl ON c.uuid = cl.uuid"
            conditions.append(f"cl.{format_name} IN ('Legal', 'Restricted')")

    query += " WHERE " + " AND ".join(conditions)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    cards = []
    seen_names = set()
    for row in rows:
        card = _row_to_card(row)
        card['scryfallId'] = row['scryfallId']

        # Deduplicate by name (same card can have multiple printings in a set)
        name = card['name']
        if name in seen_names:
            continue
        seen_names.add(name)

        # Color identity filter
        if deck_color_identity is not None:
            card_ci = set(card.get('colorIdentity', []))
            deck_ci = set(deck_color_identity)
            if not card_ci.issubset(deck_ci):
                continue

        cards.append(card)

    return cards
