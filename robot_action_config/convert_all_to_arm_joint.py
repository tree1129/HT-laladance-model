#!/usr/bin/env python3
"""Extract the eight arm joints from a 22-DOF Boost text archive."""

import argparse
from pathlib import Path


ARCHIVE_PREFIX = ["22", "serialization::archive"]
ARM_START_INDEX = 12
ARM_JOINT_COUNT = 8


def parse_archive(path: Path):
    tokens = path.read_text(encoding="utf-8").split()
    if len(tokens) < 9 or tokens[:2] != ARCHIVE_PREFIX:
        raise ValueError(f"Unsupported Boost text archive: {path}")

    archive_version = tokens[2]
    name_length = int(tokens[3])
    kind = tokens[4]
    if len(kind) != name_length:
        raise ValueError(f"Invalid archive type header: {kind}")
    if tokens[5:7] != ["0", "0"] or tokens[8] != "0":
        raise ValueError("Unsupported archive metadata")

    frame_count = int(tokens[7])
    cursor = 9
    frames = []
    for frame_index in range(frame_count):
        if cursor + 2 > len(tokens):
            raise ValueError(f"Truncated frame header at index {frame_index}")
        width = int(tokens[cursor])
        marker = tokens[cursor + 1]
        cursor += 2
        if marker != "0" or cursor + width > len(tokens):
            raise ValueError(f"Invalid frame at index {frame_index}")
        frames.append(tokens[cursor:cursor + width])
        cursor += width

    if cursor != len(tokens):
        raise ValueError(f"Unexpected trailing tokens: {len(tokens) - cursor}")
    return archive_version, kind, frames


def write_arm_archive(path: Path, archive_version: str, frames):
    lines = [
        f"22 serialization::archive {archive_version} 9 arm_joint 0 0 {len(frames)} 0"
    ]
    for frame in frames:
        arm_values = frame[ARM_START_INDEX:ARM_START_INDEX + ARM_JOINT_COUNT]
        if len(arm_values) != ARM_JOINT_COUNT:
            raise ValueError("Source frame does not contain all eight arm joints")
        lines.append("8 0 " + " ".join(arm_values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Refusing to overwrite the source archive")

    archive_version, kind, frames = parse_archive(args.source)
    if kind != "all":
        raise ValueError(f"Expected an 'all' archive, got '{kind}'")
    if not frames or any(len(frame) != 22 for frame in frames):
        raise ValueError("Expected non-empty 22-DOF frames")

    write_arm_archive(args.output, archive_version, frames)
    print(
        f"Converted {len(frames)} frames: all/22 joints -> arm_joint/8 joints: "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()
