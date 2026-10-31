import Foundation
import EventKit

struct CalendarError: Error, CustomStringConvertible {
    let description: String
    init(_ message: String) { description = message }
}

func output(_ object: [String: Any]) throws {
    let data = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data([10]))
}

func accessName() -> String {
    switch EKEventStore.authorizationStatus(for: .event) {
    case .notDetermined: return "not_determined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .fullAccess: return "full_access"
    case .writeOnly: return "write_only"
    @unknown default: return "unknown"
    }
}

func sourceTypeName(_ type: EKSourceType) -> String {
    switch type {
    case .local: return "local"
    case .exchange: return "exchange"
    case .calDAV: return "caldav"
    case .mobileMe: return "mobileme"
    case .subscribed: return "subscribed"
    case .birthdays: return "birthdays"
    @unknown default: return "unknown"
    }
}

func metadata() -> [String: Any] {
    [
        "access": accessName(),
        "read_only_client": false,
        "writes_require_confirm_flag": true,
        "queried_at": ISO8601DateFormatter().string(from: Date()),
        "system_timezone": TimeZone.current.identifier,
        "source": "Apple EventKit local store; last server sync time unavailable"
    ]
}

func sourceRecord(_ source: EKSource) -> [String: Any] {
    ["id": source.sourceIdentifier, "title": source.title, "type": sourceTypeName(source.sourceType)]
}

func calendarRecord(_ calendar: EKCalendar) -> [String: Any] {
    [
        "id": calendar.calendarIdentifier,
        "title": calendar.title,
        "source": calendar.source.title,
        "source_id": calendar.source.sourceIdentifier,
        "subscribed": calendar.isSubscribed,
        "writable": calendar.allowsContentModifications
    ]
}

func parseDate(_ value: String, zone: TimeZone) throws -> Date {
    if value.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.timeZone = zone
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.isLenient = false
        if let date = formatter.date(from: value), formatter.string(from: date) == value { return date }
    } else if value.range(of: #"(Z|[+-]\d{2}:\d{2})$"#, options: .regularExpression) != nil {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: value) { return date }
        formatter.formatOptions.insert(.withFractionalSeconds)
        if let date = formatter.date(from: value) { return date }
    }
    throw CalendarError("Invalid date '\(value)'. Use YYYY-MM-DD or an ISO 8601 timestamp with UTC offset.")
}

struct Query {
    var start: Date
    var end: Date
    var zone: TimeZone
    var calendarIDs: [String]
    var allCalendars: Bool
    var search: String?
    var notes: Bool
    var links: Bool
    var limit: Int

    init(_ args: [String]) throws {
        var values: [String: String] = [:]
        var ids: [String] = []
        var all = false
        var includeNotes = false
        var includeLinks = false
        var i = 0
        while i < args.count {
            let option = args[i]
            if option == "--all-calendars" { all = true; i += 1; continue }
            if option == "--include-notes" { includeNotes = true; i += 1; continue }
            if option == "--include-links" { includeLinks = true; i += 1; continue }
            guard ["--from", "--to", "--timezone", "--calendar", "--search", "--limit"].contains(option), i + 1 < args.count else {
                throw CalendarError("Unknown option or missing value: \(option)")
            }
            if option == "--calendar" { ids.append(args[i + 1]) }
            else {
                guard values[option] == nil else { throw CalendarError("Repeated option: \(option)") }
                values[option] = args[i + 1]
            }
            i += 2
        }
        guard let from = values["--from"], let to = values["--to"] else {
            throw CalendarError("events requires --from and --to (exclusive end).")
        }
        guard all != !ids.isEmpty else {
            throw CalendarError("Choose --calendar ID (repeatable) OR --all-calendars.")
        }
        guard let tz = TimeZone(identifier: values["--timezone"] ?? TimeZone.current.identifier) else {
            throw CalendarError("Unknown timezone.")
        }
        let first = try parseDate(from, zone: tz)
        let last = try parseDate(to, zone: tz)
        guard last > first, last.timeIntervalSince(first) <= 366 * 86400 else {
            throw CalendarError("The interval must be positive and at most 366 days.")
        }
        guard let cap = Int(values["--limit"] ?? "500"), (1...10000).contains(cap) else {
            throw CalendarError("--limit must be an integer from 1 to 10000.")
        }
        start = first
        end = last
        zone = tz
        calendarIDs = ids
        allCalendars = all
        search = values["--search"]
        notes = includeNotes
        links = includeLinks
        limit = cap
    }
}

struct CLIOptions {
    var values: [String: String] = [:]
    var flags: Set<String> = []

    init(_ args: [String], valueOptions: Set<String>, flagOptions: Set<String>) throws {
        var i = 0
        while i < args.count {
            let option = args[i]
            if flagOptions.contains(option) {
                guard !flags.contains(option) else { throw CalendarError("Repeated option: \(option)") }
                flags.insert(option)
                i += 1
                continue
            }
            guard valueOptions.contains(option), i + 1 < args.count else {
                throw CalendarError("Unknown option or missing value: \(option)")
            }
            guard values[option] == nil else { throw CalendarError("Repeated option: \(option)") }
            values[option] = args[i + 1]
            i += 2
        }
    }
}

struct EnsureCalendarRequest {
    let title: String
    let sourceID: String
    let confirm: Bool

    init(_ args: [String]) throws {
        let parsed = try CLIOptions(args, valueOptions: ["--title", "--source"], flagOptions: ["--confirm"])
        guard let title = parsed.values["--title"], !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              !title.contains("\n"), let sourceID = parsed.values["--source"] else {
            throw CalendarError("ensure-link-calendar requires --title TEXT and --source ID.")
        }
        self.title = title
        self.sourceID = sourceID
        confirm = parsed.flags.contains("--confirm")
    }
}

struct ResourceInput: Decodable {
    let label: String
    let kind: String?
    let url: String?
    let path: String?
}

struct LinkedResource {
    let label: String
    let kind: String
    let primaryURL: URL
    let fileURL: URL?
    let path: String?
}

func loadResources(_ manifestPath: String) throws -> [LinkedResource] {
    guard manifestPath.hasPrefix("/"), FileManager.default.fileExists(atPath: manifestPath) else {
        throw CalendarError("--resources must be an existing absolute JSON file path.")
    }
    let data = try Data(contentsOf: URL(fileURLWithPath: manifestPath))
    let inputs: [ResourceInput]
    do { inputs = try JSONDecoder().decode([ResourceInput].self, from: data) }
    catch { throw CalendarError("Invalid resources JSON: \(error)") }
    guard (1...100).contains(inputs.count) else {
        throw CalendarError("The resources manifest must contain from 1 to 100 entries.")
    }
    return try inputs.map { item in
        let label = item.label.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !label.isEmpty, !label.contains("\n") else {
            throw CalendarError("Each resource label must be non-empty and on one line.")
        }
        var fileURL: URL? = nil
        var isDirectory: ObjCBool = false
        if let path = item.path {
            guard path.hasPrefix("/"), FileManager.default.fileExists(atPath: path, isDirectory: &isDirectory) else {
                throw CalendarError("Resource path does not exist or is not absolute: \(path)")
            }
            fileURL = URL(fileURLWithPath: path, isDirectory: isDirectory.boolValue)
        }
        let primaryURL: URL
        if let raw = item.url {
            guard let url = URL(string: raw), let scheme = url.scheme?.lowercased(),
                  ["zotero", "file", "https", "http"].contains(scheme) else {
                throw CalendarError("Resource URL must use zotero, file, https, or http: \(raw)")
            }
            primaryURL = url
        } else if let local = fileURL {
            primaryURL = local
        } else {
            throw CalendarError("Each resource requires url or path.")
        }
        let inferredKind: String
        if isDirectory.boolValue { inferredKind = "dossier" }
        else if let path = item.path, path.contains("/Obsidian/") { inferredKind = "note-obsidian" }
        else if primaryURL.scheme?.lowercased() == "zotero" { inferredKind = "zotero" }
        else if item.path != nil { inferredKind = "fichier" }
        else { inferredKind = "web" }
        let kind = (item.kind ?? inferredKind).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !kind.isEmpty, !kind.contains("\n") else { throw CalendarError("Resource kind must be on one line.") }
        return LinkedResource(label: label, kind: kind, primaryURL: primaryURL, fileURL: fileURL, path: item.path)
    }
}

struct LinkRequest {
    let eventID: String
    let sourceCalendarID: String
    let start: Date
    let expectedTitle: String
    let resources: [LinkedResource]
    let targetCalendarID: String?
    let confirm: Bool

    init(_ args: [String]) throws {
        let parsed = try CLIOptions(
            args,
            valueOptions: ["--event", "--source-calendar", "--start", "--expected-title", "--resources", "--target-calendar"],
            flagOptions: ["--confirm"]
        )
        guard let eventID = parsed.values["--event"],
              let sourceCalendarID = parsed.values["--source-calendar"],
              let startText = parsed.values["--start"], startText.contains("T"),
              let expectedTitle = parsed.values["--expected-title"],
              let resourcesPath = parsed.values["--resources"] else {
            throw CalendarError("link-resources requires --event ID --source-calendar ID --start ISO_TIMESTAMP --expected-title TEXT --resources ABSOLUTE_JSON_PATH.")
        }
        self.eventID = eventID
        self.sourceCalendarID = sourceCalendarID
        start = try parseDate(startText, zone: .current)
        self.expectedTitle = expectedTitle
        resources = try loadResources(resourcesPath)
        targetCalendarID = parsed.values["--target-calendar"]
        confirm = parsed.flags.contains("--confirm")
    }
}

func eventRecord(_ event: EKEvent, zone: TimeZone, includeNotes: Bool, includeLinks: Bool) -> [String: Any] {
    let iso = ISO8601DateFormatter()
    iso.timeZone = zone
    var row: [String: Any] = [
        "id": event.eventIdentifier ?? "",
        "calendar_id": event.calendar.calendarIdentifier,
        "calendar": event.calendar.title,
        "writable": event.calendar.allowsContentModifications,
        "title": event.title ?? "",
        "start": iso.string(from: event.startDate),
        "end": iso.string(from: event.endDate),
        "all_day": event.isAllDay,
        "location": event.location ?? "",
        "event_timezone": event.timeZone?.identifier ?? "floating",
        "recurring": event.hasRecurrenceRules,
        "detached_occurrence": event.isDetached,
        "status": [0: "none", 1: "confirmed", 2: "tentative", 3: "canceled"][event.status.rawValue] ?? "unknown",
        "availability": [-1: "unsupported", 0: "busy", 1: "free", 2: "tentative", 3: "unavailable"][event.availability.rawValue] ?? "unknown"
    ]
    if let occurrence = event.occurrenceDate { row["occurrence_date"] = iso.string(from: occurrence) }
    if includeNotes { row["notes"] = event.notes ?? "" }
    if includeLinks { row["url"] = event.url?.absoluteString ?? "" }
    return row
}

func resolveEvent(store: EKEventStore, request: LinkRequest) throws -> EKEvent {
    guard let calendar = store.calendar(withIdentifier: request.sourceCalendarID) else {
        throw CalendarError("Source calendar not found. Run calendars again.")
    }
    let candidates = store.events(matching: store.predicateForEvents(
        withStart: request.start.addingTimeInterval(-1),
        end: request.start.addingTimeInterval(1),
        calendars: [calendar]
    ))
    let matches = candidates.filter {
        $0.eventIdentifier == request.eventID &&
        $0.calendar.calendarIdentifier == request.sourceCalendarID &&
        abs($0.startDate.timeIntervalSince(request.start)) < 1
    }
    guard matches.count == 1, let event = matches.first else {
        throw CalendarError("Exact source event not found or ambiguous. Re-read it and reuse its current id, calendar_id, and start.")
    }
    guard (event.title ?? "") == request.expectedTitle else {
        throw CalendarError("Source event title changed. Expected '\(request.expectedTitle)', found '\(event.title ?? "")'. Re-read before linking.")
    }
    return event
}

let resourcesStart = "[Ressources liées]"
let resourcesEnd = "[/Ressources liées]"

func resourceURLs(_ resource: LinkedResource) -> [String] {
    var urls = [resource.primaryURL.absoluteString]
    if let fileURL = resource.fileURL, fileURL.absoluteString != resource.primaryURL.absoluteString {
        urls.append(fileURL.absoluteString)
    }
    return urls
}

func resourceEntry(_ resource: LinkedResource) -> String {
    var lines = ["- [\(resource.kind)] \(resource.label)", "  Ouvrir : \(resource.primaryURL.absoluteString)"]
    if let fileURL = resource.fileURL, fileURL.absoluteString != resource.primaryURL.absoluteString {
        lines.append("  Fichier : \(fileURL.absoluteString)")
    }
    return lines.joined(separator: "\n")
}

func appendResources(notes: String?, existingURL: URL?, resources: [LinkedResource]) -> (String, [LinkedResource]) {
    let original = notes ?? ""
    let haystack = original + "\n" + (existingURL?.absoluteString ?? "")
    let additions = resources.filter { resource in
        !resourceURLs(resource).allSatisfy { haystack.contains($0) }
    }
    guard !additions.isEmpty else { return (original, []) }
    let entries = additions.map(resourceEntry).joined(separator: "\n")
    if let endRange = original.range(of: resourcesEnd) {
        var updated = original
        let prefix = updated[..<endRange.lowerBound]
        let separator = prefix.hasSuffix("\n") ? "" : "\n"
        updated.insert(contentsOf: separator + entries + "\n", at: endRange.lowerBound)
        return (updated, additions)
    }
    let separator = original.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "" : "\n\n"
    return (original + separator + resourcesStart + "\n" + entries + "\n" + resourcesEnd, additions)
}

func resourceRecord(_ resource: LinkedResource) -> [String: Any] {
    [
        "label": resource.label,
        "kind": resource.kind,
        "url": resource.primaryURL.absoluteString,
        "path": resource.path ?? "",
        "file_url": resource.fileURL?.absoluteString ?? ""
    ]
}

func sourceMarker(event: EKEvent) -> String {
    let utc = ISO8601DateFormatter()
    utc.timeZone = TimeZone(secondsFromGMT: 0)
    return [
        "[Événement source]",
        "Identifiant : \(event.eventIdentifier ?? "")",
        "Début UTC : \(utc.string(from: event.startDate))",
        "Calendrier : \(event.calendar.title)",
        "[/Événement source]"
    ].joined(separator: "\n")
}

func findCompanion(store: EKEventStore, sourceEvent: EKEvent, targetCalendar: EKCalendar) -> EKEvent? {
    let utc = ISO8601DateFormatter()
    utc.timeZone = TimeZone(secondsFromGMT: 0)
    let idLine = "Identifiant : \(sourceEvent.eventIdentifier ?? "")"
    let startLine = "Début UTC : \(utc.string(from: sourceEvent.startDate))"
    let start = sourceEvent.startDate.addingTimeInterval(-1)
    let end = max(sourceEvent.endDate, sourceEvent.startDate.addingTimeInterval(1)).addingTimeInterval(1)
    return store.events(matching: store.predicateForEvents(withStart: start, end: end, calendars: [targetCalendar])).first {
        let notes = $0.notes ?? ""
        return notes.contains(idLine) && notes.contains(startLine)
    }
}

func runEnsureCalendar(store: EKEventStore, request: EnsureCalendarRequest) throws {
    guard let source = store.sources.first(where: { $0.sourceIdentifier == request.sourceID }) else {
        throw CalendarError("Calendar source not found. Run sources again.")
    }
    if let existing = store.calendars(for: .event).first(where: {
        $0.source.sourceIdentifier == source.sourceIdentifier && $0.title == request.title
    }) {
        var result = metadata()
        result["preview"] = !request.confirm
        result["changed"] = false
        result["action"] = "already_exists"
        result["calendar"] = calendarRecord(existing)
        try output(result)
        return
    }
    var result = metadata()
    result["preview"] = !request.confirm
    result["changed"] = request.confirm
    result["action"] = request.confirm ? "created" : "would_create"
    result["title"] = request.title
    result["calendar_source"] = sourceRecord(source)
    if request.confirm {
        let calendar = EKCalendar(for: .event, eventStore: store)
        calendar.title = request.title
        calendar.source = source
        try store.saveCalendar(calendar, commit: true)
        result["calendar"] = calendarRecord(calendar)
    }
    try output(result)
}

func runLink(store: EKEventStore, request: LinkRequest) throws {
    let sourceEvent = try resolveEvent(store: store, request: request)
    let direct = sourceEvent.calendar.allowsContentModifications && request.targetCalendarID == nil
    var targetEvent: EKEvent
    var mode: String
    var action: String

    if direct {
        targetEvent = sourceEvent
        mode = "direct"
        action = "update_source_event"
    } else {
        guard let targetID = request.targetCalendarID,
              let targetCalendar = store.calendar(withIdentifier: targetID) else {
            throw CalendarError("The source calendar is read-only. Supply --target-calendar with a writable companion calendar returned by calendars.")
        }
        guard targetCalendar.allowsContentModifications else {
            throw CalendarError("Target companion calendar is not writable.")
        }
        mode = "companion"
        if let existing = findCompanion(store: store, sourceEvent: sourceEvent, targetCalendar: targetCalendar) {
            targetEvent = existing
            action = "update_companion_event"
        } else {
            targetEvent = EKEvent(eventStore: store)
            targetEvent.calendar = targetCalendar
            targetEvent.title = "📎 Ressources · \(sourceEvent.title ?? "Événement")"
            targetEvent.startDate = sourceEvent.startDate
            targetEvent.endDate = sourceEvent.endDate
            targetEvent.isAllDay = sourceEvent.isAllDay
            targetEvent.timeZone = sourceEvent.timeZone
            targetEvent.location = sourceEvent.location
            targetEvent.availability = .free
            targetEvent.notes = sourceMarker(event: sourceEvent)
            action = "create_companion_event"
        }
    }

    let appended = appendResources(notes: targetEvent.notes, existingURL: targetEvent.url, resources: request.resources)
    var changedFields: [String] = []
    if !appended.1.isEmpty {
        targetEvent.notes = appended.0
        changedFields.append("notes")
    }
    if targetEvent.url == nil, let first = request.resources.first {
        targetEvent.url = first.primaryURL
        changedFields.append("url")
    }
    let wouldCreate = action == "create_companion_event"
    let hasChange = wouldCreate || !changedFields.isEmpty
    if !hasChange { action = "already_linked" }
    if request.confirm && hasChange {
        try store.save(targetEvent, span: .thisEvent, commit: true)
    }

    var result = metadata()
    result["preview"] = !request.confirm
    result["confirmed"] = request.confirm
    result["changed"] = request.confirm && hasChange
    result["mode"] = mode
    result["action"] = request.confirm ? action : "would_\(action)"
    result["changed_fields"] = changedFields
    result["source_event"] = eventRecord(sourceEvent, zone: .current, includeNotes: false, includeLinks: true)
    result["target_calendar"] = calendarRecord(targetEvent.calendar)
    result["resources"] = request.resources.map(resourceRecord)
    result["new_resources"] = appended.1.map(resourceRecord)
    if request.confirm {
        result["target_event"] = eventRecord(targetEvent, zone: .current, includeNotes: true, includeLinks: true)
    }
    try output(result)
}

func run() throws {
    let args = Array(CommandLine.arguments.dropFirst())
    let command = args.first ?? "help"
    if ["help", "--help", "-h"].contains(command) {
        print("""
        apple-calendar: read calendars and link events to one or more resources.
          status
          authorize
          sources
          calendars
          events --from DATE --to DATE (--calendar ID ... | --all-calendars)
                 [--timezone Europe/Paris] [--search TEXT] [--include-notes]
                 [--include-links] [--limit 500]
          ensure-link-calendar --title TEXT --source ID [--confirm]
          link-resources --event ID --source-calendar ID --start ISO_TIMESTAMP
                 --expected-title TEXT --resources ABSOLUTE_JSON_PATH
                 [--target-calendar ID] [--confirm]

        Resources JSON is an array of objects with label and url and/or absolute path;
        kind is optional. Files, folders, Obsidian notes, project artifacts, web URLs,
        and zotero:// item links are supported.

        Mutation commands are previews unless --confirm is present. The caller must show
        the preview and obtain the user's explicit approval immediately before using --confirm.
        A read-only source event requires a writable --target-calendar; a companion event
        is then created or updated without altering the subscribed event.
        """)
        return
    }
    let allowed = ["status", "authorize", "sources", "calendars", "events", "ensure-link-calendar", "link-resources"]
    guard allowed.contains(command) else { throw CalendarError("Unknown command '\(command)'. Use --help.") }
    guard command == "events" || command == "ensure-link-calendar" || command == "link-resources" || args.count == 1 else {
        throw CalendarError("Unexpected arguments.")
    }
    let query = command == "events" ? try Query(Array(args.dropFirst())) : nil
    let ensureRequest = command == "ensure-link-calendar" ? try EnsureCalendarRequest(Array(args.dropFirst())) : nil
    let linkRequest = command == "link-resources" ? try LinkRequest(Array(args.dropFirst())) : nil

    if command == "status" { try output(metadata()); return }
    if command == "authorize" {
        let access = accessName()
        if access == "full_access" { try output(metadata()); return }
        guard access == "not_determined" || access == "write_only" else {
            throw CalendarError("Calendar access is \(access). Enable Calendar access in macOS System Settings > Privacy & Security > Calendars.")
        }
        let store = EKEventStore()
        let done = DispatchSemaphore(value: 0)
        store.requestFullAccessToEvents { _, _ in done.signal() }
        guard done.wait(timeout: .now() + 45) == .success else {
            throw CalendarError("Permission request pending or timed out. Respond to the macOS prompt, then run status.")
        }
        guard accessName() == "full_access" else {
            throw CalendarError("Calendar permission was not granted (\(accessName())).")
        }
        try output(metadata())
        return
    }
    guard accessName() == "full_access" else {
        throw CalendarError("Calendar access is \(accessName()). Use authorize for first-time setup; denied access requires macOS System Settings.")
    }

    let store = EKEventStore()
    let calendars = store.calendars(for: .event).sorted {
        ($0.source.title, $0.title, $0.calendarIdentifier) < ($1.source.title, $1.title, $1.calendarIdentifier)
    }
    if command == "sources" {
        var result = metadata()
        let sources = store.sources.sorted { ($0.title, $0.sourceIdentifier) < ($1.title, $1.sourceIdentifier) }
        result["sources"] = sources.map(sourceRecord)
        result["count"] = sources.count
        try output(result)
        return
    }
    if command == "calendars" {
        var result = metadata()
        result["calendars"] = calendars.map(calendarRecord)
        result["count"] = calendars.count
        try output(result)
        return
    }
    if let request = ensureRequest { try runEnsureCalendar(store: store, request: request); return }
    if let request = linkRequest { try runLink(store: store, request: request); return }

    guard let q = query else { throw CalendarError("Missing query.") }
    let selected: [EKCalendar]
    if q.allCalendars { selected = calendars }
    else {
        let missing = q.calendarIDs.filter { id in !calendars.contains { $0.calendarIdentifier == id } }
        guard missing.isEmpty else {
            throw CalendarError("Calendar IDs not found: \(missing.joined(separator: ", ")). Run calendars again.")
        }
        selected = calendars.filter { q.calendarIDs.contains($0.calendarIdentifier) }
    }
    let iso = ISO8601DateFormatter()
    iso.timeZone = q.zone
    var events = selected.isEmpty ? [] : store.events(matching: store.predicateForEvents(withStart: q.start, end: q.end, calendars: selected))
    events = events.filter { event in
        let overlaps = event.startDate < q.end && (event.endDate > q.start || (event.endDate == event.startDate && event.startDate >= q.start))
        let searchable = [event.title ?? "", event.location ?? "", q.notes ? (event.notes ?? "") : ""].joined(separator: "\n")
        return overlaps && (q.search == nil || searchable.localizedCaseInsensitiveContains(q.search!))
    }.sorted {
        ($0.startDate, $0.endDate, $0.title ?? "") < ($1.startDate, $1.endDate, $1.title ?? "")
    }
    var result = metadata()
    result["query"] = [
        "from": iso.string(from: q.start),
        "to_exclusive": iso.string(from: q.end),
        "timezone": q.zone.identifier,
        "calendars": selected.map(calendarRecord)
    ]
    result["matching_count"] = events.count
    result["returned_count"] = min(events.count, q.limit)
    result["truncated"] = events.count > q.limit
    result["events"] = events.prefix(q.limit).map {
        eventRecord($0, zone: q.zone, includeNotes: q.notes, includeLinks: q.links)
    }
    try output(result)
}

do { try run() }
catch {
    try? output(["error": String(describing: error)])
    exit(1)
}
