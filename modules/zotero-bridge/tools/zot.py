#!/usr/bin/env python3
"""Client local du Zotero Bridge, pour tout agent IA (Claude Code, Codex…).

Usage:
  python3 zot.py <commande> ['<args JSON>'] [options]
  python3 zot.py <commande> - [options]                 # JSON depuis stdin

Options principales:
  --prepare              valide une mutation sans l'exécuter et crée son requestId
  --request-id UUID      identifiant obligatoire pour exécuter une mutation
  --timeout SECONDES     délai réseau (30 s par défaut)
  --compact              JSON sur une seule ligne
  --envelope             conserve l'enveloppe complète de la réponse

Le token n'est jamais accepté sur la ligne de commande et n'est jamais affiché.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import socket
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_URL = "http://127.0.0.1:23119/codex/execute"
DEFAULT_TOKEN_FILE = Path.home() / ".codex-zotero-bridge" / "token"

READ_ONLY_COMMANDS = {
    "ping",
    "capabilities",
    "list_collections",
    "search_items",
    "get_items",
    "get_annotations",
}
MUTATING_COMMANDS = {
    "ensure_collection",
    "create_collection",
    "rename_collection",
    "create_item",
    "file_items",
    "add_tags",
    "remove_tags",
    "set_field",
    "add_note",
    "link_file",
    "trash_items",
    "trash_collection",
    "batch",
}
ALL_COMMANDS = READ_ONLY_COMMANDS | MUTATING_COMMANDS


class ClientError(Exception):
    def __init__(self, code: str, message: str, *, exit_code: int = 2, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details


def _object(value: Any, name: str = "args") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ClientError("INVALID_ARGS", f"{name} doit être un objet JSON.")
    return value


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClientError("INVALID_ARGS", f"{name} doit être une chaîne non vide.")
    return value.strip()


def _string_list(value: Any, name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ClientError("INVALID_ARGS", f"{name} doit être une liste non vide.")
    if any(not isinstance(v, str) or not v.strip() for v in value):
        raise ClientError("INVALID_ARGS", f"Chaque valeur de {name} doit être une chaîne non vide.")
    return value


def validate_args(command: str, args: Any, *, nested: bool = False) -> dict[str, Any]:
    args = _object(args)
    if command not in ALL_COMMANDS:
        available = ", ".join(sorted(ALL_COMMANDS))
        raise ClientError("UNKNOWN_COMMAND", f"Commande inconnue « {command} ». Disponibles : {available}.")

    if command in {"ping", "capabilities"}:
        if args:
            raise ClientError("INVALID_ARGS", f"{command} n'accepte aucun argument.")
    elif command == "list_collections":
        if "query" in args:
            _nonempty_string(args["query"], "query")
        if "limit" in args and (not isinstance(args["limit"], int) or not 1 <= args["limit"] <= 500):
            raise ClientError("INVALID_ARGS", "limit doit être un entier entre 1 et 500.")
    elif command == "search_items":
        _nonempty_string(args.get("query"), "query")
        if "limit" in args and (not isinstance(args["limit"], int) or not 1 <= args["limit"] <= 100):
            raise ClientError("INVALID_ARGS", "limit doit être un entier entre 1 et 100.")
        if "offset" in args and (not isinstance(args["offset"], int) or args["offset"] < 0):
            raise ClientError("INVALID_ARGS", "offset doit être un entier positif ou nul.")
    elif command == "get_items":
        keys = _string_list(args.get("itemKeys"), "itemKeys")
        if len(keys) > 100:
            raise ClientError("INVALID_ARGS", "get_items accepte au maximum 100 clés.")
    elif command == "get_annotations":
        _nonempty_string(args.get("itemKey"), "itemKey")
        if "types" in args:
            _string_list(args["types"], "types")
        if "colors" in args:
            _string_list(args["colors"], "colors")
        for name in ("commentsOnly", "includePosition"):
            if name in args and not isinstance(args[name], bool):
                raise ClientError("INVALID_ARGS", f"{name} doit être un booléen.")
        if "limit" in args and (
            type(args["limit"]) is not int or not 1 <= args["limit"] <= 500
        ):
            raise ClientError("INVALID_ARGS", "limit doit être un entier entre 1 et 500.")
        if "offset" in args and (
            type(args["offset"]) is not int or args["offset"] < 0
        ):
            raise ClientError("INVALID_ARGS", "offset doit être un entier positif ou nul.")
    elif command == "ensure_collection":
        _string_list(args.get("path"), "path")
    elif command == "create_collection":
        _nonempty_string(args.get("name"), "name")
        if args.get("parentKey") is not None:
            _nonempty_string(args["parentKey"], "parentKey")
    elif command == "rename_collection":
        _nonempty_string(args.get("collectionKey"), "collectionKey")
        _nonempty_string(args.get("name"), "name")
    elif command == "create_item":
        _nonempty_string(args.get("title"), "title")
        if args.get("collectionKey") and args.get("collectionPath"):
            raise ClientError("INVALID_ARGS", "Utilise collectionKey ou collectionPath, pas les deux.")
        if "collectionPath" in args:
            _string_list(args["collectionPath"], "collectionPath")
        if "attachments" in args:
            _string_list(args["attachments"], "attachments", allow_empty=True)
        if "tags" in args:
            _string_list(args["tags"], "tags", allow_empty=True)
        if "creators" in args and not isinstance(args["creators"], list):
            raise ClientError("INVALID_ARGS", "creators doit être une liste.")
    elif command == "file_items":
        _string_list(args.get("itemKeys"), "itemKeys")
        _nonempty_string(args.get("collectionKey"), "collectionKey")
    elif command in {"add_tags", "remove_tags"}:
        _nonempty_string(args.get("itemKey"), "itemKey")
        _string_list(args.get("tags"), "tags")
    elif command == "set_field":
        _nonempty_string(args.get("itemKey"), "itemKey")
        _nonempty_string(args.get("field"), "field")
        if "value" not in args:
            raise ClientError("INVALID_ARGS", "value est requis (une chaîne vide est autorisée).")
    elif command == "add_note":
        _nonempty_string(args.get("parentKey"), "parentKey")
        _nonempty_string(args.get("html"), "html")
        if "tags" in args:
            _string_list(args["tags"], "tags", allow_empty=True)
    elif command == "link_file":
        path = Path(_nonempty_string(args.get("absPath"), "absPath"))
        if not path.is_absolute():
            raise ClientError("INVALID_ARGS", "absPath doit être un chemin absolu.")
        if args.get("parentKey") and args.get("collectionKey"):
            raise ClientError("INVALID_ARGS", "Utilise parentKey ou collectionKey, pas les deux.")
    elif command == "trash_items":
        _string_list(args.get("itemKeys"), "itemKeys")
    elif command == "trash_collection":
        _nonempty_string(args.get("collectionKey"), "collectionKey")
    elif command == "batch":
        if nested:
            raise ClientError("INVALID_ARGS", "Les batch imbriqués sont interdits.")
        ops = args.get("ops")
        if not isinstance(ops, list) or not ops:
            raise ClientError("INVALID_ARGS", "ops doit être une liste non vide.")
        if len(ops) > 50:
            raise ClientError("INVALID_ARGS", "Un batch est limité à 50 opérations.")
        for index, op in enumerate(ops):
            if not isinstance(op, dict):
                raise ClientError("INVALID_ARGS", f"ops[{index}] doit être un objet.")
            nested_command = _nonempty_string(op.get("command"), f"ops[{index}].command")
            if nested_command not in MUTATING_COMMANDS or nested_command == "batch":
                raise ClientError(
                    "INVALID_ARGS",
                    f"ops[{index}] doit être une commande mutante non-batch.",
                )
            validate_args(nested_command, op.get("args", {}), nested=True)
    return args


def load_payload(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if raw == "-":
        raw = sys.stdin.read()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClientError(
            "INVALID_JSON",
            f"JSON invalide à la ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}.",
        ) from None
    return _object(value)


def token_file() -> Path:
    configured = os.environ.get("CODEX_ZOTERO_BRIDGE_TOKEN_FILE")
    return Path(configured).expanduser() if configured else DEFAULT_TOKEN_FILE


def read_token(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise ClientError(
            "TOKEN_MISSING",
            f"Token introuvable : {path}. Installe le bridge : voir references/installation.md du skill zotero-bridge.",
            exit_code=3,
        ) from None
    except OSError as exc:
        raise ClientError("TOKEN_UNREADABLE", f"Token illisible : {exc}.", exit_code=3) from None
    if len(token) < 32:
        raise ClientError("TOKEN_INVALID", "Le fichier de token est vide ou invalide.", exit_code=3)
    return token


def parse_server_error(payload: Any, status: int) -> ClientError:
    if status == 404 and not (isinstance(payload, dict) and isinstance(payload.get("error"), dict)):
        return ClientError(
            "BRIDGE_NOT_LOADED",
            "Zotero répond, mais /codex/execute est absent : vérifier l'installation et "
            "l'activation du plugin Zotero Bridge. Ne pas renouveler le token pour une erreur 404.",
            exit_code=8,
        )
    if isinstance(payload, dict):
        value = payload.get("error", payload)
        if isinstance(value, dict):
            return ClientError(
                str(value.get("code") or f"HTTP_{status}"),
                str(value.get("message") or "Erreur du bridge Zotero."),
                exit_code=7 if status in {401, 403} else 8,
                details=value.get("details"),
            )
        if isinstance(value, str):
            return ClientError(f"HTTP_{status}", value, exit_code=7 if status in {401, 403} else 8)
    return ClientError(f"HTTP_{status}", f"Le bridge a répondu HTTP {status}.", exit_code=8)


def call_bridge(command: str, args: dict[str, Any], request_id: str | None, timeout: float) -> dict[str, Any]:
    body: dict[str, Any] = {"command": command, "args": args}
    if request_id:
        body["requestId"] = request_id
    body["token"] = read_token(token_file())
    data = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    req = request.Request(
        os.environ.get("CODEX_ZOTERO_BRIDGE_URL", DEFAULT_URL),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = None
        raise parse_server_error(payload, exc.code) from None
    except error.URLError as exc:
        reason = exc.reason
        err_no = getattr(reason, "errno", None)
        if isinstance(reason, PermissionError) or err_no in {errno.EPERM, errno.EACCES}:
            raise ClientError(
                "SANDBOX_DENIED",
                "Le bac à sable bloque 127.0.0.1. Relance exactement cette commande avec "
                "sandbox_permissions=require_escalated ; cela n'autorise pas une écriture Zotero.",
                exit_code=4,
            ) from None
        if isinstance(reason, ConnectionRefusedError) or err_no == errno.ECONNREFUSED:
            raise ClientError(
                "BRIDGE_OFFLINE",
                "Connexion refusée : ouvre Zotero et vérifie que « Zotero Bridge » est activé.",
                exit_code=5,
            ) from None
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise ClientError("TIMEOUT", "Le bridge Zotero n'a pas répondu avant le délai.", exit_code=6) from None
        raise ClientError("NETWORK_ERROR", f"Erreur de connexion locale : {reason}.", exit_code=5) from None
    except (TimeoutError, socket.timeout):
        raise ClientError("TIMEOUT", "Le bridge Zotero n'a pas répondu avant le délai.", exit_code=6) from None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise ClientError("INVALID_RESPONSE", "Le bridge a renvoyé une réponse non JSON.", exit_code=9) from None
    if not isinstance(payload, dict):
        raise ClientError("INVALID_RESPONSE", "Le bridge a renvoyé une réponse inattendue.", exit_code=9)
    if not payload.get("ok"):
        raise parse_server_error(payload, 500)
    return payload


def print_json(value: Any, compact: bool) -> None:
    kwargs: dict[str, Any] = {"ensure_ascii": False}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    print(json.dumps(value, **kwargs))


def fail(exc: ClientError, *, request_id: str | None = None) -> int:
    payload: dict[str, Any] = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
    if exc.details is not None:
        payload["error"]["details"] = exc.details
    if request_id:
        payload["requestId"] = request_id
        if exc.code in {"TIMEOUT", "NETWORK_ERROR"}:
            payload["error"]["retry"] = (
                "Résultat incertain : vérifie l'état Zotero puis réutilise exactement ce requestId."
            )
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return exc.exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", help="commande nommée du bridge")
    parser.add_argument("payload", nargs="?", help="objet JSON, ou '-' pour stdin")
    parser.add_argument("--prepare", action="store_true", help="valide sans appeler Zotero")
    parser.add_argument("--request-id", help="UUID d'idempotence obligatoire pour une mutation")
    parser.add_argument("--timeout", type=float, default=30.0, help="délai réseau en secondes")
    parser.add_argument("--compact", action="store_true", help="sortie JSON compacte")
    parser.add_argument("--envelope", action="store_true", help="affiche la réponse complète")
    ns = parser.parse_args()

    request_id = ns.request_id
    try:
        args = validate_args(ns.command, load_payload(ns.payload))
        mutating = ns.command in MUTATING_COMMANDS
        if ns.prepare:
            if not mutating:
                raise ClientError("NOT_MUTATING", "--prepare est réservé aux commandes mutantes.")
            request_id = request_id or str(uuid.uuid4())
            print_json(
                {
                    "ok": True,
                    "prepared": True,
                    "command": ns.command,
                    "args": args,
                    "requestId": request_id,
                },
                ns.compact,
            )
            return 0
        if mutating and not request_id:
            raise ClientError(
                "REQUEST_ID_REQUIRED",
                "Mutation bloquée : lance d'abord la même commande avec --prepare, puis réutilise son requestId après confirmation de l'utilisateur.",
            )
        if request_id:
            try:
                request_id = str(uuid.UUID(request_id))
            except ValueError:
                raise ClientError("INVALID_REQUEST_ID", "--request-id doit être un UUID valide.") from None
        if ns.timeout <= 0 or ns.timeout > 300:
            raise ClientError("INVALID_TIMEOUT", "--timeout doit être compris entre 0 et 300 secondes.")
        response = call_bridge(ns.command, args, request_id, ns.timeout)
        output: Any = response if ns.envelope else response.get("result")
        if mutating and not ns.envelope:
            output = {"requestId": response.get("requestId", request_id), "result": output}
        print_json(output, ns.compact)
        return 0
    except ClientError as exc:
        return fail(exc, request_id=request_id)


if __name__ == "__main__":
    raise SystemExit(main())
