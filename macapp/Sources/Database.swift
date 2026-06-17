import Foundation
import SQLite3

/// Access to the SQLite source-of-truth the Python pipeline writes.
/// Reads are read-only. The ONLY thing the app writes is the user layer
/// (fragments.state / fragments.user_text) — capture/transcribe/organize all
/// still go through python, which owns every other column.
enum Database {
    private static let TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    private static func open() -> OpaquePointer? {
        var db: OpaquePointer?
        let flags = SQLITE_OPEN_READONLY
        if sqlite3_open_v2(Paths.dbPath, &db, flags, nil) == SQLITE_OK {
            return db
        }
        sqlite3_close(db)
        return nil
    }

    /// Open read-write for the small user-layer mutations. busy_timeout lets us
    /// wait out a concurrent python ingest instead of failing "database locked".
    private static func openWrite() -> OpaquePointer? {
        var db: OpaquePointer?
        let flags = SQLITE_OPEN_READWRITE
        if sqlite3_open_v2(Paths.dbPath, &db, flags, nil) == SQLITE_OK {
            sqlite3_busy_timeout(db, 3000)
            return db
        }
        sqlite3_close(db)
        return nil
    }

    private static func text(_ stmt: OpaquePointer?, _ col: Int32) -> String {
        guard let c = sqlite3_column_text(stmt, col) else { return "" }
        return String(cString: c)
    }

    static func fragments() -> [Fragment] {
        guard let db = open() else { return [] }
        defer { sqlite3_close(db) }
        let sql = """
            SELECT f.id, f.yap_id, f.type, f.quote, f.text, f.tags,
                   y.captured_at, f.state, f.user_text
              FROM fragments f JOIN yaps y ON y.id = f.yap_id
             ORDER BY y.captured_at DESC, f.id
            """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return [] }
        defer { sqlite3_finalize(stmt) }
        var out: [Fragment] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let tagsJSON = text(stmt, 5)
            let tags = (try? JSONDecoder().decode([String].self,
                                                  from: Data(tagsJSON.utf8))) ?? []
            let userText = sqlite3_column_type(stmt, 8) == SQLITE_NULL
                ? nil : text(stmt, 8)
            out.append(Fragment(
                id: Int(sqlite3_column_int64(stmt, 0)),
                yapId: Int(sqlite3_column_int64(stmt, 1)),
                type: text(stmt, 2),
                quote: text(stmt, 3),
                text: text(stmt, 4),
                tags: tags,
                capturedAt: text(stmt, 6),
                state: text(stmt, 7),
                userText: userText
            ))
        }
        return out
    }

    /// Set a fragment's state (active|done|archived|deleted). User layer only.
    @discardableResult
    static func setState(_ id: Int, _ state: String) -> Bool {
        guard let db = openWrite() else { return false }
        defer { sqlite3_close(db) }
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "UPDATE fragments SET state = ? WHERE id = ?",
                                 -1, &stmt, nil) == SQLITE_OK else { return false }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_text(stmt, 1, state, -1, TRANSIENT)
        sqlite3_bind_int64(stmt, 2, sqlite3_int64(id))
        return sqlite3_step(stmt) == SQLITE_DONE
    }

    /// Set (or clear, with nil) the user-edited text. Never touches `text`,
    /// `quote`, or the raw transcript.
    @discardableResult
    static func setUserText(_ id: Int, _ value: String?) -> Bool {
        guard let db = openWrite() else { return false }
        defer { sqlite3_close(db) }
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "UPDATE fragments SET user_text = ? WHERE id = ?",
                                 -1, &stmt, nil) == SQLITE_OK else { return false }
        defer { sqlite3_finalize(stmt) }
        if let value, !value.isEmpty {
            sqlite3_bind_text(stmt, 1, value, -1, TRANSIENT)
        } else {
            sqlite3_bind_null(stmt, 1)
        }
        sqlite3_bind_int64(stmt, 2, sqlite3_int64(id))
        return sqlite3_step(stmt) == SQLITE_DONE
    }

    static func yap(_ id: Int) -> YapDetail? {
        guard let db = open() else { return nil }
        defer { sqlite3_close(db) }
        let sql = """
            SELECT id, captured_at, transcript, raw_audio_path, duration_sec
              FROM yaps WHERE id = ?
            """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return nil }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_int64(stmt, 1, sqlite3_int64(id))
        guard sqlite3_step(stmt) == SQLITE_ROW else { return nil }
        return YapDetail(
            id: Int(sqlite3_column_int64(stmt, 0)),
            capturedAt: text(stmt, 1),
            transcript: text(stmt, 2),
            audioPath: text(stmt, 3),
            durationSec: sqlite3_column_double(stmt, 4)
        )
    }
}
