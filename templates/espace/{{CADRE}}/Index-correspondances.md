---
type: index_correspondances
derniere_mise_a_jour: {{DATE}}
---

# Index des correspondances

Cet index aide les agents à relier les différentes façons de nommer un même élément de travail ({{UNITE}}) : agenda, programme officiel, bibliothèque de références, notes et fichiers de l'espace.

Les relations sont plusieurs-à-plusieurs : une séance peut pointer vers plusieurs ressources et une ressource peut servir à plusieurs {{UNITES}} ou séances.

## Statuts

- `confirmée` : association donnée ou validée explicitement par l'utilisateur ;
- `observée` : information lue dans une source, sans validation d'un choix personnel ;
- `candidate` : rapprochement plausible, à présenter comme tel et à faire valider avant enregistrement.

<!-- si:apple-calendar -->
La confirmation d'une association n'autorise pas à modifier l'agenda. La colonne `Lien agenda` indique séparément si l'écriture a été faite.

<!-- fin:apple-calendar -->
## Unités et alias

| Code | Intitulé | Rattachement | Période | Crédits | Alias et indices dans l'agenda | Tags utiles | Statut |
|---|---|---|---|---:|---|---|---|

## Ressources associées

<!-- si:apple-calendar -->
| Identifiant | Unité(s) | Type | Ressource | Accès | Indices de recherche | Association | Lien agenda |
|---|---|---|---|---|---|---|---|
<!-- fin:apple-calendar -->
<!-- si:!apple-calendar -->
| Identifiant | Unité(s) | Type | Ressource | Accès | Indices de recherche | Association |
|---|---|---|---|---|---|---|
<!-- fin:!apple-calendar -->

Identifiant : `<CODE>-<ACTIVITÉ><NN>` (par exemple `ABC-TP03`), ou `<CODE>-<MOT-CLÉ>` pour une ressource hors séance. Accès : chemin local vérifié ou lien web. Un dossier est une ressource à part entière.
<!-- si:zotero-bridge -->
Pour un élément Zotero, noter le lien `zotero://select/library/items/<CLÉ>`, la clé de la pièce jointe et le chemin du PDF dans `{{ZOTERO_FICHIERS}}`.
<!-- fin:zotero-bridge -->

<!-- si:apple-calendar -->
## Occurrences d'agenda observées

| Calendrier | Intitulé exact | Horaire | Lieu | Indices de contenu | Unité | Ressource confirmée | État |
|---|---|---|---|---|---|---|---|

Les identifiants d'événements sont volatils : ne pas les conserver comme clés durables. Relire l'occurrence exacte avant chaque préparation de lien.

<!-- fin:apple-calendar -->
## Règles de maintenance

- Conserver les intitulés sources pour que les rapprochements restent vérifiables.
- Ne pas supposer qu'un titre de document contient le nom du cours : utiliser aussi les tags, les acronymes et le contenu.
<!-- si:universite -->
- Ne pas déduire le groupe de TD/TP de l'utilisateur de la présence de plusieurs groupes dans une description d'événement.
<!-- fin:universite -->
- Vérifier qu'un chemin local existe avant de l'ajouter comme ressource.
- N'enregistrer une correspondance nouvelle que si elle est sourcée ou confirmée ; marquer `candidate` les rapprochements incertains.
- Mettre à jour `derniere_mise_a_jour` à chaque modification.
<!-- si:apple-calendar -->
- Pour une écriture dans l'agenda, suivre le skill `apple-calendar` : aperçu exact, accord explicite, écriture, vérification, puis mise à jour de la colonne `Lien agenda`.
<!-- fin:apple-calendar -->
