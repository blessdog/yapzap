import Foundation

/// Where the Python pipeline + its data live. Hardcoded for the v1 personal
/// build; the Mac app reuses the proven engine rather than reimplementing it.
enum Paths {
    static let projectRoot = "/Users/SSDrive/projects/recorder"
    static var python: String { projectRoot + "/.venv/bin/python" }
    static var dbPath: String { projectRoot + "/library/recorder.db" }
    static let ffmpeg = "/opt/homebrew/bin/ffmpeg"
    static let recorderMount = "/Volumes/Recorder/record"
}

struct Fragment: Identifiable, Hashable {
    let id: Int
    let yapId: Int
    let type: String   // joke | idea | insight | practical
    let quote: String
    let text: String
    let tags: [String]
    let capturedAt: String
}

struct YapDetail: Identifiable, Hashable {
    let id: Int
    let capturedAt: String
    let transcript: String
    let audioPath: String
    let durationSec: Double
}

extension String {
    /// "2026-05-13T12:40:30" -> "May 13, 2026 · 12:40 PM" (best-effort).
    var prettyTimestamp: String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime]
        var iso = self
        if !iso.contains("Z") && !iso.contains("+") { iso += "Z" }
        guard let date = parser.date(from: iso) else { return self }
        let out = DateFormatter()
        out.dateFormat = "MMM d, yyyy · h:mm a"
        out.timeZone = .current
        return out.string(from: date)
    }
}
