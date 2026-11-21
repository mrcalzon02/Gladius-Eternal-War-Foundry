# Proper wagh! — Grotz death produces a Grotpost

**Status:** committed source candidate; engine load, actual death triggers,
placement, and multiplayer behavior are **not yet verified**.

## Rule

- Regular **playable Orks/Grotz** squads only. The new three-figure GrotTrio
  shares one engine member slot, so the trigger occurs when the entire
  squad dies, **not per animated figure**.
- The built-in Gladius 1.5+ `onUnitDisappeared` trait area evaluates at the
  departing unit's tile (radius 0), and attempts to create
  `Orks/Grotpost`.
- Terrain must be land, no other unit on the tile, no enemy city, no
  Resource or WireWeed category feature, and no GravityWaves feature.
  Failing conditions means **no post**.
- Grotpost creation has **no ore action cost** on death, unlike the retained
  20-ore manual build action. The Grotpost keeps its original stats,
  upkeep, weapons, transport and HarvestResourceFeatures trait.
- Removes the AI-only Grotz `constructNoctilithCrown` build workaround.
  No AI-selected build action is needed. Human build remains available.
- Neutral/Grotz and Orks/GrotzKamando remain unaffected.

## Engine caveats and acceptance requirements

This is an **engine-native candidate**, not a demonstrated spawn. The
community and developer change notes establish the
`onUnitDisappeared><area` mechanism and `addUnit` tile effect, but not
the precise timing of the now-departed tile nor the generated unit's owner.

1. Verify the game loads Proper wagh! with no resource/trait errors.
2. In a headed new skirmish, create one AI-owned Orks/Grotz next to an
   empty legal land hex; destroy the unit by normal combat.
3. Confirm exactly one **Ork-owned** Grotpost appears on the departing hex,
   and never on a different hex or as an extra AI-selected order.
4. Repeat for an occupied hex, a resource feature, water and wire weed:
   no unit overlap, illegal terrain placement or crash is acceptable.
5. Confirm an AI-owned Grotz can produce a post without any construction
   command and without a 20-ore debit. Check the post's income and attack.
6. Test voluntary disband explicitly: historical Gladius versions fire
   disappearance effects on disbanding. If disbanding also creates a
   Grotpost, determine whether acceptable before publication to avoid
   unlimited free-post exploits.
7. Test transported Grotz, simultaneous Grotz deaths, unit mortality
   conditions, save reload and multiplayer host/client state.
8. Regression: human Grotz may still manually build one post on an
   adjacent legal hex for 20 ore; neutral Grotz and Grotz Kamando never
   receive the new death trait.

**No headed run was performed in this commit. Do not claim the mechanic is
working in an actual match until these checks pass.**

References:
- Gladius v1.5.0 developer change notes, native
  `<onUnitDisappeared><area>` added, older modifier form deprecated:
  https://forum.slitherine.com/viewtopic.php?t=97020
- Gladius modding modifier/condition/action documentation:
  https://gladiusrelicsofwar.fandom.com/wiki/Modding%3AModifiers
