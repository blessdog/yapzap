import SwiftUI

/// Visual identity per fragment type — calm, glanceable, no configuration.
enum FragmentStyle {
    static func icon(_ type: String) -> String {
        switch type {
        case "joke": return "face.smiling"
        case "idea": return "lightbulb"
        case "insight": return "sparkles"
        case "practical": return "checklist"
        default: return "circle"
        }
    }
    static func color(_ type: String) -> Color {
        switch type {
        case "joke": return .orange
        case "idea": return .yellow
        case "insight": return .purple
        case "practical": return .gray
        default: return .secondary
        }
    }
}

/// What slice of time the sidebar is showing. "Archived" is folded in here so
/// the one control answers "show me: this week / month / all / the archive."
enum ScopeKind: String, CaseIterable, Identifiable {
    case week = "Week", month = "Month", all = "All", archived = "Archived"
    var id: String { rawValue }
}

/// One row in the timeline: either an extracted fragment, or a raw recording
/// that produced no fragment (so nothing captured is ever invisible).
enum TimelineItem: Identifiable, Hashable {
    case fragment(Fragment)
    case recording(Recording)

    var id: String {
        switch self {
        case .fragment(let f): return "f\(f.id)"
        case .recording(let r): return "r\(r.id)"
        }
    }
    var capturedDate: Date? {
        switch self {
        case .fragment(let f): return f.capturedDate
        case .recording(let r): return r.capturedDate
        }
    }
    var capturedAt: String {
        switch self {
        case .fragment(let f): return f.capturedAt
        case .recording(let r): return r.capturedAt
        }
    }
}

struct ReviewView: View {
    @EnvironmentObject var state: AppState
    @State private var search = ""
    @State private var typeFilter = "all"
    @State private var scope: ScopeKind = .all
    @State private var dayFilter: Date?          // set by the calendar popover
    @State private var selection: String?
    @State private var showCalendar = false
    @State private var calendarDate = Date()
    @State private var showFreeConfirm = false

    // MARK: filtering

    /// When the archive is selected (and we're not pinned to a specific day),
    /// show archived; otherwise show the live timeline (active + done).
    private var showingArchived: Bool { scope == .archived && dayFilter == nil }

    private var visibleByState: [Fragment] {
        state.fragments.filter { f in
            showingArchived ? f.state == "archived"
                            : (f.state == "active" || f.state == "done")
        }
    }

    private func passesTime(_ date: Date?, _ cal: Calendar) -> Bool {
        // Undated items (shouldn't happen with real data) only surface in the
        // unfiltered "All" view, never under a week/month/day window.
        guard let d = date else { return scope == .all && dayFilter == nil }
        if let day = dayFilter { return cal.isDate(d, inSameDayAs: day) }
        switch scope {
        case .week:
            let start = cal.dateInterval(of: .weekOfYear, for: Date())?.start
            return start.map { d >= $0 } ?? true
        case .month:
            let start = cal.dateInterval(of: .month, for: Date())?.start
            return start.map { d >= $0 } ?? true
        case .all, .archived:
            return true
        }
    }

    private var filteredFragments: [Fragment] {
        let cal = Calendar.current
        return visibleByState.filter { f in
            passesTime(f.capturedDate, cal)
                && (typeFilter == "all" || f.type == typeFilter)
                && matches(f)
        }
    }

    /// Recordings that yielded no (non-deleted) fragment. Shown only in the
    /// live timeline under the "All" type — they have no type of their own.
    private var unminedRecordings: [Recording] {
        guard !showingArchived, typeFilter == "all" else { return [] }
        let mined = Set(state.fragments
            .filter { $0.state != "deleted" }.map { $0.yapId })
        let cal = Calendar.current
        return state.recordings.filter { r in
            !mined.contains(r.id)
                && passesTime(r.capturedDate, cal)
                && (search.isEmpty || r.transcript.localizedCaseInsensitiveContains(search))
        }
    }

    private func matches(_ f: Fragment) -> Bool {
        guard !search.isEmpty else { return true }
        return f.displayText.localizedCaseInsensitiveContains(search)
            || f.quote.localizedCaseInsensitiveContains(search)
            || f.tags.contains { $0.localizedCaseInsensitiveContains(search) }
    }

    private var timeline: [TimelineItem] {
        let items = filteredFragments.map { TimelineItem.fragment($0) }
                  + unminedRecordings.map { TimelineItem.recording($0) }
        return items.sorted { ($0.capturedAt) > ($1.capturedAt) }
    }

    /// Timeline items bucketed by capture day, newest day first.
    private var groups: [(day: Date, items: [TimelineItem])] {
        let cal = Calendar.current
        let dict = Dictionary(grouping: timeline) { item -> Date in
            item.capturedDate.map { cal.startOfDay(for: $0) } ?? .distantPast
        }
        return dict.map { (day: $0.key, items: $0.value) }.sorted { $0.day > $1.day }
    }

    private func dayLabel(_ d: Date) -> String {
        if d == .distantPast { return "Undated" }
        let cal = Calendar.current
        if cal.isDateInToday(d) { return "Today" }
        if cal.isDateInYesterday(d) { return "Yesterday" }
        let f = DateFormatter()
        f.dateFormat = cal.isDate(d, equalTo: Date(), toGranularity: .year)
            ? "EEEE, MMM d" : "EEEE, MMM d, yyyy"
        return f.string(from: d)
    }

    /// Resolve the selection against ALL items (not just the filtered set) so
    /// the detail pane keeps showing an item right after you act on it.
    private var selectedItem: TimelineItem? {
        guard let sel = selection else { return nil }
        if sel.hasPrefix("f"), let id = Int(sel.dropFirst()),
           let f = state.fragments.first(where: { $0.id == id }) {
            return .fragment(f)
        }
        if sel.hasPrefix("r"), let id = Int(sel.dropFirst()),
           let r = state.recordings.first(where: { $0.id == id }) {
            return .recording(r)
        }
        return nil
    }

    // MARK: body

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            switch selectedItem {
            case .fragment(let f): FragmentDetail(fragment: f)
            case .recording(let r): RecordingDetail(recording: r)
            case nil:
                ContentUnavailableView("Pick a fragment", systemImage: "sparkles")
            }
        }
    }

    private var sidebar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Picker("", selection: $scope) {
                    ForEach(ScopeKind.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented).labelsHidden()
                // Scope and a pinned day are alternative lenses — choosing a
                // scope drops the day pin so the buttons never feel "dead".
                .onChange(of: scope) { _, _ in dayFilter = nil }

                Button { showCalendar = true } label: {
                    Image(systemName: "calendar")
                }
                .help("Jump to a day")
                .popover(isPresented: $showCalendar, arrowEdge: .bottom) { calendarPopover }
            }
            .padding(.horizontal, 8).padding(.top, 8)

            Picker("", selection: $typeFilter) {
                Text("All").tag("all")
                Text("Jokes").tag("joke")
                Text("Ideas").tag("idea")
                Text("Insights").tag("insight")
                Text("Practical").tag("practical")
            }
            .pickerStyle(.segmented).labelsHidden()
            .padding(8)

            if let day = dayFilter { dayChip(day) }

            listOrEmpty
        }
        .frame(minWidth: 340)
        .searchable(text: $search, placement: .sidebar, prompt: "Search your mind")
        .navigationTitle("YapZapp")
        .toolbar {
            ToolbarItem {
                Button { state.ingestNow() } label: {
                    Image(systemName: state.isBusy
                          ? "arrow.triangle.2.circlepath" : "arrow.clockwise")
                }
                .disabled(state.isBusy)
                .help("Ingest + organize now")
            }
        }
        .safeAreaInset(edge: .bottom) { devicePill }
        .alert("Free up space on the recorder?", isPresented: $showFreeConfirm) {
            Button("Free up \(state.deviceStatus?.freeableMB ?? 0) MB",
                   role: .destructive) { state.freeUpSpace() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Deletes \(state.deviceStatus?.clearable ?? 0) clip(s) from the "
               + "recorder. Every one is already copied and verified in your "
               + "library — your captures stay safe.")
        }
    }

    @ViewBuilder
    private var listOrEmpty: some View {
        if timeline.isEmpty {
            ContentUnavailableView(emptyTitle, systemImage: emptyIcon,
                                   description: Text(emptyHint))
        } else {
            List(selection: $selection) {
                ForEach(groups, id: \.day) { group in
                    Section(dayLabel(group.day)) {
                        ForEach(group.items) { item in
                            switch item {
                            case .fragment(let f): fragmentRow(f)
                            case .recording(let r):
                                RecordingRow(recording: r).tag(item.id)
                            }
                        }
                    }
                }
            }
            .listStyle(.inset)
        }
    }

    @ViewBuilder
    private func fragmentRow(_ f: Fragment) -> some View {
        FragmentRow(fragment: f).tag("f\(f.id)")
            .contextMenu { rowActions(f) }
            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                Button(role: .destructive) { state.delete(f.id) } label: {
                    Label("Delete", systemImage: "trash")
                }
                if f.state == "archived" {
                    Button { state.unarchive(f.id) } label: {
                        Label("Unarchive", systemImage: "tray.and.arrow.up")
                    }
                } else {
                    Button { state.archive(f.id) } label: {
                        Label("Archive", systemImage: "archivebox")
                    }.tint(.indigo)
                }
            }
            .swipeActions(edge: .leading) {
                Button { state.toggleDone(f.id) } label: {
                    Label(f.state == "done" ? "Undo" : "Done",
                          systemImage: f.state == "done"
                            ? "arrow.uturn.left" : "checkmark")
                }.tint(.green)
            }
    }

    @ViewBuilder
    private func rowActions(_ f: Fragment) -> some View {
        Button { state.toggleDone(f.id) } label: {
            Label(f.state == "done" ? "Mark not done" : "Mark done",
                  systemImage: "checkmark.circle")
        }
        if f.state == "archived" {
            Button { state.unarchive(f.id) } label: { Label("Unarchive", systemImage: "tray.and.arrow.up") }
        } else {
            Button { state.archive(f.id) } label: { Label("Archive", systemImage: "archivebox") }
        }
        Divider()
        Button(role: .destructive) { state.delete(f.id) } label: {
            Label("Delete", systemImage: "trash")
        }
    }

    private func dayChip(_ day: Date) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "calendar")
            Text(dayLabel(day))
            Spacer()
            Button { dayFilter = nil } label: {
                Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary)
            }.buttonStyle(.plain)
        }
        .font(.caption)
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(.quaternary, in: Capsule())
        .padding(.horizontal, 8).padding(.bottom, 6)
    }

    private var calendarPopover: some View {
        VStack(spacing: 10) {
            DatePicker("", selection: $calendarDate, displayedComponents: .date)
                .datePickerStyle(.graphical).labelsHidden()
                .onChange(of: calendarDate) { _, newValue in
                    dayFilter = newValue
                    showCalendar = false
                }
            if dayFilter != nil {
                Button("Clear day filter") { dayFilter = nil; showCalendar = false }
            }
        }
        .padding()
        .frame(width: 320)
    }

    private var devicePill: some View {
        let connected = state.deviceConnected
        let st = state.deviceStatus
        let freeable = connected && (st?.hasFreeable ?? false)
        return HStack(spacing: 8) {
            Image(systemName: connected ? "externaldrive.fill.badge.checkmark"
                                        : "externaldrive")
                .foregroundStyle(connected ? .green : .secondary)
            VStack(alignment: .leading, spacing: 1) {
                Text(connected ? "Recorder connected" : "Recorder not connected")
                    .font(.caption).fontWeight(.medium)
                if freeable {
                    Text("\(st?.clearable ?? 0) clip(s) ready to clear")
                        .font(.caption2).foregroundStyle(.secondary)
                }
            }
            Spacer()
            if freeable {
                Button("Free up space") { showFreeConfirm = true }
                    .controlSize(.small)
                    .disabled(state.isBusy)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(.bar)
    }

    // MARK: empty-state copy

    private var libraryEmpty: Bool {
        state.fragments.isEmpty && state.recordings.isEmpty
    }
    private var emptyTitle: String {
        if showingArchived { return "Nothing archived" }
        if libraryEmpty { return "Nothing captured yet" }
        if !search.isEmpty { return "No matches" }
        return "Nothing here"
    }
    private var emptyIcon: String { showingArchived ? "archivebox" : "waveform" }
    private var emptyHint: String {
        if showingArchived { return "Fragments you archive will land here." }
        if libraryEmpty { return "Plug in the recorder, or hit refresh." }
        if !search.isEmpty { return "Try a different filter or search." }
        if dayFilter != nil { return "Nothing captured on this day." }
        // A specific type with no matches in range often just needs "All".
        if typeFilter != "all" { return "No \(typeFilter)s here — try All, or a wider range." }
        switch scope {
        case .week: return "Nothing captured this week — try Month or All."
        case .month: return "Nothing captured this month — try All."
        default: return "Try a different filter or search."
        }
    }
}

struct FragmentRow: View {
    let fragment: Fragment
    private var done: Bool { fragment.state == "done" }
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: done ? "checkmark.circle.fill"
                                   : FragmentStyle.icon(fragment.type))
                .foregroundStyle(done ? Color.green : FragmentStyle.color(fragment.type))
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 2) {
                Text(fragment.displayText)
                    .lineLimit(2)
                    .strikethrough(done, color: .secondary)
                    .foregroundStyle(done ? .secondary : .primary)
                Text(fragment.capturedAt.prettyTimestamp)
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

struct FragmentDetail: View {
    let fragment: Fragment
    @EnvironmentObject var state: AppState
    @EnvironmentObject var audio: AudioPlayer
    @State private var yap: YapDetail?
    @State private var editing = false
    @State private var draft = ""

    private var done: Bool { fragment.state == "done" }
    private var archived: Bool { fragment.state == "archived" }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Label(fragment.type.capitalized,
                          systemImage: FragmentStyle.icon(fragment.type))
                        .font(.headline)
                        .foregroundStyle(FragmentStyle.color(fragment.type))
                    if done {
                        Label("Done", systemImage: "checkmark.circle.fill")
                            .font(.caption).foregroundStyle(.green)
                    }
                    if archived {
                        Label("Archived", systemImage: "archivebox")
                            .font(.caption).foregroundStyle(.indigo)
                    }
                    Spacer()
                    Text(fragment.capturedAt.prettyTimestamp)
                        .font(.subheadline).foregroundStyle(.secondary)
                }

                // Editable text (the user layer). The verbatim quote + raw
                // transcript below are never touched by this.
                if editing {
                    TextEditor(text: $draft)
                        .font(.title3)
                        .frame(minHeight: 120)
                        .overlay(RoundedRectangle(cornerRadius: 6)
                            .stroke(.quaternary))
                    HStack {
                        Button("Save") {
                            state.editText(fragment.id, to: draft); editing = false
                        }.keyboardShortcut(.defaultAction)
                        Button("Cancel") { editing = false }
                        Spacer()
                        if fragment.userText != nil {
                            Button("Reset to original", role: .destructive) {
                                state.editText(fragment.id, to: ""); editing = false
                            }
                        }
                    }
                } else {
                    Text(fragment.displayText)
                        .font(.title3)
                        .textSelection(.enabled)
                    HStack(spacing: 12) {
                        Button { draft = fragment.displayText; editing = true } label: {
                            Label("Edit", systemImage: "pencil")
                        }
                        if fragment.userText != nil {
                            Label("edited", systemImage: "pencil.circle")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }

                if !fragment.tags.isEmpty {
                    HStack {
                        ForEach(fragment.tags, id: \.self) { tag in
                            Text(tag).font(.caption)
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(.quaternary, in: Capsule())
                        }
                    }
                }

                // Actions
                HStack(spacing: 12) {
                    Button { state.toggleDone(fragment.id) } label: {
                        Label(done ? "Mark not done" : "Mark done",
                              systemImage: done ? "arrow.uturn.left" : "checkmark.circle")
                    }
                    Button {
                        archived ? state.unarchive(fragment.id) : state.archive(fragment.id)
                    } label: {
                        Label(archived ? "Unarchive" : "Archive",
                              systemImage: archived ? "tray.and.arrow.up" : "archivebox")
                    }
                    Spacer()
                    Button(role: .destructive) { state.delete(fragment.id) } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
                .buttonStyle(.bordered)

                Divider()

                VStack(alignment: .leading, spacing: 6) {
                    Text("Verbatim — your exact words, never edited")
                        .font(.caption).foregroundStyle(.secondary)
                    Text("“\(fragment.quote)”")
                        .italic()
                        .textSelection(.enabled)
                }

                if let yap {
                    Divider()
                    HStack {
                        Button { audio.toggle(yap: yap) } label: {
                            Label(audio.playingYapId == yap.id ? "Stop" : "Play recording",
                                  systemImage: audio.playingYapId == yap.id
                                    ? "stop.circle" : "play.circle")
                        }
                        Spacer()
                        Text(String(format: "%.0fs", yap.durationSec))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    DisclosureGroup("Full transcript") {
                        Text(yap.transcript)
                            .font(.callout).foregroundStyle(.secondary)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }

                Spacer()
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .onAppear { yap = Database.yap(fragment.yapId) }
        .onChange(of: fragment.id) { _, _ in
            yap = Database.yap(fragment.yapId)
            editing = false
        }
    }
}

/// A raw recording that produced no fragment — shown so nothing is invisible.
struct RecordingRow: View {
    let recording: Recording
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: recording.isNoSpeech ? "mic.slash" : "waveform")
                .foregroundStyle(.secondary)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 2) {
                Text(recording.snippet)
                    .lineLimit(2)
                    .foregroundStyle(.secondary)
                    .italic(recording.isNoSpeech)
                HStack(spacing: 6) {
                    Text(recording.capturedAt.prettyTimestamp)
                    Text("· recording")
                }
                .font(.caption).foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 2)
    }
}

struct RecordingDetail: View {
    let recording: Recording
    @EnvironmentObject var audio: AudioPlayer
    @State private var yap: YapDetail?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Label("Recording", systemImage: "waveform")
                        .font(.headline).foregroundStyle(.secondary)
                    Spacer()
                    Text(recording.capturedAt.prettyTimestamp)
                        .font(.subheadline).foregroundStyle(.secondary)
                }

                Text(recording.isNoSpeech
                     ? "No speech was detected in this clip."
                     : "No idea was extracted from this one yet — here's the raw capture, kept so nothing you said goes missing.")
                    .font(.callout).foregroundStyle(.secondary)

                if let yap {
                    HStack {
                        Button { audio.toggle(yap: yap) } label: {
                            Label(audio.playingYapId == yap.id ? "Stop" : "Play recording",
                                  systemImage: audio.playingYapId == yap.id
                                    ? "stop.circle" : "play.circle")
                        }
                        Spacer()
                        Text(String(format: "%.0fs", yap.durationSec))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }

                if !recording.isNoSpeech {
                    Divider()
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Transcript — your exact words")
                            .font(.caption).foregroundStyle(.secondary)
                        Text(recording.transcript)
                            .font(.title3)
                            .textSelection(.enabled)
                    }
                }

                Spacer()
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .onAppear { yap = Database.yap(recording.id) }
        .onChange(of: recording.id) { _, _ in yap = Database.yap(recording.id) }
    }
}
