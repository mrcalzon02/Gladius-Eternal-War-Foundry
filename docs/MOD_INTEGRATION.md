# Integrated mod installation

The seven original Workshop IDs are the runtime mod packages.

| Existing mod | Integrated content |
|---|---|
| Veteran Marines (`2175959340`) | Marine Techpriest AI construction |
| Penal Legion (`2525618649`) | Standard trooper, Veteran Sergeant, Yarrick, Guard Techpriest AI construction |
| Proper wagh! (`3038342810`) | Playable/neutral Grot models; playable Grot AI construction |
| Tyranid mod (`2525618729`) | Ripperswarm model and animations |

The prior local AI pilot, Sergeant, Grot and Ripper overlays are superseded.
Their effective behavior is preserved in the parent packages; no separate
Foundry entries are required. The [Grot trio](GROT_REPLACEMENT.md) uses one shared casualty slot and preserves
starting health and weapon copies in all four Grot definitions. Internal asset resource paths containing `Foundry` do not create mods.

The construction branches retain the installed v3 settings: builders, costs,
research, ranges and cooldowns; >60% health; nearby
enemies required for Guard/Marine defenses and not for Grotposts. Actual AI
placement and combat/save behavior remain unverified. Extra stockpile reserve
checks were removed because Gladius 1.18.3 rejects player conditions named
`ore`, `energy`, and `requisitions`. Normal construction costs still apply.

The November 15 startup failure came from unsupported uncompressed DDS exports.
All 12 affected atlases now use legacy DXT5; packaging selects it explicitly.
Run `python tools/validate_integrated_mods.py`, the Grot and Ripper repository
validators, the Sergeant package validator, and `tools/validate_standard_trooper.py`
before installation.

Use `tools/deploy_integrated_mods.py` with `--workshop`, `--config`, and a new
`--backup` directory. Its default is a read-only plan; add `--apply` with Gladius
closed to deploy. It checks the seven Steam IDs, backs up changed files and
configuration, verifies installed packages, then archives the four old overlays
outside Mods and removes their configuration entries. Original mod order and
enabled/disabled states are preserved. Use this installer instead of the retired
workspace overlay installers.

Steam Workshop uploads remain a separate publishing step. Steam may replace
local Workshop edits during updates; review upstream changes and reapply the
integrated repository packages when necessary.
