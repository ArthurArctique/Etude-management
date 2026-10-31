# Troubleshooting

Use the structured error code before changing anything.

| Code | Meaning | Action |
|---|---|---|
| `SANDBOX_DENIED` | The agent's sandbox blocked access to `127.0.0.1` | Repeat the exact command outside the sandbox as described in `SKILL.md` (Codex: `sandbox_permissions: "require_escalated"`); do not diagnose Zotero as offline. |
| `BRIDGE_NOT_LOADED`, `HTTP_404` | Zotero answers but the plugin did not register its endpoint | Check that the plugin is installed and enabled, then its loading error; do not renew the token. If it was never installed, follow `installation.md`. |
| `BRIDGE_OFFLINE` | Local connection refused | Check that Zotero is open and that the « Zotero Bridge » plugin is enabled. |
| `TOKEN_MISSING`, `TOKEN_NOT_CONFIGURED` | Client or plugin cannot read the token | Check that `~/.codex-zotero-bridge/token` exists (mode `0600` on macOS and Linux); never display it. Create it with `provision_codex_zotero_bridge.py`, then restart Zotero. |
| `AUTH_FAILED` | Client and plugin tokens differ | Stop. Reprovision one token (`--rotate`), restart Zotero, and never print either value. |
| `UNKNOWN_COMMAND` | Client/plugin version mismatch or typo | Run `capabilities`; use only the returned protocol-1 commands. |
| `INVALID_JSON`, `INVALID_ARGS`, `INVALID_ITEM`, `INVALID_FIELD`, `INVALID_PATH` | Request rejected before a write | Correct the payload and prepare a new UUID. |
| `ITEM_NOT_FOUND`, `COLLECTION_NOT_FOUND`, `FILE_NOT_FOUND` | A resolved target is absent | Search again and show the user the corrected target before preparing a mutation. |
| `COLLECTION_NAME_CONFLICT` | A sibling collection already has the requested name | Nothing was written. Show the user the conflicting path from `details`; choose another name or merge deliberately. |
| `REQUEST_ID_REQUIRED` | A mutation was attempted without preparation | Run `--prepare`, show the plan when needed, then reuse its UUID. |
| `REQUEST_ID_CONFLICT` | One UUID was reused for different arguments | Stop; never change a payload under an existing UUID. Prepare a new reviewed operation. |
| `TIMEOUT`, `NETWORK_ERROR` | The response may have been lost | Treat mutation state as uncertain. Inspect Zotero, then replay only the identical payload and UUID if Zotero has not restarted. |
| `PARTIAL_APPLY`, `PARTIAL_BATCH` | Some changes are known to exist | Read `details`; verify every returned key. Never resend the whole operation blindly. |

## Canonical nomenclature

The technical identifiers still carry the name of the first agent the bridge was written for. They are shared by every agent and must not be renamed, or existing installations stop working.

- Skill: `zotero-bridge`
- Plugin name: `Zotero Bridge`
- Plugin ID: `codex-zotero-bridge@local`
- Endpoint: `http://127.0.0.1:23119/codex/execute`
- Token: `~/.codex-zotero-bridge/token`
- Package: `tools/codex-zotero-bridge.xpi`, built by `tools/build_codex_zotero_bridge.py`

Environment overrides for the client: `CODEX_ZOTERO_BRIDGE_URL`, `CODEX_ZOTERO_BRIDGE_TOKEN_FILE`.

## Security checks

The XPI must contain no authentication token. Its source reads the token at runtime from the protected local file. Build only with `tools/build_codex_zotero_bridge.py`, which rejects token-like hexadecimal strings in packaged sources.

Do not paste the token into shell commands, JSON payloads, chat messages, logs, source files, cloud folders, or the plugin package. If a token was ever exposed, rotate it (`provision_codex_zotero_bridge.py --rotate`) and restart Zotero.

## Offline catalogue fallback

`tools/zotquery.py` is intentionally read-only and is not the normal bridge interface. It uses SQLite's backup API to create a coherent temporary snapshot, returns bounded results by default, and removes the snapshot afterward. It may be used when Zotero is closed or the bridge is unavailable, but it cannot verify the plugin's in-memory idempotency cache. Set `ZOTERO_DIR` if the Zotero data directory is not `~/Zotero`, and `ZOTERO_BASE_DIR` to the linked-files folder.

## Installation notes

- The Zotero loader requires `applications.zotero.update_url`. Removing the field makes the XPI invalid; an HTTP URL can make it incompatible. The package uses an HTTPS URL under the reserved `.invalid` domain and is updated manually. Do not weaken Zotero's update-security preference.
- The user installs the XPI from Zotero's plugin manager (*Tools → Plugins → gear menu → Install Plugin From File…*). Do not edit `extensions.json` or reset the profile. If the file picker stops responding, stop repeating the same clicks or shortcuts. During an explicitly requested repair, the native `AddonManager.getInstallForFile` API from Zotero's *Run JavaScript* window can install the verified local package; inspect `install.error` if `install.addon` is null.
- Quit Zotero with its menu. Do not automate letter-based quit shortcuts on macOS: a keyboard-layout mismatch can trigger a macOS logout instead. No bridge repair needs a logout or a system restart; restart Zotero only when necessary.
- After installation, verify `capabilities`, a bounded `search_items`, and `get_items` before reporting success. Tests against mocks alone do not prove that Zotero accepts or runs the package.
- The plugin resolves the home directory with `Services.dirsvc.get("Home", Components.interfaces.nsIFile).path`. `PathUtils.homeDir` does not exist in Zotero's Gecko runtime and prevents endpoint registration.
