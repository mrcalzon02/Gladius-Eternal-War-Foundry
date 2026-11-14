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

Deployment and a fresh engine-load check are the next acceptance step. No full
match, AI production, research completion or balance acceptance is claimed yet.
