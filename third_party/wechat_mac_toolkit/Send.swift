import Cocoa
import ApplicationServices
import ScreenCaptureKit
import CryptoKit
import Darwin

struct UIError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}
func fail(_ reason: String) -> UIError { UIError(message: reason) }
func normalized(_ text: String) -> String {
    text.precomposedStringWithCompatibilityMapping.filter { !$0.isWhitespace }
}
func digest(_ text: String) -> String { SHA256.hash(data:Data(text.utf8)).map { String(format:"%02x",$0) }.joined() }
func validateArguments(_ args:[String]) throws {
    guard let command = args.first else { return }
    let values:Set<String>
    var flags:Set<String> = []
    switch command {
    case "capture-check": values = ["--chat","--pid","--window-mode","--window-width","--window-height","--capture-backend","--snapshot"]
    case "capture-picker": values = ["--chat","--pid","--window-mode","--snapshot"]
    case "read": values = ["--chat","--snapshot","--composer-top"]
    case "watch": values = ["--chat","--snapshot","--composer-top","--seconds","--interval"]
    case "send": values = ["--chat","--text","--text-file","--id","--composer-top","--state-dir","--send-key","--pid","--window-width","--window-height","--window-mode","--preflight"]; flags = ["--dry-run"]
    case "focus","session-check": values = ["--pid","--window-width","--window-height","--window-mode","--chat"]
    case "help","doctor","self-test": values = []
    default: throw fail("unknown_command")
    }
    var index = 1, seen = Set<String>()
    while index < args.count {
        let name = args[index]
        guard !seen.contains(name) else { throw fail("duplicate_option_"+name) }
        seen.insert(name)
        if flags.contains(name) { index += 1; continue }
        guard values.contains(name) else { throw fail("unknown_option_"+name) }
        guard index+1 < args.count, !args[index+1].hasPrefix("--") else { throw fail("missing_value_"+name) }
        index += 2
    }
}
func printUsage() {
    print("""
    wechat-ui doctor
    wechat-ui capture-check --pid BOUND_PID --chat 'Exact title' --window-mode main|independent
                            [--capture-backend display|window|stream] [--snapshot /private/path/prefix]
    wechat-ui capture-picker --pid BOUND_PID --chat 'Exact title' --window-mode independent --snapshot /private/path/prefix
    wechat-ui focus --pid BOUND_PID --window-width POINTS --window-height POINTS
    wechat-ui session-check --pid BOUND_PID
    wechat-ui read --chat 'Exact title' [--snapshot /path/image.png]
    wechat-ui watch --chat 'Exact title' [--seconds 30] [--interval 0.5]
    wechat-ui send --chat 'Exact title' --text 'Single-line text' --id UNIQUE_ID
                   --composer-top 0.70 [--send-key enter|cmd-enter] [--dry-run]
                   [--window-mode main|independent] [--preflight visual|ax-window-db]
                   [--state-dir .wechat-ui-state]
    wechat-ui self-test

    Open the intended chat manually first. No search, login automation or LLM.
    send requires calibrated --composer-top (input area's top / window height).
    ax-window-db explicitly skips draft/OCR/occlusion checks and requires an independent window.
    A repeated --id never silently sends again. Failed verification is not delivery.
    Do not interact with WeChat while send runs. Standard green outgoing bubbles only.
    """)
}
func screenLocked() -> Bool {
    (CGSessionCopyCurrentDictionary() as? [String:Any])?["CGSSessionScreenIsLocked"] as? Bool ?? false
}
func doctor() {
    let app = NSRunningApplication.runningApplications(withBundleIdentifier:"com.tencent.xinWeChat").first
    emit(["type":"doctor", "macOS":ProcessInfo.processInfo.operatingSystemVersionString,
          "screen_locked":screenLocked(), "screen_recording":CGPreflightScreenCaptureAccess(), "accessibility":AXIsProcessTrusted(),
          "wechat_running":app != nil, "wechat_version":app?.bundleURL.flatMap { Bundle(url:$0)?.object(forInfoDictionaryKey:"CFBundleShortVersionString") as? String } ?? "unknown"])
}
func scaled(_ image:CGImage, factor:Int) throws -> CGImage {
    guard let context = CGContext(data:nil,width:image.width*factor,height:image.height*factor,
                                  bitsPerComponent:8,bytesPerRow:0,
                                  space:CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue) else { throw fail("image_scale_failed") }
    context.interpolationQuality = .high
    context.draw(image,in:CGRect(x:0,y:0,width:image.width*factor,height:image.height*factor))
    guard let result = context.makeImage() else { throw fail("image_scale_failed") }
    return result
}
func chatLeft(_ image:CGImage, chat:String) throws -> Double {
    let header = try crop(image,CGRect(x:0,y:0,width:image.width,height:min(80,Int(Double(image.height)*0.10))))
    let languages = chat.unicodeScalars.allSatisfy { $0.isASCII } ? ["en-US"] : ["zh-Hans","en-US"]
    var matches:[Line] = []
    // First pass only locates text. Identity requires a unique exact high-confidence
    // result from the isolated second pass; no fuzzy matching or expected-word hints.
    for line in try recognize(header) where line.box.minX > 0.15 {
        let bounds = CGRect(x:Double(line.box.minX)*Double(header.width)-6,
                            y:Double(1-line.box.maxY)*Double(header.height)-6,
                            width:Double(line.box.width)*Double(header.width)+12,
                            height:Double(line.box.height)*Double(header.height)+12)
            .intersection(CGRect(x:0,y:0,width:header.width,height:header.height))
        let isolated = try scaled(crop(header,bounds),factor:4)
        let refined = try recognize(isolated,languages:languages)
        if refined.count == 1 && refined[0].text == chat && refined[0].confidence >= 0.5 {
            matches.append(line)
        }
    }
    guard matches.count == 1 else { throw fail("chat_title_not_verified") }
    return max(0,Double(matches[0].box.minX)*Double(image.width)-16)
}
func targetWindow() async throws -> (SCWindow, SCDisplay) {
    guard !screenLocked() else { throw fail("screen_locked") }
    let content = try await SCShareableContent.excludingDesktopWindows(true,onScreenWindowsOnly:true)
    let windows = content.windows.filter {
        $0.owningApplication?.bundleIdentifier == "com.tencent.xinWeChat" &&
        ["Weixin","WeChat","微信"].contains($0.title ?? "") && $0.frame.width > 600 && $0.frame.height > 450
    }
    guard windows.count == 1 else { throw fail("expected_one_visible_main_window") }
    let w = windows[0]
    guard let d = content.displays.first(where: { $0.frame.contains(w.frame) }) else { throw fail("window_must_fit_one_display") }
    return (w,d)
}
func waitImage(_ session:CaptureSession) async throws -> CGImage {
    if session.screenshotBackend {
        guard let frame = try await session.freshScreenshot() else { throw fail("no_frame_after_filter_refresh") }
        return frame
    }
    for attempt in 0..<2 {
        if attempt == 1 { try await session.refresh() }
        for _ in 0..<40 {
            if let image = try session.nextImage() { return image }
            try await Task.sleep(for:.milliseconds(50))
        }
    }
    emit(["type":"capture_not_ready","statistics":session.frameStatistics()])
    throw fail("no_frame_after_filter_refresh")
}
func crop(_ image:CGImage,_ rect:CGRect) throws -> CGImage {
    guard let result = image.cropping(to:rect.integral) else { throw fail("invalid_crop") }
    return result
}
func composerRect(_ image:CGImage, left:Double, top:Double) throws -> CGRect {
    let r = CGRect(x:left+12,y:Double(image.height)*top+8,
                   width:Double(image.width)-left-32,height:Double(image.height)*(1-top)-68)
    guard r.width > 100 && r.height > 35 else { throw fail("invalid_composer_geometry") }
    return r
}
func composerText(_ image:CGImage,left:Double,top:Double) throws -> String {
    try recognize(crop(image, composerRect(image,left:left,top:top))).map(\.text).joined()
}
func composerEmpty(_ image:CGImage,left:Double,top:Double) throws -> Bool {
    let region = try crop(image,composerRect(image,left:left,top:top))
    let lines = try recognize(region)
    let placeholders:Set<String> = [normalized("Hold mouse to input by voice")]
    guard lines.allSatisfy({ placeholders.contains(normalized($0.text)) }) else { return false }
    // Mask only the known empty-composer hint; non-text attachments remain visible.
    var sample = pixels(region)
    let sorted = sample.sorted(), background = Int(sorted[sorted.count/2])
    for line in lines {
        let x0 = max(0,Int(line.box.minX*200)-2), x1 = min(199,Int(line.box.maxX*200)+2)
        let y0 = max(0,Int((1-line.box.maxY)*160)-2), y1 = min(159,Int((1-line.box.minY)*160)+2)
        for y in y0...y1 { for x in x0...x1 { sample[y*200+x] = UInt8(background) } }
    }
    let nonBackground = sample.filter { abs(Int($0)-background) > 35 }.count
    return Double(nonBackground)/Double(sample.count) < 0.001
}
func emptyComposerFrame(_ session:CaptureSession,chat:String,top:Double,pid:pid_t,reason:String) async throws -> (CGImage,Double) {
    // Require two fresh empty frames. A blinking caret or activation animation
    // may temporarily make a genuinely empty composer fail the pixel check.
    var emptyFrames = 0
    var last:CGImage?
    for _ in 0..<8 {
        try requireFrontmost(pid)
        let image = try await waitImage(session)
        last = image
        let left = try chatLeft(image,chat:chat)
        if try composerEmpty(image,left:left,top:top) { emptyFrames += 1 }
        if emptyFrames == 2 { return (image,left) }
        try await Task.sleep(for:.milliseconds(150))
    }
    if let last {
        let path = URL(fileURLWithPath:option("--state-dir",".wechat-ui-state"),isDirectory:true)
            .appendingPathComponent(digest(option("--id",""))+".composer-check.png").path
        try? privatePNG(last,path:path)
    }
    emit(["type":"composer_check_failed","empty_frames":emptyFrames,"frames":8])
    throw fail(reason)
}
func rgba(_ image:CGImage) -> [UInt8] {
    var bytes = [UInt8](repeating:0,count:image.width*image.height*4)
    bytes.withUnsafeMutableBytes { storage in
        let c = CGContext(data:storage.baseAddress,width:image.width,height:image.height,bitsPerComponent:8,
                          bytesPerRow:image.width*4,space:CGColorSpaceCreateDeviceRGB(),
                          bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
        c.draw(image,in:CGRect(x:0,y:0,width:image.width,height:image.height))
    }
    return bytes
}
func outgoingContains(_ image:CGImage,left:Double,top:Double,text:String) throws -> Bool {
    let region = try crop(image,CGRect(x:left,y:65,width:Double(image.width)-left,height:Double(image.height)*top-65))
    let bytes = rgba(region), width = region.width, height = region.height
    let lines = try recognize(region).filter { line in
        // Only lines in a green bubble on the right of the conversation panel.
        guard line.box.midX > 0.5 else { return false }
        let x = max(0,Int(line.box.minX*Double(width))-7)
        let y = min(height-1,max(0,Int((1-line.box.midY)*Double(height))))
        let i = (y*width+x)*4
        let r = Int(bytes[i]), g = Int(bytes[i+1]), b = Int(bytes[i+2])
        return g > 130 && g-r > 15 && g-b > 15
    }
    return normalized(lines.map(\.text).joined()).contains(normalized(text))
}
func requireFrontmost(_ pid:pid_t) throws {
    guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else { throw fail("wechat_lost_focus") }
}
func axAttribute(_ element:AXUIElement, _ name:CFString) -> CFTypeRef? {
    var value:CFTypeRef?
    guard AXUIElementCopyAttributeValue(element,name,&value) == .success else { return nil }
    return value
}
func accountSecurityNotice(_ text:String) -> Bool {
    normalized(text).lowercased().contains(normalized("For account security, log in again.").lowercased())
}
func requireNoAccountSecurityNotice(_ pid:pid_t) throws {
    guard NSRunningApplication(processIdentifier:pid)?.bundleIdentifier == "com.tencent.xinWeChat" else { throw fail("process_binding_changed") }
    let root = AXUIElementCreateApplication(pid)
    guard let windows = axAttribute(root,kAXWindowsAttribute as CFString) as? [AXUIElement] else { return }
    var budget = 120
    func texts(_ element:AXUIElement,depth:Int) -> [String] {
        guard budget > 0, depth <= 6 else { return [] }
        budget -= 1
        var result = [kAXTitleAttribute,kAXValueAttribute,kAXDescriptionAttribute].compactMap {
            axAttribute(element,$0 as CFString) as? String
        }
        for child in axAttribute(element,kAXChildrenAttribute as CFString) as? [AXUIElement] ?? [] {
            result += texts(child,depth:depth+1)
        }
        return result
    }
    for window in windows {
        if accountSecurityNotice(texts(window,depth:0).joined(separator:" ")) {
            throw fail("wechat_account_security_prompt")
        }
    }
}
func boundMainWindow(calibrated:Bool) throws -> (pid_t,NSRunningApplication,AXUIElement) {
    guard !screenLocked() else { throw fail("screen_locked") }
    guard AXIsProcessTrusted() else { throw fail("accessibility_permission_required") }
    guard let pid = Int32(option("--pid","")),
          let app = NSRunningApplication(processIdentifier:pid),
          app.bundleIdentifier == "com.tencent.xinWeChat" else { throw fail("process_binding_changed") }
    let width = Double(option("--window-width","")),height = Double(option("--window-height",""))
    let mode = try windowMode()
    guard (width == nil) == (height == nil), !calibrated || width != nil else { throw fail("calibrated_window_size_changed") }
    let root = AXUIElementCreateApplication(pid)
    try requireNoAccountSecurityNotice(pid)
    guard let windows = axAttribute(root,kAXWindowsAttribute as CFString) as? [AXUIElement] else { throw fail("main_window_unavailable") }
    let matches = windows.filter { window in
        guard let title = axAttribute(window,kAXTitleAttribute as CFString) as? String,
              matchesWindowTitle(title,mode:mode,chat:option("--chat","")),
              let raw = axAttribute(window,kAXSizeAttribute as CFString),
              CFGetTypeID(raw) == AXValueGetTypeID() else { return false }
        var size = CGSize.zero
        guard AXValueGetValue(raw as! AXValue,.cgSize,&size) else { return false }
        if let width,let height { return size.width == width && size.height == height }
        return size.width >= (mode == .main ? 600 : 360) && size.height >= 450
    }
    guard matches.count == 1 else { throw fail("calibrated_main_window_not_unique") }
    return (pid,app,matches[0])
}
// Read-only session/window evidence; presence alone is not proof of authentication.
func checkWeChatSession() throws {
    _ = try boundMainWindow(calibrated:false)
    emit(["type":"session_window_ready","authentication_verified":false,"input_events":0])
}
// Explicit preparation; never searches chats, types or modifies another app.
func focusWeChat() async throws {
    let (pid,app,window) = try boundMainWindow(calibrated:true)
    if axAttribute(window,kAXMinimizedAttribute as CFString) as? Bool == true {
        guard AXUIElementSetAttributeValue(window,kAXMinimizedAttribute as CFString,kCFBooleanFalse) == .success else { throw fail("main_window_restore_failed") }
    }
    guard app.activate(options:[]) else { throw fail("wechat_activation_failed") }
    guard AXUIElementPerformAction(window,kAXRaiseAction as CFString) == .success else { throw fail("main_window_raise_failed") }
    for _ in 0..<20 {
        if NSWorkspace.shared.frontmostApplication?.processIdentifier == pid,
           let focused = axAttribute(AXUIElementCreateApplication(pid),kAXFocusedWindowAttribute as CFString),
           CFEqual(focused,window) {
            emit(["type":"wechat_focused","persistent_topmost":false]); return
        }
        try await Task.sleep(for:.milliseconds(100))
    }
    throw fail("wechat_activation_failed")
}
func clickPoint(_ point:CGPoint) throws {
    for kind in [CGEventType.leftMouseDown, .leftMouseUp] {
        guard let event = CGEvent(mouseEventSource:nil,mouseType:kind,mouseCursorPosition:point,mouseButton:.left) else { throw fail("mouse_event_failed") }
        event.post(tap:.cghidEventTap)
        usleep(35_000)
    }
}
final class ClipboardLease {
    let pasteboard:NSPasteboard, original:[[NSPasteboard.PasteboardType:Data]], originalChange:Int
    var installedChange:Int?
    init(pasteboard:NSPasteboard = .general) throws {
        self.pasteboard = pasteboard
        originalChange = pasteboard.changeCount
        var saved:[[NSPasteboard.PasteboardType:Data]] = []
        let items = pasteboard.pasteboardItems ?? []
        guard !items.isEmpty || (pasteboard.types ?? []).isEmpty else { throw fail("clipboard_snapshot_unavailable") }
        for item in items {
            var record:[NSPasteboard.PasteboardType:Data] = [:]
            for type in item.types {
                guard let data = item.data(forType:type) else { throw fail("clipboard_snapshot_unavailable") }
                record[type] = data
            }
            saved.append(record)
        }
        guard pasteboard.changeCount == originalChange else { throw fail("clipboard_changed_before_paste") }
        original = saved
    }
    func install(_ text:String) throws {
        guard installedChange == nil, pasteboard.changeCount == originalChange else { throw fail("clipboard_changed_before_paste") }
        pasteboard.clearContents()
        installedChange = pasteboard.changeCount
        guard pasteboard.setString(text,forType:.string) else { throw fail("clipboard_write_failed") }
        installedChange = pasteboard.changeCount
    }
    @discardableResult func restore() -> String {
        guard let installed = installedChange else { return "unchanged" }
        installedChange = nil
        guard pasteboard.changeCount == installed else { return "preserved_new_content" }
        let items = original.map { record in
            let item = NSPasteboardItem()
            for (type,data) in record { item.setData(data,forType:type) }
            return item
        }
        pasteboard.clearContents()
        return items.isEmpty || pasteboard.writeObjects(items) ? "restored" : "restore_failed"
    }
}
func pasteOnce(_ text:String,pid:pid_t,clipboard:ClipboardLease) throws {
    try requireFrontmost(pid)
    try requireNoAccountSecurityNotice(pid)
    try clipboard.install(text)
    try requireFrontmost(pid)
    for down in [true,false] {
        guard let event = CGEvent(keyboardEventSource:nil,virtualKey:9,keyDown:down) else { throw fail("keyboard_event_failed") }
        event.flags = .maskCommand
        event.postToPid(pid)
        usleep(25_000)
    }
}
func enter(_ pid:pid_t,command:Bool) throws {
    try requireFrontmost(pid)
    for down in [true,false] {
        guard let event = CGEvent(keyboardEventSource:nil,virtualKey:36,keyDown:down) else { throw fail("keyboard_event_failed") }
        if command { event.flags = .maskCommand }
        event.postToPid(pid)
        usleep(25_000)
    }
}
func validMessage(_ value:String) -> Bool {
    !value.trimmingCharacters(in:.whitespaces).isEmpty && value.unicodeScalars.count <= 200 && !value.unicodeScalars.contains { CharacterSet.controlCharacters.contains($0) }
}
func validDegradedMessage(_ value:String) -> Bool {
    !value.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && value.unicodeScalars.count <= 1000 &&
    !value.unicodeScalars.contains { $0.properties.generalCategory == .control && $0.value != 10 }
}
func testSendUtilities() {
    precondition(validDegradedMessage("今晚吃点清淡的吧。\nTake your time  🙂"))
    precondition(validDegradedMessage("晚安，周末和家人一起散步吧 👨‍👩‍👧‍👦"))
    precondition(validDegradedMessage(String(repeating:"晚",count:1000)))
    precondition(!validDegradedMessage(String(repeating:"晚",count:1001)))
    precondition(!validDegradedMessage("\n  ") && !validDegradedMessage("晚\t安") && !validDegradedMessage("晚\r安"))
    precondition(matchesWindowTitle("WeChat",mode:.main,chat:"friend"))
    precondition(!matchesWindowTitle("friend",mode:.main,chat:"friend"))
    precondition(matchesWindowTitle("friend",mode:.independent,chat:"friend"))
    precondition(!matchesWindowTitle("other",mode:.independent,chat:"friend"))
    precondition(!matchesWindowTitle("WeChat",mode:.independent,chat:"WeChat"))
    let blackContext = CGContext(data:nil,width:80,height:80,bitsPerComponent:8,bytesPerRow:0,
                                space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
    blackContext.setFillColor(NSColor.black.cgColor)
    blackContext.fill(CGRect(x:0,y:0,width:80,height:80))
    precondition(!diagnosticTitleVerified(blackContext.makeImage()!,chat:"synthetic"))
    precondition(normalized("Ａ B　你好") == "AB你好")
    precondition(validMessage("今天过得怎么样？") && !validMessage("a\nb") && !validMessage(""))
    precondition(digest("a") == digest("a") && digest("a") != digest("b"))
    let screen = CGRect(x:-1920,y:-1080,width:1920,height:1080)
    let panel = CGRect(x:-1800,y:-80,width:1600,height:80)
    precondition(clearDockSurface(screen,panel:panel,target:CGRect(x:-1900,y:-1000,width:880,height:640)))
    precondition(!clearDockSurface(screen,panel:panel,target:CGRect(x:-1900,y:-700,width:880,height:640)))
    precondition(!clearDockSurface(panel,panel:panel,target:CGRect(x:-1900,y:-1000,width:880,height:640)))
    precondition(accountSecurityNotice("Tip For account security, log in again. OK"))
    precondition(!accountSecurityNotice("Tip Please check the chat. OK"))
    // Use a private named pasteboard: self-test never changes the user's clipboard.
    let pasteboard = NSPasteboard.withUniqueName()
    defer { pasteboard.releaseGlobally() }
    pasteboard.setString("original",forType:.string)
    do {
        let clipboard = try ClipboardLease(pasteboard:pasteboard)
        try clipboard.install("中文 punctuation  😀")
        precondition(pasteboard.string(forType:.string) == "中文 punctuation  😀")
        precondition(clipboard.restore() == "restored")
        precondition(pasteboard.string(forType:.string) == "original")
        let changed = try ClipboardLease(pasteboard:pasteboard)
        try changed.install("synthetic")
        pasteboard.clearContents(); pasteboard.setString("new user copy",forType:.string)
        precondition(changed.restore() == "preserved_new_content")
        precondition(pasteboard.string(forType:.string) == "new user copy")
        pasteboard.clearContents()
        let empty = try ClipboardLease(pasteboard:pasteboard)
        try empty.install("temporary")
        precondition(empty.restore() == "restored" && (pasteboard.types ?? []).isEmpty)
    } catch { preconditionFailure("private_pasteboard_self_test_failed") }
}
// Journals intentionally contain hashes/status only; no chat names or message text.
final class Journal {
    let file:URL, signature:String
    let lockFD:Int32
    init(directory:String,id:String,signature:String) throws {
        self.signature = signature
        let dir = URL(fileURLWithPath:directory,isDirectory:true)
        try FileManager.default.createDirectory(at:dir,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        lockFD = Darwin.open(dir.appendingPathComponent("send.lock").path,O_CREAT|O_RDWR|O_NOFOLLOW,0o600)
        guard lockFD >= 0 else { throw fail("cannot_open_send_lock") }
        guard flock(lockFD,LOCK_EX|LOCK_NB) == 0 else { Darwin.close(lockFD); throw fail("another_sender_is_running") }
        file = dir.appendingPathComponent(digest(id)+".json")
    }
    deinit { flock(lockFD,LOCK_UN); Darwin.close(lockFD) }
    func existing() throws -> String? {
        guard FileManager.default.fileExists(atPath:file.path) else { return nil }
        let raw = try JSONSerialization.jsonObject(with:Data(contentsOf:file)) as? [String:String]
        guard raw?["signature"] == signature else { throw fail("id_reused_with_different_payload") }
        return raw?["status"] ?? "unknown"
    }
    func save(_ status:String) throws {
        let value = ["status":status,"signature":signature,"at":ISO8601DateFormatter().string(from:Date())]
        try JSONSerialization.data(withJSONObject:value,options:.sortedKeys).write(to:file,options:.atomic)
        try FileManager.default.setAttributes([.posixPermissions:0o600],ofItemAtPath:file.path)
    }
}
func sendMessage() async throws {
    let chat = option("--chat",""), id = option("--id","")
    let textFile = option("--text-file","")
    guard textFile.isEmpty || option("--text","").isEmpty else { throw fail("choose_text_or_text_file") }
    let text = textFile.isEmpty ? option("--text","") : try String(contentsOfFile:textFile,encoding:.utf8)
    let key = option("--send-key","enter"), dry = CommandLine.arguments.contains("--dry-run")
    let preflight = option("--preflight","visual")
    guard ["visual","ax-window-db"].contains(preflight) else { throw fail("invalid_send_preflight") }
    guard !chat.isEmpty, (preflight == "ax-window-db" ? validDegradedMessage(text) : validMessage(text)), !id.isEmpty,
          let top = Double(option("--composer-top","")), top.isFinite, top >= 0.45, top <= 0.88,
          ["enter","cmd-enter"].contains(key) else { throw fail("send_requires_chat_text_id_and_calibrated_composer_top; text_must_be_single_line_and_at_most_200_characters") }
    if preflight == "ax-window-db" {
        try await sendWithoutCapture(chat:chat,text:text,id:id,top:top,key:key,dry:dry)
        return
    }
    guard CGPreflightScreenCaptureAccess(), AXIsProcessTrusted() else { throw fail("screen_recording_and_accessibility_permissions_required") }
    guard let requestedPID = Int32(option("--pid","")) else { throw fail("process_binding_changed") }
    try requireNoAccountSecurityNotice(requestedPID)
    let journal = try Journal(directory:option("--state-dir",".wechat-ui-state"),id:id,signature:digest(chat+"\0"+text))
    if let status = try journal.existing() {
        if status == "sent_ui_verified" { emit(["type":"already_sent","id":id]); return }
        throw fail("id_already_attempted_"+status+"; inspect_WeChat_before_any_new_id")
    }
    let (window,display) = try await targetWindow()
    guard let expectedWidth = Double(option("--window-width","")),
          let expectedHeight = Double(option("--window-height","")),
          expectedWidth == window.frame.width, expectedHeight == window.frame.height else { throw fail("calibrated_window_size_changed") }
    guard let owner = window.owningApplication, let app = NSRunningApplication(processIdentifier:owner.processID) else { throw fail("wechat_not_running") }
    guard let expectedPID = Int32(option("--pid","")), owner.processID == expectedPID else { throw fail("process_binding_changed") }
    try requireUnobscured(window, expectedPID)
    let session = CaptureSession()
    do {
        try await session.start(window:window,display:display,interval:0.25)
        var (image,left) = try await emptyComposerFrame(session,chat:chat,top:top,pid:expectedPID,reason:"composer_not_empty_or_wrong_composer_top")
        guard try !outgoingContains(image,left:left,top:top,text:text) else { throw fail("same_text_already_visible; refusing_duplicate") }
        if dry {
            emit(["type":"send_preflight_ok","dry_run":true]); await session.stop(); return
        }
        try journal.save("prepared")
        _ = app // Already frontmost; never activate during preflight or send.
        try requireUnobscured(window, owner.processID)
        try await Task.sleep(for:.milliseconds(300))
        try requireFrontmost(owner.processID)
        let (current,_) = try await targetWindow()
        guard current.windowID == window.windowID && current.frame == window.frame else { throw fail("window_moved_before_typing") }
        (image,left) = try await emptyComposerFrame(session,chat:chat,top:top,pid:owner.processID,reason:"composer_changed_before_typing")
        let (readyToType,_) = try await targetWindow()
        guard readyToType.windowID == window.windowID && readyToType.frame == window.frame else { throw fail("window_moved_before_typing") }
        try requireUnobscured(readyToType, owner.processID)
        let point = CGPoint(x:window.frame.minX+left+80,y:window.frame.minY+Double(image.height)*top+30)
        try clickPoint(point); try await Task.sleep(for:.milliseconds(100))
        let clipboard = try ClipboardLease()
        defer { emit(["type":"clipboard_cleanup","status":clipboard.restore()]) }
        try pasteOnce(text,pid:owner.processID,clipboard:clipboard)
        var typed = false
        for _ in 0..<8 {
            try await Task.sleep(for:.milliseconds(300))
            image = try await waitImage(session); left = try chatLeft(image,chat:chat)
            if try composerText(image,left:left,top:top) == text { typed = true; break }
        }
        guard typed else { throw fail("draft_verification_failed; no_enter_pressed; inspect_draft") }
        try requireFrontmost(owner.processID)
        let (beforeSend,_) = try await targetWindow()
        guard beforeSend.windowID == window.windowID && beforeSend.frame == window.frame else { throw fail("window_moved_before_send") }
        try requireUnobscured(beforeSend, owner.processID)
        image = try await waitImage(session); left = try chatLeft(image,chat:chat)
        guard try composerText(image,left:left,top:top) == text else { throw fail("draft_changed_before_send") }
        try requireFrontmost(owner.processID)
        try requireNoAccountSecurityNotice(owner.processID)
        try journal.save("dispatching")
        try enter(owner.processID,command:key == "cmd-enter")
        for _ in 0..<10 {
            try await Task.sleep(for:.milliseconds(400))
            try requireNoAccountSecurityNotice(owner.processID)
            image = try await waitImage(session); left = try chatLeft(image,chat:chat)
            if try composerEmpty(image,left:left,top:top) && outgoingContains(image,left:left,top:top,text:text) {
                try journal.save("sent_ui_verified")
                emit(["type":"sent_ui_verified","id":id,"delivery_receipt":false])
                await session.stop(); return
            }
        }
        throw fail("send_result_uncertain; never_retry_automatically; inspect_WeChat")
    } catch {
        await session.stop()
        throw error
    }
}

// ScreenCaptureKit may capture a covered/background window: prove input visibility separately.
func clearDockSurface(_ surface:CGRect,panel:CGRect,target:CGRect) -> Bool {
    !panel.isEmpty && surface.contains(panel) && surface.contains(target) &&
    surface.height > panel.height*2 && !panel.intersects(target)
}
func transparentDockSurface(_ info:[String:Any],bounds:CGRect,target:CGRect) -> Bool {
    guard let pid = info[kCGWindowOwnerPID as String] as? pid_t,
          NSRunningApplication(processIdentifier:pid)?.bundleIdentifier == "com.apple.dock",
          info[kCGWindowLayer as String] as? Int == Int(CGWindowLevelForKey(.dockWindow)),
          info[kCGWindowName as String] as? String == "Dock" else { return false }
    // macOS 27 reports a display-sized transparent Dock surface. Its one AXList
    // exposes the real panel. Unknown layouts or an intersecting panel still block.
    let root = AXUIElementCreateApplication(pid)
    guard let children = axAttribute(root,kAXChildrenAttribute as CFString) as? [AXUIElement],
          children.count == 1,
          axAttribute(children[0],kAXRoleAttribute as CFString) as? String == kAXListRole,
          let rawPoint = axAttribute(children[0],kAXPositionAttribute as CFString),
          let rawSize = axAttribute(children[0],kAXSizeAttribute as CFString),
          CFGetTypeID(rawPoint) == AXValueGetTypeID(), CFGetTypeID(rawSize) == AXValueGetTypeID() else { return false }
    var point = CGPoint.zero, size = CGSize.zero
    guard AXValueGetValue(rawPoint as! AXValue,.cgPoint,&point),
          AXValueGetValue(rawSize as! AXValue,.cgSize,&size) else { return false }
    return clearDockSurface(bounds,panel:CGRect(origin:point,size:size),target:target)
}
func requireUnobscured(_ target:SCWindow, _ pid:pid_t) throws {
    try requireFrontmost(pid)
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly,.excludeDesktopElements], kCGNullWindowID) as? [[String:Any]] else { throw fail("window_inventory_unavailable") }
    var found = false
    for info in windows {
        guard let id = info[kCGWindowNumber as String] as? UInt32 else { continue }
        if id == target.windowID { found = true; break }
        guard let alpha = info[kCGWindowAlpha as String] as? Double, alpha > 0,
              let bounds = info[kCGWindowBounds as String] as? [String:Any],
              let rect = CGRect(dictionaryRepresentation:bounds as CFDictionary) else { continue }
        // Ignore the system menu bar, reject every intersecting visible foreground surface.
        if rect.height > 28 && rect.intersects(target.frame) {
            if transparentDockSurface(info,bounds:rect,target:target.frame) { continue }
            throw fail("main_window_obscured")
        }
    }
    guard found else { throw fail("main_window_not_visible") }
}
