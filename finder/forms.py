from django import forms

from .services.card_lookup import get_sets_for_dropdown


FORMAT_CHOICES = [
    ('commander', 'Commander'),
    ('standard', 'Standard'),
    ('modern', 'Modern'),
    ('pioneer', 'Pioneer'),
    ('legacy', 'Legacy'),
    ('vintage', 'Vintage'),
    ('pauper', 'Pauper'),
    ('oathbreaker', 'Oathbreaker'),
    ('duel', 'Duel Commander'),
    ('brawl', 'Brawl'),
    ('historic', 'Historic'),
    ('timeless', 'Timeless'),
    ('paupercommander', 'Pauper Commander'),
    ('standardbrawl', 'Standard Brawl'),
]


class DecklistForm(forms.Form):
    decklist = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 20,
            'placeholder': (
                'Paste your decklist here...\n\n'
                'Format:\n'
                '1 Card Name\n'
                '1x Card Name\n\n'
                'Section headers like "Commander" or "Sideboard" are ignored.'
            ),
        }),
        label='Decklist',
    )
    set_code = forms.ChoiceField(
        label='Target Set',
    )
    format_name = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        label='Deck Format',
        initial='commander',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['set_code'].choices = get_sets_for_dropdown()
