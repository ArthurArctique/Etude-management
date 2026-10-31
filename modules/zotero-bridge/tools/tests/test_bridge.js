"use strict";

const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync(require("path").join(__dirname, "..", "codex-zotero-bridge", "bootstrap.js"), "utf8");
const context = {
	console,
	Components: {interfaces: {nsIFile: {}}},
	Services: {dirsvc: {get(key) {assert.strictEqual(key, "Home"); return {path: "/fake-home"};}}},
	PathUtils: {join(...parts) {assert(parts.every(p => typeof p === "string")); return parts.join("/");}},
	IOUtils: {async exists() {return true;}, async readUTF8(path) {
		assert.strictEqual(path, "/fake-home/.codex-zotero-bridge/token");
		return "test-token-value-not-a-real-secret-for-startup";
	}},
	Zotero: {
		version: "9.test",
		Libraries: {userLibraryID: 1},
		initializationPromise: Promise.resolve(),
		Server: {Endpoints: {}},
		debug() {}
	}
};
vm.createContext(context);
vm.runInContext(source, context);

const bridge = context.CodexZoteroBridge;
assert(bridge, "bridge global missing");
assert.strictEqual(bridge.ENDPOINT, "/codex/execute");
assert.strictEqual(bridge.secureEqual("same-value", "same-value"), true);
assert.strictEqual(bridge.secureEqual("same-value", "different"), false);

(async () => {
	await context.startup();
	assert(context.Zotero.Server.Endpoints[bridge.ENDPOINT], "startup did not register the endpoint");
	const Endpoint = context.Zotero.Server.Endpoints[bridge.ENDPOINT];
	const [status, , body] = await new Endpoint().init({data: {command: "ping", token: bridge.TOKEN}});
	assert.strictEqual(status, 200);
	assert.strictEqual(JSON.parse(body).ok, true);
	context.shutdown();
	assert.strictEqual(context.Zotero.Server.Endpoints[bridge.ENDPOINT], undefined);

	const annotations = [
		{
			key: "ANN00002", deleted: false, annotationType: "highlight",
			annotationText: "Second passage", annotationComment: "À revoir",
			annotationColor: "#ffd400", annotationPageLabel: "3",
			annotationSortIndex: "00002", annotationAuthorName: "Utilisateur",
			annotationPosition: JSON.stringify({pageIndex: 2, rects: [[1, 2, 3, 4]]}),
			dateAdded: "2026-09-17", dateModified: "2026-09-17",
			getTags() {return [{tag: "important"}];}
		},
		{
			key: "ANN00001", deleted: false, annotationType: "underline",
			annotationText: "Premier passage", annotationComment: "",
			annotationColor: "#2ea8e5", annotationPageLabel: "2",
			annotationSortIndex: "00001", annotationPosition: JSON.stringify({pageIndex: 1}),
			getTags() {return [];}
		}
	];
	const attachment = {
		id: 20, key: "ATTACH01", deleted: false, attachmentContentType: "application/pdf",
		isAttachment() {return true;},
		isRegularItem() {return false;},
		getField(field) {assert.strictEqual(field, "title"); return "Cours annoté.pdf";},
		getAnnotations() {return annotations;}
	};
	const regularItem = {
		id: 10, key: "ITEM0001", deleted: false,
		isAttachment() {return false;},
		isRegularItem() {return true;},
		getAttachments(includeTrashed) {assert.strictEqual(includeTrashed, false); return [20];}
	};
	context.Zotero.Items = {
		getByLibraryAndKey(libraryID, key) {
			assert.strictEqual(libraryID, 1);
			return key === regularItem.key ? regularItem : key === attachment.key ? attachment : null;
		},
		get(id) {return id === attachment.id ? attachment : null;}
	};
	const annotationResult = await bridge.handle("get_annotations", {
		itemKey: regularItem.key,
		commentsOnly: true,
		colors: ["#FFD400"],
		limit: 10
	});
	assert.strictEqual(annotationResult.total, 1);
	assert.strictEqual(annotationResult.attachments[0].annotationCount, 2);
	assert.strictEqual(annotationResult.annotations[0].key, "ANN00002");
	assert.strictEqual(annotationResult.annotations[0].pageIndex, 2);
	assert.strictEqual("position" in annotationResult.annotations[0], false,
		"annotation geometry should be omitted by default");

	const positionedResult = await bridge.handle("get_annotations", {
		itemKey: attachment.key,
		types: ["highlight"],
		includePosition: true,
		limit: 1
	});
	assert.deepStrictEqual(
		JSON.parse(JSON.stringify(positionedResult.annotations[0].position)),
		{pageIndex: 2, rects: [[1, 2, 3, 4]]}
	);

	const makeCollection = (key, name, parentKey = null, deleted = false) => ({
		key, name, parentKey, deleted, saves: 0,
		async saveTx() {this.saves++;}
	});
	const collections = [
		makeCollection("SCIENCE1", "Sciences"),
		makeCollection("GENOMIC1", "Genomique", "SCIENCE1"),
		makeCollection("SEQUENC1", "Séquences", "SCIENCE1"),
		makeCollection("BIOLOGY1", "Biologie"),
		makeCollection("GENOMIC2", "Génomique", "BIOLOGY1"),
		makeCollection("TRASHED1", "Ancienne", "SCIENCE1", true)
	];
	context.Zotero.Collections = {
		getByLibraryAndKey(libraryID, key) {
			assert.strictEqual(libraryID, 1);
			return collections.find(collection => collection.key === key) || null;
		},
		getByLibrary(libraryID, recursive) {
			assert.strictEqual(libraryID, 1);
			assert.strictEqual(recursive, true);
			return collections;
		}
	};
	const genomic = collections[1];
	const renamed = await bridge.handle("rename_collection", {collectionKey: "GENOMIC1", name: "  Génomique  "});
	assert.strictEqual(genomic.name, "Génomique", "name should be trimmed and applied");
	assert.strictEqual(genomic.saves, 1);
	assert.deepStrictEqual(JSON.parse(JSON.stringify(renamed)), {
		collection: {key: "GENOMIC1", name: "Génomique", parentKey: "SCIENCE1", path: ["Sciences", "Génomique"]},
		previousName: "Genomique",
		previousPath: ["Sciences", "Genomique"],
		changed: true
	}, "a homonym under another parent must not block the rename");

	const unchanged = await bridge.handle("rename_collection", {collectionKey: "GENOMIC1", name: "Génomique"});
	assert.strictEqual(unchanged.changed, false);
	assert.strictEqual(genomic.saves, 1, "an unchanged name must not be saved again");

	await assert.rejects(
		bridge.handle("rename_collection", {collectionKey: "SEQUENC1", name: "Génomique"}),
		error => error.code === "COLLECTION_NAME_CONFLICT" && error.details.conflictKey === "GENOMIC1"
	);
	assert.strictEqual(collections[2].name, "Séquences", "a conflicting rename must not write");
	assert.strictEqual(collections[2].saves, 0);

	const revived = await bridge.handle("rename_collection", {collectionKey: "SEQUENC1", name: "Ancienne"});
	assert.strictEqual(revived.changed, true, "a trashed sibling must not block the rename");
	await assert.rejects(
		bridge.handle("rename_collection", {collectionKey: "TRASHED1", name: "Autre"}),
		error => error.code === "COLLECTION_NOT_FOUND"
	);
	await assert.rejects(
		bridge.handle("rename_collection", {collectionKey: "BIOLOGY1", name: "   "}),
		error => error.code === "INVALID_ARGS"
	);
	await bridge.validate("batch", {ops: [
		{command: "rename_collection", args: {collectionKey: "BIOLOGY1", name: "Biologie générale"}}
	]});
	assert(bridge.capabilities().commands.write.includes("rename_collection"));

	let calls = 0;
	bridge.WRITE_COMMANDS = new Set(["mutate"]);
	bridge.handle = async (command, args) => {
		calls++;
		return {command, args, calls};
	};
	const requestId = "123e4567-e89b-42d3-a456-426614174000";
	const first = await bridge.execute("mutate", {value: 1}, requestId);
	const replay = await bridge.execute("mutate", {value: 1}, requestId);
	assert.deepStrictEqual(first, replay);
	assert.strictEqual(calls, 1, "idempotent replay executed twice");

	await assert.rejects(
		bridge.execute("mutate", {value: 2}, requestId),
		error => error.code === "REQUEST_ID_CONFLICT"
	);
	console.log("bridge tests: OK");
})().catch(error => {
	console.error(error);
	process.exit(1);
});
