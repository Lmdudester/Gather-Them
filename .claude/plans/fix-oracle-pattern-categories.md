# Fix Oracle Pattern Categories

**Branch:** `fix/oracle-pattern-categories`
**Issues:** #28, #29

## Problem

In `finder/data/oracle_patterns.json`, ~28 oracle patterns have incorrect `category` assignments. The root cause is a systematic shift: when patterns were added or reorganized, categories drifted so that many patterns received the category of the *previous* thematic group instead of their own.

This causes themes to appear under wrong headings in the per-category analysis view and in the results page filter sidebar.

## Patterns Requiring Category Changes

| Line | Label | Current Category | Correct Category |
|------|-------|-----------------|-----------------|
| 228–232 | Gain life | `Graveyard` | `Life` |
| 254–257 | Attack trigger | `Life` | `Combat` |
| 289–292 | Blink | `Combat` | `Blink & bounce` |
| 348–351 | Land ramp | `Control & theft` | `Ramp & mana` |
| 353–357 | Mana production | `Control & theft` | `Ramp & mana` |
| 397–402 | Tutor | `Untap` | `Tutor & library` |
| 402–407 | Topdeck peek | `Untap` | `Tutor & library` |
| 408–411 | ETB trigger | `Tutor & library` | `Enters the battlefield` |
| 413–417 | LTB trigger | `Tutor & library` | `Enters the battlefield` |
| 423–427 | Discard | `Enters the battlefield` | `Discard & hand disruption` |
| 427–431 | Hand disruption | `Enters the battlefield` | `Discard & hand disruption` |
| 448–452 | Equipment | `Discard & hand disruption` | `Equipment & auras` |
| 453–457 | Aura | `Discard & hand disruption` | `Equipment & auras` |
| 478–482 | Enchantress trigger | `Equipment & auras` | `Enchantress / constellation` |
| 483–487 | Constellation | `Equipment & auras` | `Enchantress / constellation` |
| 493–497 | Anthem | `Enchantress / constellation` | `Tribal / type matters` |
| 498–502 | Tribal payoff | `Enchantress / constellation` | `Tribal / type matters` |
| 503–507 | Spellcast trigger | `Tribal / type matters` | `Spellslinger` |
| 508–512 | Spell graveyard | `Tribal / type matters` | `Spellslinger` |
| 514–517 | Artifact ETB trigger | `Spellslinger` | `Artifacts matter` |
| 518–522 | Artifact count | `Spellslinger` | `Artifacts matter` |
| 533–537 | Landfall | `Artifacts matter` | `Lands matter` |
| 538–542 | Extra land drop | `Artifacts matter` | `Lands matter` |
| 559–562 | Extra turns | `Lands matter` | `Miscellaneous archetypes` |
| 563–567 | Planeswalker matters | `Lands matter` | `Planeswalker` |
| 568–571 | Loyalty | `Extra turns` | `Planeswalker` |
| 573–577 | Voting | `Planeswalker` | `Voting & politics` |
| 578–581 | Monarch | `Planeswalker` | `Voting & politics` |

**Total: 28 patterns to fix**

## Patterns Verified as Correct (no change needed)

These patterns were called out in Issue #29 but are already correct:

- **Self-untap** (line 389–392): `Untap` ✓
- **Initiative** (line 583–587): `Voting & politics` ✓

## Categories Unaffected by the Shift

The following category groups have all patterns correctly assigned and require no changes:

- Counters (lines 3–32)
- Tokens (lines 33–72)
- Go wide / token payoffs (lines 73–82)
- Card draw & selection (lines 83–112)
- Removal (lines 113–152)
- Sacrifice & death (lines 153–187)
- Graveyard (lines 188–227) — except "Gain life" which is the last entry before the shift begins
- Life (lines 233–252) — correct entries are Lifegain trigger, Life loss, Pay life, Life total manipulation
- Combat (lines 258–288) — correct entries are Combat damage trigger, Extra combat, Evasion, Block trigger, Forced combat, Threaten
- Blink & bounce (lines 293–307) — correct entries are Bounce, Flicker, Copy
- Copy & clone (lines 308–322)
- Control & theft (lines 324–347) — correct entries are Tap control, Freeze, Counterspell, Protection, Lockdown
- Ramp & mana (lines 358–387) — correct entries are Mana fixing, Cost reduction, Free cast, Land untap, Untap creature, Mass untap
- Untap (lines 388–396) — correct entry is Self-untap, Untap trigger
- Discard & hand disruption (lines 433–447) — correct entries are Madness, Hand size matters, Hand count matters
- Equipment & auras (lines 458–477) — correct entries are Modified, Voltron payoff, Reconfigure, Attachment
- Enchantress / constellation (lines 488–492) — correct entry is Enchantment count
- Power/Toughness (lines 673–682)
- Miscellaneous archetypes (lines 588–717) — large group, all correct

## Implementation Approach

1. **Single file change:** Edit `finder/data/oracle_patterns.json` to update the `category` field on each of the 28 patterns listed above.
2. **Validation:** After editing, verify:
   - The JSON is still valid (parse test)
   - Every pattern's category matches its thematic group
   - No duplicate or orphaned categories were introduced
3. **No code changes needed:** The category field is purely data — no application code references specific category strings by name for logic purposes. The categories only affect UI grouping/display.

## Risks

- **Ambiguous categorizations:** All 28 corrections are clear-cut based on the pattern labels and regexes. The "Anthem" pattern (creatures you control get +X/+X) could arguably fit under multiple categories, but `Tribal / type matters` is correct since it synergizes with go-wide tribal strategies and is grouped with "Tribal payoff".
- **UI impact:** Changing categories will shift how patterns appear in the per-category view and filter sidebar. This is the intended fix — the current groupings are incorrect and confusing.
- **No breaking changes:** Category strings are used for display grouping only. No application logic depends on specific category values.

## Test Plan

- [ ] `cat finder/data/oracle_patterns.json | python3 -m json.tool > /dev/null` — validates JSON syntax
- [ ] Manual review: scan every pattern's category to confirm it matches its thematic label
- [ ] If the project has tests, run them to confirm no regressions
