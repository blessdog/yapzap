import Foundation
import AppKit

/// App-wide state: the loaded fragments, pipeline status, and the
/// plug-in-and-it-loads trigger (auto-ingest when the recorder mounts).
@MainActor
final class AppState: ObservableObject {
    @Published var fragments: [Fragment] = []
    @Published var recordings: [Recording] = []
    @Published var status: String = ""
    @Published var isBusy = false
    @Published var deviceConnected = false
    @Published var deviceStatus: DeviceStatus?

    init() {
        refresh()
        deviceConnected = Engine.recorderIsMounted
        // Pull anything new if the recorder is already plugged in at launch
        // (the mount notification only fires for a *new* mount).
        if Engine.recorderIsMounted {
            ingestNow(auto: true)
        } else {
            refreshDeviceStatus()
        }
        // queue: .main → these run on the main thread; assumeIsolated lets us
        // touch main-actor state without the compiler's Sendable warning.
        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(forName: NSWorkspace.didMountNotification,
                           object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self, Engine.recorderIsMounted else { return }
                self.deviceConnected = true
                self.ingestNow(auto: true)
            }
        }
        center.addObserver(forName: NSWorkspace.didUnmountNotification,
                           object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.deviceConnected = Engine.recorderIsMounted
                self.refreshDeviceStatus()
            }
        }
    }

    func refresh() {
        fragments = Database.fragments()
        recordings = Database.recordings()
        if !isBusy { updateStatus() }
    }

    private func updateStatus() {
        let live = fragments.filter { $0.state != "deleted" && $0.state != "archived" }
        status = live.isEmpty ? "No fragments yet" : "\(live.count) fragments"
    }

    func ingestNow(auto: Bool = false) {
        guard !isBusy else { return }
        isBusy = true
        status = auto ? "Recorder connected — pulling in recordings…"
                      : "Importing & transcribing…"
        startProgressPolling()
        Task.detached {
            let result = Engine.ingestAndOrganize()
            await MainActor.run {
                self.isBusy = false
                self.refresh()
                self.refreshDeviceStatus()
                if !result.ok {
                    self.status = "Last run had errors"
                }
            }
        }
    }

    /// While the pipeline runs, re-read the DB every couple seconds so new
    /// recordings and transcripts visibly appear as python commits them —
    /// giving real "it's processing / coming through" feedback, not a frozen
    /// wait. python commits per clip, so the stream fills in incrementally.
    private func startProgressPolling() {
        Task { @MainActor in
            while isBusy {
                try? await Task.sleep(nanoseconds: 1_500_000_000)
                guard isBusy else { break }
                fragments = Database.fragments()
                recordings = Database.recordings()
            }
        }
    }

    // MARK: - Device

    func refreshDeviceStatus() {
        Task.detached {
            let st = Engine.deviceStatus()
            await MainActor.run {
                self.deviceStatus = st
                self.deviceConnected = st?.connected ?? Engine.recorderIsMounted
            }
        }
    }

    /// Wipe verified-copied clips off the recorder (python re-verifies hashes
    /// before deleting). Only call after the user confirms.
    func freeUpSpace() {
        guard !isBusy else { return }
        isBusy = true
        status = "Freeing up space on the recorder…"
        Task.detached {
            let result = Engine.clearDevice()
            await MainActor.run {
                self.isBusy = false
                self.status = result.ok ? "Recorder cleared" : "Couldn't free space"
                self.refreshDeviceStatus()
            }
        }
    }

    // MARK: - Fragment user layer (optimistic: update memory, persist in bg)

    private func mutate(_ id: Fragment.ID, _ change: (inout Fragment) -> Void) {
        guard let i = fragments.firstIndex(where: { $0.id == id }) else { return }
        change(&fragments[i])
        updateStatus()
    }

    func setState(_ id: Fragment.ID, _ state: String) {
        mutate(id) { $0.state = state }
        Task.detached { Database.setState(id, state) }
    }

    func toggleDone(_ id: Fragment.ID) {
        guard let f = fragments.first(where: { $0.id == id }) else { return }
        setState(id, f.state == "done" ? "active" : "done")
    }

    func archive(_ id: Fragment.ID) { setState(id, "archived") }
    func unarchive(_ id: Fragment.ID) { setState(id, "active") }
    func delete(_ id: Fragment.ID) { setState(id, "deleted") }

    func editText(_ id: Fragment.ID, to value: String) {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        let stored: String? = trimmed.isEmpty ? nil : trimmed
        mutate(id) { $0.userText = stored }
        Task.detached { Database.setUserText(id, stored) }
    }
}
