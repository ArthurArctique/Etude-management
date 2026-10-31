# Maintenance

Toutes les commandes : `python3 -I '<dépôt>/scripts/etude.py' <commande>`. Commencer toujours par `status`.

## Commandes

| Commande | Effet |
|---|---|
| `status` | Configuration, espace, agents, modules (choisis, installés, à jour), problèmes et prochaine étape |
| `modules` | Modules disponibles et compatibilité avec ce système |
| `init --answers FICHIER` | Crée l'espace et la configuration ; n'écrase rien |
| `install MODULE …` | Installe ou met à jour des modules, puis réinstalle tous les modules déjà installés |
| `update [--force]` | Réinstalle les modules installés (après un `git pull`, un `set`…) |
| `link` | Relie ce skill aux dossiers de skills des autres agents |
| `set CLE=VALEUR`, `set +drapeau`, `set -drapeau` | Modifie la configuration ; `CLE=` (vide) retire une variable |
| `fragment MODULE` ou `fragment DRAPEAU` | Blocs de l'`AGENTS.md` liés à un module ou à une option (`supports-zotero`, `moodle-bridge`, `obsidian`) : `a_ajouter` et `a_remplacer` |

## Mettre à jour Etude management

```bash
git -C '<dépôt>' pull
python3 -I '<dépôt>/scripts/etude.py' update
```

`update` réécrit les fichiers des modules dont le contenu a changé. Un fichier modifié à la main depuis la dernière installation est conservé et listé dans `modifies_a_la_main_conserves` : montrer la différence à l'utilisateur avant de proposer `--force`. Les fichiers construits sur place (mini-app Calendrier, plugin Zotero `.xpi`) ne sont jamais touchés. Pour Zotero, si le plugin a changé, le reconstruire et le réinstaller (`installation.md` du module).

L'espace n'est jamais mis à jour automatiquement : si les gabarits ont évolué, comparer et proposer les changements à la main.

## Ajouter un module après coup

1. `set` des variables requises (`ZOTERO_FICHIERS`, `CLASSEUR`) et, pour Zotero avec les supports de cours, `set +supports-zotero`.
2. `install <module>`.
3. `fragment <module>`, et `fragment <drapeau>` pour chaque option activée (par exemple `fragment supports-zotero`) : montrer à l'utilisateur les blocs à ajouter à `AGENTS.md` et les passages qu'ils remplacent ; les appliquer après accord.
4. Suivre le « Premier usage » du `SKILL.md` installé.

## Retirer un module

L'installateur ne supprime rien de lui-même. Après accord :

1. supprimer le dossier du module dans le dossier de skills de l'agent principal et les liens des autres agents (vérifier d'abord la présence de `.etude-module.json`) ;
2. retirer le module de `modules` et de `modules_choisis` dans `local/config.json` ;
3. proposer de retirer de l'`AGENTS.md` de l'espace les passages du module (`fragment <module>` les liste).

Pour Zotero, le plugin se désinstalle depuis Zotero et le token `~/.codex-zotero-bridge/token` peut rester. Pour Calendrier et Mail, les autorisations se retirent dans *Réglages Système → Confidentialité et sécurité*.

## Changer un chemin

- Dossier des archives Zotero, classeur : `set CLE=/nouveau/chemin`, puis `update`.
- Déplacer l'espace : déplacer le dossier, `set ESPACE=/nouveau/chemin INDEX=/nouveau/chemin/00_Cadre/Index-correspondances.md` (et `NOTES` si les notes sont dans l'espace), puis `update`. Les chemins écrits dans les fichiers de l'espace (index, `AGENTS.md`) se corrigent à la main, après accord.
- Changer d'agent principal : modifier `principal` et `agents` dans `local/config.json`, supprimer les anciens dossiers rendus (après vérification), puis `update`.

## Désinstaller

Supprimer les dossiers des modules (ceux qui contiennent `.etude-module.json`), les liens symboliques et le dossier du dépôt. L'espace reste intact : il n'a jamais dépendu du dépôt pour fonctionner, seulement les skills.

## Dépannage

| Symptôme | Piste |
|---|---|
| `existe déjà et n'a pas été créé par Etude management` | Un autre skill porte ce nom : demander s'il faut le renommer ou garder le sien. Ne jamais le supprimer d'office. |
| `Variables manquantes` | Les définir avec `set`, puis relancer. |
| `ne fonctionne pas sur ce système` | Module réservé à macOS. |
| `a_jour: false` dans `status` | Lancer `update`. |
| L'agent ne suit pas `AGENTS.md` | Ouvrir la session dans le dossier de l'espace. Pour une version de Claude Code qui ne lit pas `AGENTS.md`, créer `CLAUDE.md` contenant `@AGENTS.md`. |
| Le skill d'un module n'apparaît pas | Recharger les skills de l'agent ou ouvrir une nouvelle session. |
| Chemin avec apostrophe signalé | Les commandes des skills mettent les chemins entre apostrophes : renommer le dossier, puis `set` et `update`. |
