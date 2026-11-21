# Proper wagh! Grot trio

Regular Grotz and Grotz Kamando use the same three-figure character in the Ork and Neutral unit definitions. Each instance contains a spanner-carrying Mek, a slugga gunner, and a choppa fighter. Their formation fills one engine member slot. The combined native mesh keeps their individual skeletons and poses. The pistol attaches to the gunner's right hand and fires from its own muzzle socket. The choppa attaches to the cutter's right hand, and grenade throws use the gunner's free left hand.

| Unit | Previous member count × HP | New member count × HP | Grotter, Choppa and unlocked Stikkbomb copies at full strength |
| --- | --- | --- | ---: |
| Regular Grotz | 6 × 1 | 1 × 6 | 6 of each |
| Grotz Kamando | 3 × 2 | 1 × 6 | 3 of each |

The three figures share their six HP and die together. Formerly, the loss of each member also removed that member's weapons. The trio keeps its weapon copies until its shared HP reaches zero. Incoming damage caps, effects that count models, and casualty-based morale can therefore behave differently. Costs, upkeep, recruitment, weapon definitions, per-copy melee attacks, accuracy, upgrades, and construction actions retain their previous values.

The native files live in the existing Workshop package, **Proper wagh!** (3038342810). The authoring and interchange files, preview, and native validation evidence are in the [trio workbench](../model-workbench/Grot-Mob/Trio/). The [manifest](grot/manifest.json) records hashes and the previous four unit signatures. Run `python tools/validate_grot_repository.py` to verify the binaries, material, textures, attachment names, animation skeletons, file hashes, and XML changes. This revision has not been launched in Gladius.

The [earlier single-Grot model](../model-workbench/Grot-Sneak/) and its [round-trip measurements](grot/native-verification.json) document the previous character.

## Grotpost death conversion (20 November 2026)

Playable **regular** Orks/Grotz now carry the passive `Orks/GrotpostOnDeath`
trait. A destroyed one-slot, three-figure Grotz unit attempts to create one
`Orks/Grotpost` on its former hex, subject to normal legal-land and no-unit
conditions. No AI action choice, build order, or ore payment is required.
The old AI-only `constructNoctilithCrown` workaround is removed; the human
20-ore adjacent construction command remains. Neutral Grotz and Grotz
Kamando are not changed. The existing Grotpost combat, transport and
resource-harvesting traits are preserved.

This is **source integrated but not yet game validated**. Engine behavior
on disband, transport destruction, death-tile occupancy, simultaneous
deaths, ownership, save loading and multiplayer has not been proven.
See [the acceptance plan](GROTPOST_DEATH_CONVERSION.md).
