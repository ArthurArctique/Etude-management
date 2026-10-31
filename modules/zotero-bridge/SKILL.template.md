---
name: zotero-bridge
description: "Retrouver la source exacte (support, chapitre, article) avant de répondre sur le contenu d'un cours, d'une séance, d'un exercice ou d'un passage cité de l'espace « {{TITRE}} » : fichiers locaux d'abord, puis Zotero tant que le PDF n'est pas clairement identifié. Sert aussi à chercher, consulter et organiser prudemment la bibliothèque Zotero locale de l'utilisateur (références, collections, tags, notes, métadonnées, fichiers liés) et, seulement sur demande explicite, ses annotations et surlignages. Jamais d'écriture directe dans SQLite ni d'API cloud Zotero."
---
<!-- Généré par Etude management ({{DATE}}). Pour le régénérer : python3 -I '{{DEPOT}}/scripts/etude.py' update -->

# Zotero Bridge

Pont local à commandes nommées entre l'agent et Zotero. Il n'expose aucune commande de code arbitraire et ne supprime jamais définitivement une donnée Zotero. Il fonctionne avec tout agent capable de lancer des commandes sur l'ordinateur de l'utilisateur (Claude Code, Codex…).

Client canonique, toujours appelé par son chemin absolu :

`{{SKILL_DIR}}/tools/zot.py`

Le token est lu localement dans `~/.codex-zotero-bridge/token` (nom historique, commun à tous les agents). Ne jamais l'afficher, le copier dans une commande ou un message, ni le journaliser.

Ce skill ne marche que lorsque les commandes s'exécutent sur l'ordinateur où Zotero est ouvert. Dans un environnement isolé (chat web, machine distante, cloud), `127.0.0.1` n'est pas cet ordinateur : dire que Zotero n'est pas joignable d'ici plutôt que de conclure que Zotero est fermé.

## Premier usage

Lancer d'abord :

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' capabilities
```

- Réponse correcte : le pont est prêt, passer à la suite.
- `BRIDGE_OFFLINE` : Zotero est fermé, ou le plugin n'est pas installé.
- `TOKEN_MISSING`, `BRIDGE_NOT_LOADED` ou `HTTP_404` : le plugin n'est pas encore installé ou activé.

Si le plugin n'a jamais été installé sur cet ordinateur, suivre [references/installation.md](references/installation.md) avec l'utilisateur : créer le token, construire le plugin, puis l'utilisateur l'installe lui-même dans Zotero. Pour toute autre erreur, lire [references/troubleshooting.md](references/troubleshooting.md).

Si un bac à sable (sandbox) bloque la connexion locale alors que Zotero est ouvert (connexion refusée ou interdite, `SANDBOX_DENIED`) : sous Codex, relancer la même commande avec `sandbox_permissions: "require_escalated"` ; sous Claude Code, la relancer une fois hors sandbox avec une courte explication (« Accéder en lecture seule au pont Zotero local »). Cette permission d'exécution ne vaut que pour joindre le pont : elle n'autorise aucune modification de Zotero. Garder ensuite le même mode d'exécution pour les appels suivants de la tâche.

## Retrouver la source exacte d'une question de cours

Activer ce déroulé dès que l'utilisateur interroge le contenu d'un cours ou d'une unité de travail (une des {{UNITES}} de l'espace), d'une séance, d'un exercice ou d'un passage cité ou paraphrasé, même sans parler de Zotero.

1. Identifier l'unité concernée (une des {{UNITES}} de l'espace), la séance et les alias utiles dans `{{INDEX}}`.
2. Chercher d'abord dans les fichiers de l'espace (`{{ESPACE}}/{{TRAVAIL}}/`) et dans les notes (`{{NOTES}}`). Une source n'est trouvée que lorsque le PDF exact, ou le support explicitement cité, est identifié avec assez d'indices pour correspondre à l'unité et à la séance. Une note voisine, un fichier au titre ressemblant ou une connaissance générale suffisante pour répondre ne comptent pas.
3. Si le support n'est pas clairement trouvé localement, interroger Zotero avant de répondre : code et nom complet, numéro ou date de séance, mots distinctifs cités, concepts, tags probables. Inspecter les résultats plausibles avec `get_items` pour obtenir leurs pièces jointes.
4. Lire le passage utile dans le document original, puis séparer ce que dit la source, l'explication pédagogique de l'agent et ses éventuelles inférences.
5. Si les recherches ciblées échouent, s'arrêter et dire ce qui a été cherché. Demander un titre, une date, un fichier ou un autre repère plutôt que de présenter une réponse comme issue du cours. Ne répondre sans source que si l'utilisateur le demande explicitement.

Ce déroulé est en lecture seule : il n'autorise aucune modification de Zotero.

## Lire et retrouver des références

Lectures libres tant que Zotero est ouvert :

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' search_items '{"query":"terme","limit":20}'
python3 '{{SKILL_DIR}}/tools/zot.py' get_items '{"itemKeys":["ABCD1234"]}'
python3 '{{SKILL_DIR}}/tools/zot.py' list_collections '{"query":"statistiques"}'
```

Seulement si Zotero ou le pont sont indisponibles, utiliser le secours hors ligne en lecture seule :

```bash
ZOTERO_BASE_DIR='{{ZOTERO_FICHIERS}}' python3 '{{SKILL_DIR}}/tools/zotquery.py' search "terme" --limit 20
```

Pour une question sur un document, une transcription Markdown voisine peut servir d'aide, mais vérifier citations, tableaux, schémas, mise en page et passages ambigus dans le PDF.

## Ranger un document dans Zotero

Les PDF ajoutés par le pont sont des **fichiers liés** : ils restent sur le disque, dans `{{ZOTERO_FICHIERS}}`, et Zotero pointe vers eux. Pour ajouter un support :

1. lister les collections (`list_collections`) et choisir une collection **existante** dont le sujet correspond au contenu du document ;
2. copier le PDF dans `{{ZOTERO_FICHIERS}}/<chemin de la collection>/`, sans écraser un fichier différent ;
3. créer l'élément avec `create_item` et ce chemin absolu dans `attachments` (voir les mutations plus bas) ;
4. vérifier l'élément, puis l'indexer dans `{{INDEX}}` (section « Ressources associées ») avec sa clé d'élément, sa clé de pièce jointe et le chemin du PDF. Un import n'est terminé qu'une fois indexé.

Règles de classement :

- Les collections décrivent des **sujets** (par exemple `Mathématiques > Statistiques`), pas le cursus courant de l'utilisateur. Ne pas créer de collection pour un code de cours, une séance, un semestre ou une provenance : ces informations vont dans des tags.
- Pour un support identifié, ajouter des tags précis : `cours`, le code officiel vérifié, l'intitulé ou sa forme courte, le repère de séance ({{ACTIVITES}} suivi du numéro). N'ajouter établissement, année ou enseignant que s'ils sont vérifiés. Ne jamais inventer un code ou un numéro à partir d'un nom de fichier ambigu.
- Si aucune collection existante ne convient, présenter le chemin de collection proposé et les tags prévus, et attendre l'accord avant de la créer. Une demande d'ajout sans collection précisée n'autorise pas l'agent à choisir seul une nouvelle organisation.
- Pour renommer une collection, résoudre sa clé avec `list_collections`, puis utiliser `rename_collection {collectionKey, name}` ; ne pas l'émuler par création, déplacement et corbeille.

## Annotations et surlignages : seulement sur demande explicite

Ne jamais charger les annotations automatiquement, ni en cherchant une source, ni en inspectant un élément, ni parce qu'une pièce jointe en contient. Appeler `get_annotations` uniquement quand l'utilisateur demande explicitement de lire, montrer, analyser ou utiliser ses annotations, surlignages ou commentaires. Localiser d'abord l'élément exact, puis demander une page bornée (`limit`, `offset`, `types`, `colors`, `commentsOnly`). Ne mettre `includePosition: true` que si la géométrie est vraiment nécessaire.

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' get_annotations '{"itemKey":"ABCD1234","commentsOnly":true,"limit":100}'
```

Les annotations montrent ce que l'utilisateur a lu et souligné ; elles ne remplacent pas la source.

## Mutations : préparation, puis confirmation selon le contexte

Ne jamais écrire dans `zotero.sqlite` ni utiliser les API cloud de Zotero. Chaque mutation, y compris `ensure_collection`, suit ce déroulé :

1. Valider localement avec `--prepare` : rien n'est envoyé à Zotero et un `requestId` est renvoyé.
2. Décider s'il faut une confirmation :
   - **demande explicite et suffisamment ciblée de l'utilisateur** (y compris mettre un élément ou une collection à la corbeille, qui est réversible) : passer directement à l'étape 3, après avoir résolu la cible en lecture si sa clé n'est pas donnée ;
   - **proposition spontanée de l'agent**, ou demande dont la cible ou la portée reste à choisir par l'agent : montrer un plan exact et attendre une confirmation explicite juste avant l'exécution.
3. Exécuter la commande inchangée avec `--request-id <UUID préparé>`.
4. Vérifier les clés obtenues avec `get_items`, `search_items` ou `list_collections`, et dire exactement ce qui a changé.

```bash
python3 '{{SKILL_DIR}}/tools/zot.py' add_tags '{"itemKey":"ABCD1234","tags":["statistiques"]}' --prepare
python3 '{{SKILL_DIR}}/tools/zot.py' add_tags '{"itemKey":"ABCD1234","tags":["statistiques"]}' --request-id '<UUID renvoyé par --prepare>'
```

Pour un `batch`, l'utilisateur confirme aussi qu'une sauvegarde de `~/Zotero/zotero.sqlite` vient d'être faite. Garder les lots petits ; un lot n'est pas transactionnel : en cas d'échec, partir de `failedIndex` et `applied`, ne jamais renvoyer tout le lot sous un nouvel identifiant. Ne jamais vider la corbeille de Zotero ni supprimer un fichier lié du disque.

## Reprises et résultats incertains

Le pont garde chaque mutation en mémoire par `requestId` pendant la session Zotero. Après un délai dépassé ou une réponse perdue, inspecter d'abord Zotero, puis ne rejouer que la commande identique avec le même UUID. Ne jamais réutiliser un UUID pour d'autres arguments. Si Zotero a redémarré, vérifier l'état et demander à l'utilisateur avant une nouvelle mutation.

Référence complète des commandes : [references/commands.md](references/commands.md). Erreurs et vérifications : [references/troubleshooting.md](references/troubleshooting.md).
