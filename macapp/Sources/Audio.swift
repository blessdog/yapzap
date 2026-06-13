import Foundation

/// Plays a yap's audio. The recorder writes WAVs with broken headers that Core
/// Audio refuses to open, so we repair to a temp file with ffmpeg first (same
/// fix the transcription path uses), then play with `afplay`.
@MainActor
final class AudioPlayer: ObservableObject {
    @Published var playingYapId: Int?
    private var proc: Process?

    func toggle(yap: YapDetail) {
        if playingYapId == yap.id { stop(); return }
        play(yap)
    }

    func play(_ yap: YapDetail) {
        stop()
        let tmp = NSTemporaryDirectory() + "recorder-play-\(yap.id).wav"
        let repair = Process()
        repair.executableURL = URL(fileURLWithPath: Paths.ffmpeg)
        repair.arguments = ["-y", "-loglevel", "error", "-i", yap.audioPath,
                            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", tmp]
        do { try repair.run() } catch { return }
        repair.waitUntilExit()
        guard repair.terminationStatus == 0 else { return }

        let play = Process()
        play.executableURL = URL(fileURLWithPath: "/usr/bin/afplay")
        play.arguments = [tmp]
        play.terminationHandler = { [weak self] _ in
            Task { @MainActor in
                if self?.playingYapId == yap.id { self?.playingYapId = nil }
            }
        }
        do { try play.run() } catch { return }
        proc = play
        playingYapId = yap.id
    }

    func stop() {
        proc?.terminationHandler = nil
        if proc?.isRunning == true { proc?.terminate() }
        proc = nil
        playingYapId = nil
    }
}
