import json
import re
import sqlite3

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from finder.forms import SetAnalysisForm
from finder.services.card_lookup import lookup_cards
from finder.services.set_filter import filter_cards_by_tags
from finder.services.set_selection import MAX_SET_SELECTIONS, normalize_set_codes
from finder.services.theme_extractor import extract_oracle_patterns


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


def _build_view_card(name, types=None, supertypes=None, text='', color_identity=None):
    """Build the card fields consumed by the server-rendered result viewer."""
    slug = name.lower().replace(' ', '-')
    return {
        'name': name,
        'faceName': None,
        'flavorName': None,
        'text': text,
        'types': types or ['Creature'],
        'subtypes': ['Goblin'],
        'supertypes': supertypes or [],
        'colors': [],
        'colorIdentity': color_identity or [],
        'keywords': [],
        'printings': ['S1'],
        'language': 'English',
        'setCode': 'S1',
        'number': '1',
        'rarity': 'common',
        'manaValue': 2,
        'power': '2',
        'toughness': '2',
        'flavorText': None,
        'scryfallId': f'scryfall-{slug}',
    }


class PublicMaintenanceControlsTests(TestCase):
    """Homepage maintenance actions do not require Django authentication."""

    def test_anonymous_homepage_shows_maintenance_controls(self):
        with (
            patch('finder.forms.get_sets_for_dropdown', return_value=[]),
            patch('finder.views.check_set_flow_database'),
        ):
            response = self.client.get(reverse('finder:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Update Database')
        self.assertContains(response, 'Refresh Oracle Patterns')
        self.assertContains(response, 'no admin login is required')

    def test_anonymous_user_can_refresh_oracle_patterns(self):
        with patch('finder.services.oracle_patterns.refresh_cache') as refresh_cache:
            response = self.client.post(reverse('finder:refresh_patterns'))

        self.assertEqual(response.status_code, 302)
        refresh_cache.assert_called_once_with()

    def test_anonymous_user_can_start_database_update(self):
        with (
            patch('finder.views.is_maintenance_mode', return_value=False),
            patch('finder.views.set_maintenance_mode') as set_maintenance_mode,
            patch('finder.views.threading.Thread') as thread,
        ):
            response = self.client.post(reverse('finder:update_db'))

        self.assertEqual(response.status_code, 302)
        set_maintenance_mode.assert_called_once_with(True)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()


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


class SetSelectionTests(TestCase):
    def test_normalization_deduplicates_in_submitted_order(self):
        self.assertEqual(
            normalize_set_codes(['MKM', ' MKC ', 'MKM']),
            ['MKM', 'MKC'],
        )

    def test_normalization_enforces_only_the_explicit_limit(self):
        values = [f'S{i}' for i in range(MAX_SET_SELECTIONS + 1)]
        with self.assertRaises(ValueError):
            normalize_set_codes(values, max_count=MAX_SET_SELECTIONS)
        self.assertEqual(normalize_set_codes(values), values)

    def test_set_form_deduplicates_and_rejects_over_limit(self):
        choices = [(f'S{i}', f'Set {i}') for i in range(MAX_SET_SELECTIONS + 1)]
        with patch('finder.forms.get_sets_for_dropdown', return_value=choices):
            form = SetAnalysisForm(data={'set_code': ['S2', 'S1', 'S2']})
            self.assertTrue(form.is_valid())
            self.assertEqual(form.cleaned_data['set_code'], ['S2', 'S1'])

            too_many = SetAnalysisForm(
                data={'set_code': [f'S{i}' for i in range(MAX_SET_SELECTIONS + 1)]}
            )
            self.assertFalse(too_many.is_valid())
            self.assertIn('at most', str(too_many.errors))

    @patch(
        'finder.services.theme_extractor.get_oracle_patterns',
        return_value=[(re.compile('token'), 'Token'), (re.compile('draw'), 'Draw')],
    )
    @patch(
        'finder.services.theme_extractor.get_oracle_pattern_exclude_types',
        return_value={},
    )
    def test_oracle_extraction_counts_distinct_cards_and_singletons(self, _exclude, _patterns):
        cards = [
            {'name': 'Shared', 'text': 'Create a token.', 'types': ['Creature']},
            {'name': 'Shared', 'text': 'Create a token.', 'types': ['Creature']},
            {'name': 'Draw One', 'text': 'Draw a card.', 'types': ['Sorcery']},
        ]
        self.assertEqual(
            extract_oracle_patterns(cards),
            [('Draw', 1), ('Token', 1)],
        )

    @patch(
        'finder.services.set_filter.get_oracle_pattern_map',
        return_value={'Mana production': re.compile('add')},
    )
    @patch(
        'finder.services.set_filter.get_oracle_pattern_exclude_types',
        return_value={'Mana production': {'Land'}},
    )
    def test_set_oracle_exclusions_do_not_change_deck_matcher_default(self, _exclude, _patterns):
        cards = [
            {'name': 'Land Card', 'text': 'Add one mana.', 'types': ['Land']},
            {'name': 'Spell Card', 'text': 'Add one mana.', 'types': ['Instant']},
        ]
        tag = ['Oracle Pattern:Mana production']
        self.assertEqual(len(filter_cards_by_tags(cards, tag)), 2)
        self.assertEqual(
            [card['name'] for card, _, _ in filter_cards_by_tags(
                cards, tag, apply_oracle_exclusions=True,
            )],
            ['Spell Card'],
        )

    def test_get_routes_preserve_deck_get_and_redirect_new_post_get(self):
        with patch('finder.views.check_set_flow_database'):
            with patch('finder.forms.get_sets_for_dropdown', return_value=[]):
                self.assertEqual(self.client.get(reverse('finder:analyze')).status_code, 200)
                self.assertEqual(self.client.get(reverse('finder:results')).status_code, 200)
                self.assertEqual(self.client.get(reverse('finder:set_analyze')).status_code, 302)
                self.assertEqual(self.client.get(reverse('finder:set_results')).status_code, 302)

    def test_empty_set_submission_renders_actionable_picker_error(self):
        with (
            patch('finder.views.check_set_flow_database'),
            patch('finder.forms.get_sets_for_dropdown', return_value=[('TRK', 'Star Trek (TRK)')]),
        ):
            response = self.client.post(reverse('finder:set_analyze'), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please select at least one target set.')

    def test_set_flow_database_failure_renders_recovery_page(self):
        with patch(
            'finder.views.check_set_flow_database',
            side_effect=sqlite3.OperationalError('simulated outage'),
        ):
            response = self.client.get(reverse('finder:set_index'))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'Card data is temporarily unavailable', status_code=503)
        self.assertContains(response, 'Try Again', status_code=503)


class ViewFlowTests(TestCase):
    def setUp(self):
        self.choices = [('S1', 'Set One (S1)'), ('S2', 'Set Two (S2)')]

    def test_set_analysis_and_results_handoff_is_set_only(self):
        cards = [_build_view_card('Token Card', text='Create a token.')]
        matched = [(cards[0], ['Oracle Pattern:Token'], 1)]
        with (
            patch('finder.views.check_set_flow_database'),
            patch('finder.forms.get_sets_for_dropdown', return_value=self.choices),
            patch('finder.views.get_sets_for_dropdown', return_value=self.choices),
            patch('finder.views.get_set_cards', return_value=cards) as get_cards,
            patch(
                'finder.views.extract_oracle_patterns',
                return_value=[('Token', 1)],
            ),
        ):
            analysis = self.client.post(
                reverse('finder:set_analyze'),
                {'set_code': ['S1', 'S2']},
            )

        self.assertEqual(analysis.status_code, 200)
        self.assertContains(analysis, 'Set Oracle Analysis')
        self.assertContains(analysis, 'Analyzed <strong>1</strong> card')
        self.assertContains(analysis, 'Token')
        self.assertNotContains(analysis, 'Deck Format')
        get_cards.assert_called_once_with(['S1', 'S2'], max_set_codes=100)

        with (
            patch('finder.views.check_set_flow_database'),
            patch('finder.forms.get_sets_for_dropdown', return_value=self.choices),
            patch('finder.views.get_sets_for_dropdown', return_value=self.choices),
            patch('finder.views.get_set_cards', return_value=cards) as get_cards,
            patch(
                'finder.views.get_oracle_patterns',
                return_value=[(re.compile('token'), 'Token')],
            ),
            patch('finder.views.filter_cards_by_tags', return_value=matched) as matcher,
        ):
            results = self.client.post(
                reverse('finder:set_results'),
                {
                    'set_codes': json.dumps(['S1', 'S2', 'S1']),
                    'tags': ['Oracle Pattern:Token', 'Oracle Pattern:Token'],
                },
            )

        self.assertEqual(results.status_code, 200)
        self.assertContains(results, 'Set Matching Cards')
        self.assertContains(results, 'Token Card')
        self.assertNotContains(results, 'Deck Format')
        get_cards.assert_called_once_with(['S1', 'S2'], max_set_codes=100)
        matcher.assert_called_once_with(
            cards,
            ['Oracle Pattern:Token'],
            apply_oracle_exclusions=True,
        )

    def test_deck_results_keep_query_filters_exclusions_and_land_merge(self):
        basic = _build_view_card('Basic Card', types=['Land'], supertypes=['Basic'])
        in_deck = _build_view_card('In Deck')
        allowed = _build_view_card('Allowed')
        land_extra = _build_view_card('Land Extra', types=['Land'])
        set_cards = [basic, in_deck, allowed]
        matched = [
            (basic, ['Subtype:Basic'], 1),
            (in_deck, ['Subtype:Goblin'], 1),
            (allowed, ['Subtype:Goblin'], 1),
        ]
        with (
            patch('finder.views.get_set_cards', return_value=set_cards) as get_cards,
            patch('finder.views.get_set_lands', return_value=[allowed, land_extra]) as get_lands,
            patch('finder.views.filter_cards_by_tags', return_value=matched) as matcher,
            patch('finder.views.get_sets_for_dropdown', return_value=self.choices),
        ):
            response = self.client.post(
                reverse('finder:results'),
                {
                    'set_codes': json.dumps(['S1']),
                    'format_name': 'commander',
                    'color_identity': json.dumps(['R']),
                    'deck_card_names': json.dumps(['In Deck']),
                    'decklist_text': json.dumps('1 In Deck'),
                    'tags': ['Subtype:Goblin'],
                    'include_lands': '1',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="card-name">Allowed</span>')
        self.assertContains(response, 'class="card-name">Land Extra</span>')
        self.assertNotContains(response, 'class="card-name">Basic Card</span>')
        self.assertNotContains(response, 'class="card-name">In Deck</span>')
        get_cards.assert_called_once_with(
            ['S1'],
            format_name='commander',
            deck_color_identity=['R'],
        )
        get_lands.assert_called_once_with(
            ['S1'],
            format_name='commander',
            deck_color_identity=['R'],
        )
        matcher.assert_called_once_with(set_cards, ['Subtype:Goblin'])

    def test_results_render_available_color_identity_filter_options(self):
        white = _build_view_card('White Card', color_identity=['W'])
        blue_red = _build_view_card('Blue Red Card', color_identity=['U', 'R'])
        colorless = _build_view_card('Colorless Card')
        cards = [white, blue_red, colorless]
        matched = [
            (white, ['Subtype:Goblin'], 1),
            (blue_red, ['Subtype:Goblin'], 1),
            (colorless, ['Subtype:Goblin'], 1),
        ]

        with (
            patch('finder.views.get_set_cards', return_value=cards),
            patch('finder.views.filter_cards_by_tags', return_value=matched),
            patch('finder.views.get_sets_for_dropdown', return_value=self.choices),
        ):
            response = self.client.post(
                reverse('finder:results'),
                {
                    'set_codes': json.dumps(['S1']),
                    'tags': ['Subtype:Goblin'],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-category="colors"')
        self.assertContains(response, 'aria-label="Color filter mode: INCLUDES"')
        self.assertContains(response, '>INCLUDES</span>')
        self.assertContains(response, 'data-value="W"')
        self.assertContains(response, 'data-value="U"')
        self.assertContains(response, 'data-value="R"')
        self.assertContains(response, 'data-value="C"')
        self.assertContains(response, 'aria-label="White"')
        self.assertContains(response, 'aria-label="Colorless"')
        self.assertContains(response, 'data-colors="W"')
        self.assertContains(response, 'data-colors="U,R"')
        self.assertContains(response, 'data-colors=""')
        self.assertNotContains(response, 'aria-label="Green"')
