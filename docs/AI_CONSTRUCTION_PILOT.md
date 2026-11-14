# Builder-based AI construction pilot

## Purpose and status

The author reports that Guard and Ork AI do not use their external construction
abilities, while Space Marines use faction deployment actions. The current mod
sources use `constructImperialStrongpoint` and `constructVoidShieldGenerator` for
builder actions. The installed Chaos Cultist supplies a separate native handler,
`constructNoctilithCrown`. The author of
[Worthy AI](https://github.com/Vaeki-on-Git/WH40k-Gladius-Worthy-AI/blob/main/Worthy%20AI/Data/World/Units/AstraMilitarum/TechpriestEnginseer.xml)
uses that handler for AI-only Guard Strongpoint and Void Shield construction.
This is evidence for a focused experiment, not proof that the handler fixes all
placement decisions or that the same behavior is guaranteed in Foundry matches.

The optional pilot has passed a fresh engine load with the seven Foundry mods
enabled and zero startup warnings/errors. Actual AI construction remains
unverified. The author retains control of the running game.

## Rules preserved

The author chose to keep nearby Grotz required. The pilot does not add Ork
orbital deployment or a mapwide faction call-in. Every branch retains its
builder, target range, spawned structure, construction costs, research gate,
model/animation and cooldown:

| Builder | Structure | Cost | Range | Cooldown |
|---|---|---|---|---|
| Marine Techpriest | Marine Imperial Strongpoint | 10 requisitions | 1 | 4 |
| Guard Techpriest | Imperial Strongpoint | 40 ore | 1 | 5 |
| Guard Techpriest | Void Shield Generator | 20 ore + 20 energy | 1 | 5 |
| Ork Grotz | Grotpost | 20 ore | 1 | 10 |

The human-facing actions retain their original handlers and gain only a human
controller condition. Separate AI-only actions use the native Noctilith Crown
handler, with the original effects and unit types. No Chaos unit, asset, research
requirement or faction is substituted into the player's roster.

## Experimental AI guards

- Builder health must be above 60%.
- Guard and Marine defenses require a non-invulnerable enemy other than a Webway Gate within three tiles.
- Ork Grotposts do not require a nearby enemy in v3, permitting pre-combat consideration.
- Each resource balance must exceed twice that action's resource cost.
- Existing target-tile restrictions remain; AI targets also exclude enemy cities.
- Original construction costs and cooldowns still apply.

The default reserves therefore require over 20 requisitions for a Marine
Strongpoint, over 80 ore for a Guard Strongpoint, over 40 ore and 40 energy for a
Void Shield, and over 40 ore for a Grotpost. These thresholds are test settings,
not settled balance. A stockpile guard does not measure net income, upkeep or
future obligations. Enemy proximity does not compare army strength. Nearby
duplicate defenses are not explicitly prevented beyond the original cooldowns
and native placement heuristics; watch for overspending or clustering.

## Rebuilding and loading

```powershell
python -m unittest discover -s tools/tests -v
python tools/build_ai_construction_pilot.py --output 'C:\path\to\new\Foundry AI Construction Pilot'
```

The generator refuses an existing output destination. It creates three unit XML
overrides, fifteen English action strings (including the original scoped Grotpost action), a README and a source-hash manifest.
It reads the current Foundry sources rather than shipping stale copied units.
Optional `--reserve-multiplier` and `--threat-range` configure the test guards.

Required enabled mods: Veteran Marines (2175959340), Penal Legion (2525618649),
and Proper wagh! (3038342810). Load the pilot after those mods. It overrides three
complete unit definitions: the two Techpriests and playable Ork Grotz. Do not
combine it with another override of these units without comparing the files.
Rebuild when any of those sources change. No Steam Workshop item ID is assigned.

The local test copy is under the Gladius user Mods directory, and is enabled for
the current test launch. Original configuration and the prior log are backed up
under the local chat workspace at `backups/ai-construction-pilot-load/`. Disabling
the pilot restores the original actions; the seven published mods are unchanged
by this experiment. Do not copy this pilot into an individual Workshop package.

## Gameplay acceptance

1. First use a builder-present scenario with required research and ample reserves.
   Confirm a legal empty adjacent land tile and an enemy within three tiles. This
   separates construction decisions from failures to recruit the builder.
2. Record whether a structure is built, who built it, resources spent, placement,
   turn and cooldown. Capture failures under conditions that should permit it.
3. Repeat with reserves below the threshold, an injured builder and no nearby
   enemies. The pilot should withhold construction in each case.
4. Run ordinary AI games with and without the pilot using matched seeds/settings.
   Measure construction frequency, useful coverage, redundant structures, builder
   deaths and resource depletion. A successful menu load is not acceptance here.

Army survival and economic recovery remain separate workstreams. Compare early
casualties to neutrals, army survival at fixed turns, production downtime and
resource income/stockpiles. Do not add broad movement locks or troop bonuses in
response to a single run. No retreat/strength planner replacement is claimed.

The Arming Chambers economic-priority review and inherited Wraithknight research
gate issue remain queued; the external construction report took priority.

## Current user-run scenario

The author selected three Guard AI versus three Ork AI on Impossible difficulty.
This is recorded from the author's statement, not verified through UI control.
The pilot was enabled at the verified startup; construction and match results
are still pending. Record the seed/map settings, successful and missed building
opportunities, placement count, builder survival and resource depletion. Use the
same configuration without the pilot as the comparison run. No victory or AI
improvement claim is made from the selected difficulty alone.

## V3 corrections from live observations

The author reported no construction and identified a question-mark Grotpost action
label. The original pilot's enemy-within-three-tiles condition prevented proactive
Ork outpost building. V3 removes that condition for Grotposts while retaining the
Grotz requirement, range 1, 20 ore cost, cooldown 10, health guard and ore reserve.
This is a correction to an overly restrictive experiment, not evidence that the
AI now plans builder journeys to resource objectives.

The author explicitly requested resource harvesting. The playable Ork Grotpost
now receives the base Fortress's `HarvestResourceFeatures` trait. Its other stats,
upkeep and weapons are unchanged; neutral Grotposts are unchanged. This adds the
native economic capability, which needs an in-game income/ownership check. It
does not copy the Space Marines' global `deployFortress` player action.

The human action asks for `Orks/ConsGrotpost`, whereas the mod supplied only
`ConsGrotpost`. All three scoped aliases are supplied, retaining the original keys.
New pilots also include the human action's scoped text. The resource audit now
checks custom explicit action names, while accepting inherited native naming
such as Frazzle's weapon-derived text. No Frazzle gameplay or labels were changed.

Test v3 separately from the current run. Distinguish an affordable, healthy Grotz
next to a legal resource-adjacent site that declines to build from an AI that never
moves its Grotz to that site. Neither successful startup nor the harvesting trait
proves that strategic travel behavior exists. Guard/Marine combat gates are still
experimental. The previous no-construction observation is recorded as a user
observation, not a controlled result with every precondition verified.
