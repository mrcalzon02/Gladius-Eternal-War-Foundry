# Gladius startup texture repair — November 15, 2026

The installed Gladius 1.18.3 aborted while loading textures. The crash log
reported `TextureLoader.cpp:105: Unknown texture format` for all three Yarrick
atlases in Penal Legion (Workshop 2525618649), followed by SIGABRT.

The packaging scripts saved Pillow's default uncompressed BGRA DDS format.
The same unsupported format was present in the Veteran Sergeant, Grot, and
Ripper overrides, for 12 installed textures total. All other DDS files in
the 11 enabled mods used legacy DXT1, DXT3, or DXT5 compression.

Converted those 12 textures to legacy DXT5, preserving dimensions and alpha,
and updated their local package copies and manifests. The four packaging
scripts now explicitly select DXT5. Each converted texture was decoded and
compared with its original; each mean channel error was below 12/255.

Original textures, hashes, staged replacements, and the pre-repair crash log
are under `backups/startup-texture-repair-20261115`. The repair script checks
all 12 exact targets and original hashes before writing installed files.
The game executable still matches the original SHA-256
`aa56fd15036897c72b9508da9bbf2650876584fd8d4b04e3f64db1b6b943c28f`.
No saves or mod configuration were changed by this repair. No remote
publication or external library checkout update was performed.

Launched through the installed Steam launcher after repair. The game loaded
all 11 enabled mods, passed texture loading, created the menu GUI and menu
cinematic, and logged `Complete.` at 22:16:51 UTC on November 15, 2026.
Direct visual inspection was unavailable because Computer Use was not approved
for Gladius; startup verification uses the live process and fresh engine log.
In-game combat and save loading have not been tested by this repair.


## Consolidated startup acceptance

The follow-up consolidation exposed unsupported `ore`, `energy`, and
`requisitions` player conditions inherited from the old AI pilot. The installed
1.18.3 executable's PlayerConditions::deserializeNode parser was inspected
read-only through its public symbols: it accepts `influence` but has no stockpile
conditions for these three resources. Removed the unsupported checks from all
four AI branches and the development generator. Original construction costs,
health and threat restrictions remain. A regression test and integrated-package
validator now reject unsupported player conditions.

The final local installation has only the seven original numeric Workshop mods;
the four former local Foundry overlays are backed up outside the Mods directory.
The fresh engine log reports all seven enabled and `Complete.` at 22:30:05 UTC
on November 15, 2026, with neither invalid conditions nor unsupported DDS formats.
Grot, Ripper and Sergeant asset checks, all 212 DDS format checks, and seven
construction tests passed. In-game combat and save loading remain untested.
