"""
Shared oracle text patterns for theme extraction and set card filtering.

Each entry is (regex_pattern, label). The regex is matched case-insensitively
against card oracle text. Labels are grouped loosely by archetype.

Patterns are curated from Scryfall oracle tags (otag:) and common
Commander/constructed deck-building archetypes.
"""

ORACLE_PATTERNS = [
    # --- Counters ---
    (r'\+1/\+1 counter', '+1/+1 counters'),
    (r'-1/-1 counter', '-1/-1 counters'),
    (r'(charge|lore|loyalty|verse|time|age|fade)\s+counter', 'Special counters'),
    (r'(oil|stun|shield|finality)\s+counter', 'Keyword counters'),
    (r'double\s+the\s+number\s+of\s+.*?counter', 'Counter doubling'),
    (r'enters\s+.*?with\s+.*?\+1/\+1\s+counter', 'Enters with counters'),

    # --- Tokens ---
    (r'create[s]?\s+.*?token', 'Create token'),
    (r'treasure\s+token', 'Treasure'),
    (r'(food\s+token|create.*?Food)', 'Food tokens'),
    (r'(clue\s+token|create.*?Clue)', 'Clue tokens'),
    (r'(blood\s+token|create.*?Blood)', 'Blood tokens'),
    (r'(map\s+token|create.*?Map)', 'Map tokens'),
    (r'(powerstone\s+token|create.*?Powerstone)', 'Powerstone tokens'),
    (r'(populate)', 'Populate'),

    # --- Go wide / token payoffs ---
    (r'for\s+each\s+(creature|token)\s+you\s+control', 'Go wide payoff'),
    (r'token[s]?\s+you\s+control', 'Token count matters'),

    # --- Card draw & selection ---
    (r'draw[s]?\s+.*?card', 'Draw cards'),
    (r'scry\s+\d+', 'Scry'),
    (r'surveil\s+\d+', 'Surveil'),
    (r'(look at the top|reveal the top).*?(library)', 'Topdeck manipulation'),
    (r'exile[s]?\s+.*?top.*?(play|cast|until)', 'Impulse draw'),
    (r'(whenever|when).*?(draw|draws)\s+.*?card', 'Draw trigger'),
    (r'(cycling|cycle\s+)', 'Cycling'),
    (r'(prowess)', 'Prowess'),

    # --- Removal ---
    (r'destroy\s+(target|all|each)', 'Destroy'),
    (r'destroy\s+(all|each)\s+(creature|permanent|artifact|enchantment)', 'Board wipe'),
    (r'exile[s]?\s+(target|all|each|a |the )', 'Exile'),
    (r'(deal|deals)\s+\d+\s+damage', 'Deal damage'),
    (r'deals?\s+damage\s+equal\s+to', 'Damage scaling'),
    (r'deals?\s+.*?damage\s+to\s+(each|all)\s+(creature|opponent|player)', 'Mass damage'),
    (r'fight[s]?\s', 'Fight'),
    (r'(bite|deals damage equal to its power)', 'Bite'),

    # --- Sacrifice & death ---
    (r'(sacrifice|sacrifices)\s+(a|an|another|target)', 'Sacrifice'),
    (r'(whenever|when)\s+.*?\s+dies', 'Death trigger'),
    (r'(each|all)\s+opponent[s]?\s+lose', 'Drain'),
    (r'(blood\s+artist|whenever.*?dies.*?lose)', 'Aristocrats'),
    (r'whenever\s+you\s+sacrifice', 'Sacrifice trigger'),
    (r'(exploit|devour|emerge)', 'Sacrifice mechanic'),
    (r'(each\s+opponent|target\s+opponent)\s+sacrifices', 'Edict effect'),

    # --- Graveyard ---
    (r'(from|to|into|in)\s+(your|a|the)\s+graveyard', 'Graveyard'),
    (r'return[s]?\s+.*?\s+from\s+.*?graveyard', 'Recursion'),
    (r'(put|return)\s+.*?from\s+.*?graveyard\s+.*?(battlefield|onto the battlefield)', 'Reanimate'),
    (r'(exile|exiles)\s+.*?from\s+.*?graveyard', 'Graveyard hate'),
    (r'(mill|puts?\s+.*?cards?\s+.*?into\s+.*?graveyard)', 'Mill'),
    (r'(dredge|delve|escape|unearth|flashback|retrace|embalm|eternalize|disturb|aftermath)', 'Graveyard cast'),
    (r'(delirium|threshold)', 'Graveyard threshold'),
    (r'(cards?\s+in\s+your\s+graveyard|graveyard\s+count)', 'Graveyard payoff'),

    # --- Life ---
    (r'(gain|gains)\s+\d+\s+life', 'Gain life'),
    (r'(whenever|when).*?gain[s]?\s+life', 'Lifegain trigger'),
    (r'(lose|loses)\s+\d+\s+life', 'Life loss'),
    (r'pay[s]?\s+\d+\s+life', 'Pay life'),
    (r'(life\s+total\s+becomes|exchange\s+life)', 'Life total manipulation'),
    (r'(lifelink)', 'Lifelink'),

    # --- Combat ---
    (r'(whenever|when)\s+.*?\s+attacks', 'Attack trigger'),
    (r'(whenever|when)\s+.*?\s+deals\s+combat\s+damage', 'Combat damage trigger'),
    (r'(additional\s+combat|extra\s+combat)', 'Extra combat'),
    (r'(can\'t\s+be\s+blocked|unblockable)', 'Evasion'),
    (r'(double\s+strike)', 'Double strike'),
    (r'(whenever|when)\s+.*?\s+blocks', 'Block trigger'),
    (r'(goad|goaded)', 'Goad'),
    (r'(must\s+attack|attacks?\s+each\s+(combat|turn)\s+if\s+able)', 'Forced combat'),
    (r'gain\s+control\s+of\s+target.*?until\s+end\s+of\s+turn', 'Threaten'),

    # --- Blink & bounce ---
    (r'exile[s]?\s+.*?return[s]?\s+.*?(battlefield|to the battlefield)', 'Blink'),
    (r'return[s]?\s+.*?to\s+(its\s+)?owner\'s\s+hand', 'Bounce'),
    (r'(flicker|exile.*?then return)', 'Flicker'),

    # --- Copy & clone ---
    (r'(copy|copies)\s+(target|a|that)\s+(spell|creature|permanent|artifact|enchantment)', 'Copy'),
    (r'(enters\s+.*?as\s+a\s+copy|becomes?\s+a\s+copy)', 'Clone'),
    (r'(copy|copies)\s+that\s+spell', 'Spell copy'),
    (r'(storm)', 'Storm'),

    # --- Control & theft ---
    (r'gain\s+control\s+of\s+(target|a|each)', 'Steal'),
    (r'(tap|taps)\s+(target|an?)\s+', 'Tap control'),
    (r'(doesn\'t\s+untap|don\'t\s+untap)', 'Freeze'),
    (r'(counter|counters)\s+(target|a|that)\s+spell', 'Counterspell'),
    (r'(hexproof|shroud|protection\s+from|ward)', 'Protection'),
    (r'(indestructible)', 'Indestructible'),
    (r'(can\'t\s+cast|can\'t\s+activate|can\'t\s+be\s+cast)', 'Lockdown'),

    # --- Ramp & mana ---
    (r'(search|searches)\s+your\s+library\s+for\s+.*?(land|basic)', 'Land ramp'),
    (r'add[s]?\s+\{', 'Mana production'),
    (r'(add[s]?\s+.*?mana\s+of\s+any)', 'Mana fixing'),
    (r'(cost[s]?\s+\{?\d*\}?\s*(less|more)|reduce[s]?\s+.*?cost)', 'Cost reduction'),
    (r'(without\s+paying\s+.*?mana\s+cost|cast\s+.*?without\s+paying)', 'Free cast'),
    (r'(untap[s]?\s+(target|all|each)\s+land)', 'Land untap'),

    # --- Untap ---
    (r'untap[s]?\s+(target|another|a|an)\s+(creature|permanent)', 'Untap creature'),
    (r'untap\s+(all|each)\s+(creature|permanent)', 'Mass untap'),
    (r'untap\s+(it|that\s+creature|enchanted\s+creature)', 'Self-untap'),
    (r'whenever.*untaps', 'Untap trigger'),

    # --- Tutor & library ---
    (r'(search|searches)\s+your\s+library', 'Tutor'),
    (r'(reveal|look\s+at)\s+cards?\s+from\s+the\s+top', 'Topdeck peek'),

    # --- Enters the battlefield ---
    (r'enters(\s+the\s+battlefield)?', 'ETB trigger'),
    (r'(leaves|left)\s+the\s+battlefield', 'LTB trigger'),
    (r'(whenever\s+a(n|nother)?\s+(creature|permanent|artifact|enchantment)\s+enters)', 'ETB payoff'),

    # --- Discard & hand disruption ---
    (r'(discard|discards)\s+(a|your|their|cards?)', 'Discard'),
    (r'(each\s+opponent|target\s+(opponent|player))\s+discards', 'Hand disruption'),
    (r'(madness)', 'Madness'),
    (r'(no\s+maximum\s+hand\s+size|hand\s+size)', 'Hand size matters'),
    (r'(cards?\s+in\s+(your\s+)?hand|number\s+of\s+cards?\s+in)', 'Hand count matters'),

    # --- Equipment & auras ---
    (r'(equip|equipped\s+creature)', 'Equipment'),
    (r'(enchanted\s+creature|aura)', 'Aura'),
    (r'(reconfigure)', 'Reconfigure'),
    (r'(attach|attached\s+to)', 'Attachment'),

    # --- Enchantress / constellation ---
    (r'whenever\s+you\s+cast\s+an?\s+enchantment', 'Enchantress trigger'),
    (r'(whenever\s+an?\s+enchantment\s+enters|constellation)', 'Constellation'),
    (r'for\s+each\s+enchantment\s+you\s+control', 'Enchantment count'),

    # --- Tribal / type matters ---
    (r'(creatures?\s+you\s+control\s+get|other\s+creatures?\s+.*?\s+get)\s+\+', 'Anthem'),
    (r'(creatures?\s+of\s+the\s+chosen\s+type|choose\s+a\s+creature\s+type)', 'Tribal payoff'),
    (r'(changeling)', 'Changeling'),

    # --- Spellslinger ---
    (r'(whenever|when)\s+you\s+cast\s+(a|an)\s+(instant|sorcery|noncreature)', 'Spellcast trigger'),
    (r'(instant[s]?\s+and\s+sorcery|sorceries?\s+and\s+instants?)\s+(card|in\s+your\s+graveyard)', 'Spell graveyard'),
    (r'(magecraft)', 'Magecraft'),

    # --- Artifacts matter ---
    (r'whenever\s+.*?artifact\s+enters', 'Artifact ETB trigger'),
    (r'for\s+each\s+artifact\s+you\s+control', 'Artifact count'),
    (r'whenever\s+you\s+cast\s+an?\s+artifact', 'Artifact cast trigger'),
    (r'(metalcraft|improvise)', 'Metalcraft/Improvise'),

    # --- Lands matter ---
    (r'(whenever\s+a\s+land\s+enters|landfall)', 'Landfall'),
    (r'(play\s+an?\s+additional\s+land|additional\s+land)', 'Extra land drop'),
    (r'(land[s]?\s+you\s+control|number\s+of\s+lands?\s+you\s+control)', 'Land count matters'),
    (r'(sacrifice\s+a\s+land|sacrifices?\s+.*?land)', 'Land sacrifice'),
    (r'(play\s+land[s]?\s+from\s+your\s+graveyard)', 'Crucible effect'),

    # --- Extra turns ---
    (r'(extra\s+turn|additional\s+turn)', 'Extra turns'),

    # --- Planeswalker ---
    (r'(planeswalker)', 'Planeswalker matters'),
    (r'(loyalty\s+counter|loyalty\s+abilit)', 'Loyalty'),

    # --- Voting & politics ---
    (r'(vote|voting|council\'s\s+dilemma|will\s+of\s+the\s+council)', 'Voting'),
    (r'(monarch|the\s+monarch)', 'Monarch'),
    (r'(the\s+initiative|initiative)', 'Initiative'),

    # --- Miscellaneous archetypes ---
    (r'(flash)', 'Flash'),
    (r'(proliferate)', 'Proliferate'),
    (r'(cascade)', 'Cascade'),
    (r'(commander)', 'Commander matters'),
    (r'(transform|transforms|transformed)', 'Transform'),
    (r'(venture\s+into\s+the\s+dungeon|completed?\s+a\s+dungeon)', 'Dungeon'),
    (r'(infect|poison\s+counter|toxic)', 'Poison'),
    (r'(corrupted)', 'Corrupted'),
    (r'(energy\s+counter|\{e\})', 'Energy'),
    (r'(experience\s+counter)', 'Experience'),
    (r'(partner|choose\s+a\s+background)', 'Partner'),
    (r'(ward\s)', 'Ward'),
    (r'(connive)', 'Connive'),
    (r'(investigate)', 'Investigate'),
    (r'(discover\s+\d+)', 'Discover'),
    (r'(manifest|manifest\s+dread)', 'Manifest'),
    (r'(morph|megamorph|face\s+down)', 'Morph'),
    (r'(foretell)', 'Foretell'),
    (r'(suspend)', 'Suspend'),
    (r'(phase[s]?\s+out|phasing)', 'Phasing'),
    (r'(ninjutsu)', 'Ninjutsu'),
    (r'(encore|myriad)', 'Multi-copy attack'),
    (r'(affinity)', 'Affinity'),
    (r'(convoke)', 'Convoke'),
    (r'(crew\s+\d+)', 'Vehicle'),
    (r'(mutate)', 'Mutate'),
    (r'(adapt\s+\d+|evolve)', 'Adapt/Evolve'),
    (r'(enrage)', 'Enrage'),
    (r'(incubat)', 'Incubate'),
    (r'(amass\s)', 'Amass'),

    # --- Wheels ---
    (r'discard[s]?\s+(your|their)\s+hand.*?draw', 'Wheel'),
    (r'whenever.*?(draws?\s+a\s+card).*?(damage|lose)', 'Wheel punishment'),

    # --- Pillowfort ---
    (r'(can\'t\s+attack\s+you|attacks?\s+you.*?pay)', 'Pillowfort'),
    (r'(cost[s]?\s+.*?more\s+to\s+cast|spells?\s+cost\s+.*?more)', 'Tax effect'),
    (r'(can\'t\s+cast\s+more\s+than\s+one|only\s+cast\s+.*?each\s+turn)', 'Casting restriction'),

    # --- Chaos / randomness ---
    (r'(flip\s+a\s+coin|coin\s+flip)', 'Coin flip'),
    (r'(roll\s+.*?d(4|6|8|10|12|20)|roll\s+a\s+.*?die)', 'Dice rolling'),
]

# Build the reverse mapping (label -> regex) for set_filter.py
ORACLE_PATTERN_MAP = {label: pattern for pattern, label in ORACLE_PATTERNS}

# Patterns that should be skipped when the card has certain types.
# Maps label -> set of card types to exclude.
ORACLE_PATTERN_EXCLUDE_TYPES = {
    'Mana production': {'Land'},
    'Mana fixing': {'Land'},
}
