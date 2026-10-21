// Local read-only capture diagnostic. Original project code; see UPSTREAM.md.
import Cocoa
import ScreenCaptureKit
import AVFoundation
import Darwin

enum WindowMode: String { case main, independent }
func windowMode() throws -> WindowMode {
    guard let mode = WindowMode(rawValue:option("--window-mode","main")) else { throw fail("invalid_window_mode") }
    return mode
}
func matchesWindowTitle(_ title:String,mode:WindowMode,chat:String) -> Bool {
    switch mode {
    case .main: return ["Weixin","WeChat","微信"].contains(title)
    case .independent: return !chat.isEmpty && !["Weixin","WeChat","微信"].contains(chat) && title == chat
    }
}
func diagnosticTitleVerified(_ image:CGImage,chat:String) -> Bool {
    !isBlank(pixels(image)) && (try? chatLeft(image,chat:chat)) != nil
}
func diagnosticImage(_ session:CaptureSession) async throws -> CGImage {
    if session.screenshotBackend {
        guard let frame = try await session.freshScreenshot() else { throw fail("capture_no_valid_frame") }
        return frame
    }
    // No filter switching or backend fallback: retain the exact tested backend.
    for _ in 0..<30 {
        if let frame = try session.nextImage() { return frame }
        try await Task.sleep(for:.milliseconds(100))
    }
    throw fail("capture_no_valid_frame")
}
func selectedCaptureWindow(calibrated:Bool) async throws -> (SCWindow,SCDisplay) {
    guard !screenLocked() else { throw fail("screen_locked") }
    guard let pid = Int32(option("--pid","")) else { throw fail("process_binding_changed") }
    try requireNoAccountSecurityNotice(pid)
    let mode = try windowMode(), chat = option("--chat","")
    let width = Double(option("--window-width","")),height = Double(option("--window-height",""))
    guard (width == nil) == (height == nil), !calibrated || width != nil else { throw fail("calibrated_window_size_changed") }
    let content = try await SCShareableContent.excludingDesktopWindows(true,onScreenWindowsOnly:true)
    let matches = content.windows.filter { w in
        guard w.owningApplication?.processID == pid,
              w.owningApplication?.bundleIdentifier == "com.tencent.xinWeChat",
              matchesWindowTitle(w.title ?? "",mode:mode,chat:chat),
              w.frame.width >= (mode == .main ? 600 : 360),w.frame.height >= 450 else { return false }
        return width == nil || (w.frame.width == width && w.frame.height == height)
    }
    guard matches.count == 1 else { throw fail("target_window_not_unique") }
    let window = matches[0]
    guard let display = content.displays.first(where: { $0.frame.contains(window.frame) }) else { throw fail("window_must_fit_one_display") }
    return (window,display)
}

// This command never activates, clicks, pastes, or presses a key. A nonempty
// picture alone is not success: exact OCR title verification is mandatory.
func checkWindowCapture() async throws {
    umask(0o077)
    guard CGPreflightScreenCaptureAccess(),AXIsProcessTrusted() else { throw fail("screen_recording_and_accessibility_permissions_required") }
    let (window,display) = try await selectedCaptureWindow(calibrated:false)
    guard let owner = window.owningApplication else { throw fail("process_binding_changed") }
    try requireUnobscured(window,owner.processID)
    let backend = option("--capture-backend","display")
    guard ["display","window","stream"].contains(backend) else { throw fail("invalid_capture_backend") }
    let session = CaptureSession()
    do {
        try await session.start(window:window,display:display,interval:0.25,backend:backend)
        for index in 0..<3 {
            let image = try await diagnosticImage(session)
            let snapshot = option("--snapshot","")
            if !snapshot.isEmpty { try privatePNG(image,path:snapshot+".\(index).png") }
            let verified = diagnosticTitleVerified(image,chat:option("--chat",""))
            emit(["type":"capture_sample","backend":backend,"window_mode":try windowMode().rawValue,
                  "width":image.width,"height":image.height,"title_verified":verified,"input_events":0])
            guard verified else { throw fail("chat_title_not_verified") }
            try await Task.sleep(for:.milliseconds(500))
        }
        emit(["type":"capture_check_passed","backend":backend,"samples":3,"input_events":0])
        await session.stop()
    } catch { await session.stop(); throw error }
}

@available(macOS 15.2, *)
final class CapturePickerObserver:NSObject,SCContentSharingPickerObserver,@unchecked Sendable {
    private let lock = NSLock()
    private var selected:SCContentFilter?
    private var error:String?
    func contentSharingPicker(_ picker:SCContentSharingPicker,didCancelFor stream:SCStream?) {
        lock.lock(); error = "capture_picker_cancelled"; lock.unlock()
    }
    func contentSharingPicker(_ picker:SCContentSharingPicker,didUpdateWith filter:SCContentFilter,for stream:SCStream?) {
        lock.lock(); selected = filter; lock.unlock()
    }
    func contentSharingPickerStartDidFailWithError(_ error:Error) {
        lock.lock(); self.error = "capture_picker_failed"; lock.unlock()
    }
    func result() throws -> SCContentFilter? {
        lock.lock(); defer { lock.unlock() }
        if let error { throw fail(error) }
        return selected
    }
}
@available(macOS 15.2, *)
final class CaptureRecordingObserver:NSObject,SCRecordingOutputDelegate,@unchecked Sendable {
    private let lock = NSLock()
    private var finished = false
    private var failed = false
    func recordingOutputDidFinishRecording(_ output:SCRecordingOutput) {
        lock.lock(); finished = true; lock.unlock()
    }
    func recordingOutput(_ output:SCRecordingOutput,didFailWithError error:Error) {
        lock.lock(); failed = true; lock.unlock()
    }
    func done() throws -> Bool {
        lock.lock(); defer { lock.unlock() }
        if failed { throw fail("capture_recording_failed") }
        return finished
    }
}
@available(macOS 15.2, *)
func checkPickerCapture() async throws {
    umask(0o077)
    let (window,_) = try await selectedCaptureWindow(calibrated:false)
    let snapshot = option("--snapshot","")
    guard !snapshot.isEmpty else { throw fail("diagnostic_snapshot_required") }
    let recordingPath = snapshot+".mp4"
    guard !FileManager.default.fileExists(atPath:recordingPath) else { throw fail("diagnostic_output_exists") }
    let observer = CapturePickerObserver()
    let picker = SCContentSharingPicker.shared
    await MainActor.run {
        var config = SCContentSharingPickerConfiguration()
        config.allowedPickerModes = [.singleWindow]
        config.allowsChangingSelectedContent = false
        picker.defaultConfiguration = config
        picker.add(observer); picker.isActive = true
        picker.present(using:.window)
    }
    do {
        emit(["type":"capture_picker_waiting","timeout_seconds":120,"input_events":0])
        var selected:SCContentFilter?
        for _ in 0..<600 {
            selected = try observer.result()
            if selected != nil { break }
            try await Task.sleep(for:.milliseconds(200))
        }
        guard let filter = selected else { throw fail("capture_picker_timeout") }
        guard filter.style == .window,filter.includedWindows.count == 1,
              filter.includedWindows[0].windowID == window.windowID,
              filter.includedWindows[0].owningApplication?.processID == window.owningApplication?.processID else {
            throw fail("capture_picker_wrong_window")
        }
        let config = SCRecordingOutputConfiguration()
        config.outputURL = URL(fileURLWithPath:recordingPath)
        let recordingObserver = CaptureRecordingObserver()
        let recording = SCRecordingOutput(configuration:config,delegate:recordingObserver)
        let session = CaptureSession()
        do {
            try await session.startDiagnostic(filter:filter,size:window.frame.size,recording:recording)
            var verified = true
            for index in 0..<4 {
                let image = try await diagnosticImage(session)
                try privatePNG(image,path:snapshot+".\(index).png")
                let exactTitle = diagnosticTitleVerified(image,chat:option("--chat",""))
                verified = verified && exactTitle
                emit(["type":"capture_sample","backend":"system_picker","title_verified":exactTitle,
                      "width":image.width,"height":image.height,"input_events":0])
                try await Task.sleep(for:.milliseconds(500))
            }
            await session.stop()
            for _ in 0..<30 {
                if try recordingObserver.done() { break }
                try await Task.sleep(for:.milliseconds(100))
            }
            guard try recordingObserver.done() else { throw fail("capture_recording_incomplete") }
            try FileManager.default.setAttributes([.posixPermissions:0o600],ofItemAtPath:recordingPath)
            emit(["type":"capture_recording_finished","title_verified":verified,"input_events":0])
            guard verified else { throw fail("chat_title_not_verified") }
        } catch { await session.stop(); throw error }
        await MainActor.run { picker.isActive = false; picker.remove(observer) }
    } catch {
        await MainActor.run { picker.isActive = false; picker.remove(observer) }
        throw error
    }
}
