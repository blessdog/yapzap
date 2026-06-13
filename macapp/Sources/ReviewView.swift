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

struct ReviewView: View {
    @EnvironmentObject var state: AppState
    @State private var search = ""
    @State private var typeFilter: String = "all"
    @State private var selection: Fragment.ID?

    private var filtered: [Fragment] {
        state.fragments.filter { f in
            (typeFilter == "all" || f.type == typeFilter) && matches(f)
        }
    }

    private func matches(_ f: Fragment) -> Bool {
        guard !search.isEmpty else { return true }
        return f.text.localizedCaseInsensitiveContains(search)
            || f.quote.localizedCaseInsensitiveContains(search)
            || f.tags.contains { $0.localizedCaseInsensitiveContains(search) }
    }

    private var selected: Fragment? { state.fragments.first { $0.id == selection } }

    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                Picker("", selection: $typeFilter) {
                    Text("All").tag("all")
                    Text("Jokes").tag("joke")
                    Text("Ideas").tag("idea")
                    Text("Insights").tag("insight")
                    Text("Practical").tag("practical")
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .padding(8)

                if filtered.isEmpty {
                    ContentUnavailableView(
                        state.fragments.isEmpty ? "Nothing captured yet" : "No matches",
                        systemImage: "waveform",
                        description: Text(state.fragments.isEmpty
                            ? "Plug in the recorder, or hit refresh."
                            : "Try a different filter or search.")
                    )
                } else {
                    List(filtered, selection: $selection) { f in
                        FragmentRow(fragment: f).tag(f.id)
                    }
                    .listStyle(.inset)
                }
            }
            .frame(minWidth: 320)
            .searchable(text: $search, placement: .sidebar, prompt: "Search your mind")
            .navigationTitle("Recorder")
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
        } detail: {
            if let f = selected {
                FragmentDetail(fragment: f)
            } else {
                ContentUnavailableView("Pick a fragment", systemImage: "sparkles")
            }
        }
        .overlay(alignment: .bottom) {
            if state.isBusy {
                Label(state.status, systemImage: "hourglass")
                    .padding(8).background(.thinMaterial, in: Capsule()).padding(8)
            }
        }
    }
}

struct FragmentRow: View {
    let fragment: Fragment
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: FragmentStyle.icon(fragment.type))
                .foregroundStyle(FragmentStyle.color(fragment.type))
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 2) {
                Text(fragment.text).lineLimit(2)
                Text(fragment.capturedAt.prettyTimestamp)
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

struct FragmentDetail: View {
    let fragment: Fragment
    @EnvironmentObject var audio: AudioPlayer
    @State private var yap: YapDetail?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Label(fragment.type.capitalized,
                          systemImage: FragmentStyle.icon(fragment.type))
                        .font(.headline)
                        .foregroundStyle(FragmentStyle.color(fragment.type))
                    Spacer()
                    Text(fragment.capturedAt.prettyTimestamp)
                        .font(.subheadline).foregroundStyle(.secondary)
                }

                Text(fragment.text)
                    .font(.title3)
                    .textSelection(.enabled)

                if !fragment.tags.isEmpty {
                    HStack {
                        ForEach(fragment.tags, id: \.self) { tag in
                            Text(tag).font(.caption)
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(.quaternary, in: Capsule())
                        }
                    }
                }

                Divider()

                VStack(alignment: .leading, spacing: 6) {
                    Text("Verbatim").font(.caption).foregroundStyle(.secondary)
                    Text("“\(fragment.quote)”")
                        .italic()
                        .textSelection(.enabled)
                }

                if let yap {
                    Divider()
                    HStack {
                        Button {
                            audio.toggle(yap: yap)
                        } label: {
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
        .onChange(of: fragment.id) { _, _ in yap = Database.yap(fragment.yapId) }
    }
}
