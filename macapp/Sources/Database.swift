import Foundation
import SQLite3

/// Read-only access to the SQLite source-of-truth the Python pipeline writes.
/// The app never mutates it — capture/transcribe/organize all go through python.
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

    private static func text(_ stmt: OpaquePointer?, _ col: Int32) -> String {
        guard let c = sqlite3_column_text(stmt, col) else { return "" }
        return String(cString: c)
    }

    static func fragments() -> [Fragment] {
        guard let db = open() else { return [] }
        defer { sqlite3_close(db) }
        let sql = """
            SELECT f.id, f.yap_id, f.type, f.quote, f.text, f.tags,
                   y.captured_at
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
            out.append(Fragment(
                id: Int(sqlite3_column_int64(stmt, 0)),
                yapId: Int(sqlite3_column_int64(stmt, 1)),
                type: text(stmt, 2),
                quote: text(stmt, 3),
                text: text(stmt, 4),
                tags: tags,
                capturedAt: text(stmt, 6)
            ))
        }
        return out
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
