#!/usr/bin/env python3
"""Validate that .env.example and config.py Settings are in sync.

Parses the Settings class with Python's stdlib AST module (no extra
dependencies needed) and compares field names against the keys declared in
.env.example.  Exits with status 1 if any drift is found so CI fails fast.

Usage (from repo root):
    python scripts/check_env_keys.py
"""
import ast
import sys
from pathlib import Path


def env_example_keys(path: Path) -> set[str]:
    """Extract variable names from an env file (skip comments and blank lines)."""
    keys: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def settings_fields(config_path: Path) -> set[str]:
    """Extract annotated field names from the Settings class via AST.

    Returns names uppercased (matching env-var convention), skipping
    ``model_config`` and any ClassVar / non-annotated attributes.
    """
    tree = ast.parse(config_path.read_text())
    fields: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for item in node.body:
                if (
                    isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    and item.target.id != "model_config"
                ):
                    fields.add(item.target.id.upper())
    return fields


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env.example"
    config_path = root / "backend" / "src" / "chronocanvas" / "config.py"

    for p in (env_path, config_path):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)

    env_keys = env_example_keys(env_path)
    cfg_fields = settings_fields(config_path)

    missing_from_env = cfg_fields - env_keys
    extra_in_env = env_keys - cfg_fields

    ok = True

    if missing_from_env:
        ok = False
        print("FAIL: present in config.py Settings but absent from .env.example:")
        for key in sorted(missing_from_env):
            print(f"  - {key}")

    if extra_in_env:
        ok = False
        print("FAIL: present in .env.example but absent from config.py Settings:")
        for key in sorted(extra_in_env):
            print(f"  - {key}")

    if ok:
        print(f"OK: {len(env_keys)} keys are consistent between .env.example and config.py")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
