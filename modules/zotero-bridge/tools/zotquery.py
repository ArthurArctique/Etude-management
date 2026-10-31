#!/usr/bin/env python3
"""zotquery — secours hors ligne EN LECTURE SEULE pour Zotero.

Utiliser normalement ``zot.py search_items`` et ``zot.py get_items``. Ce programme
reste disponible lorsque Zotero ou le bridge n'est pas lancé. Il crée un instantané
cohérent avec l'API de sauvegarde SQLite, puis ouvre cet instantané en lecture seule.

Détection des chemins (surchargeable par variables d'environnement) :
  ZOTERO_DIR       dossier contenant zotero.sqlite   (défaut : ~/Zotero)
  ZOTERO_BASE_DIR  base des fichiers LIÉS             (auto-détecté)

Commandes :
  list                     liste les références + chemins PDF (100 max par défaut)
  search <termes...>       recherche (titre, auteurs, résumé, tags, collections)
  path <clé|bout de titre> chemin(s) absolu(s) du/des PDF d'une référence
  collections              liste des collections et nb d'items
Options : --json · --pdf-only · --limit N · --all
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Détection des chemins (multi-plateforme : macOS / Windows / Linux)
# --------------------------------------------------------------------------- #
def find_zotero_dir() -> Path:
    env = os.environ.get("ZOTERO_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Zotero"  # même défaut sur macOS et Windows


def find_base_dir() -> Path:
    env = os.environ.get("ZOTERO_BASE_DIR")
    if env:
        return Path(env).expanduser()
    home = Path.home()
    candidates = [
        home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Zotero",  # macOS iCloud
        home / "iCloudDrive" / "Zotero",   # Windows iCloud (défaut)
        home / "iCloud Drive" / "Zotero",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # macOS par défaut, à surcharger via ZOTERO_BASE_DIR


# --------------------------------------------------------------------------- #
# Ouverture sûre (copie -> read-only)
# --------------------------------------------------------------------------- #
def open_db(zdir: Path):
    src = zdir / "zotero.sqlite"
    if not src.exists():
        sys.exit(f"[zotquery] zotero.sqlite introuvable dans {zdir}\n"
                 f"           -> définis la variable ZOTERO_DIR.")
    tmp = Path(tempfile.mkdtemp(prefix="zotquery_"))
    snapshot = tmp / src.name
    source = None
    destination = None
    snapshot_error = None
    deadline = time.monotonic() + 5

    def stop_if_busy(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError("Zotero maintient la base active")

    try:
        source = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=2)
        destination = sqlite3.connect(snapshot)
        source.backup(destination, pages=256, progress=stop_if_busy, sleep=0.05)
    except (sqlite3.Error, TimeoutError) as exc:
        snapshot_error = exc
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
    if snapshot_error is not None:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(
            f"[zotquery] instantané indisponible : {snapshot_error}. "
            "Utilise zot.py pendant que Zotero est ouvert, ou ferme Zotero avant le secours hors ligne."
        )
    con = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con, tmp


# --------------------------------------------------------------------------- #
# Briques de requête
# --------------------------------------------------------------------------- #
def field(con, item_id, name):
    r = con.execute(
        "SELECT idv.value FROM itemData id "
        "JOIN itemDataValues idv ON idv.valueID = id.valueID "
        "JOIN fields f ON f.fieldID = id.fieldID "
        "WHERE id.itemID = ? AND f.fieldName = ?", (item_id, name)).fetchone()
    return r[0] if r else None


def creators(con, item_id):
    rows = con.execute(
        "SELECT c.lastName, c.firstName FROM itemCreators ic "
        "JOIN creators c ON c.creatorID = ic.creatorID "
        "WHERE ic.itemID = ? ORDER BY ic.orderIndex", (item_id,)).fetchall()
    out = []
    for last, first in rows:
        name = (last or "").strip()
        if first:
            name = f"{name}, {first}".strip(", ")
        if name:
            out.append(name)
    return out


def collections_of(con, item_id):
    rows = con.execute(
        "SELECT col.collectionName FROM collectionItems ci "
        "JOIN collections col ON col.collectionID = ci.collectionID "
        "WHERE ci.itemID = ?", (item_id,)).fetchall()
    return [r[0] for r in rows]


def tags_of(con, item_id):
    rows = con.execute(
        "SELECT t.name FROM itemTags it JOIN tags t ON t.tagID = it.tagID "
        "WHERE it.itemID = ?", (item_id,)).fetchall()
    return [r[0] for r in rows]


def resolve(path, key, zdir, base):
    """Résout un chemin de pièce jointe Zotero -> chemin absolu du fichier."""
    if not path:
        return None
    if path.startswith("storage:"):
        return str(zdir / "storage" / key / path[len("storage:"):])
    if path.startswith("attachments:"):
        return str(base / path[len("attachments:"):])
    return path  # fichier lié en chemin absolu (pas de base directory)


def attachments(con, parent_id, zdir, base):
    rows = con.execute(
        "SELECT att.key AS key, ia.contentType AS ct, ia.path AS path "
        "FROM itemAttachments ia JOIN items att ON att.itemID = ia.itemID "
        "WHERE ia.parentItemID = ? "
        "AND ia.itemID NOT IN (SELECT itemID FROM deletedItems)",
        (parent_id,)).fetchall()
    return [{"key": r["key"], "contentType": r["ct"],
             "abspath": resolve(r["path"], r["key"], zdir, base)} for r in rows]


def top_level_items(con):
    return con.execute(
        "SELECT i.itemID AS id, i.key AS key, it.typeName AS type "
        "FROM items i JOIN itemTypes it ON it.itemTypeID = i.itemTypeID "
        "WHERE it.typeName NOT IN ('attachment','note','annotation') "
        "AND i.itemID NOT IN (SELECT itemID FROM deletedItems) "
        "ORDER BY i.itemID").fetchall()


def build_record(con, row, zdir, base):
    iid = row["id"]
    atts = attachments(con, iid, zdir, base)
    pdfs = [a["abspath"] for a in atts if a["contentType"] == "application/pdf"]
    return {
        "key": row["key"],
        "type": row["type"],
        "title": field(con, iid, "title"),
        "date": field(con, iid, "date"),
        "creators": creators(con, iid),
        "collections": collections_of(con, iid),
        "tags": tags_of(con, iid),
        "abstract": field(con, iid, "abstractNote"),
        "pdfs": pdfs,
        "attachments": atts,
    }


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #
def exists_mark(p):
    try:
        return "OK " if p and Path(p).exists() else "ABS"
    except OSError:
        return " ? "


def print_record(rec, pdf_only=False):
    if pdf_only:
        for p in rec["pdfs"]:
            print(p)
        return
    print(f"[{rec['key']}] {rec['title'] or '(sans titre)'}")
    if rec["creators"]:
        print(f"    Auteurs    : {'; '.join(rec['creators'])}")
    meta = [x for x in (rec["date"], rec["type"]) if x]
    if meta:
        print(f"    Infos      : {' · '.join(meta)}")
    if rec["collections"]:
        print(f"    Collections: {', '.join(rec['collections'])}")
    if rec["tags"]:
        print(f"    Tags       : {', '.join(rec['tags'])}")
    for p in rec["pdfs"]:
        print(f"    PDF [{exists_mark(p)}] : {p}")
    print()


def searchable(rec):
    parts = [rec["title"] or "", rec["abstract"] or "",
             " ".join(rec["creators"]), " ".join(rec["collections"]),
             " ".join(rec["tags"])]
    return " ".join(parts).lower()


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Accès lecture seule à Zotero")
    ap.add_argument("command", choices=["list", "search", "path", "collections"])
    ap.add_argument("terms", nargs="*")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    ap.add_argument("--pdf-only", action="store_true", help="n'affiche que les chemins PDF")
    ap.add_argument("--limit", type=int, default=100, help="nombre maximal de résultats")
    ap.add_argument("--all", action="store_true", help="désactive la limite")
    args = ap.parse_args()

    if args.limit < 1:
        ap.error("--limit doit être supérieur ou égal à 1")

    zdir, base = find_zotero_dir(), find_base_dir()
    con, tmp = open_db(zdir)
    try:
        if args.command == "collections":
            rows = con.execute(
                "SELECT col.collectionName, COUNT(ci.itemID) "
                "FROM collections col "
                "LEFT JOIN collectionItems ci ON ci.collectionID = col.collectionID "
                "GROUP BY col.collectionID ORDER BY col.collectionName").fetchall()
            if args.json:
                print(json.dumps([{"name": r[0], "items": r[1]} for r in rows],
                                 ensure_ascii=False, indent=2))
            else:
                for name, n in rows:
                    print(f"  {n:>3}  {name}")
            return

        records = [build_record(con, r, zdir, base) for r in top_level_items(con)]

        if args.command == "search":
            q = " ".join(args.terms).lower().strip()
            if not q:
                sys.exit("[zotquery] search : précise un terme.")
            records = [r for r in records if all(w in searchable(r) for w in q.split())]

        if args.command == "path":
            key = " ".join(args.terms).strip()
            if not key:
                sys.exit("[zotquery] path : précise une clé ou un bout de titre.")
            match = [r for r in records if r["key"].lower() == key.lower()]
            if not match:
                match = [r for r in records if key.lower() in (r["title"] or "").lower()]
            pdf_count = 0
            for r in match:
                for p in r["pdfs"]:
                    print(p)
                    pdf_count += 1
            if not match:
                sys.exit(f"[zotquery] aucune référence pour « {key} ».")
            if not pdf_count:
                sys.exit(f"[zotquery] référence trouvée, mais aucun PDF associé pour « {key} ».")
            return

        if not args.all:
            records = records[:args.limit]

        if args.json:
            print(json.dumps(records, ensure_ascii=False, indent=2))
        else:
            if not records:
                print("(aucune référence)")
            for r in records:
                print_record(r, pdf_only=args.pdf_only)
    finally:
        con.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
