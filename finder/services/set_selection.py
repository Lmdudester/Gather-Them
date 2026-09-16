"""Validation helpers shared by set-mode forms and card queries."""

MAX_SET_SELECTIONS = 100


def normalize_set_codes(set_codes, max_count=None):
    """Return non-empty set codes once, preserving submitted order.

    The optional limit is intentionally opt-in so the existing deck workflow
    keeps its historical behavior. Set-mode callers pass the documented safe
    maximum before constructing SQL placeholders.
    """
    if isinstance(set_codes, str):
        set_codes = [set_codes]
    if not isinstance(set_codes, (list, tuple)):
        raise ValueError('Set codes must be a list.')

    normalized = []
    seen = set()
    for code in set_codes:
        if not isinstance(code, str):
            raise ValueError('Set codes must be strings.')
        code = code.strip()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)

    if max_count is not None and len(normalized) > max_count:
        raise ValueError(f'You can select at most {max_count} sets.')
    return normalized
