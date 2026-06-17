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
    let text: String           // the LLM's cleaned text (never edited here)
    let tags: [String]
    let capturedAt: String
    var state: String          // active | done | archived | deleted
    var userText: String?      // user's edit; overrides `text` for display

    /// What the UI shows: the user's edit if present, else the LLM text.
    var displayText: String { (userText?.isEmpty == false ? userText! : text) }

    /// Capture instant, parsed from the stored ISO string (local time).
    var capturedDate: Date? { capturedAt.parsedTimestamp }
}

/// Snapshot of what's freeable on the recorder (decoded from `device-status
/// --json`). snake_case keys are mapped via the decoder in Engine.
struct DeviceStatus: Decodable, Equatable {
    var connected: Bool
    var total: Int
    var clearable: Int
    var blocked: Int
    var junk: Int
    var freeableBytes: Int

    var freeableMB: Int { freeableBytes / (1024 * 1024) }
    /// Something is actually deletable (real clips or junk).
    var hasFreeable: Bool { clearable > 0 || junk > 0 }
}

struct YapDetail: Identifiable, Hashable {
    let id: Int
    let capturedAt: String
    let transcript: String
    let audioPath: String
    let durationSec: Double
}

extension String {
    /// Parse a stored capture timestamp ("2026-05-13T12:40:30", local wall
    /// time) into a Date. The recorder writes naive local timestamps; we treat
    /// them as local so day-bucketing lines up with the user's calendar.
    var parsedTimestamp: Date? {
        let fmt = DateFormatter()
        fmt.calendar = Calendar(identifier: .gregorian)
        fmt.locale = Locale(identifier: "en_US_POSIX")
        fmt.timeZone = .current
        fmt.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return fmt.date(from: String(self.prefix(19)))
    }

    /// "2026-05-13T12:40:30" -> "May 13, 2026 · 12:40 PM" (best-effort).
    var prettyTimestamp: String {
        guard let date = parsedTimestamp else { return self }
        let out = DateFormatter()
        out.dateFormat = "MMM d, yyyy · h:mm a"
        out.timeZone = .current
        return out.string(from: date)
    }
}
