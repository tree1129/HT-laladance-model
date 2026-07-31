#!/usr/bin/env python3
"""Merge lala action entries into a robot's existing action YAML files."""

import argparse
import copy
from pathlib import Path

import yaml


LALA_NAMES = {f"lala{index:02d}" for index in range(1, 8)}


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def write_yaml(path: Path, data):
    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)


def merge_base(target, source):
    target_items = target.get("multi_waypoint_config") or []
    source_items = {
        item.get("name"): item
        for item in source.get("multi_waypoint_config") or []
        if item.get("name") in LALA_NAMES
    }
    retained = [item for item in target_items if item.get("name") not in LALA_NAMES]
    insert_at = next(
        (index + 1 for index, item in enumerate(retained) if item.get("name") == "cheer"),
        len(retained),
    )
    lala_items = [copy.deepcopy(source_items[name]) for name in sorted(source_items)]
    target["multi_waypoint_config"] = retained[:insert_at] + lala_items + retained[insert_at:]
    return target


def merge_custom(target, source):
    source_profiles = {
        profile.get("production_type"): profile
        for profile in source or []
    }
    for profile in target or []:
        source_profile = source_profiles.get(profile.get("production_type")) or {}
        source_items = {
            item.get("name"): item
            for item in source_profile.get("multi_waypoint_config") or []
            if item.get("name") in LALA_NAMES
        }
        target_items = profile.get("multi_waypoint_config") or []
        retained = [item for item in target_items if item.get("name") not in LALA_NAMES]
        insert_at = next(
            (index + 1 for index, item in enumerate(retained) if item.get("name") == "cheer"),
            len(retained),
        )
        lala_items = [copy.deepcopy(source_items[name]) for name in sorted(source_items)]
        profile["multi_waypoint_config"] = retained[:insert_at] + lala_items + retained[insert_at:]
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target_base", type=Path)
    parser.add_argument("target_custom", type=Path)
    parser.add_argument("source_base", type=Path)
    parser.add_argument("source_custom", type=Path)
    parser.add_argument("output_base", type=Path)
    parser.add_argument("output_custom", type=Path)
    args = parser.parse_args()

    merged_base = merge_base(load_yaml(args.target_base), load_yaml(args.source_base))
    merged_custom = merge_custom(load_yaml(args.target_custom), load_yaml(args.source_custom))
    write_yaml(args.output_base, merged_base)
    write_yaml(args.output_custom, merged_custom)

    base_names = [
        item.get("name")
        for item in merged_base.get("multi_waypoint_config") or []
        if item.get("name") in LALA_NAMES
    ]
    print(f"Merged base actions: {', '.join(base_names)}")


if __name__ == "__main__":
    main()
