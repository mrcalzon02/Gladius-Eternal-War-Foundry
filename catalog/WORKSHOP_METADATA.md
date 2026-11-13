# Workshop title, description and preview recovery

Seven Steam Workshop install folders are preserved on `main` under their original numeric IDs. Every imported `SteamID.txt` matches the containing folder and every folder has three local `Preview*.png` images. The corresponding `WORKSHOP.md` documents are placed **inside the correct Workshop folders**, not in a separate disconnected list.

**Metadata status (13 November 2026):** The current Steam Workshop index lists four public titles by the author, but individual item pages refused automated fetches/rate-limited the session. These are **candidates**, not verified ID/title pairings. The other three titles are intentionally unknown until an authoritative item-specific response is available. Never treat source-derived summaries as the exact live descriptions.

| Workshop ID | Candidate Steam title | Content observed | Metadata |
|---|---|---|---|
| [2175959340](../2175959340/WORKSHOP.md) | Veteran Marines | SpaceMarines | unconfirmed_id_mapping |
| [2525618649](../2525618649/WORKSHOP.md) | Not retrieved | AstraMilitarum | not_resolved |
| [2525618729](../2525618729/WORKSHOP.md) | Not retrieved | Tyranids | not_resolved |
| [3038342810](../3038342810/WORKSHOP.md) | Proper wagh! | Orks | unconfirmed_id_mapping |
| [3107612342](../3107612342/WORKSHOP.md) | Wonders and Horrors | Neutral, Terrain | unconfirmed_id_mapping |
| [3267312159](../3267312159/WORKSHOP.md) | Aeldari Ascendant | Eldar | unconfirmed_id_mapping |
| [3305007655](../3305007655/WORKSHOP.md) | Not retrieved | Necrons | not_resolved |

## Official metadata recovery

The script `tools/sync_workshop_metadata.py` calls Valve's public `ISteamRemoteStorage/GetPublishedFileDetails/v1/` POST endpoint for these exact IDs. It does not need a Steam API key. It preflights the folder names and `SteamID.txt` values, validates the game's app ID in the response, refuses to write incomplete responses by default, and generates:

- The official live title and structured details in `catalog/mods.json`.
- A `WORKSHOP.md` inside each corresponding numbered directory, with the exact current Steam description as captured, the recovered local previews and the live thumbnail link when returned.
- A raw `WORKSHOP_DESCRIPTION.txt` inside each numbered directory, retaining Steam BBCode unchanged.

From a network-connected clone, run:

    python tools/sync_workshop_metadata.py --check-only
    python tools/sync_workshop_metadata.py --dry-run
    python tools/sync_workshop_metadata.py

If Steam returns only some records (e.g. deleted or private items), the tool fails without writing by default. Use `--allow-partial` only if you intentionally want updates for the successful IDs. Review changes in GitKraken before committing and pushing; this tool **does not upload anything to Steam**.

Sources for initial candidate titles: [Steam Workshop public browse](https://steamcommunity.com/app/489630/workshop/?l=english&language=latam); [Wonders and Horrors mirror](https://catalogue.smods.ru/archives/531411). See each folder for link to its actual ID.
