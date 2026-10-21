import Cocoa
import ScreenCaptureKit
import Vision
import CoreMedia
import CoreImage
import ImageIO
import UniformTypeIdentifiers

// MIT licensed. Local ScreenCaptureKit/Vision reader; see Send.swift for explicit sends.
func emit(_ event: [String: Any]) {
    var value = event
    value["at"] = ISO8601DateFormatter().string(from: Date())
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
       let string = String(data: data, encoding: .utf8) { print(string); fflush(stdout) }
}
func privatePNG(_ image:CGImage, path:String) throws {
    guard !FileManager.default.fileExists(atPath:path),
          FileManager.default.createFile(atPath:path,contents:nil,attributes:[.posixPermissions:0o600]),
          let destination = CGImageDestinationCreateWithURL(URL(fileURLWithPath:path) as CFURL,
              UTType.png.identifier as CFString,1,nil) else { throw fail("diagnostic_snapshot_failed") }
    CGImageDestinationAddImage(destination,image,nil)
    guard CGImageDestinationFinalize(destination) else { throw fail("diagnostic_snapshot_failed") }
    try FileManager.default.setAttributes([.posixPermissions:0o600],ofItemAtPath:path)
}
func option(_ name: String, _ fallback: String) -> String {
    guard let i = CommandLine.arguments.firstIndex(of: name), i + 1 < CommandLine.arguments.count else { return fallback }
    return CommandLine.arguments[i + 1]
}
struct Line {
    let text: String
    let box: CGRect
    let confidence: Float
    var json: [String: Any] { ["text": text, "x": box.minX, "y": 1-box.maxY,
        "width": box.width, "height": box.height, "confidence": confidence] }
}
func recognize(_ image: CGImage, languages:[String] = ["zh-Hans", "en-US"]) throws -> [Line] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = languages
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image).perform([request])
    return (request.results ?? []).compactMap {
        guard let text = $0.topCandidates(1).first else { return nil }
        return Line(text: text.string, box: $0.boundingBox, confidence: text.confidence)
    }.sorted { $0.box.midY > $1.box.midY }
}
// A small grayscale representation avoids re-running OCR on an unchanged panel.
func pixels(_ image: CGImage) -> [UInt8] {
    var data = [UInt8](repeating: 0, count: 200 * 160)
    data.withUnsafeMutableBytes { p in
        let context = CGContext(data: p.baseAddress, width: 200, height: 160,
            bitsPerComponent: 8, bytesPerRow: 200, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: 0)!
        context.draw(image, in: CGRect(x: 0, y: 0, width: 200, height: 160))
    }
    return data
}
func difference(_ a: [UInt8], _ b: [UInt8]) -> Double {
    guard a.count == b.count, !a.isEmpty else { return .infinity }
    return zip(a,b).reduce(0.0) { $0 + Double(abs(Int($1.0)-Int($1.1))) } / Double(a.count)
}
func isBlank(_ data: [UInt8]) -> Bool {
    guard let lo = data.min(), let hi = data.max() else { return true }
    return Int(hi)-Int(lo) < 8
}
// Only reports an appended OCR sequence if previous visible context overlaps.
// Reflow, OCR corrections, scrolling and lack of overlap produce a reset instead.
func appendStart(old: [String], new: [String]) -> Int? {
    guard !old.isEmpty, !new.isEmpty else { return nil }
    for count in stride(from: min(old.count, new.count), through: 1, by: -1) {
        if Array(old.suffix(count)) == Array(new.prefix(count)) { return count }
    }
    return nil
}

final class CaptureSession: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private let context = CIContext()
    private var image: CGImage?
    private var failure: Error?
    private var sequence = 0
    private var consumed = 0
    private var stream: SCStream?
    private var boundWindow:SCWindow?
    private var boundDisplay:SCDisplay?
    private var boundInterval:Double = 0.25
    private var frameCounts:[String:Int] = [:]
    private(set) var screenshotBackend = false
    private var explicitBackend:String?
    var backendName:String { explicitBackend ?? (screenshotBackend ? "visible_display_crop" : "app_to_window_stream") }
    var key = ""
    private func isCurrent(_ candidate:SCStream) -> Bool {
        lock.lock(); defer { lock.unlock() }; return stream === candidate
    }
    private func install(_ active:SCStream?) -> SCStream? {
        lock.lock(); defer { lock.unlock() }
        let previous = stream
        stream = active; image = nil; failure = nil; sequence += 1; consumed = sequence
        return previous
    }
    private func noteFrame(_ name:String) {
        lock.lock(); frameCounts[name,default:0] += 1; lock.unlock()
    }
    func frameStatistics() -> [String:Any] {
        lock.lock(); defer { lock.unlock() }
        return ["counts":frameCounts,"has_image":image != nil,"sequence":sequence]
    }
    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer, of type: SCStreamOutputType) {
        noteFrame("callback")
        guard isCurrent(stream) else { noteFrame("other_stream"); return }
        guard type == .screen else { noteFrame("non_screen"); return }
        guard sample.isValid else { noteFrame("invalid_sample"); return }
        guard let attachments = CMSampleBufferGetSampleAttachmentsArray(sample,createIfNecessary:false) as? [[String:Any]],
              let raw = attachments.first?[SCStreamFrameInfo.status.rawValue] as? NSNumber,
              let status = SCFrameStatus(rawValue:raw.intValue) else { noteFrame("invalid_metadata"); return }
        noteFrame("status_\(status.rawValue)")
        if status == .idle {
            // ScreenCaptureKit reports an unchanged surface without another image.
            // It can refresh only an existing complete frame from this stream.
            lock.lock(); if self.stream === stream && image != nil { sequence += 1 }; lock.unlock()
            return
        }
        guard status == .complete, let pixel = sample.imageBuffer else {
            lock.lock(); if self.stream === stream { image = nil }; lock.unlock()
            return
        }
        noteFrame("complete_pixels")
        let input = CIImage(cvPixelBuffer: pixel)
        guard let frame = context.createCGImage(input, from: input.extent) else { return }
        lock.lock(); if self.stream === stream { image = frame; sequence += 1 }; lock.unlock()
    }
    func stream(_ stream: SCStream, didStopWithError error: Error) {
        guard isCurrent(stream) else { return }
        lock.lock(); if self.stream === stream { failure = error }; lock.unlock()
    }
    func serial() -> Int { lock.lock(); defer { lock.unlock() }; return sequence }
    func latest() throws -> CGImage? {
        lock.lock(); defer { lock.unlock() }
        if let failure { throw failure }
        return image
    }
    func nextImage() throws -> CGImage? {
        lock.lock(); defer { lock.unlock() }
        if let failure { throw failure }
        guard sequence > consumed, let image else { return nil }
        consumed = sequence
        return image
    }
    private func storeScreenshot(_ frame:CGImage) {
        lock.lock(); image = frame; sequence += 1; lock.unlock()
    }
    func freshScreenshot() async throws -> CGImage? {
        guard let window = boundWindow, let display = boundDisplay,
              let owner = window.owningApplication else { throw fail("capture_not_started") }
        try requireUnobscured(window,owner.processID)
        let config = SCStreamConfiguration()
        config.width = Int(window.frame.width); config.height = Int(window.frame.height)
        config.showsCursor = false
        config.sourceRect = CGRect(x:window.frame.minX-display.frame.minX,
            y:window.frame.minY-display.frame.minY,width:window.frame.width,height:window.frame.height)
        // Match the Windows screen-grab approach: capture the visible desktop crop.
        // Foreground/occlusion checks above are mandatory; this is never background UI input.
        let filter = explicitBackend == "window" ? SCContentFilter(desktopIndependentWindow:window) : SCContentFilter(display:display,excludingWindows:[])
        if explicitBackend == "window" { config.sourceRect = .zero }
        let frame = try await SCScreenshotManager.captureImage(contentFilter:filter,configuration:config)
        guard !isBlank(pixels(frame)) else { return nil }
        storeScreenshot(frame)
        return frame
    }
    func refresh() async throws {
        guard let window = boundWindow, let display = boundDisplay else { throw fail("capture_not_started") }
        await stop()
        try await start(window:window,display:display,interval:boundInterval,backend:explicitBackend)
    }
    func start(window: SCWindow, display: SCDisplay, interval: Double, backend:String? = nil) async throws {
        guard let app = window.owningApplication else { throw NSError(domain:"capture",code:1) }
        boundWindow = window; boundDisplay = display; boundInterval = interval
        explicitBackend = backend
        screenshotBackend = false
        if let backend {
            if backend != "stream" {
                guard try await freshScreenshot() != nil else { throw fail("no_frame_after_filter_refresh") }
                screenshotBackend = true
                emit(["type":"capture_backend","backend":backend]); return
            }
            let config = SCStreamConfiguration()
            config.width = Int(window.frame.width); config.height = Int(window.frame.height)
            config.showsCursor = false
            config.minimumFrameInterval = CMTime(seconds:interval,preferredTimescale:600)
            let active = SCStream(filter:SCContentFilter(desktopIndependentWindow:window),configuration:config,delegate:self)
            _ = install(active)
            try active.addStreamOutput(self,type:.screen,sampleHandlerQueue:DispatchQueue(label:"wechat.diagnostic.frames"))
            try await active.startCapture()
            emit(["type":"capture_backend","backend":"stream"]); return
        }
        if let frame = try? await freshScreenshot() {
            screenshotBackend = true
            emit(["type":"capture_backend","backend":"visible_display_crop"])
            _ = frame
            return
        }
        emit(["type":"capture_backend","backend":"app_to_window_stream"])
        let config = SCStreamConfiguration()
        config.width = Int(window.frame.width); config.height = Int(window.frame.height)
        config.showsCursor = false
        config.minimumFrameInterval = CMTime(seconds: interval, preferredTimescale: 600)
        config.queueDepth = 3
        config.sourceRect = CGRect(x:window.frame.minX-display.frame.minX,
            y:window.frame.minY-display.frame.minY, width:window.frame.width, height:window.frame.height)
        // Reproducible macOS workaround: app-filter stream -> window-filter update.
        // Direct single-window streams and one-shot screenshots omit this WeChat window.
        let initial = SCContentFilter(display:display, including:[app], exceptingWindows:[])
        let active = SCStream(filter:initial, configuration:config, delegate:self)
        _ = install(active)
        try active.addStreamOutput(self, type:.screen, sampleHandlerQueue:DispatchQueue(label:"wechat.frames"))
        try await active.startCapture()
        try await Task.sleep(for:.milliseconds(250))
        try await active.updateContentFilter(SCContentFilter(display:display, including:[window]))
        try await Task.sleep(for:.milliseconds(550))
    }
    func stop() async { if let previous = install(nil) { try? await previous.stopCapture() } }
    @available(macOS 15.2, *)
    func startDiagnostic(filter:SCContentFilter,size:CGSize,recording:SCRecordingOutput) async throws {
        let config = SCStreamConfiguration()
        config.width = Int(size.width); config.height = Int(size.height)
        config.showsCursor = false; config.capturesAudio = false
        config.minimumFrameInterval = CMTime(seconds:0.25,preferredTimescale:600)
        let active = SCStream(filter:filter,configuration:config,delegate:self)
        screenshotBackend = false; _ = install(active)
        try active.addStreamOutput(self,type:.screen,sampleHandlerQueue:DispatchQueue(label:"wechat.picker.frames"))
        try active.addRecordingOutput(recording)
        try await active.startCapture()
    }
}

#if !LIBRARY
@main struct Monitor {
    static func main() async {
        _ = NSApplication.shared
        let command = CommandLine.arguments.dropFirst().first ?? "help"
        if command == "help" || CommandLine.arguments.contains("--help") { printUsage(); return }
        do { try validateArguments(Array(CommandLine.arguments.dropFirst())) }
        catch { emit(["type":"error", "reason":error.localizedDescription]); exit(2) }
        if command == "doctor" { doctor(); return }
        if command == "session-check" {
            do { try checkWeChatSession() } catch {
                emit(["type":"error", "reason":error.localizedDescription]); exit(2)
            }
            return
        }
        if command == "focus" {
            do { try await focusWeChat() } catch {
                emit(["type":"error", "reason":error.localizedDescription]); exit(2)
            }
            return
        }
        if command == "capture-check" {
            do { try await checkWindowCapture() } catch {
                emit(["type":"error","reason":error.localizedDescription]); exit(2)
            }
            return
        }
        if command == "capture-picker" {
            if #available(macOS 15.2, *) {
                do { try await checkPickerCapture() } catch {
                    emit(["type":"error","reason":error.localizedDescription]); exit(2)
                }
            } else { emit(["type":"error","reason":"capture_picker_requires_macos_15_2"]); exit(2) }
            return
        }
        if command == "send" {
            do { try await sendMessage() } catch {
                emit(["type":"error", "reason":error.localizedDescription]); exit(2)
            }
            return
        }
        guard ["read", "watch", "self-test"].contains(command) else { printUsage(); exit(2) }
        if command == "self-test" {
            testSendUtilities()
            precondition(isBlank([0,0,0]) && !isBlank([0,255]))
            precondition(difference([0,100], [0,102]) == 1)
            precondition(appendStart(old:["a","b"],new:["b","c"]) == 1)
            precondition(appendStart(old:["a","b"],new:["a","b","b"]) == 2)
            precondition(appendStart(old:["a"],new:["z"]) == nil)
            emit(["type":"self_test", "passed":true]); return
        }
        let chat = option("--chat", "")
        guard !chat.isEmpty else { emit(["type":"error", "reason":"--chat is required"]); exit(2) }
        guard let seconds = Double(option("--seconds", "30")), seconds.isFinite, seconds >= 1,
              let interval = Double(option("--interval", "0.5")), interval.isFinite, interval >= 0.25, interval <= 10 else {
            emit(["type":"error", "reason":"invalid --seconds or --interval"]); exit(2)
        }
        guard let composerTop = Double(option("--composer-top", "0.70")), composerTop.isFinite,
              composerTop >= 0.45, composerTop <= 0.88 else {
            emit(["type":"error", "reason":"invalid_composer_top"]); exit(2)
        }
        var panelX: Double?
        let once = command == "read"
        let snapshot = option("--snapshot", "")
        guard CGPreflightScreenCaptureAccess() else {
            emit(["type":"blocked", "reason":"screen_recording_permission_missing"]); exit(2)
        }
        var previousPixels: [UInt8] = []
        var previousLines: [String] = []
        var previousWindow: CGWindowID?
        var session: CaptureSession?
        var lastStatus = ""
        var frames = 0, ocrRuns = 0, skipped = 0
        var captureTimes: [Double] = [], ocrTimes: [Double] = []
        let started = Date()
        emit(["type":"started", "chat":chat, "mode":"read_only", "interval_seconds":interval])
        while Date().timeIntervalSince(started) < seconds {
            let tick = Date()
            do {
                guard !screenLocked() else { throw fail("screen_locked") }
                let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
                let candidates = content.windows.filter {
                    $0.owningApplication?.bundleIdentifier == "com.tencent.xinWeChat" &&
                    ["Weixin", "WeChat", "微信"].contains($0.title ?? "") &&
                    $0.frame.width > 600 && $0.frame.height > 450
                }
                guard let window = candidates.max(by: { $0.frame.width < $1.frame.width }) else {
                    throw NSError(domain:"monitor", code:1, userInfo:[NSLocalizedDescriptionKey:"main_window_unavailable"])
                }
                if previousWindow != window.windowID {
                    previousPixels = []; previousLines = []; previousWindow = window.windowID
                }
                guard let display = content.displays.first(where: { $0.frame.contains(window.frame) }) else {
                    throw NSError(domain:"monitor",code:3,userInfo:[NSLocalizedDescriptionKey:"window_must_fit_one_display"])
                }
                let key = "\(window.windowID):\(window.frame):\(display.displayID)"
                let beforeCapture = Date()
                if session?.key != key {
                    await session?.stop()
                    let fresh = CaptureSession(); session = fresh
                    try await fresh.start(window:window, display:display, interval:interval)
                    fresh.key = key; previousPixels = []; previousLines = []; panelX = nil
                    emit(["type":"capture_ready", "backend":fresh.backendName, "window_id":window.windowID])
                }
                var newest = try session?.latest()
                if session?.screenshotBackend == true { newest = try await session?.freshScreenshot() }
                if newest == nil {
                    for _ in 0..<30 {
                        try await Task.sleep(for:.milliseconds(50))
                        newest = try session?.latest()
                        if newest != nil { break }
                    }
                }
                guard let image = newest else {
                    throw NSError(domain:"monitor",code:4,userInfo:[NSLocalizedDescriptionKey:"no_frame_after_filter_refresh"])
                }
                let captureMS = Date().timeIntervalSince(beforeCapture)*1000
                captureTimes.append(captureMS); frames += 1
                if frames == 1 && !snapshot.isEmpty {
                    if let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath:snapshot) as CFURL,
                        UTType.png.identifier as CFString, 1, nil) {
                        CGImageDestinationAddImage(dest, image, nil); CGImageDestinationFinalize(dest)
                    }
                }
                if panelX == nil { panelX = try chatLeft(image, chat:chat) / Double(image.width) }
                let x = panelX!
                let rect = CGRect(x:Double(image.width)*x, y:0,
                    width:Double(image.width)*(1-x), height:Double(image.height)*composerTop).integral
                guard let panel = image.cropping(to:rect) else { throw NSError(domain:"monitor",code:2) }
                let small = pixels(panel)
                if isBlank(small) {
                    if lastStatus != "blank" { emit(["type":"blocked", "reason":"blank_capture", "window_id":window.windowID]) }
                    lastStatus = "blank"; previousPixels = []; previousLines = []
                } else if difference(previousPixels, small) < 0.15 {
                    skipped += 1
                } else {
                    let beforeOCR = Date()
                    let lines = try recognize(panel)
                    let ocrMS = Date().timeIntervalSince(beforeOCR)*1000
                    ocrTimes.append(ocrMS); ocrRuns += 1
                    // Verify the header independently; whole-panel language inference can
                    // confuse short ASCII names with visually similar capital letters.
                    _ = try chatLeft(image,chat:chat)
                    let body = lines.filter { 1-$0.box.maxY >= 0.12 }
                    let texts = body.map(\.text)
                    let kind: String
                    let offset: Int
                    if previousLines.isEmpty { kind = "baseline"; offset = 0 }
                    else if texts == previousLines { kind = "unchanged_text"; offset = texts.count }
                    else if let start = appendStart(old: previousLines, new: texts) { kind = "candidate_added_lines"; offset = start }
                    else { kind = "context_reset"; offset = 0 }
                    if kind != "unchanged_text" {
                        emit(["type":kind, "chat":chat, "sender":"unverified", "safe_to_autoreply":false,
                            "lines":Array(body.dropFirst(offset)).map(\.json), "capture_ms":captureMS, "ocr_ms":ocrMS])
                    }
                    lastStatus = "readable"; previousLines = texts; previousPixels = small
                }
            } catch {
                let reason = error.localizedDescription
                if lastStatus != reason { emit(["type":"blocked", "reason":reason]) }
                lastStatus = reason; previousPixels = []; previousLines = []
                await session?.stop(); session = nil
            }
            if once { break }
            let remaining = interval-Date().timeIntervalSince(tick)
            if remaining > 0 { try? await Task.sleep(nanoseconds: UInt64(remaining*1_000_000_000)) }
        }
        await session?.stop()
        func average(_ values:[Double]) -> Double { values.isEmpty ? 0 : values.reduce(0,+)/Double(values.count) }
        emit(["type":"stopped", "frames":frames, "ocr_runs":ocrRuns, "unchanged_skipped":skipped,
            "frame_fetch_mean_ms":average(captureTimes), "ocr_mean_ms":average(ocrTimes), "last_status":lastStatus,
            "elapsed_seconds":Date().timeIntervalSince(started)])
        if lastStatus != "readable" { exit(2) }
    }
}

#endif
