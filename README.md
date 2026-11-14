# Gladius: Eternal War Foundry

**MrCalzon02's Warhammer 40,000: Gladius – Relics of War mod-development home**

This repository is intended to collect, maintain, test, and eventually package the individual mods associated with the Steam Workshop collection **The Gift of Eternal War**.

> Unofficial fan modding project; not affiliated with or endorsed by Games Workshop, Proxy Studios, or the game's publisher.

## Current status

**Seven Steam Workshop mod directories have been recovered to `main`: 608 files (~267.7 MB) across seven original numeric Workshop ID folders.** The repository tree and all seven `SteamID.txt` values have been checked. Original unpublished development files remain unavailable. Byte-for-byte comparison with the local Workshop folders and in-game functionality have **not** yet been tested.

See [`catalog/mods.json`](catalog/mods.json) for the file counts, source paths and recorded import commit. Workshop **titles, descriptions, source links and primary thumbnail URLs are now verified from Steam's API** (13 November 2026). Published version numbers and game compatibility still require verification.

## Intended layout

- `<WorkshopItemID>/` — **preserved original imported Workshop directory**, containing each mod's actual published files (do not rename during recovery)
- `catalog/mods.json` — checked-in source inventory, Workshop item IDs and tentative content areas; official Steam Workshop titles and descriptions are verified; mod versions remain unverified
- `tools/` — common validation/packaging utilities, as required
- `.github/workflows/` — small, manually dispatched tests and publishing controls, added only after the mod build and upload processes are proven
- `docs/` — intake, compatibility and release documentation

Do not add empty placeholder mod folders as though they were imported mods, and do not replace the numeric original folders with synthetic rearrangements before backup validation.

## Recovery and validation milestones

1. **Completed:** Import all seven downloaded Workshop directories without changing their original layouts; verify the seven `SteamID.txt` values match folder names.
2. **Completed:** Recover the official Workshop titles, full published descriptions and current thumbnail URLs from Steam's API for all seven IDs. **Pending:** Independently verify game-version requirements, dependencies, and mod versions.
3. **Pending:** Compare the checked-in tree to local copies or known Steam manifests to detect any omitted files.
4. **Pending:** Check XML syntax, internal resource references and per-mod compatibility; test each mod in Gladius before declaring it operational.
5. **Pending:** Build per-mod package and publication tooling with explicit approval and protected Steam credentials. No automatic publishing is enabled.


## Recovered Steam Workshop references

Every Workshop directory now has a [WORKSHOP.md](2175959340/WORKSHOP.md) with links to the actual Steam item and its three preserved preview files. See the [seven-mod Workshop index](catalog/WORKSHOP_METADATA.md) for all titles and verification status.

The [official Steam metadata sync script](tools/sync_workshop_metadata.py) successfully retrieved the seven published titles, descriptions and thumbnail URLs on 13 November 2026. Every numeric Workshop folder now has a `WORKSHOP.md` and a raw `WORKSHOP_DESCRIPTION.txt`. The script can be run again from an internet-connected clone to refresh this snapshot. No Steam publishing occurs.

## Compatibility repairs

The [compatibility repair ledger](docs/COMPATIBILITY_REPAIRS.md) records the first
23 restored DLC production actions, repeatable source checks, known remaining
findings, and the pending gameplay and AI acceptance work.

## Development policy

- Work on the single `main` branch unless explicitly directed otherwise.
- Use minimal manual-dispatch CI initially; do not enable uncontrolled recurring jobs or auto-publishing.
- Keep independent mod identities, Workshop IDs, and version histories intact.
- Treat automated publishing credentials as GitHub secrets, never as committed files.
- Changes are not complete until committed and read back from GitHub.
- Respect per-mod third-party asset permissions and licenses; no blanket license for every mod is implied by this repository.

## First practical milestone

Preserve the seven recovered mod baselines, verify each mod's dependencies and requirements, and validate one mod end-to-end before introducing any automated publication.


## Veteran sergeant model

Penal Legion's Sargent now includes the accepted pistol/chainsword model, backpack,
bedroll, cigar, and idle, walk, firing and lunging melee animations. See the
[sergeant asset and validation notes](docs/SERGEANT_MODEL.md) and
[editable source](model-workbench/Sergeant-Headset-Variant/README.md). Native export
checks pass; live Gladius combat verification is pending.


## Grot replacement

The accepted Grot model and fitted animations replace the miniature Ork model
in the existing Ork and neutral Grot definitions. Stats and construction behavior
are preserved. See [Grot integration notes](docs/GROT_REPLACEMENT.md) and
[editable source](model-workbench/Grot-Sneak/README.md). Native asset checks pass;
live Gladius combat verification remains pending.
