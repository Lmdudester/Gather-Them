"""
Oracle text patterns loader with hot-reload support.

Patterns are stored in a JSON config file and loaded lazily on first access.
Call refresh_cache() to reload patterns at runtime without restarting the server.
"""

import json
import logging
import re
import threading
from typing import NamedTuple, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Evergreen / common keywords that form "cares about" archetypes.
# Cards that simply HAVE the keyword don't mention it in oracle text (MTGJSON
# stores keywords separately), so matching the keyword name in oracle text
# specifically captures cards that grant, check for, or reward the keyword.
_KEYWORD_MATTERS = [
    'flying', 'trample', 'haste', 'vigilance', 'first strike',
    'defender', 'menace', 'indestructible',
    'deathtouch', 'double strike', 'lifelink',
]

_lock = threading.Lock()


class _CacheEntry(NamedTuple):
    patterns: list       # list[(compiled_regex, label)]
    pattern_map: dict    # dict[label -> compiled_regex]
    exclude_types: dict  # dict[label -> set[str]]


_cache: Optional[_CacheEntry] = None


def _load_patterns():
    """Read JSON file, validate entries, and pre-compile regex patterns."""
    path = settings.ORACLE_PATTERNS_PATH
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    patterns = []
    pattern_map = {}
    for entry in data['patterns']:
        regex_str = entry.get('regex', '')
        label = entry.get('label', '')
        if not regex_str or not label:
            logger.warning('Skipping oracle pattern with missing regex or label: %s', entry)
            continue
        try:
            compiled = re.compile(regex_str)
        except re.error as e:
            logger.warning('Skipping invalid regex %r for label %r: %s', regex_str, label, e)
            continue
        patterns.append((compiled, label))
        pattern_map[label] = compiled

    # Generate "keyword matters" patterns dynamically
    for kw in _KEYWORD_MATTERS:
        regex_str = f'({re.escape(kw)})'
        label = f'{kw.title()} matters'
        compiled = re.compile(regex_str)
        patterns.append((compiled, label))
        pattern_map[label] = compiled

    exclude_types = {}
    for label, types_list in data.get('exclude_types', {}).items():
        exclude_types[label] = set(types_list)

    return patterns, pattern_map, exclude_types


def _ensure_loaded():
    """Lazy-load patterns on first access with double-checked locking."""
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                patterns, pattern_map, exclude_types = _load_patterns()
                _cache = _CacheEntry(patterns, pattern_map, exclude_types)


def refresh_cache():
    """Re-read the JSON file and swap the in-memory cache atomically."""
    global _cache
    patterns, pattern_map, exclude_types = _load_patterns()
    _cache = _CacheEntry(patterns, pattern_map, exclude_types)
    logger.info('Oracle patterns refreshed: %d patterns loaded.', len(patterns))


def get_oracle_patterns():
    """Return list of (compiled_regex, label) tuples."""
    _ensure_loaded()
    return _cache.patterns


def get_oracle_pattern_map():
    """Return dict mapping label -> compiled_regex."""
    _ensure_loaded()
    return _cache.pattern_map


def get_oracle_pattern_exclude_types():
    """Return dict mapping label -> set of card types to exclude."""
    _ensure_loaded()
    return _cache.exclude_types
