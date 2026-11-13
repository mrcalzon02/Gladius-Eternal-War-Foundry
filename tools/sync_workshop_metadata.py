#!/usr/bin/env python3
"""Read authoritative Steam Workshop metadata for the recovered Gladius mods.

Uses Steam's public, keyless GetPublishedFileDetails endpoint. Run from any
internet-connected machine with Python 3.9+:

    python tools/sync_workshop_metadata.py

Review generated changes, then commit and push them through GitKraken.
No Workshop content is uploaded or modified by this utility.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
GAME_APP_ID = 489630
PREVIEWS = ("Preview.png", "Preview1.png", "Preview2.png")


def check_local(repo, mods):
    """Validate Workshop IDs and preserve the original source layout."""
    ids = set()
    for mod in mods:
        item_id = str(mod["workshop_id"])
        folder = repo / mod["path"]
        if not item_id.isdigit() or mod["path"] != item_id or item_id in ids:
            raise ValueError("Duplicate/invalid Workshop ID or path: " + item_id)
        ids.add(item_id)
        if not folder.is_dir():
            raise ValueError("Missing original Workshop directory: " + str(folder))
        steam_id_file = folder / "SteamID.txt"
        if not steam_id_file.is_file() or steam_id_file.read_text(encoding="utf-8-sig").strip() != item_id:
            raise ValueError("SteamID.txt does not match directory: " + item_id)
        if not (folder / PREVIEWS[0]).is_file():
            raise ValueError("Missing recovered Preview.png: " + item_id)
    return sorted(ids)


def fetch_live(ids, attempts=3, timeout=25):
    """One POST for the entire set; never requires a personal Steam API key."""
    form = {"itemcount": str(len(ids))}
    for i, item_id in enumerate(ids):
        form["publishedfileids[" + str(i) + "]"] = item_id
    body = urllib.parse.urlencode(form).encode("ascii")
    error = None
    for attempt in range(attempts):
        req = urllib.request.Request(
            API, data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "EternalWarFoundry-MetadataSync/1.0",
                "Accept": "application/json",
            }, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = json.load(response)
            details = payload["response"]["publishedfiledetails"]
            if not isinstance(details, list):
                raise ValueError("Unexpected Steam response: missing publishedfiledetails")
            return {str(row.get("publishedfileid")): row for row in details}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 4))
    raise RuntimeError("Could not retrieve Steam Workshop metadata: " + str(error))


def md_title(value):
    """Keep remote titles from injecting raw HTML into generated Markdown."""
    return html.escape(str(value), quote=False).replace("\r", " ").replace("\n", " ")


def fenced(text):
    """Safely retain original Steam BBCode and formatting in a literal block."""
    length = 3
    while chr(96) * length in text:
        length += 1
    fence = chr(96) * length
    return fence + "text\n" + text.rstrip("\n") + "\n" + fence


def generate(repo, catalog, responses, partial=False):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    planned = {}
    missing = []
    for mod in catalog["mods"]:
        item_id = str(mod["workshop_id"])
        row = responses.get(item_id, {})
        if int(row.get("result", 0)) != 1:
            missing.append(item_id + " (Steam result " + str(row.get("result", "missing")) + ")")
            continue
        if str(row.get("publishedfileid")) != item_id:
            raise ValueError("Steam response ID mismatch for " + item_id)
        app_id = int(row.get("consumer_app_id") or 0)
        if app_id != GAME_APP_ID:
            raise ValueError("Steam item " + item_id + " belongs to unexpected game app " + str(app_id))
        title = str(row.get("title") or "").strip()
        if not title:
            raise ValueError("Steam returned an empty title for " + item_id)
        description = str(row.get("description") or "")
        preview_url = str(row.get("preview_url") or "")
        url = "https://steamcommunity.com/sharedfiles/filedetails/?id=" + item_id
        folder = repo / item_id
        preview_files = [name for name in PREVIEWS if (folder / name).is_file()]
        local_images = "\n\n".join(
            "![Recovered " + name + "](" + name + ")" for name in preview_files
        )
        remote_thumb = (
            "\n\n[Current Steam thumbnail](" + preview_url + ")\n"
            if preview_url.startswith("https://") else ""
        )
        markdown = (
            "# " + md_title(title) + "\n\n"
            "**Steam Workshop ID:** " + item_id + "\n\n"
            "**Source:** [Live Steam Workshop item](" + url + ")\n\n"
            "**Metadata retrieved (UTC):** " + now + "\n\n"
            "**Content:** Recovered Steam Workshop install, not reconstructed source.\n\n"
            "## Recovered preview files\n\n" + local_images + remote_thumb + "\n\n"
            "## Steam Workshop description\n\n"
            "Captured unchanged from Steam's GetPublishedFileDetails API. "
            "BBCode is retained literally rather than guessed or paraphrased.\n\n"
            + (fenced(description) if description else "(No description returned by Steam.)")
            + "\n\nAlso saved as [raw Steam description](WORKSHOP_DESCRIPTION.txt).\n"
        )
        metadata = {
            "lookup_status": "verified_live_steam_api",
            "retrieved_at_utc": now,
            "workshop_url": url,
            "author_steam_id": str(row.get("creator") or "") or None,
            "time_created_unix": row.get("time_created"),
            "time_updated_unix": row.get("time_updated"),
            "visibility": row.get("visibility"),
            "tags": row.get("tags", []),
            "preview_url": preview_url or None,
            "local_preview_files": preview_files,
            "description_file": item_id + "/WORKSHOP_DESCRIPTION.txt",
            "description_sha256": hashlib.sha256(description.encode("utf-8")).hexdigest(),
        }
        mod["title"] = title
        mod["title_status"] = "verified_live_steam_api"
        mod["workshop"] = metadata
        planned[folder / "WORKSHOP.md"] = markdown
        planned[folder / "WORKSHOP_DESCRIPTION.txt"] = description
    if missing and not partial:
        raise ValueError(
            "Steam did not return all items; no files changed. "
            "Retry later or use --allow-partial. Missing: " + ", ".join(missing)
        )
    planned[repo / "catalog/mods.json"] = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    return planned, missing


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check-only", action="store_true", help="Check local Workshop folder IDs and preview files without accessing Steam")
    p.add_argument("--dry-run", action="store_true", help="Fetch and validate Steam metadata but do not write files")
    p.add_argument("--allow-partial", action="store_true", help="Update only public/resolvable Workshop items if others are unavailable")
    p.add_argument("--response-json", type=Path, help="Import a saved Steam API JSON response instead of making a network request")
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    args = p.parse_args()

    repo = args.repo.resolve()
    catalog_path = repo / "catalog/mods.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    ids = check_local(repo, catalog["mods"])
    print("Verified", len(ids), "existing Workshop directories and SteamID.txt files")
    if args.check_only:
        return
    if args.response_json:
        raw = json.loads(args.response_json.read_text(encoding="utf-8"))
        response_list = raw["response"]["publishedfiledetails"]
        responses = {str(row.get("publishedfileid")): row for row in response_list}
    else:
        responses = fetch_live(ids)
    planned, missing = generate(repo, catalog, responses, partial=args.allow_partial)
    for mod in catalog["mods"]:
        print(mod["workshop_id"], ":", mod.get("title") or "[unavailable]", "-", mod.get("title_status") or "unverified")
    if missing:
        print("Items not resolved:", ", ".join(missing), file=sys.stderr)
    if args.dry_run:
        print("Dry run: no files written")
        return
    for path, content in planned.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print("Updated", path.relative_to(repo))
    print("Done. Inspect Git changes and push only after review; Steam Workshop was NOT modified.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
