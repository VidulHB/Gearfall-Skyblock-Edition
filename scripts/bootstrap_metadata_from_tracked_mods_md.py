#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

HEADER_TO_SECTION = {
    "### Technology Mods (core of Gearfall)": "technology_core",
    "### Other create mod addons": "create_addons",
    "### QOL Mods": "qol",
    "### Visual mods and resource packs": "visual_mods",
    "### Exploration Mods": "exploration",
    "### Building Mods": "building",
    "### Utility Mods": "utility",
    "### Performance Mods": "performance",
    "### Library Mods": "library",
}


def split_row(line: str):
    parts = [p.strip() for p in line.strip().strip("|").split("|")]
    return parts


def read_tracked_file(path: str):
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Seed metadata from tracked mods.md")
    parser.add_argument("--tracked-path", default="mods.md")
    parser.add_argument("--metadata", default="scripts/mods_metadata.json")
    args = parser.parse_args()

    tracked = read_tracked_file(args.tracked_path)
    lines = tracked.splitlines()

    metadata_path = Path(args.metadata)
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
    else:
        metadata = {"mods": {}}

    mods = metadata.setdefault("mods", {})

    current_section = None
    in_table = False
    header_cols = []

    for line in lines:
        line = line.rstrip("\n")

        for heading, section in HEADER_TO_SECTION.items():
            if line.startswith(heading):
                current_section = section
                in_table = False
                header_cols = []
                break

        if line.startswith("|"):
            cells = split_row(line)
            if not cells or all(not c for c in cells):
                continue

            # Header row starts a table.
            if not in_table:
                header_cols = cells
                in_table = True
                continue

            # Separator row.
            if cells and all(c.startswith("---") for c in cells):
                continue

            if not current_section:
                continue

            if "Mod" in header_cols[0] or "Resource Pack" in header_cols[0]:
                if len(cells) < len(header_cols):
                    continue

                name = cells[0]
                if not name:
                    continue

                entry = mods.setdefault(name, {})

                section = current_section
                if current_section == "visual_mods" and "Resource Pack" in header_cols[0]:
                    section = "visual_resource_packs"

                entry["section"] = section

                if "Purpose" in header_cols:
                    purpose_idx = header_cols.index("Purpose")
                    if purpose_idx < len(cells):
                        purpose = cells[purpose_idx]
                        if purpose:
                            entry["purpose"] = purpose

                if "Required by" in header_cols:
                    req_idx = header_cols.index("Required by")
                    if req_idx < len(cells):
                        required_by = cells[req_idx]
                        if required_by:
                            entry["requiredBy"] = required_by

                if "Modrinth" in header_cols:
                    modrinth_idx = header_cols.index("Modrinth")
                    if modrinth_idx < len(cells) and cells[modrinth_idx].upper() == "N/A":
                        entry["forceNoModrinth"] = True

        else:
            in_table = False
            header_cols = []

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Seeded metadata entries: {len(mods)}")


if __name__ == "__main__":
    main()
