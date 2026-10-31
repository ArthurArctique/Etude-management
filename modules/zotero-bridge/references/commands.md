# Command reference — protocol 1

The client accepts one named command and one JSON object. Use `-` instead of inline JSON
to read a reviewed payload from stdin. If a sandbox blocks the local connection, use the execution mode described in `SKILL.md`.

## Read-only commands

- `capabilities {}` returns the bridge name, version, protocol, and command inventory.
- `ping {}` returns the Zotero, bridge, protocol, and library versions/identifiers.
- `list_collections {query?, limit?}` returns collection keys, parent keys, and complete
  paths. The default limit is 200; the maximum is 500.
- `search_items {query, limit?, offset?}` searches Zotero title, creator, year, tags, and
  related indexed fields. It returns regular items with collection paths and attachments.
  The default limit is 20; the maximum is 100.
- `get_items {itemKeys[]}` returns exact regular-item records plus a `missing` list.
- `get_annotations {itemKey, types?[], colors?[], commentsOnly?, includePosition?,
  limit?, offset?}` reads annotations belonging to one regular item or one attachment.
  `itemKey` may therefore be the parent bibliographic key returned by `search_items`, or
  an attachment key returned by `get_items`. The response contains the attachment key,
  annotation type, highlighted text, comment, color, page label/index, sort index,
  author, tags, and dates. The default limit is 100 and the maximum is 500. Use `offset`
  for pagination. `commentsOnly: true` keeps only annotations with a non-empty comment;
  `types` and `colors` are exact case-insensitive filters. Detailed PDF geometry can be
  large and is omitted unless `includePosition: true` is explicitly supplied.

  This command is subject to a usage boundary, not merely a technical option: call it
  only when the user explicitly asks to read, show, analyze, or use his highlights,
  annotations, or associated comments. Never call it automatically after `search_items`
  or `get_items`, including while grounding a course question.

Example, after the user explicitly asks for his commented highlights:

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' get_annotations '{"itemKey":"ABCD1234","commentsOnly":true,"limit":100}'
```

## Collection and item mutations

- `ensure_collection {path[]}` finds or creates each segment and returns the leaf key plus
  the exact collections created. It is a mutation even when the path may already exist.
- `create_collection {name, parentKey?}` always creates one collection.
- `rename_collection {collectionKey, name}` renames one collection in place. Its key,
  parent, items, and subcollections are unchanged; subcollection paths simply reflect
  the new name. The name is trimmed. A non-trashed collection with exactly the same
  name under the same parent is rejected with `COLLECTION_NAME_CONFLICT` before any
  write, so `ensure_collection` paths stay unambiguous. The result contains the
  updated `collection`, `previousName`, `previousPath`, and `changed` (`false` when
  the name was already identical; nothing is saved then).
- `create_item` requires `title` and accepts:
  - `itemType?` (default `document`)
  - `creators?`: Zotero creator objects using either `name`, or `firstName` + `lastName`,
    with optional `creatorType`
  - `date?`, `abstract?`, `extra?`, `tags?[]`
  - exactly one of `collectionKey?` or `collectionPath?[]`
  - `attachments?[]`: existing absolute file paths, never objects
- `file_items {itemKeys[], collectionKey}` adds existing items to a collection without
  removing them from other collections.
- `add_tags {itemKey, tags[]}` and `remove_tags {itemKey, tags[]}` preserve unrelated tags.
- `set_field {itemKey, field, value}` sets or clears one Zotero field.
- `add_note {parentKey, html, tags?[]}` creates a child note.
- `link_file {absPath, parentKey? | collectionKey?}` creates a linked attachment; it never
  copies, uploads, changes, or deletes the file.
- `trash_items {itemKeys[]}` and `trash_collection {collectionKey}` only move Zotero
  records to its reversible trash. Trashing a collection preserves its items.
- `batch {ops:[{command,args},...]}` executes 1–50 non-batch mutations sequentially.

The plugin validates keys, argument shapes, item construction, and every attachment path
before the first write when possible. Some multi-step Zotero operations still cannot be
fully atomic. `PARTIAL_APPLY` and `PARTIAL_BATCH` therefore include the exact applied keys
or prior results; inspect them before deciding what remains.

## Preparation and execution examples

Prepare a new item without contacting Zotero:

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' create_item '{"title":"Titre vérifié","itemType":"document","date":"2026","collectionPath":["Mathématiques","Statistiques"],"tags":["statistiques"],"attachments":["/chemin/absolu/document.pdf"]}' --prepare
```

After showing the exact plan and receiving the user's confirmation, run the unchanged
payload with the returned UUID:

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' create_item '{"title":"Titre vérifié","itemType":"document","date":"2026","collectionPath":["Mathématiques","Statistiques"],"tags":["statistiques"],"attachments":["/chemin/absolu/document.pdf"]}' --request-id '<UUID retourné par --prepare>'
```

For a reviewed batch, prefer stdin to fragile shell quoting:

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' batch - --prepare < payload.json
```

After confirmation and backup verification, execute that same file with its prepared
UUID. Do not rebuild or reorder the payload between preparation and execution.

## Client guarantees

- Unknown commands, malformed JSON, common missing fields, invalid limits, relative file
  paths, and missing mutation UUIDs fail locally before contacting Zotero.
- HTTP error bodies are preserved as structured `code`, `message`, and `details` values.
- The token is loaded from a protected file, never accepted as a CLI argument, and never
  printed.
- A mutating success prints both the `requestId` and the Zotero result.
- `--timeout` accepts 0–300 seconds; 30 seconds is the default.
- `--compact` emits one-line JSON; `--envelope` retains the complete protocol response.
