import Foundation
import AppKit

/// App-wide state: the loaded fragments, pipeline status, and the
/// plug-in-and-it-loads trigger (auto-ingest when the recorder mounts).
@MainActor
final class AppState: ObservableObject {
    @Published var fragments: [Fragment] = []
    @Published var status: String = ""
    @Published var isBusy = false

    init() {
        refresh()
        // Pull anything new if the recorder is already plugged in at launch
        // (the mount notification only fires for a *new* mount).
        if Engine.recorderIsMounted {
            ingestNow(auto: true)
        }
        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didMountNotification, object: nil, queue: .main
        ) { [weak self] _ in
            guard let self, Engine.recorderIsMounted else { return }
            self.ingestNow(auto: true)
        }
    }

    func refresh() {
        fragments = Database.fragments()
        if !isBusy { updateStatus() }
    }

    private func updateStatus() {
        status = fragments.isEmpty ? "No fragments yet"
                                   : "\(fragments.count) fragments"
    }

    func ingestNow(auto: Bool = false) {
        guard !isBusy else { return }
        isBusy = true
        status = auto ? "Recorder detected — importing…" : "Importing & organizing…"
        Task.detached {
            let result = Engine.ingestAndOrganize()
            await MainActor.run {
                self.isBusy = false
                self.refresh()
                if !result.ok {
                    self.status = "Last run had errors"
                }
            }
        }
    }
}
