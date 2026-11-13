# Neutral-unit labels and icons: static source repair

**Mod:** [Wonders and Horrors](WORKSHOP.md) — Steam Workshop ID `3107612342`.

## Reported symptom

Several neutral units introduced through `Data/World/Blueprints/WorldGenerator/Wildlife.xml.ext` appeared without readable unit names or with question-mark icons in Gladius.

## Source findings

- The Workshop backup defines eight `Data/World/Units/Neutral/*.xml` units, but originally lacked `Data/Core/Languages/English/Units.xml`. Gladius localization requires keys matching the unit's full folder/entity ID.
- Six valid-size (1504-byte, DXT5 30×30 overlay) icons were originally stored at `Data/Video/Textures/Icons/Overlay/Units/<unit>.dds` without the `Neutral` namespace. Their original files have been **preserved** and the same Git blob objects additionally placed under `.../Overlay/Units/Neutral/<unit>.dds`.
- The `Neutral/Boy` primary icon existed at 160×160 but there was no overlay icon. A 30×30 DXT5 five-mip overlay was derived from the recovered Boy primary icon, with no new art substituted.
- The `Neutral/ImperialStrongpoint` unit had no standalone icon pair in this Workshop package. A matching strongpoint main/overlay icon pair already authored and backed up in the same GitHub repository under `2175959340` (Veteran Marines) is now copied into this mod, so it does **not** depend on the other mod being installed.

## Repair scope

Added `Data/Core/Languages/English/Units.xml`: three localizable text keys (`name`, `Description`, `Flavor`) for each of these **eight** units: `Boy`, `FlayedOne`, `Guardian`, `Guardsman`, `Immortal`, `ImperialStrongpoint`, `Raider`, `Succubus`.

Added **nine** namespaced icon files under `Icons/Overlay/Units/Neutral/` or `Icons/Units/Neutral/`, without touching any `World` mechanics or the source assets in the original paths. No existing icon blob was removed. The original Workshop description, thumbnails and ID were also untouched.

## Static checks (not a game test)

- Every neutral unit's XML entity path matches a localization group of three entries.
- All eight units have a corresponding main icon and a corresponding overlay DDS file in the neutral namespace.
- Existing copied images reuse the exact source blob SHA; the newly derived Boy overlay is DXT5, 30×30, five mip levels and 1,504 bytes.
- No changes were made to wildlife spawning, units' combat stats, traits, DLC gates or animation references.

## Required local game test before Steam publication

1. Pull the repaired `main` branch. Copy this mod's *contents* to a **separate local test mod** in `Documents/Proxy Studios/Gladius/Mods/` and keep the original subscribed Workshop folder unchanged.
2. Disable the subscribed copy and other conflicting mods, enable the local test copy, and start a **new** skirmish with wildlife enabled.
3. Inspect tooltips and large and small icons for Ork Boyz, Necron Flayed Ones, Aeldari Guardians, Imperial Guardsmen, Necron Immortals, Imperial Strongpoint, Drukhari Raider and Drukhari Succubus.
4. Confirm no question-mark text or icons, and inspect `Documents/Proxy Studios/Gladius/Logs/Gladius.error.log` if any remain missing.
5. Re-enable other mods to check load-order conflicts. Only publish to Steam after local acceptance.

**Remaining unknown:** The game runtime and DLC availability have not been tested from this GitHub session. The language file contains English entries; other user-selected game languages may need equivalent translations.

## File-layout references

- [Official Gladius wiki: create a new unit](https://gladiusrelicsofwar.fandom.com/wiki/Modding:_How_to_Create_a_New_Unit)
- [Gladius icon conventions](https://gladiusrelicsofwar.fandom.com/wiki/Modding:units)
- [Community guide: localization and icon file hierarchy](https://steamcommunity.com/sharedfiles/filedetails/?id=3129734749)
