/* Zotero Bridge — protocole local restreint, sans code arbitraire. */
"use strict";

var CodexZoteroBridge = {
	NAME: "Zotero Bridge",
	VERSION: "1.2.0",
	PROTOCOL: 1,
	ENDPOINT: "/codex/execute",
	TOKEN: null,
	TOKEN_PATH: null,
	REQUESTS: new Map(),
	MAX_CACHED_REQUESTS: 500,
	READ_COMMANDS: new Set([
		"ping", "capabilities", "list_collections", "search_items", "get_items",
		"get_annotations"
	]),
	WRITE_COMMANDS: new Set([
		"ensure_collection", "create_collection", "rename_collection", "create_item", "file_items",
		"add_tags", "remove_tags", "set_field", "add_note", "link_file",
		"trash_items", "trash_collection", "batch"
	]),

	BridgeError: class BridgeError extends Error {
		constructor(code, message, details = null, status = 400) {
			super(message);
			this.name = "BridgeError";
			this.code = code;
			this.details = details;
			this.status = status;
		}
	},

	error(code, message, details = null, status = 400) {
		return new this.BridgeError(code, message, details, status);
	},

	errorObject(error) {
		return {
			code: error && error.code ? error.code : "INTERNAL_ERROR",
			message: error && error.message ? error.message : String(error),
			details: error && error.details !== undefined ? error.details : null
		};
	},

	stableStringify(value) {
		if (Array.isArray(value)) {
			return "[" + value.map(v => this.stableStringify(v)).join(",") + "]";
		}
		if (value && typeof value === "object") {
			return "{" + Object.keys(value).sort().map(key => (
				JSON.stringify(key) + ":" + this.stableStringify(value[key])
			)).join(",") + "}";
		}
		return JSON.stringify(value);
	},

	secureEqual(left, right) {
		left = String(left || "");
		right = String(right || "");
		let mismatch = left.length ^ right.length;
		let length = Math.max(left.length, right.length);
		for (let i = 0; i < length; i++) {
			mismatch |= (left.charCodeAt(i % Math.max(left.length, 1)) || 0)
				^ (right.charCodeAt(i % Math.max(right.length, 1)) || 0);
		}
		return mismatch === 0;
	},

	requireObject(value, name = "args") {
		if (!value || typeof value !== "object" || Array.isArray(value)) {
			throw this.error("INVALID_ARGS", name + " doit être un objet JSON.");
		}
		return value;
	},

	requireString(value, name) {
		if (typeof value !== "string" || !value.trim()) {
			throw this.error("INVALID_ARGS", name + " doit être une chaîne non vide.");
		}
		return value.trim();
	},

	requireStringList(value, name, allowEmpty = false) {
		if (!Array.isArray(value) || (!allowEmpty && !value.length)) {
			throw this.error("INVALID_ARGS", name + " doit être une liste non vide.");
		}
		for (let entry of value) {
			this.requireString(entry, name + "[]");
		}
		return value;
	},

	collection(key) {
		let collection = Zotero.Collections.getByLibraryAndKey(
			Zotero.Libraries.userLibraryID,
			this.requireString(key, "collectionKey")
		);
		if (!collection || collection.deleted) {
			throw this.error("COLLECTION_NOT_FOUND", "Collection introuvable : " + key + ".");
		}
		return collection;
	},

	item(key) {
		let item = Zotero.Items.getByLibraryAndKey(
			Zotero.Libraries.userLibraryID,
			this.requireString(key, "itemKey")
		);
		if (!item || item.deleted) {
			throw this.error("ITEM_NOT_FOUND", "Item introuvable : " + key + ".");
		}
		return item;
	},

	collectionPath(collection) {
		let path = [];
		let current = collection;
		while (current) {
			path.unshift(current.name);
			current = current.parentKey
				? Zotero.Collections.getByLibraryAndKey(Zotero.Libraries.userLibraryID, current.parentKey)
				: null;
		}
		return path;
	},

	siblingNamed(name, parentKey, excludeKey = null) {
		return Zotero.Collections.getByLibrary(Zotero.Libraries.userLibraryID, true).find(collection => (
			!collection.deleted && collection.key !== excludeKey && collection.name === name
			&& (collection.parentKey || null) === (parentKey || null)
		)) || null;
	},

	serializeCollection(collection) {
		return {
			key: collection.key,
			name: collection.name,
			parentKey: collection.parentKey || null,
			path: this.collectionPath(collection)
		};
	},

	async serializeItem(item) {
		let collections = item.getCollections(false).map(id => Zotero.Collections.get(id))
			.filter(Boolean).map(collection => this.serializeCollection(collection));
		let attachments = [];
		for (let attachmentID of item.getAttachments(false)) {
			let attachment = Zotero.Items.get(attachmentID);
			if (!attachment || attachment.deleted) continue;
			let path = await attachment.getFilePathAsync();
			attachments.push({
				key: attachment.key,
				title: attachment.getField("title") || "",
				contentType: attachment.attachmentContentType || "",
				path: path || null,
				exists: Boolean(path)
			});
		}
		return {
			key: item.key,
			itemType: item.itemType,
			title: item.getField("title") || "",
			date: item.getField("date") || "",
			abstract: item.getField("abstractNote") || "",
			creators: item.getCreatorsJSON(),
			tags: item.getTags().map(tag => tag.tag),
			collections,
			attachments
		};
	},

	annotationPosition(annotation) {
		let raw = annotation.annotationPosition;
		if (!raw) return {pageIndex: null, value: null};
		if (typeof raw === "object") {
			return {
				pageIndex: Number.isInteger(raw.pageIndex) ? raw.pageIndex : null,
				value: raw
			};
		}
		try {
			let parsed = JSON.parse(raw);
			return {
				pageIndex: parsed && Number.isInteger(parsed.pageIndex) ? parsed.pageIndex : null,
				value: parsed
			};
		} catch (error) {
			return {pageIndex: null, value: String(raw)};
		}
	},

	serializeAnnotation(annotation, attachment, includePosition = false) {
		let position = this.annotationPosition(annotation);
		let tags = typeof annotation.getTags === "function"
			? annotation.getTags().map(tag => tag.tag).filter(Boolean) : [];
		let result = {
			key: annotation.key,
			attachmentKey: attachment.key,
			attachmentTitle: attachment.getField("title") || "",
			type: annotation.annotationType || "",
			text: annotation.annotationText || "",
			comment: annotation.annotationComment || "",
			color: annotation.annotationColor || "",
			pageLabel: annotation.annotationPageLabel || "",
			pageIndex: position.pageIndex,
			sortIndex: annotation.annotationSortIndex || "",
			authorName: annotation.annotationAuthorName || "",
			tags,
			dateAdded: annotation.dateAdded || "",
			dateModified: annotation.dateModified || ""
		};
		if (includePosition) result.position = position.value;
		return result;
	},

	async annotationAttachments(item) {
		if (typeof item.isAttachment === "function" && item.isAttachment()) return [item];
		if (typeof item.isRegularItem !== "function" || !item.isRegularItem()) {
			throw this.error("ITEM_NOT_ANNOTATABLE",
				"La clé doit désigner un item bibliographique ou une pièce jointe Zotero.");
		}
		let attachments = [];
		for (let attachmentID of item.getAttachments(false)) {
			let attachment = Zotero.Items.get(attachmentID);
			if (attachment && !attachment.deleted
				&& typeof attachment.isAttachment === "function" && attachment.isAttachment()) {
				attachments.push(attachment);
			}
		}
		return attachments;
	},

	async validateFilePath(path) {
		path = this.requireString(path, "absPath");
		if (!PathUtils.isAbsolute(path)) {
			throw this.error("INVALID_PATH", "Le chemin doit être absolu : " + path + ".");
		}
		if (!(await IOUtils.exists(path))) {
			throw this.error("FILE_NOT_FOUND", "Fichier introuvable : " + path + ".");
		}
		return path;
	},

	validateLimit(value, fallback, maximum) {
		if (value === undefined || value === null) return fallback;
		if (!Number.isInteger(value) || value < 1 || value > maximum) {
			throw this.error("INVALID_ARGS", "limit doit être compris entre 1 et " + maximum + ".");
		}
		return value;
	},

	async validate(command, args, nested = false) {
		args = this.requireObject(args || {});
		if (!this.READ_COMMANDS.has(command) && !this.WRITE_COMMANDS.has(command)) {
			throw this.error("UNKNOWN_COMMAND", "Commande inconnue : " + command + ".");
		}
		switch (command) {
			case "ping":
			case "capabilities":
				if (Object.keys(args).length) {
					throw this.error("INVALID_ARGS", command + " n'accepte aucun argument.");
				}
				break;
			case "list_collections":
				if (args.query !== undefined) this.requireString(args.query, "query");
				this.validateLimit(args.limit, 200, 500);
				break;
			case "search_items":
				this.requireString(args.query, "query");
				this.validateLimit(args.limit, 20, 100);
				if (args.offset !== undefined && (!Number.isInteger(args.offset) || args.offset < 0)) {
					throw this.error("INVALID_ARGS", "offset doit être positif ou nul.");
				}
				break;
			case "get_items":
				if (this.requireStringList(args.itemKeys, "itemKeys").length > 100) {
					throw this.error("INVALID_ARGS", "get_items accepte au maximum 100 clés.");
				}
				break;
			case "get_annotations": {
				this.item(args.itemKey);
				if (args.types !== undefined) this.requireStringList(args.types, "types");
				if (args.colors !== undefined) this.requireStringList(args.colors, "colors");
				for (let name of ["commentsOnly", "includePosition"]) {
					if (args[name] !== undefined && typeof args[name] !== "boolean") {
						throw this.error("INVALID_ARGS", name + " doit être un booléen.");
					}
				}
				this.validateLimit(args.limit, 100, 500);
				if (args.offset !== undefined && (!Number.isInteger(args.offset) || args.offset < 0)) {
					throw this.error("INVALID_ARGS", "offset doit être positif ou nul.");
				}
				break;
			}
			case "ensure_collection":
				this.requireStringList(args.path, "path");
				break;
			case "create_collection":
				this.requireString(args.name, "name");
				if (args.parentKey) this.collection(args.parentKey);
				break;
			case "rename_collection": {
				let collection = this.collection(args.collectionKey);
				let sibling = this.siblingNamed(this.requireString(args.name, "name"),
					collection.parentKey, collection.key);
				if (sibling) {
					throw this.error("COLLECTION_NAME_CONFLICT",
						"Une collection du même parent porte déjà ce nom : "
						+ this.collectionPath(sibling).join(" / ") + ".",
						{conflictKey: sibling.key, path: this.collectionPath(sibling)}, 409);
				}
				break;
			}
			case "create_item": {
				this.requireString(args.title, "title");
				if (args.collectionKey && args.collectionPath) {
					throw this.error("INVALID_ARGS", "Utilise collectionKey ou collectionPath, pas les deux.");
				}
				if (args.collectionKey) this.collection(args.collectionKey);
				if (args.collectionPath) this.requireStringList(args.collectionPath, "collectionPath");
				this.requireStringList(args.tags || [], "tags", true);
				if (args.creators !== undefined && !Array.isArray(args.creators)) {
					throw this.error("INVALID_ARGS", "creators doit être une liste.");
				}
				for (let path of this.requireStringList(args.attachments || [], "attachments", true)) {
					await this.validateFilePath(path);
				}
				let probe;
				try {
					probe = new Zotero.Item(args.itemType || "document");
					probe.setField("title", String(args.title));
					if (args.date) probe.setField("date", String(args.date));
					if (args.abstract) probe.setField("abstractNote", String(args.abstract));
					if (args.extra) probe.setField("extra", String(args.extra));
				} catch (error) {
					throw this.error("INVALID_ITEM", error.message || String(error));
				}
				break;
			}
			case "file_items":
				this.requireStringList(args.itemKeys, "itemKeys").forEach(key => this.item(key));
				this.collection(args.collectionKey);
				break;
			case "add_tags":
			case "remove_tags":
				this.item(args.itemKey);
				this.requireStringList(args.tags, "tags");
				break;
			case "set_field":
				this.item(args.itemKey);
				this.requireString(args.field, "field");
				if (!("value" in args)) throw this.error("INVALID_ARGS", "value est requis.");
				break;
			case "add_note":
				this.item(args.parentKey);
				this.requireString(args.html, "html");
				this.requireStringList(args.tags || [], "tags", true);
				break;
			case "link_file":
				await this.validateFilePath(args.absPath);
				if (args.parentKey && args.collectionKey) {
					throw this.error("INVALID_ARGS", "Utilise parentKey ou collectionKey, pas les deux.");
				}
				if (args.parentKey) this.item(args.parentKey);
				if (args.collectionKey) this.collection(args.collectionKey);
				break;
			case "trash_items":
				this.requireStringList(args.itemKeys, "itemKeys").forEach(key => this.item(key));
				break;
			case "trash_collection":
				this.collection(args.collectionKey);
				break;
			case "batch": {
				if (nested) throw this.error("INVALID_ARGS", "Les batch imbriqués sont interdits.");
				if (!Array.isArray(args.ops) || !args.ops.length || args.ops.length > 50) {
					throw this.error("INVALID_ARGS", "ops doit contenir entre 1 et 50 opérations.");
				}
				for (let [index, op] of args.ops.entries()) {
					this.requireObject(op, "ops[" + index + "]");
					let nestedCommand = this.requireString(op.command, "ops[" + index + "].command");
					if (!this.WRITE_COMMANDS.has(nestedCommand) || nestedCommand === "batch") {
						throw this.error("INVALID_ARGS", "ops[" + index + "] n'est pas une mutation autorisée.");
					}
					await this.validate(nestedCommand, op.args || {}, true);
				}
				break;
			}
		}
		return args;
	},

	async ensurePath(path) {
		this.requireStringList(path, "path");
		let all = Zotero.Collections.getByLibrary(Zotero.Libraries.userLibraryID, true);
		let parentKey = null;
		let created = [];
		try {
			for (let rawName of path) {
				let name = this.requireString(rawName, "path[]");
				let found = all.find(collection => (
					collection.name === name && (collection.parentKey || null) === parentKey && !collection.deleted
				));
				if (!found) {
					let collection = new Zotero.Collection();
					collection.libraryID = Zotero.Libraries.userLibraryID;
					collection.name = name;
					if (parentKey) collection.parentID = this.collection(parentKey).id;
					await collection.saveTx();
					all.push(collection);
					created.push({key: collection.key, name});
					found = collection;
				}
				parentKey = found.key;
			}
			return {key: parentKey, created};
		} catch (error) {
			if (created.length) {
				throw this.error("PARTIAL_APPLY", "Chemin de collections créé partiellement.", {
					created,
					cause: this.errorObject(error)
				}, 409);
			}
			throw error;
		}
	},

	async linkOne(path, parentID, collectionID) {
		path = await this.validateFilePath(path);
		let options = {file: Zotero.File.pathToFile(path)};
		if (parentID) options.parentItemID = parentID;
		else if (collectionID) options.collections = [collectionID];
		let attachment = await Zotero.Attachments.linkFromFile(options);
		return attachment.key;
	},

	capabilities() {
		return {
			name: this.NAME,
			bridge: this.VERSION,
			protocol: this.PROTOCOL,
			endpoint: this.ENDPOINT,
			idempotency: "requestId obligatoire pour toute mutation; cache limité à la session Zotero",
			commands: {
				read: Array.from(this.READ_COMMANDS).sort(),
				write: Array.from(this.WRITE_COMMANDS).sort()
			}
		};
	},

	async handle(command, args, nested = false) {
		await this.validate(command, args, nested);
		switch (command) {
			case "ping":
				return {zotero: Zotero.version, library: Zotero.Libraries.userLibraryID,
					bridge: this.VERSION, protocol: this.PROTOCOL};
			case "capabilities":
				return this.capabilities();
			case "list_collections": {
				let query = args.query ? args.query.toLocaleLowerCase() : null;
				let limit = this.validateLimit(args.limit, 200, 500);
				let collections = Zotero.Collections.getByLibrary(Zotero.Libraries.userLibraryID, true)
					.filter(collection => !collection.deleted)
					.map(collection => this.serializeCollection(collection));
				if (query) {
					collections = collections.filter(collection => (
						collection.path.join(" / ").toLocaleLowerCase().includes(query)
					));
				}
				collections.sort((a, b) => a.path.join("/").localeCompare(b.path.join("/"), "fr"));
				return {total: collections.length, collections: collections.slice(0, limit)};
			}
			case "search_items": {
				let query = this.requireString(args.query, "query");
				let search = new Zotero.Search();
				search.libraryID = Zotero.Libraries.userLibraryID;
				search.addCondition("quicksearch-fields", "contains", query);
				let ids = await search.search();
				let exact = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, query.toUpperCase());
				if (exact && !ids.includes(exact.id)) ids.unshift(exact.id);
				let items = await Zotero.Items.getAsync(ids);
				if (!Array.isArray(items)) items = items ? [items] : [];
				items = items.filter(item => item && !item.deleted && item.isRegularItem());
				let offset = args.offset || 0;
				let limit = this.validateLimit(args.limit, 20, 100);
				let selected = items.slice(offset, offset + limit);
				return {
					query,
					total: items.length,
					offset,
					limit,
					items: await Promise.all(selected.map(item => this.serializeItem(item)))
				};
			}
			case "get_items": {
				let items = [];
				let missing = [];
				for (let key of args.itemKeys) {
					let item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, key);
					if (!item || item.deleted || !item.isRegularItem()) missing.push(key);
					else items.push(await this.serializeItem(item));
				}
				return {items, missing};
			}
			case "get_annotations": {
				let target = this.item(args.itemKey);
				let attachments = await this.annotationAttachments(target);
				let types = args.types
					? new Set(args.types.map(value => value.trim().toLocaleLowerCase())) : null;
				let colors = args.colors
					? new Set(args.colors.map(value => value.trim().toLocaleLowerCase())) : null;
				let annotations = [];
				let scanned = [];
				for (let [attachmentOrder, attachment] of attachments.entries()) {
					let values = typeof attachment.getAnnotations === "function"
						? await Promise.resolve(attachment.getAnnotations()) : [];
					if (!Array.isArray(values)) values = values ? [values] : [];
					values = values.filter(annotation => annotation && !annotation.deleted);
					scanned.push({
						key: attachment.key,
						title: attachment.getField("title") || "",
						contentType: attachment.attachmentContentType || "",
						annotationCount: values.length
					});
					for (let annotation of values) {
						let type = String(annotation.annotationType || "").toLocaleLowerCase();
						let color = String(annotation.annotationColor || "").toLocaleLowerCase();
						if (types && !types.has(type)) continue;
						if (colors && !colors.has(color)) continue;
						if (args.commentsOnly && !String(annotation.annotationComment || "").trim()) continue;
						annotations.push({attachmentOrder, annotation});
					}
				}
				annotations.sort((left, right) => {
					if (left.attachmentOrder !== right.attachmentOrder) {
						return left.attachmentOrder - right.attachmentOrder;
					}
					let leftIndex = String(left.annotation.annotationSortIndex || "");
					let rightIndex = String(right.annotation.annotationSortIndex || "");
					return leftIndex.localeCompare(rightIndex)
						|| String(left.annotation.key || "").localeCompare(String(right.annotation.key || ""));
				});
				let offset = args.offset || 0;
				let limit = this.validateLimit(args.limit, 100, 500);
				let selected = annotations.slice(offset, offset + limit);
				return {
					itemKey: target.key,
					targetType: typeof target.isAttachment === "function" && target.isAttachment()
						? "attachment" : "regularItem",
					total: annotations.length,
					offset,
					limit,
					attachments: scanned,
					annotations: selected.map(entry => this.serializeAnnotation(
						entry.annotation,
						attachments[entry.attachmentOrder],
						Boolean(args.includePosition)
					))
				};
			}
			case "ensure_collection":
				return await this.ensurePath(args.path);
			case "create_collection": {
				let collection = new Zotero.Collection();
				collection.libraryID = Zotero.Libraries.userLibraryID;
				collection.name = args.name.trim();
				if (args.parentKey) collection.parentID = this.collection(args.parentKey).id;
				await collection.saveTx();
				return this.serializeCollection(collection);
			}
			case "rename_collection": {
				let collection = this.collection(args.collectionKey);
				let previous = this.serializeCollection(collection);
				let name = args.name.trim();
				let changed = collection.name !== name;
				if (changed) {
					collection.name = name;
					await collection.saveTx();
				}
				return {
					collection: this.serializeCollection(collection),
					previousName: previous.name,
					previousPath: previous.path,
					changed
				};
			}
			case "create_item": {
				let item = null;
				let attachmentKeys = [];
				try {
					item = new Zotero.Item(args.itemType || "document");
					item.libraryID = Zotero.Libraries.userLibraryID;
					item.setField("title", String(args.title));
					if (args.date) item.setField("date", String(args.date));
					if (args.abstract) item.setField("abstractNote", String(args.abstract));
					if (args.extra) item.setField("extra", String(args.extra));
					if (Array.isArray(args.creators)) {
						item.setCreators(args.creators.map(creator => creator.name
							? {creatorType: creator.creatorType || "author", name: String(creator.name), fieldMode: 1}
							: {creatorType: creator.creatorType || "author",
								firstName: String(creator.firstName || ""), lastName: String(creator.lastName || "")}));
					}
					for (let tag of args.tags || []) item.addTag(String(tag));
					let collectionKey = args.collectionKey || null;
					if (!collectionKey && args.collectionPath) {
						collectionKey = (await this.ensurePath(args.collectionPath)).key;
					}
					if (collectionKey) item.addToCollection(this.collection(collectionKey).id);
					await item.saveTx();
					for (let path of args.attachments || []) {
						attachmentKeys.push(await this.linkOne(path, item.id, null));
					}
					return {key: item.key, itemType: item.itemType, attachments: attachmentKeys};
				} catch (error) {
					if (item && item.key) {
						throw this.error("PARTIAL_APPLY", "L'item a été créé mais l'opération n'est pas complète.", {
							itemKey: item.key,
							attachmentKeys,
							cause: this.errorObject(error)
						}, 409);
					}
					throw error;
				}
			}
			case "file_items": {
				let target = this.collection(args.collectionKey);
				let items = args.itemKeys.map(key => this.item(key));
				for (let item of items) {
					item.addToCollection(target.id);
					await item.saveTx();
				}
				return {filed: items.map(item => item.key), collection: this.serializeCollection(target)};
			}
			case "add_tags": {
				let item = this.item(args.itemKey);
				for (let tag of args.tags) item.addTag(String(tag));
				await item.saveTx();
				return {itemKey: item.key, added: args.tags};
			}
			case "remove_tags": {
				let item = this.item(args.itemKey);
				for (let tag of args.tags) item.removeTag(String(tag));
				await item.saveTx();
				return {itemKey: item.key, removed: args.tags};
			}
			case "set_field": {
				let item = this.item(args.itemKey);
				try {
					item.setField(String(args.field), String(args.value));
				} catch (error) {
					throw this.error("INVALID_FIELD", error.message || String(error));
				}
				await item.saveTx();
				return {itemKey: item.key, field: args.field, value: String(args.value)};
			}
			case "add_note": {
				let parent = this.item(args.parentKey);
				let note = new Zotero.Item("note");
				note.libraryID = Zotero.Libraries.userLibraryID;
				note.parentID = parent.id;
				note.setNote(String(args.html));
				for (let tag of args.tags || []) note.addTag(String(tag));
				await note.saveTx();
				return {key: note.key, parentKey: parent.key};
			}
			case "link_file": {
				let parentID = args.parentKey ? this.item(args.parentKey).id : null;
				let collectionID = !parentID && args.collectionKey
					? this.collection(args.collectionKey).id : null;
				return {key: await this.linkOne(args.absPath, parentID, collectionID)};
			}
			case "trash_items": {
				let items = args.itemKeys.map(key => this.item(key));
				for (let item of items) {
					item.deleted = true;
					await item.saveTx();
				}
				return {trashed: items.map(item => item.key), reversible: true};
			}
			case "trash_collection": {
				let collection = this.collection(args.collectionKey);
				let result = this.serializeCollection(collection);
				collection.deleted = true;
				await collection.saveTx();
				return {trashed: result, itemsPreserved: true, reversible: true};
			}
			case "batch": {
				let results = [];
				for (let [index, op] of args.ops.entries()) {
					try {
						results.push(await this.handle(op.command, op.args || {}, true));
					} catch (error) {
						throw this.error("PARTIAL_BATCH", "Le batch s'est arrêté à l'opération " + index + ".", {
							failedIndex: index,
							failedCommand: op.command,
							applied: results,
							cause: this.errorObject(error)
						}, 409);
					}
				}
				return {count: results.length, results};
			}
		}
		throw this.error("UNKNOWN_COMMAND", "Commande inconnue : " + command + ".");
	},

	trimRequestCache() {
		while (this.REQUESTS.size > this.MAX_CACHED_REQUESTS) {
			this.REQUESTS.delete(this.REQUESTS.keys().next().value);
		}
	},

	async execute(command, args, requestId) {
		let mutating = this.WRITE_COMMANDS.has(command);
		if (!mutating) return await this.handle(command, args || {});
		if (typeof requestId !== "string"
			|| !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(requestId)) {
			throw this.error("REQUEST_ID_REQUIRED", "Un requestId UUID valide est obligatoire pour toute mutation.");
		}
		let fingerprint = this.stableStringify({command, args: args || {}});
		let existing = this.REQUESTS.get(requestId);
		if (existing) {
			if (existing.fingerprint !== fingerprint) {
				throw this.error("REQUEST_ID_CONFLICT", "Ce requestId est déjà associé à une autre opération.", null, 409);
			}
			return await existing.promise;
		}
		let promise = this.handle(command, args || {});
		this.REQUESTS.set(requestId, {fingerprint, promise});
		this.trimRequestCache();
		return await promise;
	},

	async loadToken() {
		this.TOKEN_PATH = PathUtils.join(Services.dirsvc.get("Home", Components.interfaces.nsIFile).path, ".codex-zotero-bridge", "token");
		if (!(await IOUtils.exists(this.TOKEN_PATH))) {
			this.TOKEN = null;
			return;
		}
		let token = (await IOUtils.readUTF8(this.TOKEN_PATH)).trim();
		this.TOKEN = token.length >= 32 ? token : null;
	},

	registerEndpoints() {
		let bridge = this;
		let Endpoint = function () {};
		Endpoint.prototype = {
			supportedMethods: ["POST"],
			supportedDataTypes: ["application/json"],
			init: async function (request) {
				let requestId = null;
				try {
					if (!bridge.TOKEN) {
						throw bridge.error("TOKEN_NOT_CONFIGURED",
							"Token absent ou invalide dans ~/.codex-zotero-bridge/token.", null, 503);
					}
					let data = request && request.data !== undefined ? request.data : request;
					if (typeof data === "string") data = JSON.parse(data);
					data = bridge.requireObject(data || {}, "request");
					requestId = data.requestId || null;
					if (!bridge.secureEqual(data.token, bridge.TOKEN)) {
						throw bridge.error("AUTH_FAILED", "Token invalide.", null, 401);
					}
					let command = bridge.requireString(data.command, "command");
					let result = await bridge.execute(command, data.args || {}, requestId);
					return [200, "application/json", JSON.stringify({ok: true, requestId, result})];
				} catch (error) {
					let normalized = error instanceof bridge.BridgeError
						? error : bridge.error("INTERNAL_ERROR", error.message || String(error), null, 500);
					return [normalized.status || 500, "application/json", JSON.stringify({
						ok: false,
						requestId,
						error: bridge.errorObject(normalized)
					})];
				}
			}
		};

		Zotero.Server.Endpoints[this.ENDPOINT] = Endpoint;
	},

	unregisterEndpoints() {
		try { delete Zotero.Server.Endpoints[this.ENDPOINT]; } catch (error) {}
	}
};

async function startup() {
	await Zotero.initializationPromise;
	await CodexZoteroBridge.loadToken();
	CodexZoteroBridge.registerEndpoints();
	Zotero.debug("[codex-zotero-bridge] v" + CodexZoteroBridge.VERSION + " actif");
}

function shutdown() {
	CodexZoteroBridge.unregisterEndpoints();
}

function install() {}
function uninstall() {}
