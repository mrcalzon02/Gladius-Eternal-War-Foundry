# DLC compatibility repair ledger

## Iteration 1: official production access (13 November 2026)

Compared the seven mods with the locally installed Gladius 1.18.3, Steam build
24676278. Added 23 missing official production actions across 13 building files.
Every new action retains the installed game's exact unit and research attributes.
Existing actions, modifiers, strategy scores, and specialized facilities were
preserved. This is source validation; gameplay and AI acceptance are pending.

| Workshop ID | Mod | Restored production targets |
|---|---|---|
| 2525618649 | Penal Legion | AttilanRoughRider, FieldOrdnanceBattery, ArmouredSentinel, Deathstrike |
| 2175959340 | Veteran Marines | PrimarisIntercessor, PrimarisAggressor, PrimarisHellblaster, PrimarisInceptor, AssaultTerminator |
| 2525618729 | Horrors of The Numberless Horde | Harpy, Genestealer, Venomthrope, Maleceptor, NornEmissary |
| 3038342810 | Proper wagh! | BurnaBoy, Kommando, SquighogBoy, WazbomBlastajet |
| 3267312159 | Aeldari Ascendant | WarpSpider, Vyper |
| 3305007655 | Reclamator Awakening | CanoptekReanimator, HexmarkDestroyer, SeraptekHeavyConstruct |
| 3107612342 | Wonders and Horrors | No missing official production actions in this audit; prior UI repair retained |

### Rogal Dorn

Penal Legion already contains both production actions:

- `Data/World/Buildings/AstraMilitarum/Vehicles.xml`
- `Data/World/Buildings/AstraMilitarum/Vehicles7.xml`

`Construction.xml` constructs Logistica, which constructs Vehicles7 after the
Rogal Dorn upgrade. The upgrade retains `dlc="Supplement12"` and requires Vehicles.
The installed official unit also requires Supplement12. No DLC gate was removed.

The existing launch log from 13 November reports Gladius 1.18.3 and an installed-DLC
list ending at Supplement8. A separate `World/Supplement12: 1` configuration line
is not proof of entitlement. Confirm actual DLC recognition in a fresh game launch
before diagnosing this as a missing production action. File presence alone does
not establish ownership or availability.

### Findings from iteration 1

At iteration 1, the isolated-mod audit returned two findings. The Magos
Entrenching dependency was resolved in iteration 3; the Carnifex difference remains:

1. Penal Legion's `World/Units/AstraMilitarum/Magos.xml` requires
   `SpaceMarines/Entrenching`, supplied by Veteran Marines, not Penal Legion or the
   installed base data. An explicit Veteran Marines dependency resolves the file
   reference; Astra Militarum's ability to research it remains unverified. Review
   whether this should be a declared dependency or faction-specific implementation.
2. Tyranid `World/Buildings/Tyranids/Vehicles.xml` produces Carnifex without the
   official research prerequisite. This existing behavior may be intentional;
   it was retained for balance review rather than silently reset.

These are not a comprehensive list of defects. Trait, weapon, asset, localization,
research-cycle, AI behavior, load-order, and complete reachability audits remain.

## Repeating the source audit

Use Python 3 with the standard library. No game or repository files are modified.

```powershell
python -m unittest discover -s tools/tests -v
python tools/audit_production_compatibility.py --game-data 'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data' --report source-audit.json
python tools/audit_production_compatibility.py --game-data 'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data' --mod 2525618649 --dependency 2175959340
```

`--mod` can be repeated. Without it, every numeric mod directory is checked
independently. `--dependency` supplies explicit fallback mods, last wins; the
selected mod has precedence. This models reference lookup only, not the game's
unverified load-order semantics. Exit 0 means no findings within this scope;
exit 1 means findings, and exit 2 means invalid arguments or unreadable inputs.

Reports record selected World definition hashes and the hashes of official inputs
actually consulted. Only hashes and findings are saved, not proprietary game files.
Gladius localization deliberately uses embedded string markup incompatible with
strict XML parsers, so language files are excluded from this XML check.

## Next iterations and acceptance

1. **Resource integrity:** reconcile active Workshop versions; verify the previous
   Wonders and Horrors UI repair is loaded. Trace log-confirmed missing Entrenching
   icons/text, Bayonet and Imperial traits, battlefield resources, and neutral names.
2. **Feature routes:** catalog all units, buildings, research, traits, actions,
   and assets. Trace faction start through construction and research to production;
   detect cycles and inaccessible custom content. Review the two findings above.
3. **AI access:** use matched scenarios and several seeds. Record research,
   facility construction, unit production, and ability use separately. Investigate
   Penal Legion's specialized factories sharing vehicle-production scores before
   adjusting priorities. File-level strategy scores do not prove AI adoption.
4. **Game acceptance:** test each mod alone, relevant overlapping combinations,
   DLC-present and DLC-unavailable configurations, save/load, and fresh logs. Verify
   actual production completion and AI use. Record exact source hashes, active mod
   paths, DLC recognition, scenario, and result for every test.

Do not mark a mod fully compatible until the relevant game tests pass. Do not
overwrite divergent active Workshop files while deploying a test build; preserve
them and use a reversible test copy. No Steam Workshop publication is performed
by these tools.

## Iteration 2: weapon attachment references

Corrected two nonexistent LeftHand references to the verified Guardsman socket
LeftHandBone. The mesh-aware audit checks 115 unit definitions with zero missing
attachment/muzzle names after repair; 13 regression tests pass. Five custom
weapon combinations across four units still require visual acceptance. See the
[attachment guide](WEAPON_ATTACHMENTS.md) for exact XML examples, the repair
evidence, pivot and animation constraints, and the remaining review queue.
The two hand-socket corrections were installed into the active local Penal Legion
Workshop files after checking their pre-repair versions and backing up original
bytes and hashes. In-game appearance remains unverified; no Workshop upload was
performed.

## Iteration 3: resources and faction research access

The resource audit initially reported 21 issues and now reports zero across 356
World XML files in seven isolated mods. This limited scope checks exact-case
trait/feature/weapon references, material textures, new-unit English names and
portraits/overlays, and duplicate language keys; it does not attest all assets or
actual AI behavior. All 19 regression tests pass.

- Penal Legion: corrected Battlefield's trait ID from `battlefield` to
  `Battlefield` and three material texture paths from `Battlfield1` to
  `Battlefield1`; the original DDS assets and trait already existed.
- Added the missing Bayonet informational trait with the existing weapon icon
  and English text. Weapon activation and damage definitions are unchanged.
- Restored Valkyrie's intended `AstraMilitarum/ImperialLegacy` reference in place
  of the nonexistent `Imperial` trait, matching the other Militarum units.
- Fixed the duplicate CombatShovel localization key: the second entry is its
  Flavor text, so the weapon name is no longer overwritten.
- Veteran Marines: supplied the missing scoped Entrenching name/flavor and icon,
  plus the shared description/flavor aliases. Existing icon art was reused.
- Proper wagh!: supplied all 12 missing name/description/flavor entries for four
  neutral variants, copied from their authored Ork counterparts. Their portrait
  and overlay icons were already present and were not replaced.
- Penal Legion Magos: moved Entrenching to a self-contained Astra Militarum trait
  and research node with matching icon and localization. The existing +1 armour
  effect, tier-1 position and infantry research score are preserved from the
  authored Veteran Marines definition. This removes a cross-mod and cross-faction
  research dependency. Its ExtraInfantryArmour gate now uses the existing
  AstraMilitarum upgrade instead of the SpaceMarines upgrade.

The production audit now reports only the existing Carnifex research-gate
change. Magos still references the hidden `SpaceMarines/LastStand` upgrade;
this existing quest/reward-related gate is recorded for further reachability
review rather than silently granting the morale bonus.

Repeat resource checks with:

```powershell
python tools/audit_resource_integrity.py --game-data 'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data' --report resources.json
```

The language scanner accepts Gladius embedded string markup. The file index
checks identifier case even on Windows. Runtime render textures used by shipped
materials are distinguished from missing DDS files. No proprietary game assets
are copied into the repository by this audit.

Installed 37 changed/new Data files into the active Workshop mods after checking
existing files against known source versions and backing up originals. A fresh
Gladius 1.18.3 launch completed at 5:09 PM Alaska time on 13 November with all
seven mods enabled, zero startup warnings, and no startup errors detected. The
prior log contained 50 warning lines. This confirms startup/resource loading,
not a full match, AI production, completed research, or balance acceptance. The
user took over game controls; no further UI automation was performed.

The fresh launch still recognizes DLC only through Supplement8, so DLC-present
production of Rogal Dorn (Supplement12) and the newer restored units remains
unverified on this installation. No DLC entitlement checks were bypassed.

See [sanitized startup evidence](../catalog/compatibility/2026-11-13-resource-load.json).
Full logs and original-file backups stay in the local chat workspace.

## Iteration 4: custom-unit AI production roles

Four custom units had no producer advertising the corresponding production role:
Space Marines Magos (Housing2), Astra Militarum Magos and Officer (Schola), and
Ork SqigHunter (Influence). Added the shipped-game default role score of 1.0:
`increaseHeroesProductionScore` for Housing2 and Schola, and
`increaseInfantryProductionScore` for Influence. Existing economy, other strategy
effects, costs, units and production actions were retained.

The production audit now checks that each custom hero or explicitly scored
infantry unit has at least one producer advertising its role. Fixed-headquarters
only units and valid alternate production routes are excluded to avoid forcing
extra construction priorities everywhere. All 21 regression tests pass; the
only remaining production-audit finding is the preserved Carnifex gate difference.
This is a conservative source-level AI integration repair, not observed proof
of improved AI selection. These three new building edits have not been deployed
or loaded into the user's current game session. Matched AI runs are still needed.

## Iteration 5: preserve power generation as the primary role

Per the author's clarification, Veteran Marines' Energy building is primarily
power infrastructure; recruiting its Techpriest is an additional function.
Restored the shipped `increaseEnergyScore base="1.0"` in place of the incorrect
infantry-production priority. No extra factory-construction priority was added.
The +6 energy, loyalty, production, costs, upkeep and existing Techpriest
production action are unchanged. The current Magos production route remains
Housing2. Exact non-strategy XML equivalence and the shipped energy score were
verified. AI construction/recruitment behavior still needs a matched game test.

Installed the corrected Energy XML into the active Veteran Marines Workshop
folder with Gladius closed, after verifying the pre-repair version and saving
original bytes and hashes under the local chat workspace backup directory
`backups/energy-priority-227875e/`. Fresh game behavior is not yet verified.

## Iteration 6: external construction experiment

Prioritized the author's report that AI builders fail to place external defenses.
Built an optional, builder-based construction pilot for Guard Strongpoints and
Void Shields, Marine Strongpoints, and Ork Grotposts. Nearby Grotz remain required;
no faction-wide call-in was added. Native AI action adapters retain the original
range, costs, research and cooldowns, with experimental health, threat and reserve
guards. All 27 tests pass. A fresh launch enabled the pilot and all seven Foundry
mods with no startup warnings/errors. Generated unit stats and non-action data
match their sources. Actual construction and placement remain unverified.

The pilot is a separate local test mod, not a change to the seven published mod
packages. Its source-hash manifest detects which unit versions it was built from.
See [construction pilot guide](AI_CONSTRUCTION_PILOT.md) and
[sanitized load evidence](../catalog/compatibility/2026-11-13-ai-construction-pilot.json).
Army preservation and economy recovery need their own measured gameplay tests;
no broad movement restrictions or hidden resource bonuses have been introduced.

## Iteration 7: live-test feedback and carried weapon

Fixed the reported Grotpost question mark by adding the scoped action keys the
unit actually requests, retaining old aliases. Added a custom-action-name audit
that respects native weapon-action naming. The reported absence of construction
exposed the pilot's over-restrictive Ork combat gate: v3 permits proactive Grotpost
consideration. Per explicit author request, playable Grotposts gain the native
HarvestResourceFeatures trait. Nearby Grotz, costs, range, cooldown and reserves
remain required. Travel planning, actual placement and harvesting income are
unverified; a global Space Marine call-in has not been added.

Moved Sargent's chainsword to a dedicated pelvis-attached, correctly oriented hip
variant at the author's request. Its pistol and combat rules are unchanged. A
static preview was inspected; animation behavior still needs in-game review.
All 34 regression tests pass; the resource audit reports zero findings and the
attachment-name audit reports zero errors. The earlier match is not evidence
that these new corrections are loaded. See the construction and weapon guides.
The Arming Chambers and Wraithknight reviews remain queued.
