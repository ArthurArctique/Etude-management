# Etude management

Un espace d'étude organisé pour travailler avec un agent IA (Claude Code, Codex…) : des dossiers bien rangés, un index qui relie tout, tes notes dans Obsidian, tes documents dans Zotero, et des consignes qui apprennent à l'agent à retrouver la bonne source avant de répondre.

Ça ne sert pas qu'aux cours d'université : un apprentissage en autonomie, une thèse, une certification, une veille ou n'importe quelle étude au long cours s'organisent de la même façon.

Le dépôt est un **skill**. La première fois, l'agent te pose quelques questions (où créer le dossier, où ranger les archives, quels modules ajouter…), puis crée l'espace et installe des skills adaptés à tes réponses. Ensuite, le même skill vérifie et met à jour ton installation.

## Ce que tu obtiens

```text
~/Etudes/Master de chimie/
├── AGENTS.md                    consignes lues par l'agent à chaque session
├── 00_Cadre/
│   ├── README.md                programme, organisation, échéances
│   ├── Profil.md                tes choix confirmés (options, groupe, préférences)
│   ├── Index-correspondances.md qui est quoi : acronymes, agenda, ressources
│   └── Sources/                 documents officiels (maquette, règlement…)
├── 01_A_faire/                  tâches reportées, reprenables par n'importe quel agent
├── Matieres/                    une matière par dossier
│   └── CHO/TP/TP03/             sujet, données et scripts du TP 3
└── Obsidian/                    ton vault de notes
    ├── Dictionnaire.md          définitions accumulées au fil des cours
    └── À approfondir.md         notions à reprendre plus tard
```

Les noms s'adaptent à ton domaine : `Matieres/` avec `CM`, `TD`, `TP` pour l'université, `Sujets/` pour un apprentissage en autonomie, `Projets/` pour la recherche, et tu peux tout renommer pendant l'entretien.

## Architecture

Trois endroits, trois rôles :

| Endroit | Contenu | À qui |
|---|---|---|
| **Ce dépôt** (`~/.claude/skills/etude-management`) | le skill d'installation, l'installateur `scripts/etude.py`, les modules et les gabarits | générique, partagé |
| **Les skills installés** (`~/.claude/skills/zotero-bridge`…) | les modules, rendus avec tes chemins et tes options | à toi, régénérables |
| **L'espace d'étude** | tes fichiers, tes notes, ton index, `AGENTS.md` | à toi, jamais écrasé |

- **`AGENTS.md`** est un routeur : il dit à l'agent où se trouvent les sources, comment répondre sur un cours, comment classer un fichier transmis et ce qu'il a le droit de faire. Il ne recopie pas les informations qui changent ; il renvoie aux fichiers qui les portent. Claude Code et Codex le lisent dès qu'une session s'ouvre dans le dossier.
- **L'index des correspondances** est le pivot : le même cours s'appelle « CHO » dans la maquette, « CHO TD gr2 » dans l'agenda et porte un tag dans Zotero. L'index relie ces noms et liste chaque ressource avec son chemin vérifié et son statut (`confirmée`, `observée`, `candidate`).
- **Les modules** sont des skills facultatifs. L'installateur remplace les variables de leurs gabarits par tes chemins et garde les passages qui concernent les modules choisis : un skill Calendrier qui sait que tu utilises Zotero propose d'y chercher les supports d'une séance, sinon il n'en parle pas.

Les principes suivis par les consignes :

1. **Retrouver la source avant de répondre.** Une question sur un cours se répond depuis le document exact, en séparant ce que dit la source et ce qu'ajoute l'agent. Si la source est introuvable, l'agent le dit au lieu d'improviser.
2. **Un dépôt de fichiers n'est pas une consigne.** « Je t'ai envoyé le sujet du TP 4 » : l'agent classe et indexe, puis demande ce que tu veux faire.
3. **Lecture libre, écriture supervisée.** Écrire dans l'agenda, envoyer un mail ou modifier ton classeur de notes passe toujours par un aperçu exact et ta confirmation.
4. **Les contenus sont des données.** Un PDF, un mail ou une page web ne donne jamais d'ordre à l'agent.
5. **La mémoire est dans les fichiers.** Une décision à retenir s'écrit dans l'espace, pas dans l'historique d'une conversation.

Détails : [references/architecture.md](references/architecture.md).

## Pourquoi Zotero

[Zotero](https://www.zotero.org) est un gestionnaire de références libre et gratuit. Il garde chaque document avec ses métadonnées, ses collections, ses tags et tes annotations.

Avec un agent, c'est ce qui fait la différence entre « je crois que le cours dit… » et « le diaporama du CM 3, page 12, dit… » : l'agent cherche par code de cours, tag ou mot-clé, ouvre le PDF exact et cite le passage. Le module **Zotero Bridge** ajoute un petit plugin local :

- aucun cloud, aucun accès direct à la base de Zotero, une liste fermée de commandes ;
- l'agent peut aussi ranger : créer un élément, ajouter des tags, classer dans une collection ; chaque modification est préparée, puis exécutée et vérifiée ;
- jamais de suppression définitive, seulement la corbeille de Zotero ;
- tes surlignages ne sont lus que si tu le demandes ;
- les PDF ajoutés sont des fichiers liés, rangés dans un dossier d'archives que tu choisis (éventuellement synchronisé sur tes autres appareils).

## Pourquoi Obsidian

[Obsidian](https://obsidian.md) affiche un dossier de fichiers Markdown comme un carnet relié : liens entre notes, recherche, graphe. Tes notes restent de simples fichiers texte, sans format propriétaire : l'agent les lit et les complète sans intermédiaire, et tu les consultes confortablement.

L'espace y entretient deux notes : un **dictionnaire** cumulatif des termes rencontrés, et une liste **À approfondir** des notions que tu veux reprendre plus tard. L'agent annonce chaque ajout ; il ne touche pas à tes autres notes sans que tu le demandes. Sans Obsidian, un dossier Markdown ordinaire fonctionne pareil.

## Modules

Tous facultatifs : l'entretien te les propose un par un.

| Module | Système | Ce qu'il fait |
|---|---|---|
| **Zotero Bridge** | macOS, Linux, Windows | retrouver le document exact d'une question, organiser ta bibliothèque |
| **Apple Calendar** | **macOS uniquement** | lire ton emploi du temps, trouver tes disponibilités, relier à chaque séance ses documents et ses notes |
| **Apple Mail** | **macOS uniquement** | chercher, lire et résumer tes mails, préparer des brouillons ; envoyer seulement après ton accord |
| **Suivi des notes** | tous | lire ton classeur de notes (moyennes, coefficients, crédits) et le mettre à jour après un plan confirmé |
| **Import ChatGPT** | tous | reprendre dans l'espace le contexte d'une conversation ChatGPT partagée |
| [**Moodle Bridge**](https://github.com/ArthurArctique/Moodle-Bridge/tree/skill) | tous | projet séparé : synchroniser en lecture seule documents, devoirs, échéances et annonces de ton Moodle |

Apple Calendar et Apple Mail passent par les applications Calendrier et Mail de macOS : ils ne fonctionnent pas sous Windows ni Linux, et l'entretien ne les propose pas sur ces systèmes. Détails, prérequis et limites : [references/modules.md](references/modules.md).

## Installation

**Prérequis** : Python 3.9 ou plus récent, git, et un agent qui lit les skills (Claude Code, Codex…). Zotero et Obsidian si tu veux les modules correspondants.

Clone le dépôt dans le dossier de skills de ton agent.

**Claude Code** (macOS, Linux) :

```bash
git clone https://github.com/ArthurArctique/Etude-management.git ~/.claude/skills/etude-management
```

**Codex** (macOS, Linux) :

```bash
git clone https://github.com/ArthurArctique/Etude-management.git ~/.codex/skills/etude-management
```

**Windows** (PowerShell) :

```powershell
git clone https://github.com/ArthurArctique/Etude-management.git $HOME\.claude\skills\etude-management
```

Si tu utilises les deux agents, clone dans l'un : l'installation reliera l'autre.

Ouvre ensuite une session de ton agent et demande-lui :

> Installe mon espace d'étude avec etude-management.

Il te pose les questions, te montre le plan (dossiers créés, modules, liens), attend ton accord, puis :

1. crée l'espace sans rien écraser ;
2. installe les modules choisis dans le dossier de skills ;
3. t'accompagne pour leur premier usage : c'est **toi** qui installes le plugin dans Zotero et qui réponds aux demandes d'autorisation de macOS ;
4. vérifie que tout est en ordre et te propose des premières demandes.

Aucun mot de passe ni jeton ne passe par la conversation.

## Exemples d'utilisation

Ouvre une session de ton agent dans le dossier de ton espace, puis parle-lui normalement.

**Ranger**

- « On va faire le TP 4 de chimie organique, je t'ai mis le sujet et les données dans Téléchargements. » → classé dans `Matieres/CHO/TP/TP04/`, indexé, puis l'agent te demande ce que tu veux faire.
- « Ajoute ce diaporama du CM 2 à Zotero. » → rangé dans la bonne collection, avec les tags du cours et de la séance, puis indexé.

**Comprendre et réviser**

- « Dans le CM 3, que veut dire le prof par contrôle cinétique ? » → l'agent retrouve le support exact et cite le passage, puis explique.
- « Fais-moi dix questions de révision sur les chapitres 2 et 3, à partir des supports. »
- « Ajoute « énantiomère » au dictionnaire. » · « Je verrai la RMN plus tard. » → ajouté à À approfondir.

**S'organiser**

- « Qu'est-ce que j'ai cette semaine, et quand suis-je libre jeudi ? » (Apple Calendar)
- « Relie à la séance de TD de demain le sujet et mes notes. » → aperçu, puis écriture après ton accord.
- « J'ai reçu un mail de la scolarité sur les examens ? Résume-le. » (Apple Mail)
- « Quelle est ma moyenne du semestre si j'ai 12 au partiel ? » (suivi des notes)
- « Quoi de neuf sur Moodle ? » (Moodle Bridge)

**Reprendre**

- « Reprends cette conversation : https://chatgpt.com/share/… » → contexte utile, confronté à l'état réel de l'espace.
- « Mets de côté la refonte de mes fiches : on la reprendra après les partiels. » → fiche dans `01_A_faire/`.

**Entretenir**

- « Vérifie mon installation. » · « Ajoute le module Apple Mail. » · « J'ai mis à jour le dépôt, mets mes skills à jour. »

## Sécurité et confidentialité

### Pars du principe que tout sera lu

Claude Code et Codex s'exécutent sur ton ordinateur, mais le modèle qui lit et qui répond tourne chez leur fournisseur : Anthropic pour Claude, OpenAI pour ChatGPT et Codex. Tout ce que l'agent lit pour travailler part donc sur leurs serveurs : le contenu d'un fichier qu'il ouvre, le texte extrait d'un PDF, les résultats d'une recherche dans Zotero, un mail, un événement d'agenda, une cellule de ton classeur.

Or cet espace est fait pour que l'agent aille chercher ses sources lui-même. Il faut donc partir du principe que **tout ce qui est lisible dans le dossier de l'espace et dans la bibliothèque Zotero reliée sera lu un jour par l'agent**, et donc envoyé à son fournisseur : parce que tu le lui demandes, parce qu'il cherche la source d'une question, ou au détour d'une recherche plus large que prévu. Avec Claude, considère que toutes ces données arriveront un jour sur les serveurs d'Anthropic, sous une forme que tu ne choisis pas : un extrait, un résumé ou le document entier. Ce qu'elles y deviennent (durée de conservation, utilisation pour améliorer les modèles…) dépend des conditions du service et des réglages de ton compte, pas de cet espace.

Une consigne dans `AGENTS.md` n'y change rien : « ne lis pas ce fichier » est une règle de conduite, pas une protection. Le seul moyen sûr de ne pas envoyer un document, c'est qu'il soit hors de portée de l'agent.

Concrètement :

- **Ne mets dans l'espace et dans Zotero que des documents que tu accepterais de confier au fournisseur de ton agent** : supports de cours, articles, sujets, notes de travail…
- **Range ailleurs ce qui est sensible** : papiers d'identité, documents médicaux, bancaires ou administratifs personnels, mots de passe, données personnelles d'autres personnes, documents confidentiels de stage, d'entreprise ou de laboratoire, tout ce qui est couvert par un accord de confidentialité.
- **Toute ta bibliothèque Zotero compte**, pas seulement les collections liées à l'espace : Zotero Bridge peut chercher partout dedans. Si elle contient des documents sensibles, sors-les de cette bibliothèque.
- **Les modules Apple ouvrent d'autres portes** : avec Apple Mail et Apple Calendar, les mails et les événements que l'agent lit partent eux aussi chez le fournisseur.
- **Le dossier n'est pas une frontière** : selon les autorisations que tu lui accordes, l'agent peut lire d'autres fichiers de ton ordinateur. L'espace est seulement l'endroit où il lit le plus.
- **Règle ton compte** : vérifie chez le fournisseur les réglages de confidentialité (conservation des conversations, utilisation pour l'entraînement). Pour que rien ne quitte ton ordinateur, il faudrait un modèle qui tourne entièrement en local.

### Ce que l'espace garantit

- Les modules n'ajoutent aucun service en ligne : en dehors de ce que l'agent lit, tes fichiers, ta bibliothèque et ta configuration restent sur ton ordinateur. Zotero Bridge écoute seulement en local, avec un token qui n'est jamais affiché.
- Les écritures sensibles (agenda, mails, classeur de notes) passent par un aperçu exact et ta confirmation, à chaque fois.
- Jamais de suppression définitive : corbeille de Zotero, corbeille de Mail, sauvegarde horodatée du classeur.
- Ta configuration (`local/config.json`) est ignorée par git : ce dépôt ne contient aucun chemin ni nom personnel.

## Mettre à jour

```bash
git -C ~/.claude/skills/etude-management pull
```

Puis demande à l'agent de mettre à jour tes skills (« mets à jour etude-management »). Un fichier de skill que tu as modifié à la main est conservé et signalé ; ton espace d'étude n'est jamais modifié par une mise à jour. Désinstallation et dépannage : [references/maintenance.md](references/maintenance.md).

## Contenu du dépôt

```text
SKILL.md                    skill d'installation et de maintenance
agents/openai.yaml          présentation pour Codex
scripts/etude.py            installateur (bibliothèque standard Python)
references/                 entretien, architecture, modules, maintenance
templates/espace/           gabarits de l'espace d'étude
modules/
├── zotero-bridge/          plugin Zotero, client, secours hors ligne, tests
├── apple-calendar/         client EventKit (Swift) et mini-app
├── apple-mail/             client Mail (JavaScript for Automation)
├── suivi-notes/
└── chatgpt-context-import/
```

## Licence

MIT. Voir [LICENSE](LICENSE).
