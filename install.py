#!/usr/bin/env python3
import argparse
import os
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict

HOME = Path.home()
SCRIPT_DIR = Path(__file__).parent

FILES_CONFIG: List[Dict[str, str]] = [
    {"path": ".local/bin/nvim", "link_name": "nvim"},
    {"path": ".local/share/nvim", "link_name": "share"},
    {"path": ".config/nvim", "link_name": "config"},
]


def print_help():
    help_text = """
Usage: python install.py [OPTIONS]

Options:
    -i, --install      Install symlinks (default)
    -f, --force        Force installation, overwrite existing files
    -u, --uninstall    Uninstall symlinks
    -b, --backup       Create backup before installation/uninstallation
    -h, --help         Show this help message

Examples:
    python install.py              # Install
    python install.py -i           # Install
    python install.py -i -f        # Force install
    python install.py -u           # Uninstall
    python install.py -i -b        # Install with backup
    python install.py -u -b        # Uninstall with backup
"""
    print(help_text)


def check_existing_files(config: List[Dict[str, str]]) -> List[str]:
    existing = []
    for item in config:
        target_path = HOME / item["path"]
        if target_path.exists():
            existing.append(str(target_path))
    return existing


def backup():
    parent_dir = SCRIPT_DIR.parent
    folder_name = SCRIPT_DIR.name
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup_filename = f"{folder_name}-{timestamp}.tar.gz"
    backup_path = parent_dir / backup_filename

    link_names = set()
    for item in FILES_CONFIG:
        link_name = item.get("link_name", "")
        if link_name:
            link_names.add(link_name)

    with tarfile.open(backup_path, "w:gz") as tar:
        for dirpath, dirnames, filenames in os.walk(SCRIPT_DIR, followlinks=False):
            current_dir = Path(dirpath)
            
            dirnames[:] = [d for d in dirnames if not (current_dir / d).is_symlink()]
            
            for filename in filenames:
                file_path = current_dir / filename
                if file_path.is_symlink():
                    continue
                rel_path = file_path.relative_to(SCRIPT_DIR)
                if rel_path.name not in link_names:
                    tar.add(file_path, arcname=rel_path)

    print(f"Created backup: {backup_path}")
    return backup_path


def install(force: bool = False, backup_first: bool = False):
    if backup_first:
        backup()

    for item in FILES_CONFIG:
        rel_path = item["path"]
        link_name = item.get("link_name", "")
        
        source_path = SCRIPT_DIR / rel_path
        
        if link_name:
            link_path = SCRIPT_DIR / link_name
            if link_path.resolve() == source_path.resolve():
                print(f"Error: link_name '{link_name}' would overwrite the source file '{source_path}'")
                print("       link_name cannot point to the same location as the source file")
                sys.exit(1)

    existing_files = check_existing_files(FILES_CONFIG)
    if existing_files and not force:
        print("Error: The following files/directories already exist:")
        for f in existing_files:
            print(f"  - {f}")
        print("\nUse --force to overwrite existing files.")
        sys.exit(1)

    for item in FILES_CONFIG:
        rel_path = item["path"]
        link_name = item.get("link_name", "")

        source_path = SCRIPT_DIR / rel_path
        target_path = HOME / rel_path

        if not source_path.exists():
            print(f"Warning: Source path does not exist: {source_path}")
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.exists() or target_path.is_symlink():
            target_path.unlink()

        os.symlink(source_path, target_path)
        print(f"Created symlink: {target_path} -> {source_path}")

        if link_name:
            link_path = SCRIPT_DIR / link_name
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            os.symlink(source_path, link_path)
            print(f"Created symlink: {link_path} -> {source_path}")

    print("\nInstallation completed successfully.")


def uninstall(backup_first: bool = False):
    if backup_first:
        backup()

    for item in FILES_CONFIG:
        rel_path = item["path"]
        link_name = item.get("link_name", "")

        target_path = HOME / rel_path
        link_path = SCRIPT_DIR / link_name if link_name else None

        if target_path.is_symlink():
            target_path.unlink()
            print(f"Removed symlink: {target_path}")
        elif target_path.exists():
            print(f"Warning: {target_path} exists but is not a symlink, skipping")

        if link_path and link_path.is_symlink():
            link_path.unlink()
            print(f"Removed symlink: {link_path}")

    print("\nUninstallation completed successfully.")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-i", "--install", action="store_true", help="Install symlinks")
    parser.add_argument("-f", "--force", action="store_true", help="Force installation")
    parser.add_argument("-u", "--uninstall", action="store_true", help="Uninstall symlinks")
    parser.add_argument("-b", "--backup", action="store_true", help="Create backup (can be used alone)")
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")

    args = parser.parse_args()

    if args.help:
        print_help()
        sys.exit(0)

    if args.backup and not args.install and not args.uninstall:
        backup()
        print("\nBackup completed successfully.")
        sys.exit(0)

    if args.uninstall:
        uninstall(backup_first=args.backup)
    else:
        install(force=args.force, backup_first=args.backup)


if __name__ == "__main__":
    main()