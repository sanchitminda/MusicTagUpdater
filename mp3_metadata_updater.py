#!/usr/bin/env python3
"""
mp3_metadata_updater.py

Scan a directory (and subdirectories) for MP3 files and update ID3 metadata.

Features:
- Recursively find .mp3 files
- Show a CLI menu to pick which tag(s) to update
- For each tag, allow value source: parent folder name, grandparent folder name, or custom value
- Dry-run mode to preview changes before writing
- Option to apply changes in batch

Requires: mutagen
"""
import argparse
import os
import sys
from collections import defaultdict
from typing import List, Dict, Tuple

try:
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3NoHeaderError
except Exception:
    print("Missing dependency 'mutagen'. Install with: pip install -r requirements.txt")
    raise


DEFAULT_TAGS = [
    "title",
    "artist",
    "album",
    "date",
    "tracknumber",
    "genre",
]


def scan_mp3_files(root: str) -> List[str]:
    mp3s = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith('.mp3'):
                mp3s.append(os.path.join(dirpath, fn))
    return mp3s


def read_tags(path: str) -> Dict[str, List[str]]:
    try:
        tags = EasyID3(path)
    except ID3NoHeaderError:
        # No ID3 header; return empty mapping
        return {}
    except Exception:
        return {}
    return dict(tags)


def preview_changes(files: List[str], tag: str, source: str, custom_value: str = None) -> List[Tuple[str, str, str]]:
    """Return list of (file, old_value, new_value) tuples for preview."""
    results = []
    for f in files:
        tags = read_tags(f)
        old = ', '.join(tags.get(tag, [])) if tags.get(tag) else ''
        new = ''
        if source == 'parent':
            new = os.path.basename(os.path.dirname(f))
        elif source == 'grandparent':
            new = os.path.basename(os.path.dirname(os.path.dirname(f)))
        elif source == 'custom':
            new = custom_value or ''
        results.append((f, old, new))
    return results


def apply_changes(previews: List[Tuple[str, str, str]], tag: str, commit: bool) -> int:
    written = 0
    if not commit:
        return 0
    for f, old, new in previews:
        try:
            try:
                tags = EasyID3(f)
            except ID3NoHeaderError:
                tags = EasyID3()
            if new:
                tags[tag] = new
            else:
                # remove tag if empty
                if tag in tags:
                    del tags[tag]
            tags.save(f)
            written += 1
        except Exception as e:
            print(f"Failed to write {f}: {e}")
    return written


def ask_choice(prompt: str, choices: List[str]) -> int:
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    while True:
        v = input(prompt + ' ')
        if not v:
            continue
        try:
            vi = int(v)
            if 1 <= vi <= len(choices):
                return vi - 1
        except ValueError:
            pass
        print("Please enter a valid number from the menu.")


def interactive_menu(root: str, files: List[str]):
    if not files:
        print("No mp3 files found under:", root)
        return

    print(f"Found {len(files)} mp3 files under: {root}")

    # let user pick tags to update
    print("\nWhich metadata field would you like to update? (select one)")
    tag_idx = ask_choice("Enter number:", DEFAULT_TAGS + ["other (provide ID3 key)"])
    if tag_idx < len(DEFAULT_TAGS):
        tag = DEFAULT_TAGS[tag_idx]
    else:
        tag = input("Enter the ID3 key (e.g., composer, albumartist, title): ").strip()
        if not tag:
            print("No tag provided; aborting.")
            return

    # choose source
    print("\nChoose source for new value:")
    source_idx = ask_choice("Enter number:", ["parent folder name", "grandparent folder name", "custom value"])
    source_map = {0: 'parent', 1: 'grandparent', 2: 'custom'}
    source = source_map[source_idx]
    custom_value = None
    if source == 'custom':
        custom_value = input("Enter the custom value to set (leave empty to clear the tag): ").strip()

    # preview
    previews = preview_changes(files, tag, source, custom_value)
    # show a compact preview: up to first 20 changes
    print("\nPreview of changes (first 50 shown):")
    for i, (f, old, new) in enumerate(previews[:50], 1):
        rel = os.path.relpath(f, root)
        print(f"{i}. {rel}\n    old: {old!r}\n    new: {new!r}")
    if len(previews) > 50:
        print(f"... and {len(previews)-50} more files")

    # confirm
    confirm = input('\nApply these changes? Type "yes" to commit, anything else to abort (dry-run): ').strip().lower()
    commit = confirm == 'yes'
    written = apply_changes(previews, tag, commit)
    if commit:
        print(f"Wrote tags to {written} files.")
    else:
        print("Dry-run complete. No files were modified.")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Scan and update MP3 metadata (ID3)')
    p.add_argument('root', nargs='?', default='.', help='Root folder to scan for MP3 files')
    p.add_argument('--non-interactive', '-n', action='store_true', help='Non-interactive: just list files found and exit')
    p.add_argument('--tags', '-t', nargs='*', help='Show tags for a sample of files (comma separated)')
    p.add_argument('--dry-run', action='store_true', help='Only preview changes (used with programmatic options).')
    return p


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    root = os.path.abspath(args.root)
    files = scan_mp3_files(root)

    if args.non_interactive:
        print(f"Found {len(files)} mp3 files under: {root}")
        # show tags for up to 5 files if requested
        sample = files[:5]
        for f in sample:
            print('-', os.path.relpath(f, root))
            tags = read_tags(f)
            if tags:
                for k, v in tags.items():
                    print(f"    {k}: {', '.join(v)}")
            else:
                print("    (no tags)")
        return

    try:
        interactive_menu(root, files)
    except KeyboardInterrupt:
        print('\nInterrupted. Exiting.')


if __name__ == '__main__':
    main()
