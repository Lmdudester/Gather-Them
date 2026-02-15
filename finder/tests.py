import sqlite3

from django.test import TestCase
from unittest.mock import patch

from finder.services.card_lookup import lookup_cards


def _build_test_db():
    """Create an in-memory SQLite DB mimicking MTGJSON's schema."""
    conn = sqlite3.connect(':memory:')
    conn.execute("""
        CREATE TABLE cards (
            uuid TEXT PRIMARY KEY,
            name TEXT,
            faceName TEXT,
            flavorName TEXT,
            text TEXT,
            types TEXT,
            subtypes TEXT,
            supertypes TEXT,
            colors TEXT,
            colorIdentity TEXT,
            keywords TEXT,
            printings TEXT,
            language TEXT,
            setCode TEXT,
            number TEXT,
            rarity TEXT,
            manaValue REAL,
            power TEXT,
            toughness TEXT,
            flavorText TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE cardIdentifiers (
            uuid TEXT PRIMARY KEY,
            scryfallId TEXT
        )
    """)
    # Normal card
    conn.execute(
        "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('uuid-bolt', 'Lightning Bolt', None, None, 'Deal 3 damage.',
         'Instant', '', '', 'R', 'R', '', 'M21', 'English', 'M21', '1', 'common',
         1.0, None, None, None),
    )
    conn.execute(
        "INSERT INTO cardIdentifiers VALUES (?, ?)",
        ('uuid-bolt', 'scryfall-bolt'),
    )
    # UB card: canonical name in `name`, UB name in `flavorName`
    conn.execute(
        "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('uuid-reaver', 'The Reaver Cleaver', None, "Knuckles's Gloves",
         'Equip and attack.', 'Artifact', 'Equipment', 'Legendary', 'R', 'R',
         'Equip', 'SLD', 'English', 'SLD', '2095', 'rare', 3.0, None, None, None),
    )
    conn.execute(
        "INSERT INTO cardIdentifiers VALUES (?, ?)",
        ('uuid-reaver', 'scryfall-reaver'),
    )
    # Another UB card
    conn.execute(
        "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('uuid-sigarda', "Sigarda's Aid", None, "Captain America's Aid",
         'Flash. Auras and Equipment enter attached.', 'Enchantment', '', '',
         'W', 'W', 'Flash', 'SLD', 'English', 'SLD', '2100', 'rare',
         1.0, None, None, None),
    )
    conn.execute(
        "INSERT INTO cardIdentifiers VALUES (?, ?)",
        ('uuid-sigarda', 'scryfall-sigarda'),
    )
    conn.row_factory = sqlite3.Row
    return conn


class LookupCardsTests(TestCase):
    """Tests for lookup_cards including Universes Beyond flavorName fallback."""

    def setUp(self):
        self.test_conn = _build_test_db()
        self.patcher = patch(
            'finder.services.card_lookup.get_db',
        )
        mock_get_db = self.patcher.start()
        mock_cm = mock_get_db.return_value
        mock_cm.__enter__ = lambda s: self.test_conn
        mock_cm.__exit__ = lambda s, *a: None

    def tearDown(self):
        self.patcher.stop()
        self.test_conn.close()

    def test_exact_name_match(self):
        found, unfound = lookup_cards(['Lightning Bolt'])
        self.assertIn('Lightning Bolt', found)
        self.assertEqual(found['Lightning Bolt']['name'], 'Lightning Bolt')
        self.assertEqual(unfound, [])

    def test_flavor_name_resolves_ub_card(self):
        found, unfound = lookup_cards(["Knuckles's Gloves"])
        self.assertIn("Knuckles's Gloves", found)
        self.assertEqual(found["Knuckles's Gloves"]['name'], 'The Reaver Cleaver')
        self.assertEqual(unfound, [])

    def test_flavor_name_resolves_another_ub_card(self):
        found, unfound = lookup_cards(["Captain America's Aid"])
        self.assertIn("Captain America's Aid", found)
        self.assertEqual(found["Captain America's Aid"]['name'], "Sigarda's Aid")
        self.assertEqual(unfound, [])

    def test_canonical_name_still_works(self):
        found, unfound = lookup_cards(['The Reaver Cleaver'])
        self.assertIn('The Reaver Cleaver', found)
        self.assertEqual(unfound, [])

    def test_mixed_normal_and_ub_cards(self):
        found, unfound = lookup_cards([
            'Lightning Bolt', "Knuckles's Gloves", "Captain America's Aid",
        ])
        self.assertEqual(len(found), 3)
        self.assertIn('Lightning Bolt', found)
        self.assertIn("Knuckles's Gloves", found)
        self.assertIn("Captain America's Aid", found)
        self.assertEqual(unfound, [])

    def test_unknown_card_still_unfound(self):
        found, unfound = lookup_cards(['Totally Fake Card'])
        self.assertEqual(found, {})
        self.assertIn('Totally Fake Card', unfound)
