# Integrated mod installation

The seven original Workshop IDs identify the runtime mod packages in GitHub.
Install development and upload copies under
`Documents/Proxy Studios/Gladius/Mods/<mod title>/`, using the catalog title for
the local folder name and keeping each original `SteamID.txt` inside that folder.
Steam's `steamapps/workshop/content/489630` directory is a download cache, not
the destination for development builds or upload sources.

| GitHub source folder / Workshop ID | Local folder under `Gladius/Mods` |
|---|---|
| `2175959340` | `Veteran Marines` |
| `2525618649` | `Penal Legion` |
| `2525618729` | `Horrors of The  Numberless Horde` (two spaces before `Numberless`) |
| `3038342810` | `Proper wagh!` |
| `3107612342` | `Wonders and Horrors` |
| `3267312159` | `Aeldari Ascendant` |
| `3305007655` | `Reclamator Awakening` |

The deployer reads these titles from `catalog/mods.json`; numeric GitHub source
folders retain their original names. Each installed package has `Data/` directly
under its local folder, alongside `SteamID.txt`, `Preview.png`, and any additional
tracked root images. Do not add a second nested mod or Workshop ID folder.

| Existing mod | Integrated content |
|---|---|
| Veteran Marines (`2175959340`) | Marine Techpriest AI construction |
| Penal Legion (`2525618649`) | Standard trooper, Officer with 14 animations, Veteran Sergeant, Yarrick, Guard Techpriest AI construction |
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

Use `tools/deploy_integrated_mods.py` with `--repository`, `--mods`, and a new
`--backup` directory. `--mods` must point to the local Gladius Mods directory;
Steam directory destinations are rejected. The default is a read-only plan.
Close Gladius and add `--apply` to install. Add `--mod 2525618649` to deploy only
Penal Legion; repeat `--mod` to select several parents.

```powershell
python tools/deploy_integrated_mods.py --repository C:/GITS/Gladius-Eternal-War-Foundry --mods "C:/Users/Admin/Documents/Proxy Studios/Gladius/Mods" --config "C:/Users/Admin/Documents/Proxy Studios/Gladius/Configuration/Gladius.xml" --backup backups/local-mod-install-NEW
```

Deployment stages complete packages from tracked `Data/` files, each tracked
`SteamID.txt`, and tracked root images. It excludes untracked studies, source
workbenches, and recovery documentation. `--source-manifest` can supply a verified
frozen-source JSON file list (`["relative/path", ...]` or `{"files": [...]}`)
instead of querying `git ls-files`. Entries may be objects containing `path`,
`git_blob_sha`, and `size`; every object entry is verified against its Git blob
hash and byte length before selecting runtime files, including entries excluded
from the upload. Plain path lists remain supported and require independent
snapshot verification against the intended GitHub commit. Every staged and installed file is checked
with SHA-256, and the Steam ID is checked against the original package ID.

Existing local package directories are archived completely in the backup before
replacement, including extra files that do not belong in the new upload package.
The installer rolls back replaced packages if installation or configuration
verification fails. Other local mod folders are left alone. The retired Foundry
overlay installers must not be used to reintroduce superseded packages.

Optional `--config` backs up `Gladius.xml`, remaps selected Workshop or numeric
local paths to the correct local title folders, and preserves mod order and
existing disabled states. The old matching Workshop paths are added to
`Mods/Disabled` to prevent both copies being enabled if Steam downloads them
again. XML formatting, UTF-8 BOM, and line endings are preserved. Without
`--config`, no game configuration is changed. The deployer does not remove any
Workshop cache directories; archiving those requires a separate verified move.

After installation, select the local package in Gladius's Workshop upload flow
and check the existing item ID. Keeping the original `SteamID.txt` links the
upload to that item's identity. Steam publication remains a separate step;
this installer performs no upload.
