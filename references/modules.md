# Modules

`etude.py modules` donne la liste à jour, avec les systèmes compatibles et les variables requises. Tous les modules sont facultatifs.

| Module | Système | Requis | Ce qu'il fait |
|---|---|---|---|
| `zotero-bridge` | macOS, Linux, Windows | `ZOTERO_FICHIERS` | Chercher, lire et organiser Zotero par un plugin local à commandes fixes |
| `apple-calendar` | **macOS uniquement** | — | Lire l'agenda (EventKit) et relier des ressources aux séances, après confirmation |
| `apple-mail` | **macOS uniquement** | — | Chercher, lire, résumer ses mails ; brouillons ; envois après confirmation |
| `suivi-notes` | tous | `CLASSEUR` | Lire un classeur de notes et le mettre à jour après un plan confirmé |
| `chatgpt-context-import` | tous | — | Reprendre le contexte d'une conversation ChatGPT partagée |

## Zotero Bridge

- **Prérequis** : Zotero 7 ou plus récent (testé avec Zotero 9), Python 3.9+.
- **Premier usage** : `references/installation.md` du module. L'agent crée le token local (`~/.codex-zotero-bridge/token`, jamais affiché) et construit le plugin (`.xpi`) ; l'utilisateur l'installe lui-même depuis *Outils → Plugins* de Zotero, puis règle le répertoire de base des pièces jointes liées sur `ZOTERO_FICHIERS`.
- **Ensuite** : recherche libre ; mutations préparées (`--prepare`) puis exécutées avec le même identifiant ; corbeille réversible seulement ; annotations lues seulement sur demande explicite.
- Les noms techniques (`codex-zotero-bridge`, `/codex/execute`) datent du premier agent pour lequel le pont a été écrit ; ils sont communs à tous les agents et ne doivent pas être renommés.
- Testé sous macOS ; Linux et Windows devraient fonctionner mais n'ont pas été testés.

## Apple Calendar (macOS uniquement)

- **Prérequis** : macOS 14 ou plus récent, outils en ligne de commande d'Apple (`xcode-select --install`, lancé par l'utilisateur).
- **Premier usage** : `bash <module>/scripts/build.sh` compile la mini-app « Agent Calendar » dans le dossier du module ; `authorize` affiche la demande d'accès de macOS, à laquelle l'utilisateur répond. L'autorisation est rattachée à cette mini-app, quel que soit l'agent qui la lance.
- **Écritures** : seulement des liens de ressources (notes de l'événement ou événement compagnon dans un calendrier « Ressources liées »), toujours après aperçu et confirmation. Jamais de suppression.
- Recompiler change la signature : macOS redemande alors l'accès.

## Apple Mail (macOS uniquement)

- **Premier usage** : macOS demande si l'app de l'agent peut contrôler Mail ; l'utilisateur répond. Le module découvre ensuite les comptes et boîtes.
- **Écritures** : brouillons libres ; envoi, réponse, transfert, déplacement et mise à la corbeille après aperçu exact et confirmation, à chaque fois. Jamais de suppression définitive.
- Testé : lecture, recherche et aperçus. Pas encore exercés réellement : marquage, enregistrement de pièce jointe, brouillon et exécutions confirmées.

## Suivi des notes

- **Requis** : le chemin du classeur (`set CLASSEUR=/chemin/notes.xlsx`).
- **Premier usage** : l'agent inspecte la structure (feuilles, en-têtes, zones saisissables et calculées) et propose de la consigner dans `00_Cadre/Profil.md`.
- **Écritures** : plan cellule par cellule, sauvegarde horodatée, confirmation juste avant, vérification après. Jamais sur un classeur ouvert dans Excel.

## Import ChatGPT

- Lit un lien `chatgpt.com/share/…` et en tire objectifs, décisions, documents et points ouverts, confrontés à l'état réel de l'espace. Lecture seule par défaut.
- Crée dans l'espace `BRIEF_CHATGPT.md`, à coller au début d'une conversation ChatGPT ; il se termine par le format de « passage de relais » à rapporter à l'agent.

## Moodle Bridge (projet séparé)

[Moodle Bridge](https://github.com/ArthurArctique/Moodle-Bridge) synchronise en lecture seule les documents, devoirs, échéances, annonces et modalités de contrôle d'un Moodle, avec un coffre Obsidian généré. Il a son propre skill d'amorçage, sur la branche `skill` :

```bash
git clone --branch skill --single-branch https://github.com/ArthurArctique/Moodle-Bridge.git ~/.claude/skills/moodle-bridge
```

(`~/.codex/skills/moodle-bridge` pour Codex.) Puis demander à l'agent d'installer Moodle Bridge : son skill guide l'installation. La connexion à Moodle reste entre les mains de l'utilisateur : il lance lui-même la commande de connexion dans son terminal, et ni mot de passe ni jeton ne passent par la conversation.

Réglages recommandés pour l'intégrer à l'espace (à proposer pendant son installation, voir sa section « Installer dans un espace de travail existant ») :

- `env` : la racine de l'espace ;
- `courses[].dest` : `<dossier de travail>/<CODE>` pour chaque cours, avec le code de l'index ;
- `classify.rules` : la convention de l'espace (« `TP/TP01`, numéro sur deux chiffres ; la numérotation locale fait foi ») ;
- `classify.context_files` : `00_Cadre/Index-correspondances.md` ;
- si les supports vont dans Zotero : `zotero.enabled: true`, `zotero.search_roots` = le dossier des archives Zotero, et la règle `dest = "@zotero"` dans `classify.rules` ;
- `vault.dir` : un sous-dossier dédié (par exemple `Obsidian Moodle`), distinct du vault personnel, puisqu'il est réécrit à chaque passage ;
- `skill install --config … --target claude|codex|both` pour remplacer son skill d'amorçage par le skill installé.

Ensuite : `set +moodle-bridge` si ce n'était pas déjà fait, `update`, et `fragment moodle-bridge` pour compléter l'`AGENTS.md` de l'espace.
