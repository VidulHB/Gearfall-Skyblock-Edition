#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

MODRINTH_API = "https://api.modrinth.com/v2"
CURSEFORGE_API = "https://api.curseforge.com/v1"
USER_AGENT = "gearfall-modpack-mods-generator/1.0 (github-actions)"

SECTIONS = {
    "technology_core": {
        "title": "### Technology Mods (core of Gearfall)",
        "kind": "mod",
        "group": "content",
    },
    "create_addons": {
        "title": "### Other create mod addons",
        "kind": "mod",
        "group": "content",
    },
    "qol": {
        "title": "### QOL Mods",
        "kind": "mod",
        "group": "visuals",
    },
    "visual_mods": {
        "title": "### Visual mods",
        "kind": "mod",
        "group": "visuals",
    },
    "visual_resource_packs": {
        "title": "### Resource packs",
        "kind": "resource_pack",
        "group": "visuals",
    },
    "exploration": {
        "title": "### Exploration Mods",
        "kind": "mod",
        "group": "other",
    },
    "building": {
        "title": "### Building Mods",
        "kind": "mod",
        "group": "other",
    },
    "utility": {
        "title": "### Utility Mods",
        "kind": "mod",
        "group": "other",
    },
    "performance": {
        "title": "### Performance Mods",
        "kind": "mod",
        "group": "other",
    },
    "library": {
        "title": "### Library Mods",
        "kind": "library",
        "group": "other",
    },
    "uncategorized": {
        "title": "### Uncategorized Mods",
        "kind": "mod",
        "group": "other",
    },
}

SECTION_ORDER = [
    "technology_core",
    "create_addons",
    "qol",
    "visual_mods",
    "visual_resource_packs",
    "exploration",
    "building",
    "utility",
    "performance",
    "library",
    "uncategorized",
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def request_json(url: str, *, method: str = "GET", headers=None, data=None, timeout=20):
    req = urllib.request.Request(url=url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_modrinth_url(sha1_hash: str, cache: dict, timeout: int):
    if not sha1_hash:
        return None, "missing modrinthHash"

    if sha1_hash in cache:
        return cache[sha1_hash]

    try:
        version_info = request_json(f"{MODRINTH_API}/version_file/{sha1_hash}", timeout=timeout)
        project_id = version_info.get("project_id")
        if not project_id:
            result = (None, "no project_id in Modrinth response")
            cache[sha1_hash] = result
            return result

        project_info = request_json(f"{MODRINTH_API}/project/{project_id}", timeout=timeout)
        slug = project_info.get("slug")
        project_type = project_info.get("project_type", "mod")
        if slug:
            result = (f"https://modrinth.com/{project_type}/{slug}", None)
            cache[sha1_hash] = result
            return result

        result = (None, "no slug in Modrinth project response")
        cache[sha1_hash] = result
        return result
    except urllib.error.HTTPError as exc:
        result = (None, f"modrinth http error {exc.code}")
        cache[sha1_hash] = result
        return result
    except Exception as exc:
        result = (None, f"modrinth lookup failed: {exc}")
        cache[sha1_hash] = result
        return result


def resolve_curseforge_url(fingerprint: int, api_key: str, cache: dict, timeout: int):
    if not fingerprint:
        return None, "missing curseForgeHash"

    if fingerprint in cache:
        return cache[fingerprint]

    if not api_key:
        result = (None, "missing CURSEFORGE_API_KEY")
        cache[fingerprint] = result
        return result

    headers = {"x-api-key": api_key}

    try:
        fp_data = request_json(
            f"{CURSEFORGE_API}/fingerprints",
            method="POST",
            headers=headers,
            data={"fingerprints": [int(fingerprint)]},
            timeout=timeout,
        )
        matches = fp_data.get("data", {}).get("exactMatches", [])
        if not matches:
            result = (None, "curseforge fingerprint had no exact match")
            cache[fingerprint] = result
            return result

        file_data = matches[0].get("file", {})
        mod_id = file_data.get("modId")
        if not mod_id:
            result = (None, "curseforge exact match had no modId")
            cache[fingerprint] = result
            return result

        mod_info = request_json(f"{CURSEFORGE_API}/mods/{mod_id}", headers=headers, timeout=timeout)
        mod_data = mod_info.get("data", {})

        slug = mod_data.get("slug")
        if slug:
            result = (f"https://www.curseforge.com/minecraft/mc-mods/{slug}", None)
            cache[fingerprint] = result
            return result

        website_url = mod_data.get("links", {}).get("websiteUrl")
        if website_url:
            result = (website_url, None)
            cache[fingerprint] = result
            return result

        result = (None, "curseforge mod response had no slug/websiteUrl")
        cache[fingerprint] = result
        return result
    except urllib.error.HTTPError as exc:
        result = (None, f"curseforge http error {exc.code}")
        cache[fingerprint] = result
        return result
    except Exception as exc:
        result = (None, f"curseforge lookup failed: {exc}")
        cache[fingerprint] = result
        return result


def format_link(url: str):
    if not url:
        return "N/A"
    return f"[Click Here]({url})"


def normalize_mods(modlist_data: dict):
    mods = []
    for key, entry in modlist_data.items():
        if not isinstance(entry, dict):
            continue

        mod_id = entry.get("modId", "")
        jar_name = entry.get("jarName", key)

        # Exclude mod loader pseudo-entry from output tables.
        if "(modloader)" in jar_name.lower() or mod_id == "neoforge":
            continue

        mods.append(
            {
                "jarName": jar_name,
                "modId": mod_id,
                "name": entry.get("name", jar_name),
                "version": entry.get("version", "N/A"),
                "curseForgeHash": entry.get("curseForgeHash"),
                "modrinthHash": entry.get("modrinthHash"),
            }
        )
    return mods


def normalize_key(value: str):
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def build_metadata_lookup(metadata: dict):
    data = metadata.get("mods", {}) if isinstance(metadata, dict) else {}
    lookup = {}

    for key, item in data.items():
        if not key:
            continue
        lookup[key] = item
        norm = normalize_key(key)
        if norm and norm not in lookup:
            lookup[norm] = item

    return lookup


def find_metadata(metadata_lookup: dict, mod: dict):
    raw_keys = [mod.get("modId"), mod.get("jarName"), mod.get("name")]
    for key in raw_keys:
        if key and key in metadata_lookup:
            return metadata_lookup[key]

    for key in raw_keys:
        normalized = normalize_key(key)
        if normalized and normalized in metadata_lookup:
            return metadata_lookup[normalized]

    return {}


def section_for(mod: dict, meta: dict):
    section = meta.get("section")
    if section in SECTIONS:
        return section

    jar_name = mod.get("jarName", "").lower()
    if "resourcepack" in jar_name or "resource-pack" in jar_name:
        return "visual_resource_packs"

    return "uncategorized"


def sort_key(mod: dict):
    return (
        str(mod.get("name", "")).lower(),
        str(mod.get("modId", "")).lower(),
        str(mod.get("jarName", "")).lower(),
    )


def build_missing_report(records):
    report = {
        "missingCategory": [],
        "missingPurpose": [],
        "missingRequiredBy": [],
        "failedLinkLookups": [],
    }

    for rec in records:
        mod = rec["mod"]
        meta = rec["meta"]
        section = rec["section"]

        if section == "uncategorized":
            report["missingCategory"].append(mod)

        if SECTIONS[section]["kind"] == "library":
            if not meta.get("requiredBy"):
                report["missingRequiredBy"].append(mod)
        elif not meta.get("purpose"):
            report["missingPurpose"].append(mod)

        for source, reason in rec["linkErrors"].items():
            if reason:
                report["failedLinkLookups"].append(
                    {
                        "name": mod.get("name"),
                        "modId": mod.get("modId"),
                        "source": source,
                        "reason": reason,
                    }
                )

    return report


def render_missing_markdown(report):
    lines = [
        "# Missing Metadata Review",
        "",
        "This issue is generated by automation. Update scripts/mods_metadata.json to resolve placeholders.",
        "",
    ]

    if (
        not report["missingCategory"]
        and not report["missingPurpose"]
        and not report["missingRequiredBy"]
        and not report["failedLinkLookups"]
    ):
        lines.append("No missing metadata or link lookup failures were detected.")
        return "\n".join(lines) + "\n"

    def add_mod_list(title, mods):
        lines.append(f"## {title} ({len(mods)})")
        if not mods:
            lines.append("None.")
            lines.append("")
            return
        for mod in sorted(mods, key=sort_key):
            lines.append(f"- {mod.get('name')} ({mod.get('modId') or mod.get('jarName')})")
        lines.append("")

    add_mod_list("Missing Category", report["missingCategory"])
    add_mod_list("Missing Purpose", report["missingPurpose"])
    add_mod_list("Missing Required By", report["missingRequiredBy"])

    lines.append(f"## Failed Link Lookups ({len(report['failedLinkLookups'])})")
    if not report["failedLinkLookups"]:
        lines.append("None.")
        lines.append("")
    else:
        for item in report["failedLinkLookups"]:
            lines.append(
                f"- {item['name']} ({item['modId']}) [{item['source']}]: {item['reason']}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def render_markdown(records):
    grouped = defaultdict(list)
    for rec in records:
        grouped[rec["section"]].append(rec)

    for section in grouped:
        grouped[section].sort(key=lambda r: sort_key(r["mod"]))

    content_total = len(grouped["technology_core"]) + len(grouped["create_addons"])
    visuals_mods_count = len(grouped["qol"]) + len(grouped["visual_mods"])
    visuals_pack_count = len(grouped["visual_resource_packs"])
    other_count = (
        len(grouped["exploration"])
        + len(grouped["building"])
        + len(grouped["utility"])
        + len(grouped["performance"])
        + len(grouped["library"])
        + len(grouped["uncategorized"])
    )

    lines = [
        f"## Content ({content_total})",
        "- Since FTB mods are Curseforge only, this modpack will be available only on Curseforge",
        "",
        "<!-- Auto-generated from config/crash_assistant/modlist.json and scripts/mods_metadata.json -->",
        "",
    ]

    def render_table(section_key):
        section = SECTIONS[section_key]
        rows = grouped[section_key]
        count_title = f"{section['title']} [{len(rows)}]"
        lines.append(count_title)
        lines.append("")

        if section["kind"] == "library":
            lines.append("| Mod | Version | CurseForge | Modrinth | Required by |")
            lines.append("|---|---|---|---|---|")
            for rec in rows:
                mod = rec["mod"]
                meta = rec["meta"]
                required_by = meta.get("requiredBy", "[TODO: required by]")
                lines.append(
                    f"| {mod['name']} | {mod['version']} | {rec['curseforge']} | {rec['modrinth']} | {required_by} |"
                )
        elif section["kind"] == "resource_pack":
            lines.append("| Resource Pack | Version | CurseForge | Modrinth | Purpose |")
            lines.append("|---|---|---|---|---|")
            for rec in rows:
                mod = rec["mod"]
                meta = rec["meta"]
                purpose = meta.get("purpose", "[TODO: add purpose]")
                lines.append(
                    f"| {mod['name']} | {mod['version']} | {rec['curseforge']} | {rec['modrinth']} | {purpose} |"
                )
        else:
            lines.append("| Mod | Version | CurseForge | Modrinth | Purpose |")
            lines.append("|---|---|---|---|---|")
            for rec in rows:
                mod = rec["mod"]
                meta = rec["meta"]
                purpose = meta.get("purpose", "[TODO: add purpose]")
                lines.append(
                    f"| {mod['name']} | {mod['version']} | {rec['curseforge']} | {rec['modrinth']} | {purpose} |"
                )
        lines.append("")

    render_table("technology_core")
    render_table("create_addons")

    lines.append(f"## Visuals and QOL ({visuals_mods_count}+{visuals_pack_count})")
    lines.append("")
    render_table("qol")
    render_table("visual_mods")
    render_table("visual_resource_packs")

    lines.append(f"## Other ({other_count})")
    lines.append("")
    render_table("exploration")
    render_table("building")
    render_table("utility")
    render_table("performance")
    render_table("library")
    render_table("uncategorized")

    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate mods.md from modlist.json")
    parser.add_argument("--modlist", default="config/crash_assistant/modlist.json")
    parser.add_argument("--metadata", default="scripts/mods_metadata.json")
    parser.add_argument("--output", default="mods.md")
    parser.add_argument("--missing-json", default="scripts/missing_mod_metadata.json")
    parser.add_argument("--missing-md", default="scripts/missing_mod_metadata.md")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--skip-link-lookups", action="store_true")
    args = parser.parse_args()

    modlist_path = Path(args.modlist)
    metadata_path = Path(args.metadata)

    if not modlist_path.exists():
        print(f"modlist file not found: {modlist_path}", file=sys.stderr)
        return 1

    metadata = {"mods": {}}
    if metadata_path.exists():
        metadata = load_json(metadata_path)
    metadata_lookup = build_metadata_lookup(metadata)

    modlist_data = load_json(modlist_path)
    mods = normalize_mods(modlist_data)

    modrinth_cache = {}
    curseforge_cache = {}
    curseforge_key = os.environ.get("CURSEFORGE_API_KEY", "")

    records = []
    for mod in mods:
        meta = find_metadata(metadata_lookup, mod)
        section = section_for(mod, meta)

        modrinth_url = None
        modrinth_error = None
        curseforge_url = None
        curseforge_error = None

        if not args.skip_link_lookups:
            if not meta.get("forceNoModrinth"):
                modrinth_url, modrinth_error = resolve_modrinth_url(
                    mod.get("modrinthHash"), modrinth_cache, args.timeout
                )
            curseforge_url, curseforge_error = resolve_curseforge_url(
                mod.get("curseForgeHash"), curseforge_key, curseforge_cache, args.timeout
            )

        records.append(
            {
                "mod": mod,
                "meta": meta,
                "section": section,
                "modrinth": format_link(modrinth_url),
                "curseforge": format_link(curseforge_url),
                "linkErrors": {
                    "modrinth": modrinth_error,
                    "curseforge": curseforge_error,
                },
            }
        )

    records.sort(key=lambda r: sort_key(r["mod"]))

    markdown = render_markdown(records)
    Path(args.output).write_text(markdown, encoding="utf-8")

    missing_report = build_missing_report(records)
    Path(args.missing_json).write_text(
        json.dumps(missing_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.missing_md).write_text(render_missing_markdown(missing_report), encoding="utf-8")

    print(f"Generated {args.output} with {len(records)} mods.")
    print(f"Missing report written to {args.missing_json} and {args.missing_md}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
