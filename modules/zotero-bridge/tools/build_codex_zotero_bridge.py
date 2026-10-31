#!/usr/bin/env python3
"""Construit le XPI du Zotero Bridge et refuse tout secret embarqué."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse


TOKEN_LIKE = re.compile(r"(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])", re.IGNORECASE)
REQUIRED = ("manifest.json", "install.rdf", "bootstrap.js")


def validate(source: Path) -> None:
    missing = [name for name in REQUIRED if not (source / name).is_file()]
    if missing:
        raise SystemExit("Fichiers manquants : " + ", ".join(missing))
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    zotero = manifest.get("applications", {}).get("zotero", {})
    if zotero.get("id") != "codex-zotero-bridge@local":
        raise SystemExit("Identifiant de plugin inattendu dans manifest.json.")
    update_url = urlparse(zotero.get("update_url", ""))
    if update_url.scheme != "https" or not update_url.hostname:
        raise SystemExit("Zotero exige applications.zotero.update_url avec une URL HTTPS.")
    for field in ("strict_min_version", "strict_max_version"):
        if not zotero.get(field):
            raise SystemExit("Champ Zotero obligatoire manquant : " + field)
    for name in REQUIRED:
        text = (source / name).read_text(encoding="utf-8")
        if "claude" in text.lower():
            raise SystemExit(f"Ancienne nomenclature détectée dans {name}.")
        if TOKEN_LIKE.search(text):
            raise SystemExit(f"Secret potentiel détecté dans {name}; construction refusée.")


def build(source: Path, output: Path) -> None:
    validate(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".xpi", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in REQUIRED:
                archive.write(source / name, name)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).with_name("codex-zotero-bridge"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("codex-zotero-bridge.xpi"),
    )
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())
    print(args.output.resolve())


if __name__ == "__main__":
    main()
