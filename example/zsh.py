#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict

HOME = Path.home()
SCRIPT_DIR = Path(__file__).parent

FILES_CONFIG: List[Dict[str, str]] = [
    {"path": ".config/sheldon", "link_name": "config"},
    {"path": ".local/share/sheldon", "link_name": "share"},
    {"path": ".local/bin/sheldon", "link_name": "sheldon"},
    {"path": ".zshrc", "link_name": "zshrc"},
    {"path": ".p10k.zsh", "link_name": "p10k.zsh"},
    {"path": ".local/shell", "link_name": "shell"},
]


def print_help():
    help_text = """
Usage: python install.py [OPTIONS]

Options:
    -i, --install      Install symlinks (default)
    -f, --force        Force installation, overwrite existing files
    -u, --uninstall    Uninstall symlinks
    -h, --help         Show this help message

Examples:
    python install.py              # Install
    python install.py -i           # Install
    python install.py -i -f        # Force install
    python install.py -u           # Uninstall
"""
    print(help_text)


def check_existing_files(config: List[Dict[str, str]]) -> List[str]:
    existing = []
    for item in config:
        target_path = HOME / item["path"]
        if target_path.exists():
            existing.append(str(target_path))
    return existing


def install(force: bool = False):
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


def uninstall():
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
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")

    args = parser.parse_args()

    if args.help:
        print_help()
        sys.exit(0)

    if args.uninstall:
        uninstall()
    else:
        install(force=args.force)


if __name__ == "__main__":
    main()