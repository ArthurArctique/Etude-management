# Entretien de première installation

Regrouper les questions en deux ou trois messages, avec une valeur par défaut pour chacune : l'utilisateur doit pouvoir répondre « d'accord pour tout » ou ne corriger que ce qui l'intéresse. Constater soi-même ce qui peut l'être (système, agents installés, présence de Zotero ou d'Obsidian) au lieu de le demander. Ne jamais demander de mot de passe ni de jeton.

## Bloc 1 — L'espace

1. **Domaine et nature.** Qu'étudie-t-il, et dans quel cadre ? Le type règle les noms par défaut :

   | `type` | Pour | Dossier de travail | Unité | Activités |
   |---|---|---|---|---|
   | `universite` | licence, master, école, prépa | `Matieres` | matière | `CM`, `TD`, `TP`, `Projet` |
   | `autodidacte` | apprentissage en autonomie, MOOC | `Sujets` | sujet | `Cours`, `Exercices`, `Projets` |
   | `recherche` | thèse, mémoire, projet de recherche | `Projets` | projet | `Lectures`, `Analyses`, `Redaction` |
   | `professionnel` | formation continue, certification, veille | `Themes` | thème | `Formation`, `Exercices`, `Projets` |
   | `autre` | tout le reste | `Travail` | thème | `Cours`, `Exercices`, `Projets` |

   Demander aussi un titre court (« Master de chimie », « Apprendre le japonais ») et, si utile, une description du domaine.
2. **Emplacement.** Où créer le dossier ? Proposer `~/Etudes/<titre court>`. Un dossier synchronisé (iCloud Drive, OneDrive, Dropbox) le rend disponible sur ses autres appareils. Éviter les apostrophes dans le chemin : elles compliquent les commandes des skills. Prévenir aussi, en une phrase : avec un modèle dans le cloud, tout ce qui est lisible dans ce dossier et dans Zotero finira un jour chez le fournisseur de l'agent.
3. **Langue** des réponses et des fichiers créés : par défaut celle de la conversation.
4. **Agents.** Lesquels utilise-t-il ? Dossiers de skills par défaut : `~/.claude/skills` (Claude Code), `~/.codex/skills` (Codex). Pour un autre agent, demander son dossier de skills. L'agent principal reçoit les fichiers des modules ; les autres reçoivent un lien symbolique.
5. **Découpage.** Confirmer ou adapter l'unité et les activités proposées par le type, et les noms des trois dossiers fixes : `00_Cadre` (vision d'ensemble, index, profil, sources officielles), `01_A_faire` (tâches reportées) et le dossier de travail.

## Bloc 2 — Archives et notes

6. **Notes.** Où prendre ses notes ?
   - **Obsidian** (recommandé) : un vault dans l'espace (`Obsidian/`, par défaut) ou un vault existant ailleurs (chemin absolu). Obsidian lit de simples fichiers Markdown : les agents peuvent les lire et les compléter, et l'utilisateur garde une vue liée et consultable de ses notes, sans format propriétaire.
   - **Dossier Markdown simple** (`Notes/`) s'il ne veut pas d'Obsidian.
   L'espace y crée `Dictionnaire.md` et `À approfondir.md`, entretenus par les agents.
7. **Zotero.** Utilise-t-il Zotero, ou veut-il l'adopter ? Zotero garde les références et les PDF avec leurs métadonnées, collections et tags : l'agent y retrouve le document exact d'une question au lieu de répondre de mémoire. Si oui, module `zotero-bridge`, et deux questions :
   - **Dossier des archives** (`zotero.fichiers`) : où ranger les PDF que l'agent ajoute à Zotero (fichiers liés, un sous-dossier par collection) ? Proposer `~/Documents/Zotero Fichiers`, ou un dossier synchronisé pour retrouver les PDF sur ses autres appareils.
   - **Supports de cours** (`zotero.supports`) : les diaporamas, polycopiés et articles vont-ils dans Zotero (oui par défaut) ou restent-ils dans les dossiers de travail ?
   L'installation du plugin se fait après, au premier usage, et c'est l'utilisateur qui l'installe dans Zotero.
8. **Documents officiels.** A-t-il une maquette, un programme, un règlement ou un calendrier ? Ils iront dans `00_Cadre/Sources/` ; l'agent pourra ensuite en tirer les fiches du cadre.
9. **Moodle.** Son établissement utilise-t-il Moodle ? Si oui, suggérer **Moodle Bridge** (projet séparé, voir `modules.md`) : il synchronise en lecture seule documents, devoirs, échéances et annonces dans l'espace. Réponse `moodle: true` si l'utilisateur veut l'installer.

## Bloc 3 — Modules facultatifs

Présenter chaque module en une ligne, avec son système (`etude.py modules` donne la liste et la compatibilité). Aucun n'est obligatoire.

10. **Apple Calendar** (`apple-calendar`, **macOS uniquement**) : lire l'emploi du temps et les disponibilités, et relier aux séances leurs documents, notes et références, après confirmation.
11. **Apple Mail** (`apple-mail`, **macOS uniquement**) : chercher, lire et résumer ses mails ; brouillons ; envois seulement après aperçu et confirmation.
12. **Suivi des notes** (`suivi-notes`) : s'il tient un classeur de notes (Excel `.xlsx`), donner son chemin (`classeur`). Sans classeur, ne pas installer ce module pour l'instant.
13. **Import ChatGPT** (`chatgpt-context-import`) : reprendre dans l'espace le contexte d'une conversation ChatGPT partagée.

Sur un autre système que macOS, citer Apple Calendar et Apple Mail comme indisponibles et ne pas les proposer.

## Fichier de réponses

Seul `espace` est obligatoire ; les autres clés prennent les valeurs par défaut du type.

```json
{
  "espace": "~/Etudes/Master de chimie",
  "titre": "Master de chimie",
  "domaine": "un master de chimie organique",
  "type": "universite",
  "langue": "français",
  "agents": ["claude", "codex"],
  "principal": "claude",
  "dossiers": {"cadre": "00_Cadre", "a_faire": "01_A_faire", "travail": "Matieres"},
  "unite": ["matière", "matières"],
  "activites": ["CM", "TD", "TP", "Projet"],
  "notes": {"chemin": "Obsidian", "obsidian": true},
  "zotero": {"fichiers": "~/Documents/Zotero Fichiers", "supports": true},
  "moodle": true,
  "modules": ["zotero-bridge", "apple-calendar", "suivi-notes"],
  "classeur": "~/Documents/notes.xlsx"
}
```

- `agents` : liste de noms connus (`claude`, `codex`) ou objet `{"nom": "dossier de skills"}` pour un autre agent.
- `notes.chemin` : relatif à l'espace, ou absolu pour un vault existant ailleurs.
- `unite` : `[singulier, pluriel]`.
- `zotero.fichiers` est obligatoire avec `zotero-bridge`, `classeur` avec `suivi-notes`.
