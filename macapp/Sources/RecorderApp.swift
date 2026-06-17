import SwiftUI
import AppKit

@main
struct RecorderApp: App {
    @StateObject private var state = AppState()
    @StateObject private var audio = AudioPlayer()

    var body: some Scene {
        // Window first so it's the primary scene and opens at launch.
        Window("Recorder", id: "review") {
            ReviewView()
                .environmentObject(state)
                .environmentObject(audio)
                .frame(minWidth: 760, minHeight: 500)
        }
        .windowResizability(.contentMinSize)

        MenuBarExtra("Recorder", systemImage: "waveform") {
            MenuContent().environmentObject(state)
        }
    }
}

struct MenuContent: View {
    @EnvironmentObject var state: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Text(state.status)

        Button("Open Recorder") {
            openWindow(id: "review")
            NSApp.activate(ignoringOtherApps: true)
        }
        .keyboardShortcut("o")

        Button(state.isBusy ? "Working…" : "Ingest Now") {
            state.ingestNow()
        }
        .disabled(state.isBusy)

        Divider()

        Button("Quit Recorder") {
            NSApplication.shared.terminate(nil)
        }
        .keyboardShortcut("q")
    }
}
