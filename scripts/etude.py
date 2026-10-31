#!/usr/bin/env python3
"""Installateur d'Etude management : espace de travail et modules de skills.

Bibliothèque standard seulement (Python 3.9 ou plus récent). Chaque commande affiche du JSON.

  status                        état : configuration, espace, agents, modules, problèmes
  modules                       modules disponibles et compatibilité avec ce système
  init --answers FICHIER|-      crée l'espace de travail sans rien écraser, puis la configuration
  install MODULE [MODULE…]      installe ou met à jour des modules dans le dossier de skills
  update [--force]              réinstalle les modules déjà installés (après « git pull »)
  link                          relie ce skill aux dossiers de skills des autres agents
  set CLE=VALEUR|+DRAPEAU|-DRAPEAU …   modifie la configuration (ex. CLASSEUR=/chemin.xlsx)
  fragment MODULE|DRAPEAU       blocs d'AGENTS.md à ajouter quand un module ou une option arrive après coup

Rien n'est jamais écrasé dans l'espace de travail. Dans un dossier de skills, seuls les
dossiers créés par ce script (fichier .etude-module.json) sont mis à jour, et un fichier
modifié à la main n'est remplacé qu'avec --force.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "local" / "config.json"
MODULES_DIR = ROOT / "modules"
TEMPLATE_DIR = ROOT / "templates" / "espace"
MARKER = ".etude-module.json"
SELF_NAME = "etude-management"
RENDERED = {".md", ".yaml", ".yml"}
SKIPPED = {"module.json", ".DS_Store", "__pycache__"}

DEFAULT_AGENT_DIRS = {
    "claude": "~/.claude/skills",
    "codex": "~/.codex/skills",
}

TYPES = {
    "universite": {
        "libelle": "études universitaires",
        "travail": "Matieres",
        "unite": ["matière", "matières"],
        "activites": ["CM", "TD", "TP", "Projet"],
    },
    "autodidacte": {
        "libelle": "apprentissage en autonomie",
        "travail": "Sujets",
        "unite": ["sujet", "sujets"],
        "activites": ["Cours", "Exercices", "Projets"],
    },
    "recherche": {
        "libelle": "projet de recherche",
        "travail": "Projets",
        "unite": ["projet", "projets"],
        "activites": ["Lectures", "Analyses", "Redaction"],
    },
    "professionnel": {
        "libelle": "formation ou veille professionnelle",
        "travail": "Themes",
        "unite": ["thème", "thèmes"],
        "activites": ["Formation", "Exercices", "Projets"],
    },
    "autre": {
        "libelle": "autre domaine d'étude",
        "travail": "Travail",
        "unite": ["thème", "thèmes"],
        "activites": ["Cours", "Exercices", "Projets"],
    },
}

PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
CONDITION = re.compile(r"^[ \t]*<!-- (si|fin):(!?)([a-z0-9-]+) -->[ \t]*$")
INLINE_CONDITION = re.compile(r"<!-- (si|fin):")


class Failure(Exception):
    def __init__(self, message: str, **details: Any):
        super().__init__(message)
        self.message = message
        self.details = details


# --- Outils ------------------------------------------------------------------


def emit(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def today() -> str:
    return dt.date.today().isoformat()


def expand(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Failure(f"JSON invalide dans {path} : {exc}")


def write_atomic(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".etude.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_config(required: bool = True) -> dict[str, Any] | None:
    if not CONFIG.exists():
        if required:
            raise Failure("Aucune configuration : lancer d'abord « init --answers ».", config=str(CONFIG))
        return None
    return load_json(CONFIG)


def save_config(config: dict[str, Any]) -> None:
    write_atomic(CONFIG, (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


# --- Gabarits ----------------------------------------------------------------


def render(text: str, variables: dict[str, Any], flags: set[str], origin: str) -> tuple[str, set[str]]:
    """Applique les blocs <!-- si:x --> … <!-- fin:x --> puis remplace les {{VARIABLES}}."""
    kept: list[str] = []
    stack: list[tuple[str, bool]] = []
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        match = CONDITION.match(line.rstrip("\r\n"))
        if not match and INLINE_CONDITION.search(line):
            raise Failure(f"{origin}:{number} : une condition doit occuper une ligne entière.")
        if match:
            kind, negated, name = match.groups()
            if kind == "si":
                stack.append((name, (name in flags) != bool(negated)))
            elif not stack or stack[-1][0] != name:
                raise Failure(f"{origin}:{number} : « fin:{name} » ne ferme aucun « si:{name} ».")
            else:
                stack.pop()
            continue
        if all(active for _, active in stack):
            kept.append(line)
    if stack:
        raise Failure(f"{origin} : bloc « si:{stack[-1][0]} » non fermé.")
    missing: set[str] = set()

    def substitute(match: re.Match[str]) -> str:
        value = variables.get(match.group(1))
        if value is None:
            missing.add(match.group(1))
            return match.group(0)
        return str(value)

    result = PLACEHOLDER.sub(substitute, "".join(kept))
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result, missing


def module_names() -> list[str]:
    return sorted(p.name for p in MODULES_DIR.iterdir() if (p / "module.json").is_file())


def module_info(name: str) -> dict[str, Any]:
    path = MODULES_DIR / name / "module.json"
    if not path.is_file():
        raise Failure(f"Module inconnu : {name}.", disponibles=module_names())
    info = load_json(path)
    info["nom"] = name
    info["compatible"] = sys.platform in info.get("systemes", [sys.platform])
    return info


def module_files(name: str) -> list[tuple[str, Path]]:
    """(chemin publié, source) de chaque fichier à installer pour un module."""
    source = MODULES_DIR / name
    excluded = {source / item for item in module_info(name).get("exclure", [])}
    files = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.name in SKIPPED or path.suffix == ".pyc":
            continue
        if any(part in SKIPPED for part in path.relative_to(source).parts):
            continue
        if any(path == item or item in path.parents for item in excluded):
            continue
        relative = path.relative_to(source).as_posix()
        files.append(("SKILL.md" if relative == "SKILL.template.md" else relative, path))
    return files


def variables_for(config: dict[str, Any], dest: Path | None = None) -> dict[str, Any]:
    variables = dict(config["vars"])
    variables["DEPOT"] = str(ROOT)
    if dest is not None:
        variables["SKILL_DIR"] = str(dest)
    return variables


def flags_for(config: dict[str, Any]) -> set[str]:
    flags = set(config.get("drapeaux", []))
    flags.update(config.get("modules", {}))
    flags.update(config.get("modules_choisis", []))
    flags.update(config.get("agents", {}))
    return flags


# --- Espace de travail -------------------------------------------------------


def build_config(answers: dict[str, Any]) -> dict[str, Any]:
    if not answers.get("espace"):
        raise Failure("Réponse obligatoire manquante : « espace » (chemin du dossier de travail).")
    kind = answers.get("type", "universite")
    if kind not in TYPES:
        raise Failure(f"Type inconnu : {kind}.", types=sorted(TYPES))
    preset = TYPES[kind]
    espace = expand(answers["espace"])
    folders = {"cadre": "00_Cadre", "a_faire": "01_A_faire", "travail": preset["travail"]}
    folders.update(answers.get("dossiers", {}))
    unite = answers.get("unite", preset["unite"])
    if isinstance(unite, str):
        unite = [unite, unite + "s"]
    activites = answers.get("activites", preset["activites"])
    example = "TP" if "TP" in activites else activites[0]

    notes = answers.get("notes", {})
    notes_rel = notes.get("chemin", "Obsidian" if notes.get("obsidian", True) else "Notes")
    notes_path = expand(notes_rel) if os.path.isabs(os.path.expanduser(notes_rel)) else espace / notes_rel
    obsidian = bool(notes.get("obsidian", True))

    agents_answer = answers.get("agents", ["claude"])
    if isinstance(agents_answer, list):
        agents_answer = {name: DEFAULT_AGENT_DIRS.get(name) for name in agents_answer}
    agents = {}
    for name, folder in agents_answer.items():
        if not folder:
            raise Failure(f"Dossier de skills inconnu pour l'agent « {name} » : le préciser.")
        agents[name] = str(expand(folder))
    principal = answers.get("principal", next(iter(agents)))
    if principal not in agents:
        raise Failure(f"Agent principal « {principal} » absent de « agents ».")

    chosen = list(dict.fromkeys(answers.get("modules", [])))
    for name in chosen:
        module_info(name)
    flags = {kind}
    if obsidian:
        flags.add("obsidian")
    if answers.get("moodle"):
        flags.add("moodle-bridge")
    zotero = answers.get("zotero", {})
    if "zotero-bridge" in chosen and zotero.get("supports", True):
        flags.add("supports-zotero")
    if notes_path.parent != espace and not str(notes_path).startswith(str(espace) + os.sep):
        flags.add("notes-externes")

    variables = {
        "ESPACE": str(espace),
        "TITRE": answers.get("titre", espace.name),
        "DOMAINE": answers.get("domaine", answers.get("titre", espace.name)),
        "TYPE": kind,
        "TYPE_LIBELLE": preset["libelle"],
        "LANGUE": answers.get("langue", "français"),
        "CADRE": folders["cadre"],
        "AFAIRE": folders["a_faire"],
        "TRAVAIL": folders["travail"],
        "UNITE": unite[0],
        "UNITES": unite[1],
        "ACTIVITES": ", ".join(f"`{a}`" for a in activites),
        "ACTIVITE_EXEMPLE": f"{folders['travail']}/<CODE>/{example}/{example}01/",
        "NOTES": str(notes_path),
        "NOTES_REL": notes_rel if not os.path.isabs(os.path.expanduser(notes_rel)) else str(notes_path),
        "NOTES_LIBELLE": "le vault Obsidian" if obsidian else "le dossier de notes Markdown",
        "INDEX": str(espace / folders["cadre"] / "Index-correspondances.md"),
        "DATE": today(),
    }
    if zotero.get("fichiers"):
        variables["ZOTERO_FICHIERS"] = str(expand(zotero["fichiers"]))
    if answers.get("classeur"):
        variables["CLASSEUR"] = str(expand(answers["classeur"]))
    return {
        "version": 1,
        "cree_le": today(),
        "agents": agents,
        "principal": principal,
        "vars": variables,
        "drapeaux": sorted(flags),
        "modules_choisis": chosen,
        "modules": {},
    }


def cmd_init(args: argparse.Namespace) -> dict[str, Any]:
    raw = sys.stdin.read() if args.answers == "-" else Path(args.answers).read_text(encoding="utf-8")
    try:
        answers = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Failure(f"Réponses JSON invalides : {exc}")
    config = build_config(answers)
    previous = load_config(required=False)
    if previous and previous["vars"]["ESPACE"] != config["vars"]["ESPACE"]:
        raise Failure(
            "Ce dépôt est déjà relié à un autre espace. Modifier la configuration avec « set », "
            "ou déplacer local/config.json avant une nouvelle installation.",
            espace_actuel=previous["vars"]["ESPACE"],
        )
    if previous:
        config["modules"] = previous.get("modules", {})
        config["cree_le"] = previous.get("cree_le", config["cree_le"])

    variables, flags = variables_for(config), flags_for(config)
    espace = Path(config["vars"]["ESPACE"])
    created, existing, missing = [], [], set()
    planned: list[tuple[Path, str]] = []
    for path in sorted(TEMPLATE_DIR.rglob("*")):
        if not path.is_file() or path.name in SKIPPED:
            continue
        relative, absent = render(path.relative_to(TEMPLATE_DIR).as_posix(), variables, flags, str(path))
        content, absent_content = render(path.read_text(encoding="utf-8"), variables, flags, str(path))
        missing |= absent | absent_content
        if content.strip():
            planned.append((espace / relative, content))
    if missing:
        raise Failure("Variables manquantes pour l'espace.", variables=sorted(missing))

    for directory in (espace / config["vars"]["CADRE"] / "Sources", espace / config["vars"]["TRAVAIL"]):
        directory.mkdir(parents=True, exist_ok=True)
    for target, content in planned:
        if target.exists():
            existing.append(str(target))
            continue
        write_atomic(target, content.encode("utf-8"))
        created.append(str(target))
    save_config(config)
    return {
        "ok": True,
        "config": str(CONFIG),
        "espace": str(espace),
        "crees": created,
        "deja_presents": existing,
        "modules_a_installer": [m for m in config["modules_choisis"] if m not in config["modules"]],
        "suite": "Installer les modules choisis : etude.py install <module> …",
    }


# --- Modules -----------------------------------------------------------------


def read_marker(dest: Path) -> dict[str, Any] | None:
    marker = dest / MARKER
    if dest.is_symlink() or not marker.is_file():
        return None
    return load_json(marker)


def fingerprint(name: str, variables: dict[str, Any], flags: set[str]) -> str:
    digest = hashlib.sha256()
    for relative, path in module_files(name):
        digest.update(relative.encode() + b"\0" + path.read_bytes() + b"\0")
    digest.update(json.dumps([variables, sorted(flags)], sort_keys=True).encode())
    return digest.hexdigest()


def check_destination(name: str, dest: Path) -> None:
    marker = read_marker(dest)
    if (dest.exists() or dest.is_symlink()) and (marker is None or marker.get("module") != name):
        raise Failure(
            f"{dest} existe déjà et n'a pas été créé par Etude management : rien n'a été modifié. "
            "Demander à l'utilisateur s'il faut le renommer ou garder son skill actuel.",
            module=name, dossier=str(dest),
        )


def install_into(name: str, dest: Path, config: dict[str, Any], force: bool) -> dict[str, Any]:
    check_destination(name, dest)
    marker = read_marker(dest)
    variables, flags = variables_for(config, dest), flags_for(config) | {name}
    staged: dict[str, tuple[bytes, int]] = {}
    missing: set[str] = set()
    for relative, path in module_files(name):
        data = path.read_bytes()
        if path.suffix in RENDERED:
            text, absent = render(data.decode("utf-8"), variables, flags, f"{name}/{relative}")
            missing |= absent
            data = text.encode("utf-8")
        staged[relative] = (data, path.stat().st_mode & 0o777)
    if missing:
        raise Failure(
            f"Variables manquantes pour le module {name} : les définir avec « set ».",
            module=name, variables=sorted(missing),
        )

    previous = (marker or {}).get("fichiers", {})
    written, kept, removed = [], [], []
    for relative, (data, mode) in staged.items():
        target = dest / relative
        if target.exists() and relative in previous and not force:
            current = sha256(target.read_bytes())
            if current != previous[relative] and current != sha256(data):
                kept.append(relative)
                continue
        if not target.exists() or target.read_bytes() != data:
            write_atomic(target, data, mode)
            written.append(relative)
    for relative in previous:
        if relative not in staged and (dest / relative).is_file():
            if sha256((dest / relative).read_bytes()) == previous[relative] or force:
                (dest / relative).unlink()
                removed.append(relative)
    hashes = {rel: sha256((dest / rel).read_bytes()) for rel in staged if rel not in kept}
    hashes.update({rel: previous[rel] for rel in kept})
    write_atomic(dest / MARKER, (json.dumps({
        "module": name,
        "depot": str(ROOT),
        "revision": revision(),
        "installe_le": dt.datetime.now().isoformat(timespec="seconds"),
        "empreinte": fingerprint(name, variables, flags),
        "fichiers": hashes,
    }, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"dossier": str(dest), "ecrits": written, "modifies_a_la_main_conserves": kept, "retires": removed}


def link_secondary(name: str, dest: Path, config: dict[str, Any], force: bool) -> list[dict[str, Any]]:
    links = []
    for agent, folder in config["agents"].items():
        if agent == config["principal"]:
            continue
        link = Path(folder) / name
        entry = {"agent": agent, "lien": str(link)}
        if link.is_symlink() and link.resolve() == dest.resolve():
            entry["etat"] = "déjà relié"
        elif link.exists() or link.is_symlink():
            if read_marker(link) and read_marker(link).get("module") == name:
                entry.update(install_into(name, link, config, force), etat="copie mise à jour")
            else:
                entry["etat"] = "conflit : un autre skill porte ce nom, rien n'a été modifié"
        else:
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                link.symlink_to(dest, target_is_directory=True)
                entry["etat"] = "relié"
            except OSError:
                entry.update(install_into(name, link, config, force), etat="copie (lien impossible)")
        links.append(entry)
    return links


def install_modules(names: list[str], config: dict[str, Any], force: bool) -> list[dict[str, Any]]:
    results = []
    for name in names:
        info = module_info(name)
        if not info["compatible"]:
            raise Failure(
                f"Le module {name} ne fonctionne pas sur ce système ({sys.platform}).",
                systemes=info.get("systemes"),
            )
        missing = [v for v in info.get("requis", []) if not config["vars"].get(v)]
        if missing:
            raise Failure(
                f"Le module {name} demande d'abord : {', '.join(missing)} (« set CLE=VALEUR »).",
                module=name, variables=missing,
            )
        check_destination(name, Path(config["agents"][config["principal"]]) / name)
    # Rien n'est écrit tant que tous les modules demandés n'ont pas passé les vérifications.
    for name in names:
        if name not in config["modules_choisis"]:
            config["modules_choisis"].append(name)
        config["modules"].setdefault(name, {})
    try:
        for name in list(config["modules"]):
            dest = Path(config["agents"][config["principal"]]) / name
            result = {"module": name, **install_into(name, dest, config, force)}
            result["autres_agents"] = link_secondary(name, dest, config, force)
            config["modules"][name] = {"dossier": str(dest), "installe_le": today(), "revision": revision()}
            results.append(result)
    finally:
        # La configuration enregistrée doit décrire ce qui a réellement été écrit, même après une erreur.
        config["modules"] = {k: v for k, v in config["modules"].items() if v}
        save_config(config)
    return results


def cmd_install(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config()
    results = install_modules(args.modules, config, args.force)
    return {
        "ok": True,
        "modules": results,
        "suite": "Suivre le « premier usage » de chaque SKILL.md installé, puis recharger les skills de l'agent.",
    }


def cmd_update(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config()
    if not config["modules"]:
        return {"ok": True, "modules": [], "note": "Aucun module installé."}
    return {"ok": True, "modules": install_modules([], config, args.force)}


def cmd_link(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config()
    links = []
    for agent, folder in config["agents"].items():
        link = Path(folder) / SELF_NAME
        entry = {"agent": agent, "lien": str(link)}
        if Path(folder).resolve() == ROOT.parent.resolve() or (link.is_symlink() and link.resolve() == ROOT):
            entry["etat"] = "déjà en place"
        elif link.exists() or link.is_symlink():
            entry["etat"] = "conflit : un dossier porte déjà ce nom, rien n'a été modifié"
        else:
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(ROOT, target_is_directory=True)
            entry["etat"] = "relié"
        links.append(entry)
    return {"ok": True, "liens": links}


def cmd_set(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config()
    changes = []
    for item in args.items:
        if item[:1] in "+-" and "=" not in item:
            flags = set(config.get("drapeaux", []))
            (flags.add if item[0] == "+" else flags.discard)(item[1:])
            config["drapeaux"] = sorted(flags)
            changes.append(item)
            continue
        key, separator, value = item.partition("=")
        if not separator or not re.fullmatch(r"[A-Z_]+", key):
            raise Failure(f"Format attendu : CLE=VALEUR ou +drapeau / -drapeau, reçu « {item} ».")
        if value == "":
            config["vars"].pop(key, None)
        else:
            looks_like_path = value.startswith(("~", "/")) or re.match(r"^[A-Za-z]:\\", value)
            config["vars"][key] = str(expand(value)) if looks_like_path else value
        changes.append(key)
    save_config(config)
    return {"ok": True, "modifie": changes, "note": "Lancer « update » pour répercuter sur les modules installés."}


FRAGMENT_FLAGS = {"obsidian", "supports-zotero", "moodle-bridge", "notes-externes", *TYPES}


def cmd_fragment(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config()
    target = args.module
    if target not in FRAGMENT_FLAGS and target not in module_names():
        raise Failure(f"Ni module ni option : {target}.", modules=module_names(), options=sorted(FRAGMENT_FLAGS))
    variables, flags = variables_for(config), flags_for(config)
    template = (TEMPLATE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    # Blocs « si:cible » de premier niveau à ajouter, et blocs « si:!cible » qu'ils remplacent.
    found: dict[bool, list[dict[str, Any]]] = {False: [], True: []}
    current: list[str] | None = None
    negated = False
    depth = 0
    for line in template.splitlines(keepends=True):
        match = CONDITION.match(line.rstrip("\r\n"))
        if match and match.group(1) == "si":
            if depth == 0 and match.group(3) == target:
                current, negated, depth = [], bool(match.group(2)), 1
                continue
            depth += 1
        elif match:
            depth -= 1
            if depth == 0 and current is not None:
                active = flags - {target} if negated else flags | {target}
                text, missing = render("".join(current), variables, active, "AGENTS.md")
                found[negated].append({"texte": text.strip(), "variables_manquantes": sorted(missing)})
                current = None
                continue
        if current is not None:
            current.append(line)
    return {"ok": True, "cible": target, "a_ajouter": found[False], "a_remplacer": found[True],
            "note": "Après accord : insérer chaque bloc « a_ajouter » dans la section correspondante de "
                    "l'AGENTS.md de l'espace, et retirer les passages « a_remplacer » qu'il remplace."}


# --- État --------------------------------------------------------------------


def cmd_modules(args: argparse.Namespace) -> dict[str, Any]:
    rows = []
    for name in module_names():
        info = module_info(name)
        rows.append({k: info.get(k) for k in ("nom", "titre", "resume", "systemes", "compatible", "requis", "teste")})
    return {"systeme": sys.platform, "modules": rows}


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(required=False)
    status: dict[str, Any] = {
        "depot": str(ROOT),
        "revision": revision(),
        "systeme": sys.platform,
        "configure": config is not None,
        "config": str(CONFIG),
    }
    externes = {}
    for agent, folder in DEFAULT_AGENT_DIRS.items():
        candidate = expand(folder) / "moodle-bridge"
        if candidate.exists():
            externes.setdefault("moodle-bridge", []).append(str(candidate))
    status["externes"] = externes
    if config is None:
        status["suite"] = "Première installation : mener l'entretien (references/entretien.md), puis « init »."
        return status

    problems = []
    espace = Path(config["vars"]["ESPACE"])
    agents_md = espace / "AGENTS.md"
    status["espace"] = {"chemin": str(espace), "existe": espace.is_dir(), "agents_md": agents_md.is_file()}
    if not espace.is_dir():
        problems.append(f"Espace introuvable : {espace}")
    elif agents_md.is_file() and PLACEHOLDER.search(agents_md.read_text(encoding="utf-8")):
        problems.append("AGENTS.md contient encore des {{VARIABLES}} non remplacées.")
    for key in ("ESPACE", "INDEX", "NOTES", "ZOTERO_FICHIERS", "CLASSEUR"):
        if "'" in str(config["vars"].get(key, "")):
            problems.append(f"Le chemin {key} contient une apostrophe : les commandes des skills risquent de casser.")
    status["agents"] = {
        agent: {"dossier": folder, "existe": Path(folder).is_dir(), "principal": agent == config["principal"]}
        for agent, folder in config["agents"].items()
    }
    rows = []
    flags = flags_for(config)
    for name in module_names():
        info = module_info(name)
        row = {"nom": name, "compatible": info["compatible"], "choisi": name in config["modules_choisis"],
               "installe": name in config["modules"]}
        if row["installe"]:
            dest = Path(config["modules"][name]["dossier"])
            marker = read_marker(dest)
            row["dossier"] = str(dest)
            if marker is None:
                problems.append(f"Module {name} : dossier {dest} absent ou non géré.")
                row["a_jour"] = False
            else:
                expected = fingerprint(name, variables_for(config, dest), flags | {name})
                row["a_jour"] = marker.get("empreinte") == expected
        elif row["choisi"]:
            problems.append(f"Module {name} choisi mais pas encore installé.")
        rows.append(row)
    status["modules"] = rows
    status["drapeaux"] = config.get("drapeaux", [])
    status["problemes"] = problems
    if any(r.get("installe") and r.get("a_jour") is False for r in rows):
        status["suite"] = "Des modules ne sont pas à jour : lancer « update »."
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("modules")
    init = commands.add_parser("init")
    init.add_argument("--answers", required=True)
    install = commands.add_parser("install")
    install.add_argument("modules", nargs="+")
    install.add_argument("--force", action="store_true")
    update = commands.add_parser("update")
    update.add_argument("--force", action="store_true")
    commands.add_parser("link")
    setter = commands.add_parser("set")
    setter.add_argument("items", nargs="+")
    fragment = commands.add_parser("fragment")
    fragment.add_argument("module")
    args = parser.parse_args()
    handlers = {
        "status": cmd_status, "modules": cmd_modules, "init": cmd_init, "install": cmd_install,
        "update": cmd_update, "link": cmd_link, "set": cmd_set, "fragment": cmd_fragment,
    }
    try:
        emit(handlers[args.command](args))
        return 0
    except Failure as exc:
        emit({"ok": False, "erreur": exc.message, **exc.details})
        return 1


if __name__ == "__main__":
    sys.exit(main())
