#!/usr/bin/env python3
"""Crée ou renouvelle le token local du Zotero Bridge sans jamais l'afficher."""

from __future__ import annotations

import argparse
import os
import secrets
import stat
import tempfile
from pathlib import Path


DEFAULT_DIRECTORY = Path.home() / ".codex-zotero-bridge"
# Windows ne connaît pas les permissions POSIX : le dossier du profil protège le token.
POSIX = os.name != "nt"


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def check(token_path: Path) -> None:
    if not token_path.is_file():
        raise SystemExit(f"Token absent : {token_path}")
    if POSIX and mode(token_path) != 0o600:
        raise SystemExit(f"Permissions incorrectes sur {token_path}; attendu 0600.")
    if len(token_path.read_text(encoding="utf-8").strip()) < 32:
        raise SystemExit(f"Token invalide : {token_path}")
    print(f"Token présent et protégé : {token_path}")


def provision(directory: Path, rotate: bool) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    token_path = directory / "token"
    if token_path.exists() and not rotate:
        os.chmod(token_path, 0o600)
        check(token_path)
        return

    descriptor, temporary_name = tempfile.mkstemp(prefix="token.", dir=directory)
    temporary = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(secrets.token_hex(32) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, token_path)
        os.chmod(token_path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)
    action = "renouvelé" if rotate else "créé"
    print(f"Token {action} et protégé : {token_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="vérifie sans modifier")
    parser.add_argument("--rotate", action="store_true", help="remplace le token existant")
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    token_path = args.directory.expanduser() / "token"
    if args.check:
        check(token_path)
    else:
        provision(args.directory.expanduser(), args.rotate)


if __name__ == "__main__":
    main()
