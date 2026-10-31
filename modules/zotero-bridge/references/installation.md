# Installer le pont Zotero

À suivre avec l'utilisateur la première fois, quand `capabilities` échoue parce que le plugin n'a jamais été installé. L'agent prépare tout ; **l'utilisateur installe lui-même le plugin dans Zotero**.

## 1. Prérequis

- **Zotero 7 ou plus récent** (testé avec Zotero 9), ouvert au moins une fois : https://www.zotero.org/download/
- **Python 3.9 ou plus récent** : `python3 --version` (Windows : `py --version`).
- Un dossier stable pour les fichiers liés : `{{ZOTERO_FICHIERS}}`. Le créer s'il n'existe pas, après accord.

## 2. Créer le token local

```bash
python3 '{{SKILL_DIR}}/tools/provision_codex_zotero_bridge.py'
```

Le script crée `~/.codex-zotero-bridge/token` (droits `0600` sous macOS et Linux) sans jamais l'afficher. S'il existe déjà, il le vérifie et le garde. Le token sert au client et au plugin ; il ne quitte jamais l'ordinateur.

## 3. Construire le plugin

```bash
python3 '{{SKILL_DIR}}/tools/build_codex_zotero_bridge.py'
```

Le script vérifie les sources (aucun secret embarqué) et écrit `{{SKILL_DIR}}/tools/codex-zotero-bridge.xpi`.

## 4. L'utilisateur installe le plugin

Donner ces étapes à l'utilisateur, sans les automatiser :

1. Dans Zotero : *Outils → Plugins* (ou *Extensions*).
2. Menu en forme de roue dentée → *Installer un plugin depuis un fichier…*
3. Choisir `{{SKILL_DIR}}/tools/codex-zotero-bridge.xpi`, puis accepter.
4. Vérifier que « Zotero Bridge » apparaît activé. Redémarrer Zotero si le token vient d'être créé alors que Zotero était ouvert.

## 5. Régler les fichiers liés (recommandé)

Le pont ajoute les PDF comme **fichiers liés** : le fichier reste dans `{{ZOTERO_FICHIERS}}` et Zotero pointe vers lui. Pour que ces liens restent valables sur un autre ordinateur ou après un déplacement du dossier, l'utilisateur règle dans Zotero : *Réglages → Avancé → Fichiers et dossiers → Répertoire de base pour les pièces jointes liées* = `{{ZOTERO_FICHIERS}}`.

Si ce dossier est dans un service de synchronisation (iCloud Drive, OneDrive, Dropbox…), les PDF sont disponibles sur ses autres appareils ; la synchronisation des fichiers de Zotero n'est alors pas nécessaire pour eux.

## 6. Vérifier

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' capabilities
python3 '{{SKILL_DIR}}/tools/zot.py' search_items '{"query":"a","limit":3}'
```

Puis `get_items` sur une clé renvoyée. Ne déclarer le pont prêt qu'après ces trois lectures réussies. En cas d'erreur, lire `troubleshooting.md`.

## Mettre à jour le plugin

Après une mise à jour d'Etude management, reconstruire le XPI (étape 3) et le réinstaller par-dessus l'ancien (étape 4). Le token est conservé.
