import Foundation

/// Drives the Python pipeline (`python -m recorder ...`) via a subprocess.
/// v1 reuses the proven engine instead of reimplementing it in Swift.
enum Engine {
    struct Result { let ok: Bool; let output: String }

    @discardableResult
    static func run(_ args: [String]) -> Result {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: Paths.python)
        proc.arguments = ["-m", "recorder"] + args
        proc.currentDirectoryURL = URL(fileURLWithPath: Paths.projectRoot)

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe
        do {
            try proc.run()
        } catch {
            return Result(ok: false, output: "failed to launch python: \(error)")
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        return Result(ok: proc.terminationStatus == 0,
                      output: String(data: data, encoding: .utf8) ?? "")
    }

    /// The full loop: pull new clips off the recorder, then extract fragments.
    static func ingestAndOrganize() -> Result {
        let ingest = run(["ingest"])
        let organize = run(["organize"])
        return Result(ok: ingest.ok && organize.ok,
                      output: ingest.output + "\n" + organize.output)
    }

    static var recorderIsMounted: Bool {
        FileManager.default.fileExists(atPath: Paths.recorderMount)
    }

    /// What's freeable on the recorder right now (nil if python failed).
    static func deviceStatus() -> DeviceStatus? {
        let r = run(["device-status", "--json"])
        guard r.ok, let line = r.output
            .split(separator: "\n").last(where: { $0.contains("{") }),
              let data = String(line).data(using: .utf8) else { return nil }
        let dec = JSONDecoder()
        dec.keyDecodingStrategy = .convertFromSnakeCase
        return try? dec.decode(DeviceStatus.self, from: data)
    }

    /// Delete verified-copied clips off the device. Python re-verifies each
    /// clip's hash immediately before deleting — see recorder/device.py.
    static func clearDevice() -> Result {
        run(["clear-device"])
    }
}
