# Gladius: Eternal War Foundry

**MrCalzon02's Warhammer 40,000: Gladius – Relics of War mod-development home**

This repository is intended to collect, maintain, test, and eventually package the individual mods associated with the Steam Workshop collection **The Gift of Eternal War**.

> Unofficial fan modding project; not affiliated with or endorsed by Games Workshop, Proxy Studios, or the game's publisher.

## Current status

**Repository initialized; mod content not yet imported.** No mod source, Workshop item ID, version, successful in-game test, or publishing automation should be considered verified simply because this repository exists.

## Intended layout

- `mods/<mod-slug>/` — each mod's actual source and assets, preserved independently
- `catalog/mods.json` — per-mod display name, source folder, Steam Workshop item ID, version and release mapping (create when real identifiers are verified)
- `tools/` — common validation/packaging utilities, as required
- `.github/workflows/` — small, manually dispatched tests and publishing controls, added only after the mod build and upload processes are proven
- `docs/` — intake, compatibility and release documentation

Do not add empty placeholder mod folders as though they were imported mods.

## Import order

1. Obtain the **actual editable source** (or the current installable files, explicitly labeled as such) for each existing mod.
2. Preserve original files and record where each copy came from. Avoid accidentally checking in personal credentials, workshop upload tokens, unrelated third-party content or generated caches.
3. For each mod, record its Steam Workshop item ID, current published version (if known), dependencies, and required Gladius game version.
4. Import one mod at a time, retaining its original layout wherever possible.
5. Validate structure, launch/loading, and compatibility before declaring that mod ready.
6. Add **per-mod**, opt-in package/publish automation only after successful tests. Never silently overwrite Workshop items.

## Development policy

- Work on the single `main` branch unless explicitly directed otherwise.
- Use minimal manual-dispatch CI initially; do not enable uncontrolled recurring jobs or auto-publishing.
- Keep independent mod identities, Workshop IDs, and version histories intact.
- Treat automated publishing credentials as GitHub secrets, never as committed files.
- Changes are not complete until committed and read back from GitHub.
- Respect per-mod third-party asset permissions and licenses; no blanket license for every mod is implied by this repository.

## First practical milestone

Import and verify the current files for **one** existing mod, then expand to the remaining collection and establish a tested per-mod release pipeline.
