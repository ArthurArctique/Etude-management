/* =============================================================================
 * zotero-actions.js — secours MANUEL pour Zotero (pas de cloud, pas de SQLite brut)
 *
 * COMMENT L'UTILISER
 *   Zotero → Outils → Développeurs → « Exécuter du JavaScript »
 *   Colle ce fichier, puis en bas décommente/écris l'appel voulu, et clique « Exécuter ».
 *
 * POURQUOI CE FICHIER
 *   Le chemin normal est tools/zot.py avec « Zotero Bridge ».
 *   Ce fichier n'est qu'un secours manuel lorsque le bridge ne peut pas être utilisé.
 *
 * GARDE-FOUS (à respecter)
 *   1. Sauvegarde `~/Zotero/zotero.sqlite` avant un gros lot.
 *   2. Teste d'abord sur une collection jetable (voir DEMO en bas).
 *   3. Chaque fonction agit item par item : en cas d'erreur, rien de global n'est cassé.
 *
 * ⚠️ Aucune fonction n'est appelée automatiquement en exécutant ce fichier.
 *    Ajouter soi-même un appel explicite seulement après validation du plan par l'utilisateur.
 * ========================================================================== */

const LIB = Zotero.Libraries.userLibraryID;

function _item(key) {
  const it = Zotero.Items.getByLibraryAndKey(LIB, key);
  if (!it) throw new Error(`Item introuvable : ${key}`);
  return it;
}
function _collection(key) {
  const c = Zotero.Collections.getByLibraryAndKey(LIB, key);
  if (!c) throw new Error(`Collection introuvable : ${key}`);
  return c;
}

/* --- 1. Collections & organisation --------------------------------------- */

// Crée une collection (ou sous-collection si parentKey fourni). Renvoie sa clé.
async function createCollection(name, parentKey = null) {
  const c = new Zotero.Collection();
  c.libraryID = LIB;
  c.name = name;
  if (parentKey) c.parentID = _collection(parentKey).id;
  await c.saveTx();
  return c.key;
}

// Renomme une collection sur place (clé, items et sous-collections conservés).
// Refuse un nom déjà porté par une collection sœur non supprimée.
async function renameCollection(collectionKey, newName) {
  const c = _collection(collectionKey);
  const name = newName.trim();
  if (!name) throw new Error('Le nouveau nom est vide');
  const sibling = Zotero.Collections.getByLibrary(LIB, true).find(o => (
    !o.deleted && o.key !== c.key && o.name === name && (o.parentKey || null) === (c.parentKey || null)
  ));
  if (sibling) throw new Error(`Une collection sœur porte déjà ce nom : ${sibling.key}`);
  const previous = c.name;
  if (previous === name) return `« ${name} » inchangée`;
  c.name = name;
  await c.saveTx();
  return `« ${previous} » renommée en « ${name} »`;
}

// Ajoute une liste d'items (par clés) à une collection.
async function fileItems(itemKeys, collectionKey) {
  const col = _collection(collectionKey);
  for (const key of itemKeys) {
    const it = _item(key);
    it.addToCollection(col.id);
    await it.saveTx();
  }
  return `${itemKeys.length} item(s) rangé(s) dans « ${col.name} »`;
}

// Retire une liste d'items d'une collection (ne supprime pas les items).
async function unfileItems(itemKeys, collectionKey) {
  const col = _collection(collectionKey);
  for (const key of itemKeys) {
    const it = _item(key);
    it.removeFromCollection(col.id);
    await it.saveTx();
  }
  return `${itemKeys.length} item(s) retiré(s) de « ${col.name} »`;
}

/* --- 2. Tags, notes, métadonnées ----------------------------------------- */

// Ajoute des tags SANS toucher aux tags existants.
async function addTags(itemKey, tags) {
  const it = _item(itemKey);
  for (const t of tags) it.addTag(t);
  await it.saveTx();
  return `Tags ajoutés à ${itemKey} : ${tags.join(', ')}`;
}

// Modifie un champ de métadonnée (title, date, publisher, url, abstractNote, ...).
async function setField(itemKey, field, value) {
  const it = _item(itemKey);
  it.setField(field, value);
  await it.saveTx();
  return `${field} = « ${value} » sur ${itemKey}`;
}

// Ajoute une note-enfant (HTML simple) à un item. Renvoie la clé de la note.
async function addNote(parentKey, html, tags = []) {
  const parent = _item(parentKey);
  const note = new Zotero.Item('note');
  note.libraryID = LIB;
  note.parentID = parent.id;
  note.setNote(html);
  for (const t of tags) note.addTag(t);
  await note.saveTx();
  return note.key;
}

/* --- 3. Fichiers LIÉS (le cas dur) --------------------------------------- */

// Crée une pièce jointe de type FICHIER LIÉ (pas de copie, pas d'upload).
//   absPath        : chemin ABSOLU du fichier (idéalement sous le répertoire de base des fichiers liés)
//   parentKey      : si fourni -> pièce jointe enfant d'un item
//   collectionKey  : si pas de parent -> pièce jointe autonome rangée dans cette collection
// Zotero stocke le chemin absolu et l'affiche relativement au base directory.
async function linkFile(absPath, { parentKey = null, collectionKey = null } = {}) {
  const opts = { file: Zotero.File.pathToFile(absPath) };
  if (parentKey) {
    opts.parentItemID = _item(parentKey).id;
  } else if (collectionKey) {
    opts.collections = [_collection(collectionKey).id];
  }
  const att = await Zotero.Attachments.linkFromFile(opts);
  return att.key;
}

/* Exemple volontairement inactif :
 * return await createCollection('ZZZ - Test Codex (à supprimer)');
 */
